import asyncio
from uuid import uuid4

from app.repositories.conversation import ConversationRepository


class Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row

    def all(self):
        return []


class RecordingSession:
    def __init__(self, results=None):
        self.calls = []
        self.results = iter(results or [])

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return next(self.results, Result())


def test_thread_lookup_scopes_by_user_and_thread_id():
    user_id = uuid4()
    thread_id = uuid4()
    session = RecordingSession()

    asyncio.run(ConversationRepository(session).get_thread(user_id, thread_id))

    statement, params = session.calls[0]
    assert "user_id" in statement
    assert "thread_id" in statement
    assert params == {"user_id": str(user_id), "thread_id": str(thread_id)}


def test_append_locks_owned_thread_before_assigning_message_sequence():
    user_id = uuid4()
    thread_id = uuid4()
    session = RecordingSession([Result({"id": str(thread_id)}), Result()])

    result = asyncio.run(
        ConversationRepository(session).append_message(
            user_id, thread_id, "user", "question"
        )
    )

    assert result is None
    assert len(session.calls) == 2
    lock_statement, lock_params = session.calls[0]
    insert_statement, insert_params = session.calls[1]
    assert "for update" in lock_statement.lower()
    assert lock_params == {"user_id": str(user_id), "thread_id": str(thread_id)}
    assert "coalesce(max(m.sequence), 0) + 1" in insert_statement
    assert insert_params["user_id"] == str(user_id)
    assert insert_params["thread_id"] == str(thread_id)


def test_paper_catalog_lookup_is_scoped_to_user_and_thread():
    from app.repositories.agent_context import AgentContextRepository

    user_id = uuid4()
    thread_id = uuid4()
    session = RecordingSession()

    asyncio.run(AgentContextRepository(session).list_papers(user_id, thread_id))

    statement, params = session.calls[0]
    assert "user_id = :user_id" in statement
    assert "thread_id = :thread_id" in statement
    assert params == {"user_id": str(user_id), "thread_id": str(thread_id)}
