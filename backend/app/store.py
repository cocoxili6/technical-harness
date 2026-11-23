from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _title_from(message: str) -> str:
    compact = " ".join(message.split())
    if len(compact) <= 28:
        return compact
    return compact[:28] + "…"


@dataclass
class ThreadRecord:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
        }


class ConversationStore:
    """进程内短期记忆的界面投影；LLM 上下文由 LangGraph checkpointer 维护。"""

    def __init__(self, limit: int = 100) -> None:
        self._threads: "OrderedDict[str, ThreadRecord]" = OrderedDict()
        self._limit = limit

    def create_thread(self, first_message: str) -> ThreadRecord:
        now = _now()
        record = ThreadRecord(
            id=uuid4().hex,
            title=_title_from(first_message) or "新的调研",
            created_at=now,
            updated_at=now,
        )
        self._threads[record.id] = record
        self._threads.move_to_end(record.id)
        while len(self._threads) > self._limit:
            self._threads.popitem(last=False)
        return record

    def get(self, thread_id: Optional[str]) -> Optional[ThreadRecord]:
        if not thread_id:
            return None
        return self._threads.get(thread_id)

    def append_user(
        self, record: ThreadRecord, content: str, profile: Optional[dict] = None
    ) -> None:
        message = {"role": "user", "content": content}
        if profile:
            message["profile"] = profile
        record.messages.append(message)
        record.updated_at = _now()

    def append_assistant(
        self,
        record: ThreadRecord,
        content: str,
        sources: List[dict],
        trace: Optional[List[dict]] = None,
    ) -> None:
        record.messages.append(
            {
                "role": "assistant",
                "content": content,
                "sources": sources,
                "trace": trace or [],
            }
        )
        record.updated_at = _now()
        self._threads.move_to_end(record.id)

    def summaries(self) -> List[dict]:
        ordered = sorted(
            self._threads.values(), key=lambda item: item.updated_at, reverse=True
        )
        return [item.summary() for item in ordered]
