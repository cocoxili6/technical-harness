from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_memories(self, user_id: UUID) -> list[dict]:
        result = await self.session.execute(
            text("select * from public.memories where user_id = :user_id order by created_at desc"),
            {"user_id": str(user_id)},
        )
        return [dict(row) for row in result.mappings().all()]

    async def create_memory(
        self, user_id: UUID, content: str, kind: str, importance: int,
        stability: float, source: str = "manual", thread_id: UUID | None = None,
    ) -> dict:
        result = await self.session.execute(
            text("""
                insert into public.memories
                    (id, user_id, text, kind, importance, stability, source, thread_id)
                values (:id, :user_id, :text, :kind, :importance, :stability, :source, :thread_id)
                returning *
            """),
            {
                "id": str(uuid4()), "user_id": str(user_id), "text": content,
                "kind": kind, "importance": importance, "stability": stability,
                "source": source, "thread_id": str(thread_id) if thread_id else None,
            },
        )
        return dict(result.mappings().one())

    async def review_memory(self, user_id: UUID, memory_id: UUID) -> bool:
        result = await self.session.execute(
            text("""
                update public.memories
                set last_recalled_at = now(), recall_count = recall_count + 1,
                    stability = least(stability * 1.5 + 0.5, 3650)
                where user_id = :user_id and id = :memory_id
                returning id
            """),
            {"user_id": str(user_id), "memory_id": str(memory_id)},
        )
        return result.first() is not None

    async def delete_memory(self, user_id: UUID, memory_id: UUID) -> bool:
        result = await self.session.execute(
            text("delete from public.memories where user_id = :user_id and id = :memory_id returning id"),
            {"user_id": str(user_id), "memory_id": str(memory_id)},
        )
        return result.first() is not None
