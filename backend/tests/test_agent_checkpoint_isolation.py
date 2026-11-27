from app.agent.graph import build_agent
from app.config import Settings
from app.main import graph_config
from uuid import uuid4


def test_build_agent_uses_injected_durable_checkpointer():
    checkpointer = object()

    graph = build_agent(
        Settings(_env_file=None, deepseek_api_key="test-key"),
        checkpointer=checkpointer,
    )

    assert graph.checkpointer is checkpointer


def test_checkpoint_namespace_is_unique_per_user_for_same_thread():
    thread_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    config_a = graph_config(user_a, thread_id)
    config_b = graph_config(user_b, thread_id)

    assert config_a["configurable"]["thread_id"] == str(thread_id)
    assert config_a["configurable"]["checkpoint_ns"] == f"user:{user_a}"
    assert config_b["configurable"]["checkpoint_ns"] == f"user:{user_b}"
    assert config_a["configurable"]["checkpoint_ns"] != config_b["configurable"]["checkpoint_ns"]
