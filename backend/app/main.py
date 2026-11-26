import asyncio
import json
import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from .agent.analysis import PaperAnalyzer, PaperInput, demo_analysis
from .auth import CurrentUser, get_current_user, verify_gateway_token
from .agent.graph import build_agent
from .config import get_settings
from .demo import build_demo_reply, build_demo_sources
from .memory import KIND_LABELS, MemoryStore
from .store import ConversationStore, ThreadRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("harness")

settings = get_settings()
store = ConversationStore()
memory_store = MemoryStore(settings)
_agent = None
_analyzer = None
_background_tasks: set = set()


def spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def get_analyzer():
    global _analyzer
    if _analyzer is None and settings.llm_configured:
        _analyzer = PaperAnalyzer(settings)
    return _analyzer


def get_agent():
    global _agent
    if _agent is None and settings.llm_configured:
        _agent = build_agent(settings)
    return _agent


app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api", dependencies=[Depends(verify_gateway_token)])


PROFILE_LABELS = {
    "background": {
        "none": "零基础，没有系统学过相关课程",
        "course": "学过相关基础课程，但没读过这个方向的论文",
        "research": "有一定研究经验，读过部分相关论文",
    },
    "goal": {
        "overview": "了解领域全景",
        "project": "为毕业设计或课题做准备",
        "research": "找到可以深入的研究问题",
    },
    "preference": {
        "survey": "优先阅读综述",
        "classic": "优先阅读经典论文",
        "recent": "优先阅读最新研究",
    },
}


class LearningProfile(BaseModel):
    background: Optional[Literal["none", "course", "research"]] = None
    goal: Optional[Literal["overview", "project", "research"]] = None
    weekly_hours: Optional[int] = Field(default=None, ge=1, le=60)
    preference: Optional[Literal["survey", "classic", "recent"]] = None

    def is_empty(self) -> bool:
        return all(value is None for value in self.model_dump().values())

    def describe(self) -> str:
        lines = []
        if self.background:
            lines.append(f"- 知识基础：{PROFILE_LABELS['background'][self.background]}")
        if self.goal:
            lines.append(f"- 学习目标：{PROFILE_LABELS['goal'][self.goal]}")
        if self.weekly_hours:
            lines.append(f"- 每周可投入：约 {self.weekly_hours} 小时")
        if self.preference:
            lines.append(f"- 阅读偏好：{PROFILE_LABELS['preference'][self.preference]}")
        return "\n".join(lines)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: Optional[str] = None
    profile: Optional[LearningProfile] = None


class MemoryCreate(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    kind: Literal["interest", "background", "goal", "preference", "progress", "fact"] = "fact"
    importance: int = Field(default=3, ge=1, le=5)


def message_for_agent(
    message: str,
    profile: Optional[LearningProfile],
    memory_context: Optional[dict] = None,
) -> str:
    blocks = []
    if profile is not None and not profile.is_empty():
        blocks.append(f"【学习画像】（用户在界面上选择）\n{profile.describe()}")
    if memory_context:
        lines = []
        summary = str(memory_context.get("summary") or "")
        episodic = memory_context.get("episodic") or []
        if summary:
            lines.append(f"稳定画像（常驻）：{summary}")
        if episodic:
            if lines:
                lines.append("与当前问题相关的情景：")
            lines.extend(
                f"- [{KIND_LABELS.get(item.kind, item.kind)}] {item.text}"
                for item in episodic
            )
        if lines:
            blocks.append(
                "【长期记忆】（过去会话中关于用户的要点；只在相关时参考）\n"
                + "\n".join(lines)
            )
    if not blocks:
        return message
    blocks.append(f"【问题】\n{message}")
    return "\n\n".join(blocks)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def meta_payload(record: ThreadRecord, demo: bool) -> dict:
    return {"thread_id": record.id, "title": record.title, "demo": demo}


def text_from_chunk(chunk) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", "text_delta"):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def payload_from_content(content) -> Optional[dict]:
    if isinstance(content, list):
        content = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict)
        )
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def clean_sources(payload: Optional[dict]) -> List[dict]:
    if not payload:
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    cleaned = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", ""))
        if not (url.startswith("https://") or url.startswith("http://")):
            continue
        cleaned.append(
            {
                "title": str(item.get("title", ""))[:300],
                "authors": str(item.get("authors", ""))[:200],
                "year": str(item.get("year", ""))[:8],
                "url": url[:500],
                "category": str(item.get("category", ""))[:40],
                "summary": str(item.get("summary", ""))[:500],
            }
        )
    return cleaned


