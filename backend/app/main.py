import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from .agent.graph import build_agent
from .config import get_settings
from .demo import build_demo_reply, build_demo_sources
from .store import ConversationStore, ThreadRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("harness")

settings = get_settings()
store = ConversationStore()
_agent = None


def get_agent():
    global _agent
    if _agent is None and settings.llm_configured:
        _agent = build_agent(settings)
    return _agent


def verify_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not settings.harness_shared_token:
        return
    if authorization != f"Bearer {settings.harness_shared_token}":
        raise HTTPException(status_code=401, detail="unauthorized")


app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: Optional[str] = None


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


async def live_stream(message: str, record: ThreadRecord, request: Request):
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
    answer_fallback = ""
    sources: List[dict] = []
    seen_urls = set()
    trace: List[dict] = []

    yield sse("meta", meta_payload(record, demo=False))

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            version="v2",
        ):
            if await request.is_disconnected():
                return

            kind = event.get("event")
            if kind == "on_chat_model_stream":
                text = text_from_chunk(event.get("data", {}).get("chunk"))
                if text:
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


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "demo_mode": not settings.llm_configured,
        "llm_configured": settings.llm_configured,
        "model": settings.deepseek_model,
        "search": "arXiv + Google Scholar" if settings.scholar_configured else "arXiv",
        "memory": "in-process",
    }


@router.get("/threads")
def list_threads() -> dict:
    return {"threads": store.summaries()}


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str) -> dict:
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
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message 不能为空")

    record = store.get(payload.thread_id)
    if record is None:
        record = store.create_thread(message)
    store.append_user(record, message)

    generator = (
        demo_stream(message, record, request)
        if not settings.llm_configured
        else live_stream(message, record, request)
    )
    return StreamingResponse(
        generator, media_type="text/event-stream", headers=event_headers()
    )


app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "mode": "demo" if not settings.llm_configured else "deepseek",
    }
