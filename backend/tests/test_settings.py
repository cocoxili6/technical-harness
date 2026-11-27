from app.config import Settings


def test_supabase_runtime_settings_are_loaded_without_public_secret_fields():
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwt_audience="authenticated",
        supabase_jwt_secret="private-signing-secret",
        supabase_db_url="postgresql+asyncpg://user:pass@localhost/db",
    )

    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_jwt_issuer.endswith("/auth/v1")
    assert settings.supabase_jwt_audience == "authenticated"
    assert settings.supabase_jwt_secret.get_secret_value() == "private-signing-secret"
    assert settings.supabase_db_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert "private-signing-secret" not in repr(settings)
    assert "user:pass" not in repr(settings)


def test_supabase_settings_can_be_loaded_from_local_env1_file(tmp_path, monkeypatch):
    env_file = tmp_path / "env1.env"
    env_file.write_text(
        "SUPABASE_URL=https://example.supabase.co\n"
        "SUPABASE_DB_URL=postgresql://db-user:private-pass@localhost/postgres\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.supabase_url == "https://example.supabase.co"
    assert "private-pass" not in repr(settings)
