"""上下文管理：论文清单、工具结果归档、按 token 预算的滚动摘要。

原则：结构化事实（论文标题/链接）由代码维护，模型只写叙述性纪要；
压缩永远不阻塞回答，摘要失败时降级为少删一轮。
"""

import json
import logging
import re
from typing import List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger("harness.compact")

ARCHIVED_FLAG = "archived"
ARCHIVED_NOTE = "[检索结果已归档]"
SHORT_TOOL_CHARS = 200
SUMMARY_INPUT_TOKEN_LIMIT = 20000
SUMMARY_TEXT_LIMIT = 1200

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z0-9_]+")

SUMMARY_PROMPT = """你是科研辅导会话的纪要整理员。把下面这段即将从上下文中压缩掉的对话，整理成一份纪要和结构化状态，供后续轮次继续使用。

只输出一个 JSON 对象：
{
  "summary": "不超过 300 字：用户在做什么方向、已覆盖到哪个阅读阶段、助手给过哪些关键建议、用户的反馈或疑问",
  "decided": ["已经确定的事项，例如方向、阶段安排、用户的时间约束、明确偏好，最多 4 条"],
  "open_questions": ["尚未回答的问题或约定的下一步，最多 4 条"]
}

要求：
1. 只依据给出的对话，不编造；不确定的写进 open_questions。
2. 论文的标题、链接、引用量由系统在论文清单里单独维护，纪要里不要罗列论文元数据。
3. 用户的学习画像、每周可投入时间等约束出现过就必须写进 decided。
4. 没有内容时，对应字段返回空数组或空字符串。"""


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") in ("text", "text_delta")
        )
    return ""


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    latin_chars = sum(len(match.group(0)) for match in _LATIN.finditer(text))
    other = max(0, len(text) - cjk - latin_chars)
    return int(cjk * 0.6 + latin_chars * 0.3 + other * 0.3) + 1


def message_tokens(message) -> int:
    total = 4
    total += estimate_tokens(message_text(message))
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        try:
            total += estimate_tokens(json.dumps(tool_calls, ensure_ascii=False))
        except (TypeError, ValueError):
            total += 60
    return total


def estimate_history_tokens(messages) -> int:
    return sum(message_tokens(message) for message in messages)


