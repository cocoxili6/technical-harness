from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "migrations" / "0001_user_data.sql"
OWNED_TABLES = (
    "threads",
    "messages",
    "memories",
    "paper_catalog",
    "tool_runs",
    "context_summaries",
)


def test_each_user_owned_table_has_rls_and_auth_uid_policy():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in OWNED_TABLES:
        assert f"'{table}'" in sql
    assert "alter table public.%i enable row level security" in sql
    assert "create policy user_isolation on public.%i using" in sql
    assert "using (user_id = auth.uid())" in sql
    assert "with check (user_id = auth.uid())" in sql


def test_child_rows_are_composite_scoped_to_their_parent_user():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "foreign key (user_id, thread_id)" in sql
    assert "references public.threads(user_id, id)" in sql
