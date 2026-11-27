import json
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_engines = {}

def create_session_factory(database_url: str):
    engine = _engines.get(database_url)
    if engine is None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        _engines[database_url] = engine
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def dispose_engines() -> None:
    engines = list(_engines.values())
    _engines.clear()
    for engine in engines:
        await engine.dispose()


async def set_user_rls_context(session: AsyncSession, user_id: UUID) -> None:
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    await session.execute(text("SET LOCAL ROLE authenticated"))
    await session.execute(
        text("select set_config('request.jwt.claims', :claims, true)"),
        {"claims": claims},
    )
    await session.execute(
        text("select set_config('request.jwt.claim.sub', :sub, true)"),
        {"sub": str(user_id)},
    )


@asynccontextmanager
async def user_session(user_id: UUID) -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    raw_url = settings.supabase_db_url.get_secret_value()
    if not raw_url:
        raise RuntimeError("SUPABASE_DB_URL is not configured")
    _, factory = create_session_factory(raw_url)
    async with factory() as session, session.begin():
        await set_user_rls_context(session, user_id)
        yield session