def tool_payload(message) -> Optional[dict]:
    if not isinstance(message, ToolMessage):
        return None
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = message_text(message)
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def merge_catalog(catalog: List[dict], messages) -> List[dict]:
    """把尚未归档的工具结果中的论文并入清单，按 URL 去重且保持首次出现顺序。"""
    merged = [
        dict(item)
        for item in catalog or []
        if isinstance(item, dict) and str(item.get("url", "")).strip()
    ]
    seen = {item["url"] for item in merged}
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        if message.additional_kwargs.get(ARCHIVED_FLAG):
            continue
        payload = tool_payload(message)
        if payload is None:
            continue
        query = str(payload.get("query", ""))[:200]
        for raw in payload.get("results") or []:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url", "")).strip()
            if not (url.startswith("https://") or url.startswith("http://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            cited = raw.get("cited_by")
            merged.append(
                {
                    "title": str(raw.get("title", ""))[:300],
                    "authors": str(raw.get("authors", ""))[:200],
                    "year": str(raw.get("year", ""))[:8],
                    "url": url[:500],
                    "category": str(raw.get("category", ""))[:40],
                    "cited_by": cited if isinstance(cited, int) else None,
                    "query": query,
                }
            )
    return merged


def render_catalog(catalog: List[dict], limit: int) -> str:
    if not catalog:
        return ""
    limit = max(1, limit)
    visible = catalog[-limit:]
    lines = [
        f"【本会话论文清单】共 {len(catalog)} 篇，以下为最近 {len(visible)} 篇。"
        "引用论文时，标题和链接必须原样取自这里，不得编造。"
    ]
    for index, item in enumerate(visible, 1):
        title = str(item.get("title", "")).replace("[", "（").replace("]", "）")
        meta_parts = [part for part in (item.get("year"), item.get("category")) if part]
        cited = item.get("cited_by")
        if isinstance(cited, int):
            meta_parts.append(f"引用 {cited}")
        suffix = f"（{' · '.join(meta_parts)}）" if meta_parts else ""
        lines.append(f"{index}. [{title}]({item.get('url', '')}){suffix}")
    if len(catalog) > len(visible):
        lines.append(f"（更早的 {len(catalog) - len(visible)} 篇已省略）")
    return "\n".join(lines)


def archive_stale_tool_results(messages) -> List[ToolMessage]:
    """把当前用户轮之前的工具结果替换为占位符；返回需写回 state 的消息（按 id 原地替换）。"""
    last_human = -1
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            last_human = index
    if last_human <= 0:
        return []

    replacements = []
    for message in messages[:last_human]:
        if not isinstance(message, ToolMessage):
            continue
        if message.additional_kwargs.get(ARCHIVED_FLAG):
            continue
        if len(message_text(message)) <= SHORT_TOOL_CHARS:
            continue
        payload = tool_payload(message)
        query = str((payload or {}).get("query", ""))[:120]
        results = (payload or {}).get("results")
        count = len(results) if isinstance(results, list) else 0
        error = str((payload or {}).get("error") or "")[:80]
        tool_name = str(message.name or "search")
        if error:
            content = f"{ARCHIVED_NOTE} 工具 {tool_name}，关键词「{query}」检索失败（{error}）。"
        else:
            content = (
                f"{ARCHIVED_NOTE} 工具 {tool_name}，关键词「{query}」命中 {count} 篇，"
                "标题与链接已收录到【本会话论文清单】，详情以清单为准。"
            )
        extra = dict(message.additional_kwargs or {})
        extra[ARCHIVED_FLAG] = True
        replacements.append(
            ToolMessage(
                content=content,
                tool_call_id=message.tool_call_id,
                id=message.id,
                name=message.name,
                additional_kwargs=extra,
            )
        )
    return replacements


def find_cutoff(messages, keep_turns: int) -> int:
    """压缩切点 = 倒数第 keep_turns 个 HumanMessage 的下标；返回 0 表示无需压缩。"""
    keep_turns = max(1, keep_turns)
    human_indexes = [
        index for index, message in enumerate(messages) if isinstance(message, HumanMessage)
    ]
    if len(human_indexes) <= keep_turns:
        return 0
    return human_indexes[-keep_turns]


def _user_text(message) -> str:
    text = message_text(message)
    marker = "【问题】"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()


def _transcript(messages) -> str:
    lines = []
    for message in messages:
        if isinstance(message, HumanMessage):
            text = _user_text(message)
            if text:
                lines.append(f"用户：{text[:600]}")
        elif isinstance(message, AIMessage):
            calls = getattr(message, "tool_calls", None) or []
            queries = []
            for call in calls:
                if not isinstance(call, dict):
                    continue
                args = call.get("args") or {}
                query = str(args.get("query", "")).strip()
                if query:
                    queries.append(query[:80])
            if queries:
                lines.append(f"助手检索：{'；'.join(queries)}")
            text = message_text(message).strip()
            if text:
                lines.append(f"助手：{text[:800]}")
    return "\n".join(lines)


def _clip_transcript(messages) -> str:
    transcript = _transcript(messages)
    if estimate_tokens(transcript) <= SUMMARY_INPUT_TOKEN_LIMIT:
        return transcript
    # 预算按中文字符保守换算；超出时保留最近的对话
    char_budget = int(SUMMARY_INPUT_TOKEN_LIMIT / 0.6)
    return "（更早的内容已省略）\n" + transcript[-char_budget:]


def _parse_summary(raw: str) -> Optional[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _as_list(value) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def render_summary(data: dict) -> str:
    summary = str(data.get("summary", "")).strip()[:600]
    decided = [item.strip()[:160] for item in _as_list(data.get("decided")) if item.strip()][:4]
    open_questions = [
        item.strip()[:160] for item in _as_list(data.get("open_questions")) if item.strip()
    ][:4]

    blocks = []
    if summary:
        blocks.append(f"进展：{summary}")
    if decided:
        blocks.append("已确定：\n" + "\n".join(f"- {item}" for item in decided))
    if open_questions:
        blocks.append("待办/未答：\n" + "\n".join(f"- {item}" for item in open_questions))
    return "\n".join(blocks)[:SUMMARY_TEXT_LIMIT]


async def summarize(messages, previous_summary: str, llm: BaseChatModel) -> Optional[str]:
    parts = []
    if previous_summary:
        parts.append(f"【已有纪要】\n{previous_summary}")
    parts.append(f"【待压缩对话】\n{_clip_transcript(messages)}")
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content="\n\n".join(parts))],
            config={"tags": ["context-compaction"], "run_name": "context-compaction"},
        )
    except Exception:
        logger.exception("会话摘要调用失败")
        return None

    data = _parse_summary(message_text(response))
    if data is None:
        logger.warning("会话摘要返回格式异常")
        return None
    rendered = render_summary(data)
    return rendered or None


async def compact_history(
    messages,
    previous_summary: str,
    llm: Optional[BaseChatModel],
    keep_turns: int,
) -> dict:
    """把切点之前的消息压缩成纪要；摘要失败时降级为少删一轮。"""
    cutoff = find_cutoff(messages, keep_turns)
    if cutoff <= 0:
        return {}

    removed = list(messages[:cutoff])
    summary = await summarize(removed, previous_summary, llm) if llm is not None else None
    if summary is None:
        fallback_cutoff = find_cutoff(messages, keep_turns + 1)
        removed = list(messages[:fallback_cutoff])
        if not removed:
            return {}
        logger.warning("摘要不可用，降级为删除最早的 %d 条消息", len(removed))

    ids = [message.id for message in removed if getattr(message, "id", None)]
    if not ids:
        return {}
    return {
        "messages": [RemoveMessage(id=message_id) for message_id in ids],
        "summary": summary if summary is not None else previous_summary,
        "stats": {"removed": len(removed), "summarized": summary is not None},
    }