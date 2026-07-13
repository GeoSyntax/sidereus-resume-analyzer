from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5500,http://localhost:8000"
    max_upload_mb: int = 8
    cache_ttl_seconds: int = 24 * 60 * 60

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    # A vision-capable model on the same OpenAI-compatible endpoint. Used to OCR
    # scanned/image-only PDFs. If unset or equal to openai_model, OCR is disabled
    # unless the primary model itself accepts image input.
    openai_vision_model: str | None = None
    # Render scanned pages at this DPI before sending to the vision model. Higher
    # is more accurate but larger payloads; 150 is a good balance for resumes.
    ocr_dpi: int = 150
    # Cap how many pages we OCR to bound latency and token cost on long scans.
    ocr_max_pages: int = 5

    redis_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["*"]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def ocr_model(self) -> str | None:
        """The model used to OCR scanned pages, if any is configured."""
        return self.openai_vision_model or None

    @property
    def ocr_enabled(self) -> bool:
        """OCR needs both an API key and a vision-capable model."""
        return bool(self.openai_api_key and self.ocr_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

