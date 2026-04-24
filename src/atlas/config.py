from pathlib import Path
from pydantic_settings import BaseSettings

# Absolute path so .env is found regardless of working directory at startup
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # LLM keys
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Per-agent model overrides
    atlas_model_planner: str = ""
    atlas_model_stac_scout: str = ""
    atlas_model_response: str = ""

    # STAC endpoints
    stac_url_element84: str = "https://earth-search.aws.element84.com/v1"
    stac_url_planetary: str = "https://planetarycomputer.microsoft.com/api/stac/v1"

    # App — stored as str so pydantic-settings doesn't attempt JSON decoding
    debug: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
