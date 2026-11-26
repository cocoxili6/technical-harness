from app.config import Settings


def test_supabase_runtime_settings_are_loaded_without_public_secret_fields():
    settings = Settings(
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
