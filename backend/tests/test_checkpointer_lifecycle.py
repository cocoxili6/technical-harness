import asyncio
import sys
from contextlib import asynccontextmanager
from types import ModuleType

from app import db
from app.config import Settings


def test_checkpointer_uses_postgres_url_and_disposes_with_application(monkeypatch):
    observed = {}

    class FakeSaver:
        async def setup(self):
            observed["setup"] = True

    saver = FakeSaver()

    @asynccontextmanager
    async def from_conn_string(url):
        observed["url"] = url
        yield saver

    postgres_module = ModuleType("langgraph.checkpoint.postgres")
    postgres_module.__path__ = []
    aio_module = ModuleType("langgraph.checkpoint.postgres.aio")
    aio_module.AsyncPostgresSaver = type(
        "AsyncPostgresSaver",
        (),
        {"from_conn_string": staticmethod(from_conn_string)},
    )
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", postgres_module)
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres.aio", aio_module)
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            supabase_db_url="postgresql+asyncpg://db-user:db-pass@localhost/postgres",
        ),
    )

    async def run_lifecycle():
        initialized = await db.initialize_checkpointer()

        assert initialized is saver
        assert observed["setup"] is True
        assert observed["url"] == "postgresql://db-user:db-pass@localhost/postgres"
        assert db.get_checkpointer() is saver

        await db.dispose_checkpointer()

        assert db.get_checkpointer() is None

    asyncio.run(run_lifecycle())
