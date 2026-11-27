from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.main import memory_snapshot


def test_progress_memory_older_than_ninety_days_is_reported_forgotten():
    now = datetime.now(timezone.utc)
    snapshot = memory_snapshot(
        [
            {
                "id": uuid4(),
                "text": "completed an old milestone",
                "kind": "progress",
                "importance": 5,
                "stability": 3650,
                "created_at": now - timedelta(days=100),
                "last_recalled_at": now - timedelta(days=100),
                "recall_count": 0,
                "source": "auto",
                "thread_id": None,
            }
        ]
    )

    assert snapshot["items"][0]["forgotten"] is True
    assert snapshot["stats"]["forgotten"] == 1
