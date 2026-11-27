import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_thread(self, user_id: UUID, title: str) -> dict:
        result = await self.session.execute(
            text("""
                insert into public.threads (id, user_id, title)
                values (:id, :user_id, :title)
                returning id, title, created_at, updated_at
            """),
            {"id": str(uuid4()), "user_id": str(user_id), "title": title},
        )
        return dict(result.mappings().one())

    async def list_threads(self, user_id: UUID) -> list[dict]:
        result = await self.session.execute(
            text("""
                select t.id, t.title, t.created_at, t.updated_at,
                       count(m.id)::integer as message_count
                from public.threads t
                left join public.messages m
                  on m.user_id = t.user_id and m.thread_id = t.id
                where t.user_id = :user_id
                group by t.id
                order by t.updated_at desc
            """),
            {"user_id": str(user_id)},
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_thread(self, user_id: UUID, thread_id: UUID) -> dict | None:
        result = await self.session.execute(
            text("""
                select id, user_id, title, created_at, updated_at
                from public.threads
                where user_id = :user_id and id = :thread_id
            """),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_messages(self, user_id: UUID, thread_id: UUID) -> list[dict]:
        result = await self.session.execute(
            text("""
                select role, content, profile, sources, trace, sequence, created_at
                from public.messages
                where user_id = :user_id and thread_id = :thread_id
                order by sequence
            """),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        return [dict(row) for row in result.mappings().all()]

    async def append_message(
        self,
        user_id: UUID,
        thread_id: UUID,
        role: str,
        content: str,
        profile: dict | None = None,
        sources: list[dict] | None = None,
        trace: list[dict] | None = None,
    ) -> dict | None:
        locked_thread = await self.session.execute(
            text("""
                select id from public.threads
                where user_id = :user_id and id = :thread_id
                for update
            """),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        if locked_thread.first() is None:
            return None

        result = await self.session.execute(
            text("""
                insert into public.messages
                    (id, user_id, thread_id, role, content, profile, sources, trace, sequence)
                select :id, t.user_id, t.id, :role, :content, cast(:profile as jsonb),
                       cast(:sources as jsonb), cast(:trace as jsonb),
                       coalesce(max(m.sequence), 0) + 1
                from public.threads t
                left join public.messages m
                  on m.user_id = t.user_id and m.thread_id = t.id
                where t.user_id = :user_id and t.id = :thread_id
                group by t.user_id, t.id
                returning id, role, content, profile, sources, trace, sequence, created_at
            """),
            {
                "id": str(uuid4()), "user_id": str(user_id), "thread_id": str(thread_id),
                "role": role, "content": content,
                "profile": json.dumps(profile or {}), "sources": json.dumps(sources or []),
                "trace": json.dumps(trace or []),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        await self.session.execute(
            text("update public.threads set updated_at = now() where user_id = :user_id and id = :thread_id"),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        return dict(row)
