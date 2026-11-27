import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AgentContextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_papers(self, user_id: UUID, thread_id: UUID) -> list[dict]:
        result = await self.session.execute(
            text("""
                select canonical_url, title, authors, year, venue, citation_count,
                       summary, source, first_seen_at, last_seen_at
                from public.paper_catalog
                where user_id = :user_id and thread_id = :thread_id
                order by last_seen_at desc
            """),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        return [dict(row) for row in result.mappings().all()]

    async def load(self, user_id: UUID, thread_id: UUID) -> dict:
        result = await self.session.execute(
            text("""
                select summary, paper_catalog, summarized_through, metadata
                from public.context_summaries
                where user_id = :user_id and thread_id = :thread_id
            """),
            {"user_id": str(user_id), "thread_id": str(thread_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else {"summary": "", "paper_catalog": [], "summarized_through": 0, "metadata": {}}

    async def save(
        self, user_id: UUID, thread_id: UUID, summary: str,
        paper_catalog: list[dict], summarized_through: int, metadata: dict | None = None,
    ) -> None:
        await self.session.execute(
            text("""
                insert into public.context_summaries
                    (user_id, thread_id, summary, paper_catalog, summarized_through, metadata)
                values (:user_id, :thread_id, :summary, cast(:paper_catalog as jsonb),
                        :summarized_through, cast(:metadata as jsonb))
                on conflict (user_id, thread_id) do update set
                    summary = excluded.summary,
                    paper_catalog = excluded.paper_catalog,
                    summarized_through = excluded.summarized_through,
                    metadata = excluded.metadata,
                    updated_at = now()
            """),
            {
                "user_id": str(user_id), "thread_id": str(thread_id), "summary": summary,
                "paper_catalog": json.dumps(paper_catalog),
                "summarized_through": summarized_through,
                "metadata": json.dumps(metadata or {}),
            },
        )

    async def upsert_papers(self, user_id: UUID, thread_id: UUID, papers: list[dict]) -> None:
        for paper in papers:
            await self.session.execute(
                text("""
                    insert into public.paper_catalog
                        (user_id, thread_id, canonical_url, title, authors, year, venue,
                         citation_count, summary, source)
                    values (:user_id, :thread_id, :url, :title, cast(:authors as jsonb),
                            :year, :venue, :citation_count, :summary, :source)
                    on conflict (user_id, canonical_url) do update set
                        thread_id = excluded.thread_id, title = excluded.title,
                        authors = excluded.authors, year = excluded.year,
                        venue = excluded.venue, citation_count = excluded.citation_count,
                        summary = excluded.summary, last_seen_at = now()
                """),
                {
                    "user_id": str(user_id), "thread_id": str(thread_id),
                    "url": paper["url"], "title": paper.get("title", ""),
                    "authors": json.dumps(paper.get("authors", [])),
                    "year": paper.get("year"), "venue": paper.get("venue"),
                    "citation_count": paper.get("citation_count"),
                    "summary": paper.get("summary", ""), "source": paper.get("source", ""),
                },
            )

    async def save_tool_run(self, user_id: UUID, thread_id: UUID, run: dict) -> None:
        await self.session.execute(
            text("""
                insert into public.tool_runs
                    (user_id, thread_id, tool_name, input_summary, result_summary, status, metadata)
                values (:user_id, :thread_id, :tool_name, :input_summary, :result_summary,
                        :status, cast(:metadata as jsonb))
            """),
            {
                "user_id": str(user_id), "thread_id": str(thread_id),
                "tool_name": run.get("name", "tool"),
                "input_summary": run.get("input", ""),
                "result_summary": run.get("summary", ""),
                "status": run.get("status", "done"),
                "metadata": json.dumps(run.get("metadata", {})),
            },
        )
