import json
import logging
import math
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import Settings

logger = logging.getLogger("harness.memory")

FORGET_THRESHOLD = 0.10
INITIAL_STABILITY_BASE = 3.0
INITIAL_STABILITY_PER_IMPORTANCE = 3.0
RECALL_GROWTH = 1.5
MAX_STABILITY_DAYS = 3650.0
MAX_ITEMS = 300
MERGE_SIMILARITY = 0.5

MEMORY_KINDS = ("interest", "background", "goal", "preference", "progress", "fact")

PROFILE_KINDS = ("background", "preference")
# 科研辅导场景里，兴趣、目标、进展、事实都绑定具体研究方向，必须按主题检索
EPISODIC_KINDS = ("interest", "goal", "progress", "fact")

KIND_STABILITY_MULTIPLIER = {
    "background": 1.5,
    "preference": 1.5,
    "interest": 1.2,
    "goal": 1.0,
    "progress": 0.6,
    "fact": 1.0,
}

PROFILE_SUMMARY_CHARS = 120
EPISODIC_LIMIT = 5
EPISODIC_CHARS = 600
EPISODIC_MIN_RELEVANCE = 0.12
PROGRESS_TTL_DAYS = 90.0

KIND_LABELS = {
    "interest": "兴趣",
    "background": "背景",
    "goal": "目标",
    "preference": "偏好",
    "progress": "进展",
    "fact": "事实",
}

EXTRACTION_PROMPT = """你是科研辅导助手的长期记忆整理器。阅读下面一轮对话，只提取"关于用户本人、值得跨会话记住"的信息，并按科研学习场景分类：
- background：知识基础（学过哪些课、数学/编程/机器学习基础）
- preference：阅读与学习偏好（综述/经典/最新、中英文、节奏、每周可投入时间）
- interest：关注或正在研究的方向（必须写清方向）
- goal：某个具体方向上的学习/研究目标（入门、开题、找研究问题），必须带方向，例如"用户希望在联邦学习隐私保护方向准备开题"
- progress：某个方向上的阅读或复现进展，例如"用户读完了某篇联邦学习综述"
- fact：可复用的工具/环境/资源事实，例如"用户使用 PyTorch"
不要提取：泛化目标（如"想了解领域全景"——界面画像里已有）、一次性的问题细节、助手讲的领域知识、论文内容、寒暄。界面学习画像里已有的信息不要重复提取，除非对话补充了新的细节。
如果用户明确要求"记住某事"，必须提取，并把 importance 设为 5。
只输出一个 JSON 对象：
{"memories": [{"text": "用户……", "kind": "background|preference|interest|goal|progress|fact", "importance": 1-5}]}
要求：第三人称"用户……"；每条不超过 50 字；最多 3 条；没有值得记住的就返回 {"memories": []}。"""

