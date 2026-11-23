from typing import Annotated, List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..config import Settings
from .prompts import build_system_prompt
from .tools import search_arxiv, search_openalex, search_scholar


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


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

    async def assistant(state: AgentState, config: RunnableConfig) -> dict:
        messages = [
            SystemMessage(content=build_system_prompt(settings.scholar_configured))
        ] + list(state["messages"])
        response = await model_with_tools.ainvoke(messages, config=config)
        return {"messages": [response]}

    def route_after_assistant(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant", route_after_assistant, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "assistant")

    return builder.compile(checkpointer=MemorySaver())
