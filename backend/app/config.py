from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "研途 Research Harness"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = 0.3
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    harness_shared_token: str = ""
    arxiv_endpoint: str = "https://export.arxiv.org/api/query"
    serper_api_key: str = ""
    serper_scholar_endpoint: str = "https://google.serper.dev/scholar"
    openalex_endpoint: str = "https://api.openalex.org/works"
    openalex_api_key: str = ""

    @property
    def llm_configured(self) -> bool:
        return bool(self.deepseek_api_key.strip())

    @property
    def scholar_configured(self) -> bool:
        return bool(self.serper_api_key.strip())

    @property
    def cors_origin_list(self) -> list:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