def friendly_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "401" in text or "authentication" in text or "invalid api key" in text:
        return "DeepSeek 鉴权失败，请检查 backend/.env 中的 DEEPSEEK_API_KEY。"
    if "402" in text or "insufficient balance" in text:
        return "DeepSeek 账户余额不足，请充值后重试。"
    if "429" in text or "rate limit" in text:
        return "请求过于频繁，请稍等片刻再试。"
    if "timeout" in text:
        return "模型响应超时，请重试。"
    return "生成过程中出现错误，请查看后端日志后重试。"


def event_headers() -> dict:
    return {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }


async def live_stream(
    message: str,
    record: ThreadRecord,
    request: Request,
    profile: Optional[LearningProfile] = None,
):
    try:
        agent = get_agent()
    except Exception:
        logger.exception("failed to build agent")
        yield sse("error", {"message": "模型初始化失败，请检查后端配置。"})
        return

    if agent is None:
        yield sse("error", {"message": "模型未配置，请先设置 DEEPSEEK_API_KEY。"})
        return

    config = {"configurable": {"thread_id": record.id}, "recursion_limit": 14}
    collected = []
    needs_break = False
    answer_fallback = ""
    sources: List[dict] = []
    seen_urls = set()
    trace: List[dict] = []

    memory_context = None
    try:
        # 拼接会话主题与当前问题检索：追问"接下来读什么"时也能命中方向相关的记忆
        memory_context = memory_store.context_for(f"{record.title}\n{message}")
    except Exception:
        logger.exception("长期记忆检索失败（不影响本轮回答）")

    yield sse("meta", meta_payload(record, demo=False))

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=message_for_agent(message, profile, memory_context))]},
            config=config,
            version="v2",
        ):
            if await request.is_disconnected():
                return

            # 上下文压缩的摘要调用不进入用户可见的事件流
            if "context-compaction" in (event.get("tags") or []):
                continue

            kind = event.get("event")
            if kind == "on_chat_model_start":
                # 工具调用前后的多轮输出各自成段，避免标题粘在上一句末尾
                needs_break = bool(collected)
            elif kind == "on_chat_model_stream":
                text = text_from_chunk(event.get("data", {}).get("chunk"))
                if text:
                    if needs_break:
                        needs_break = False
                        tail = "".join(collected)[-2:]
                        if tail != "\n\n":
                            gap = "\n" if tail.endswith("\n") else "\n\n"
                            collected.append(gap)
                            yield sse("token", {"text": gap})
                    collected.append(text)
                    yield sse("token", {"text": text})
            elif kind == "on_chat_model_end":
                output = event.get("data", {}).get("output")
                if isinstance(output, AIMessage) and not output.tool_calls:
                    text = text_from_chunk(output)
                    if text.strip():
                        answer_fallback = text
            elif kind == "on_tool_start":
                raw_input = event.get("data", {}).get("input")
                query = ""
                if isinstance(raw_input, dict):
                    query = str(raw_input.get("query", ""))
                tool_id = str(event.get("run_id", ""))
                tool_name = str(event.get("name", "tool"))
                trace.append(
                    {
                        "id": tool_id,
                        "name": tool_name,
                        "query": query[:200],
                        "status": "running",
                    }
                )
                yield sse(
                    "tool_start",
                    {
                        "id": tool_id,
                        "name": tool_name,
                        "input": {"query": query[:200]},
                    },
                )
            elif kind == "on_tool_end":
                output = event.get("data", {}).get("output")
                payload_data = payload_from_content(
                    getattr(output, "content", output)
                )
                new_sources = clean_sources(payload_data)
                if payload_data and payload_data.get("error"):
                    summary = str(payload_data["error"])[:160]
                elif new_sources:
                    summary = f"检索到 {len(new_sources)} 篇文献"
                elif payload_data is not None:
                    summary = "没有找到匹配文献"
                else:
                    summary = "检索完成"

                for item in new_sources:
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        sources.append(item)

                tool_id = str(event.get("run_id", ""))
                tool_name = str(event.get("name", "tool"))
                trace_item = next(
                    (item for item in reversed(trace) if item["id"] == tool_id),
                    None,
                )
                if trace_item is None:
                    trace_item = next(
                        (
                            item
                            for item in reversed(trace)
                            if item["name"] == tool_name
                            and item["status"] == "running"
                        ),
                        None,
                    )
                if trace_item is not None:
                    trace_item["status"] = (
                        "error" if payload_data and payload_data.get("error") else "done"
                    )
                    trace_item["summary"] = summary[:200]
                    trace_item["count"] = len(new_sources)

                yield sse(
                    "tool_end",
                    {
                        "id": tool_id,
                        "name": tool_name,
                        "ok": not (payload_data and payload_data.get("error")),
                        "summary": summary,
                        "count": len(new_sources),
                    },
                )
                if new_sources:
                    yield sse("sources", {"items": new_sources})
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("agent stream failed")
        yield sse("error", {"message": friendly_error(exc)})
        return

    answer = "".join(collected).strip()
    if not answer and answer_fallback.strip():
        answer = answer_fallback.strip()
        yield sse("token", {"text": answer})
    if not answer:
        yield sse("error", {"message": "模型没有返回内容，请重试。"})
        return

    store.append_assistant(record, answer, sources, trace)
    spawn_background(
        memory_store.extract_and_remember(
            message,
            answer,
            record.id,
            profile.describe() if profile else "",
        )
    )
    yield sse("done", {"thread_id": record.id})


