import asyncio
import json
from uuid import uuid4

from app.db import set_user_rls_context


class RecordingSession:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))


def test_user_context_sets_authenticated_role_and_verified_sub_claim():
    user_id = uuid4()
    session = RecordingSession()

    asyncio.run(set_user_rls_context(session, user_id))

    statements = [statement for statement, _ in session.calls]
    assert "SET LOCAL ROLE authenticated" in statements
    claims_call = next(call for call in session.calls if "request.jwt.claims" in call[0])
    assert json.loads(claims_call[1]["claims"]) == {
        "sub": str(user_id),
        "role": "authenticated",
    }
    sub_call = next(call for call in session.calls if "request.jwt.claim.sub" in call[0])
    assert sub_call[1]["sub"] == str(user_id)
