from fastapi.testclient import TestClient

from app.main import app


def test_thread_list_requires_supabase_bearer_token():
    response = TestClient(app).get("/api/threads")
    assert response.status_code == 401
