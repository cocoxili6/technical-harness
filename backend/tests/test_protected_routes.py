from fastapi.testclient import TestClient
from uuid import uuid4

from app import main
from app.auth import CurrentUser, get_current_user
from app.main import app, get_user_db_session


class Result:
    def mappings(self):
        return self

    def all(self):
        return []


class Session:
    async def execute(self, statement, params=None):
        return Result()


async def fake_user_db_session():
    yield Session()


def test_thread_list_requires_supabase_bearer_token():
    response = TestClient(app).get("/api/threads")
    assert response.status_code == 401


def test_chat_request_body_is_flat_and_does_not_include_dependency_settings():
    schema = TestClient(app).get("/openapi.json").json()
    request_schema = schema["paths"]["/api/chat/stream"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    body_schema = schema["components"]["schemas"].get(
        request_schema.get("$ref", "").rsplit("/", 1)[-1],
        request_schema,
    )

    assert "payload" not in body_schema.get("properties", {})
    assert "settings" not in body_schema.get("properties", {})
    assert "message" in body_schema.get("properties", {})


def test_health_stays_public_when_gateway_token_is_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "harness_shared_token", "gateway-secret")
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: CurrentUser(id=uuid4(), email="user@example.com"),
    )
    monkeypatch.setitem(
        app.dependency_overrides, get_user_db_session, fake_user_db_session
    )
    client = TestClient(app)

    health = client.get("/api/health")
    missing_gateway = client.get("/api/threads")
    authenticated = client.get(
        "/api/threads", headers={"x-harness-gateway-token": "gateway-secret"}
    )

    assert health.status_code == 200
    assert missing_gateway.status_code == 401
    assert authenticated.status_code == 200
