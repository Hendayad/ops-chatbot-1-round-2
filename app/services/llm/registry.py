"""LLM model registry with pre-initialized instances."""

from typing import (
    Any,
    Dict,
    List,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger

_TOKEN_LIMIT: Dict[str, Any] = {"max_completion_tokens": settings.MAX_TOKENS}
_API_KEY = SecretStr(settings.OPENAI_API_KEY)


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    # NOTE: these must be model IDs the team's LiteLLM virtual key is
    # actually allowed to call -- confirmed via `GET /v1/models` against
    # the proxy that this key's team is restricted to `gemini/*` only, so
    # the previous gpt-5-family entries here 403'd on every single request
    # ("team not allowed to access model ... can only access
    # models=['gemini/*']").
    #
    # Also: the proxy's /v1/models list includes several *dated* Gemini
    # model IDs (gemini-2.0-flash, gemini-2.5-flash, gemini-2.5-flash-lite,
    # gemini-2.5-pro) that Google has since deprecated upstream --
    # confirmed by hitting all four and getting back
    # `litellm.NotFoundError: ... "This model models/X is no longer
    # available[...]"` for every one of them, even though the proxy still
    # lists them. Switched to Google's rolling `-latest` aliases (which
    # Google repoints at the current model instead of deprecating), plus
    # one pinned `-001` build as a fourth, independent fallback.
    LLMS: List[Dict[str, Any]] = [
        {
            "name": "gemini/gemini-flash-latest",
            "llm": ChatOpenAI(
                model="gemini/gemini-flash-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini/gemini-2.0-flash-001",
            "llm": ChatOpenAI(
                model="gemini/gemini-2.0-flash-001",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini/gemini-flash-lite-latest",
            "llm": ChatOpenAI(
                model="gemini/gemini-flash-lite-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "gemini/gemini-pro-latest",
            "llm": ChatOpenAI(
                model="gemini/gemini-pro-latest",
                api_key=_API_KEY,
                model_kwargs=_TOKEN_LIMIT,
                top_p=0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
            ),
        },
    ]

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        When kwargs are provided a fresh ChatOpenAI instance is returned with
        those overrides applied, leaving the shared registry entry untouched.

        Args:
            model_name: Name of the model to retrieve.
            **kwargs: Optional arguments to override default model configuration.

        Returns:
            BaseChatModel instance.

        Raises:
            ValueError: If model_name is not found in LLMS.
        """
        model_entry = next((e for e in cls.LLMS if e["name"] == model_name), None)

        if not model_entry:
            available = ", ".join(e["name"] for e in cls.LLMS)
            raise ValueError(f"model '{model_name}' not found in registry. available models: {available}")

        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return ChatOpenAI(model=model_name, api_key=_API_KEY, **kwargs)

        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Return all registered model names in order.

        Returns:
            List of model name strings.
        """
        return [e["name"] for e in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Return the model entry at a specific index, wrapping to 0 if out of range.

        Args:
            index: Index into LLMS.

        Returns:
            Model entry dict.
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]