async def demo_stream(message: str, record: ThreadRecord, request: Request):
    trace_item = {
        "id": "demo-search",
        "name": "search_arxiv",
        "query": message[:200],
        "status": "running",
    }
    yield sse("meta", meta_payload(record, demo=True))
    yield sse(
        "tool_start",
        {
            "id": "demo-search",
            "name": "search_arxiv",
            "input": {"query": message[:200]},
        },
    )
    await asyncio.sleep(0.45)
    if await request.is_disconnected():
        return

    items = build_demo_sources(message)
    trace_item["status"] = "done"
    trace_item["summary"] = "演示检索：未调用真实文献服务"
    trace_item["count"] = len(items)
    yield sse(
        "tool_end",
        {
            "id": "demo-search",
            "name": "search_arxiv",
            "ok": True,
            "summary": "演示检索：未调用真实文献服务",
            "count": len(items),
        },
    )
    yield sse("sources", {"items": items})

    reply = build_demo_reply(message)
    for start in range(0, len(reply), 12):
        if await request.is_disconnected():
            return
        yield sse("token", {"text": reply[start : start + 12]})
        await asyncio.sleep(0.016)

    store.append_assistant(record, reply, items, [trace_item])
    yield sse("done", {"thread_id": record.id})


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "demo_mode": not settings.llm_configured,
        "llm_configured": settings.llm_configured,
        "model": settings.deepseek_model,
        "search": "arXiv + OpenAlex + Google Scholar"
        if settings.scholar_configured
        else "arXiv + OpenAlex",
        "memory": (
            "short-term in-process with rolling summary · "
            "long-term on disk (Ebbinghaus decay)"
        ),
    }


@router.get("/threads")
def list_threads(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"threads": store.summaries()}


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    record = store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="会话不存在或已因服务重启被清除")
    return {
        "id": record.id,
        "title": record.title,
        "created_at": record.created_at,
        "messages": record.messages,
    }


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message 不能为空")

    record = store.get(payload.thread_id)
    if record is None:
        record = store.create_thread(message)
    profile = payload.profile if payload.profile and not payload.profile.is_empty() else None
    store.append_user(
        record, message, profile.model_dump(exclude_none=True) if profile else None
    )

    generator = (
        demo_stream(message, record, request)
        if not settings.llm_configured
        else live_stream(message, record, request, profile)
    )
    return StreamingResponse(
        generator, media_type="text/event-stream", headers=event_headers()
    )


@router.post("/papers/analyze")
async def analyze_paper(
    paper: PaperInput, user: CurrentUser = Depends(get_current_user)
) -> dict:
    analyzer = get_analyzer()
    if analyzer is None:
        return {"demo": True, "analysis": demo_analysis(paper).model_dump()}
    was_cached = analyzer.cached(paper.url) is not None
    try:
        analysis = await analyzer.analyze(paper)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("paper analysis failed")
        raise HTTPException(status_code=502, detail=friendly_error(exc)) from exc
    return {"demo": False, "cached": was_cached, "analysis": analysis.model_dump()}


@router.get("/memories")
def list_memories(user: CurrentUser = Depends(get_current_user)) -> dict:
    return memory_store.snapshot()


@router.post("/memories")
def add_memory(
    payload: MemoryCreate, user: CurrentUser = Depends(get_current_user)
) -> dict:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="记忆内容不能为空")
    memory_store.add(
        text,
        kind=payload.kind,
        importance=payload.importance,
        source="manual",
    )
    return memory_store.snapshot()


@router.post("/memories/{memory_id}/review")
def review_memory(
    memory_id: str, user: CurrentUser = Depends(get_current_user)
) -> dict:
    if not memory_store.review(memory_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory_store.snapshot()


@router.delete("/memories/{memory_id}")
def delete_memory(
    memory_id: str, user: CurrentUser = Depends(get_current_user)
) -> dict:
    if not memory_store.delete(memory_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory_store.snapshot()


app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "mode": "demo" if not settings.llm_configured else "deepseek",
    }
