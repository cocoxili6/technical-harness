import logging
from typing import Annotated, List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..config import Settings
from .compact import (
    archive_stale_tool_results,
    compact_history,
    estimate_history_tokens,
    estimate_tokens,
    merge_catalog,
    render_catalog,
)
from .prompts import build_system_prompt
from .tools import search_arxiv, search_openalex, search_scholar

logger = logging.getLogger("harness.agent")


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    summary: str
    paper_catalog: List[dict]


def build_agent(settings: Settings):
    llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=settings.deepseek_temperature,
        streaming=True,
        max_retries=1,
        timeout=60,
    )
    tools = [search_arxiv, search_openalex]
    if settings.scholar_configured:
        tools.append(search_scholar)
    model_with_tools = llm.bind_tools(tools)

    # 摘要调用必须非流式，否则压缩产生的 token 会混入回答的事件流
    summary_llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0,
        streaming=False,
        max_retries=0,
        timeout=30,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    system_prompt = build_system_prompt(settings.scholar_configured)
    system_tokens = estimate_tokens(system_prompt)

    async def prepare_context(state: AgentState) -> dict:
        messages = list(state.get("messages") or [])
        catalog = merge_catalog(state.get("paper_catalog") or [], messages)
        updates: dict = {"paper_catalog": catalog}

        last_human = max(
            (
                index
                for index, message in enumerate(messages)
                if isinstance(message, HumanMessage)
            ),
            default=-1,
        )
        # 工具循环内保持前缀稳定（利于 KV 缓存），归档与压缩只在新用户轮做
        if last_human != len(messages) - 1:
            return updates

        archived = archive_stale_tool_results(messages)
        if archived:
            by_id = {message.id: message for message in archived}
            messages = [by_id.get(message.id, message) for message in messages]
            updates["messages"] = archived

        summary = state.get("summary") or ""
        catalog_text = render_catalog(catalog, settings.context_catalog_limit)
        total = (
            system_tokens
            + estimate_history_tokens(messages)
            + estimate_tokens(summary)
            + estimate_tokens(catalog_text)
        )
        if total <= settings.context_token_budget:
            return updates

        result = await compact_history(
            messages, summary, summary_llm, settings.context_keep_turns
        )
        if result:
            stats = result.pop("stats", {})
            updates["messages"] = list(updates.get("messages") or []) + list(
                result.get("messages") or []
            )
            updates["summary"] = result.get("summary", summary)
            logger.info(
                "上下文压缩：估算 %d tokens 超过预算 %d，删除 %d 条消息，摘要%s",
                total,
                settings.context_token_budget,
                stats.get("removed", 0),
                "已更新" if stats.get("summarized") else "未更新（降级）",
            )
        return updates

    async def assistant(state: AgentState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(content=system_prompt)]
        summary = state.get("summary") or ""
        if summary:
            messages.append(
                SystemMessage(content=f"【会话纪要】（早期对话的压缩摘要）\n{summary}")
            )
        catalog_text = render_catalog(
            state.get("paper_catalog") or [], settings.context_catalog_limit
        )
        if catalog_text:
            messages.append(SystemMessage(content=catalog_text))
        messages.extend(state["messages"])
        response = await model_with_tools.ainvoke(messages, config=config)
        return {"messages": [response]}

    def route_after_assistant(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("prepare_context", prepare_context)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "prepare_context")
    builder.add_edge("prepare_context", "assistant")
    builder.add_conditional_edges(
        "assistant", route_after_assistant, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "prepare_context")

    return builder.compile(checkpointer=MemorySaver())