_LATIN = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _tokens(text: str) -> set:
    lowered = text.lower()
    tokens = set(_LATIN.findall(lowered))
    for run in _CJK.findall(lowered):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _overlap(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _dice(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def _initial_stability(importance: int, kind: str = "fact") -> float:
    base = INITIAL_STABILITY_BASE + INITIAL_STABILITY_PER_IMPORTANCE * importance
    return base * KIND_STABILITY_MULTIPLIER.get(kind, 1.0)


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") in ("text", "text_delta")
        )
    return ""


def _parse_extraction(raw: str) -> List[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return []
    data = json.loads(text[start : end + 1])
    entries = data.get("memories") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []

    cleaned = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text_value = str(entry.get("text", "")).strip()
        if not 4 <= len(text_value) <= 200:
            continue
        kind = str(entry.get("kind", "fact"))
        if kind not in MEMORY_KINDS:
            kind = "fact"
        try:
            importance = int(entry.get("importance", 3))
        except (TypeError, ValueError):
            importance = 3
        importance = max(1, min(5, importance))
        cleaned.append({"text": text_value, "kind": kind, "importance": importance})
        if len(cleaned) >= 3:
            break
    return cleaned


@dataclass
class MemoryItem:
    id: str
    text: str
    kind: str
    importance: int
    stability: float
    created_at: str
    last_recalled_at: str
    recall_count: int = 0
    source: str = "auto"
    thread_id: str = ""

    def retention(self, now: datetime) -> float:
        try:
            last = datetime.fromisoformat(self.last_recalled_at)
        except (TypeError, ValueError):
            last = now
        elapsed_days = max(0.0, (now - last).total_seconds()) / 86400.0
        # 进展类信息会过时：无论稳定度多高，90 天未更新即视为淡忘
        if self.kind == "progress" and elapsed_days > PROGRESS_TTL_DAYS:
            return 0.0
        return math.exp(-elapsed_days / max(self.stability, 0.1))

    def public(self, now: datetime) -> dict:
        retention = self.retention(now)
        return {
            "id": self.id,
            "text": self.text,
            "kind": self.kind,
            "importance": self.importance,
            "stability_days": round(self.stability, 1),
            "retention": round(retention, 3),
            "recall_count": self.recall_count,
            "created_at": self.created_at,
            "last_recalled_at": self.last_recalled_at,
            "forgotten": retention < FORGET_THRESHOLD,
            "source": self.source,
        }


def reinforce(item: MemoryItem, now: datetime) -> None:
    retention = item.retention(now)
    floor = _initial_stability(item.importance, item.kind)
    if retention < FORGET_THRESHOLD or item.stability < floor:
        item.stability = max(item.stability, floor)
    item.stability = min(
        item.stability * (1 + RECALL_GROWTH * (1 - retention)) + 0.5,
        MAX_STABILITY_DAYS,
    )
    item.last_recalled_at = _iso(now)
    item.recall_count += 1


class MemoryStore:
    """长期记忆：按艾宾浩斯遗忘曲线衰减，持久化到磁盘，跨会话生效。"""

    def __init__(self, settings: Settings) -> None:
        self._path = self._resolve_path(settings.memory_file)
        self._lock = threading.Lock()
        self._items: List[MemoryItem] = []
        self._load()
        self._llm = None
        if settings.llm_configured:
            self._llm = ChatOpenAI(
                model=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                temperature=0.1,
                max_retries=1,
                timeout=45,
                model_kwargs={"response_format": {"type": "json_object"}},
            )

    @staticmethod
    def _resolve_path(configured: str) -> Path:
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        return path

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            items = data.get("items") if isinstance(data, dict) else data
            if not isinstance(items, list):
                raise ValueError("items 不是列表")
            self._items = [
                MemoryItem(
                    id=str(raw.get("id") or uuid4().hex),
                    text=str(raw.get("text", "")),
                    kind=str(raw.get("kind", "fact")),
                    importance=max(1, min(5, int(raw.get("importance", 3)))),
                    stability=float(raw.get("stability", 9.0)),
                    created_at=str(raw.get("created_at", "")),
                    last_recalled_at=str(raw.get("last_recalled_at", "")),
                    recall_count=int(raw.get("recall_count", 0)),
                    source=str(raw.get("source", "auto")),
                    thread_id=str(raw.get("thread_id", "")),
                )
                for raw in items
                if isinstance(raw, dict) and str(raw.get("text", "")).strip()
            ]
        except Exception:
            logger.exception("长期记忆文件损坏，已备份并重新开始")
            try:
                self._path.replace(self._path.with_suffix(".corrupt"))
            except OSError:
                pass
            self._items = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "items": [
                {
                    "id": item.id,
                    "text": item.text,
                    "kind": item.kind,
                    "importance": item.importance,
                    "stability": item.stability,
                    "created_at": item.created_at,
                    "last_recalled_at": item.last_recalled_at,
                    "recall_count": item.recall_count,
                    "source": item.source,
                    "thread_id": item.thread_id,
                }
                for item in self._items
            ],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def _prune(self) -> None:
        if len(self._items) <= MAX_ITEMS:
            return
        now = _now()
        forgotten = [item for item in self._items if item.retention(now) < FORGET_THRESHOLD]
        forgotten.sort(key=lambda item: item.retention(now) * item.importance)
        removed = {item.id for item in forgotten[: len(self._items) - MAX_ITEMS]}
        if removed:
            self._items = [item for item in self._items if item.id not in removed]
        if len(self._items) > MAX_ITEMS:
            self._items.sort(
                key=lambda item: item.retention(now) * item.importance, reverse=True
            )
            del self._items[MAX_ITEMS:]

    def snapshot(self) -> dict:
        now = _now()
        items = [item.public(now) for item in self._items]
        items.sort(key=lambda raw: (raw["forgotten"], -raw["retention"] * raw["importance"]))
        active = [item for item in items if not item["forgotten"]]
        avg = sum(item["retention"] for item in active) / len(active) if active else 0.0
        return {
            "items": items,
            "stats": {
                "active": len(active),
                "forgotten": len(items) - len(active),
                "avg_retention": round(avg, 3),
            },
        }

    def add(
        self,
        text: str,
        kind: str = "fact",
        importance: int = 3,
        source: str = "auto",
        thread_id: str = "",
    ) -> MemoryItem:
        text = " ".join(text.split()).strip()
        now = _now()
        with self._lock:
            new_tokens = _tokens(text)
            for item in self._items:
                if _dice(new_tokens, _tokens(item.text)) >= MERGE_SIMILARITY:
                    if len(text) > len(item.text):
                        item.text = text
                    item.importance = max(item.importance, importance)
                    if kind in MEMORY_KINDS and item.kind == "fact":
                        item.kind = kind
                    reinforce(item, now)
                    self._save()
                    return item

            item = MemoryItem(
                id=uuid4().hex,
                text=text,
                kind=kind if kind in MEMORY_KINDS else "fact",
                importance=max(1, min(5, importance)),
                stability=_initial_stability(max(1, min(5, importance)), kind),
                created_at=_iso(now),
                last_recalled_at=_iso(now),
                source=source,
                thread_id=thread_id,
            )
            self._items.append(item)
            self._prune()
            self._save()
            return item

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [item for item in self._items if item.id != memory_id]
            if len(self._items) == before:
                return False
            self._save()
            return True

    def review(self, memory_id: str) -> bool:
        now = _now()
        with self._lock:
            for item in self._items:
                if item.id == memory_id:
                    reinforce(item, now)
                    self._save()
                    return True
            return False

    def context_for(self, query: str) -> dict:
        """两层注入：稳定画像常驻，情景记忆按当前问题相关性检索。"""
        now = _now()
        profile = self._profile_candidates(now)
        summary = ""
        for item in profile:
            candidate = f"{KIND_LABELS[item.kind]}：{item.text}"
            joined = f"{summary}；{candidate}" if summary else candidate
            if len(joined) > PROFILE_SUMMARY_CHARS:
                continue
            summary = joined
        if not summary and profile:
            summary = f"{KIND_LABELS[profile[0].kind]}：{profile[0].text}"[
                :PROFILE_SUMMARY_CHARS
            ]
        return {"summary": summary, "episodic": self._episodic_layer(query, now)}

    def _profile_candidates(self, now: datetime) -> List[MemoryItem]:
        active = [
            item
            for item in self._items
            if item.kind in PROFILE_KINDS and item.retention(now) >= FORGET_THRESHOLD
        ]
        by_kind = {
            kind: sorted(
                (item for item in active if item.kind == kind),
                key=lambda item: item.retention(now) * item.importance,
                reverse=True,
            )
            for kind in PROFILE_KINDS
        }
        ordered: List[MemoryItem] = []
        # 每类先取最强的一条，保证画像层类别覆盖
        for kind in PROFILE_KINDS:
            if by_kind[kind]:
                ordered.append(by_kind[kind][0])
        rest = sorted(
            (item for item in active if item not in ordered),
            key=lambda item: item.retention(now) * item.importance,
            reverse=True,
        )
        return ordered + rest

    def _episodic_layer(self, query: str, now: datetime) -> List[MemoryItem]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        matched: List[Tuple[MemoryItem, float]] = []
        for item in self._items:
            if item.kind not in EPISODIC_KINDS:
                continue
            retention = item.retention(now)
            if retention < FORGET_THRESHOLD:
                continue
            relevance = _overlap(query_tokens, _tokens(item.text))
            if relevance < EPISODIC_MIN_RELEVANCE:
                continue
            score = relevance * (0.5 + 0.1 * item.importance) * (0.4 + 0.6 * retention)
            matched.append((item, score))
        matched.sort(key=lambda pair: pair[1], reverse=True)

        picked: List[MemoryItem] = []
        used = 0
        for item, _ in matched:
            if len(picked) >= EPISODIC_LIMIT:
                break
            if used + len(item.text) > EPISODIC_CHARS:
                continue
            picked.append(item)
            used += len(item.text)

        # 只有命中当前问题的情景记忆才算"被回想"，常驻画像不因展示而强化
        if picked:
            with self._lock:
                for item in picked:
                    reinforce(item, now)
                self._save()
        return picked

    async def extract_and_remember(
        self,
        user_message: str,
        answer: str,
        thread_id: str,
        profile_text: str = "",
    ) -> List[MemoryItem]:
        if self._llm is None:
            return []

        parts = [f"【用户消息】\n{user_message[:1500]}", f"【助手回答】\n{answer[:2000]}"]
        if profile_text:
            parts.append(f"【界面学习画像】\n{profile_text}")
        try:
            response = await self._llm.ainvoke(
                [
                    SystemMessage(content=EXTRACTION_PROMPT),
                    HumanMessage(content="\n\n".join(parts)),
                ]
            )
            entries = _parse_extraction(_content_text(response.content))
        except Exception:
            logger.exception("长期记忆抽取失败（不影响本轮回答）")
            return []

        created = []
        for entry in entries:
            created.append(
                self.add(
                    entry["text"],
                    kind=entry["kind"],
                    importance=entry["importance"],
                    source="auto",
                    thread_id=thread_id,
                )
            )
        if created:
            logger.info("长期记忆更新：本轮抽取 %d 条", len(created))
        return created