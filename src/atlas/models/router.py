"""
Model router — picks the right LangChain chat model per agent.
Priority: settings override (from .env) → config/models.yaml primary → fallback.
"""

from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel

from atlas.config import settings


@lru_cache(maxsize=1)
def _load_config() -> dict:
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "models.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def _resolve_model_id(agent: str) -> str:
    override = getattr(settings, f"atlas_model_{agent.lower()}", "")
    if override:
        return override

    config = _load_config()
    return config.get("agents", {}).get(agent, {}).get(
        "primary", "ollama/nemotron-3-nano:30b-cloud"
    )


def get_llm(agent: str, **kwargs: Any) -> BaseChatModel:
    model_id = _resolve_model_id(agent)
    print(f"[router] agent={agent!r} model={model_id!r}")

    if model_id.startswith("ollama/"):
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_id.removeprefix("ollama/"),
            base_url=settings.ollama_base_url,
            **kwargs,
        )

    if model_id.startswith("anthropic/"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_id.removeprefix("anthropic/"),
            api_key=settings.anthropic_api_key,
            **kwargs,
        )

    if model_id.startswith("google/") or model_id.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_id.removeprefix("google/"),
            google_api_key=settings.google_api_key,
            **kwargs,
        )

    if model_id.startswith("groq/"):
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_id.removeprefix("groq/"),
            groq_api_key=settings.groq_api_key,
            **kwargs,
        )

    from langchain_openai import ChatOpenAI

    if model_id.startswith("openrouter/"):
        # Pass api_key explicitly — openai 2.x uses it reliably in the Bearer header.
        return ChatOpenAI(
            model=model_id.removeprefix("openrouter/"),
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://atlas.geoai",
                "X-Title": "Atlas GeoAI",
            },
            **kwargs,
        )

    return ChatOpenAI(model=model_id, api_key=settings.openai_api_key, **kwargs)
