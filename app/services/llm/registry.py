"""Registry for the Gemini chat model used by the application."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.logging import logger


def _create_model(model_name: str, **overrides: Any) -> BaseChatModel:
    """Create the configured Gemini chat model."""
    options: dict[str, Any] = {
        "temperature": settings.DEFAULT_LLM_TEMPERATURE,
        "max_tokens": settings.MAX_TOKENS,
        "timeout": settings.LLM_TOTAL_TIMEOUT,
        "max_retries": settings.MAX_LLM_CALL_RETRIES,
    }
    options.update(overrides)

    return ChatGoogleGenerativeAI(
        model=model_name,
        **options,
    )


class LLMRegistry:
    """Store the single Gemini chat model used by the application."""

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    # NOTE: as of 2026-08-04 this team switched from the shared LiteLLM proxy
    # to hitting Google's native Gemini endpoint directly (see OPENAI_BASE_URL
    # in .env), each teammate using their own personal Gemini API key. Model
    # IDs here are plain Gemini names (no "gemini/" provider prefix, which was
    # only needed for the old LiteLLM proxy routing).
    LLMS: List[Dict[str, Any]] = [
        {
            "name": "gemini-3.6-flash",
            "llm": ChatOpenAI(
                model="gemini-3.6-flash",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini-flash-latest",
            "llm": ChatOpenAI(
                model="gemini-flash-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini-flash-lite-latest",
            "llm": ChatOpenAI(
                model="gemini-flash-lite-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini-pro-latest",
            "llm": ChatOpenAI(
                model="gemini-pro-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
    LLMS: list[dict[str, Any]] = [
        {
            "name": "gemini-3.6-flash",
            "llm": _create_model("gemini-3.6-flash"),
        }
    ]

    @classmethod
    def get(cls, model_name: str, **kwargs: Any) -> BaseChatModel:
        """Return the registered model, optionally with temporary overrides."""
        model_entry = next(
            (
                entry
                for entry in cls.LLMS
                if entry["name"] == model_name
            ),
            None,
        )

        if model_entry is None:
            available = ", ".join(cls.get_all_names())
            raise ValueError(
                f"model {model_name!r} not found in registry. "
                f"available models: {available}"
            )

        if kwargs:
            logger.debug(
                "creating_llm_with_custom_args",
                model_name=model_name,
                custom_args=list(kwargs),
            )
            return _create_model(model_name, **kwargs)

        logger.debug(
            "using_default_llm_instance",
            model_name=model_name,
        )
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> list[str]:
        """Return all registered chat-model names."""
        return [str(entry["name"]) for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> dict[str, Any]:
        """Return the only registered model.

        The method is preserved because the existing LLM service uses it for
        fallback lookup.
        """
        del index
        return cls.LLMS[0]