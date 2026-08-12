"""Long-term memory service using mem0, Gemini, and pgvector."""

from mem0 import AsyncMemory

from app.core.cache import (
    cache_key,
    cache_service,
)
from app.core.config import settings
from app.core.logging import logger


_MEMORY_EMBEDDING_DIMS = 1536


class MemoryService:
    """Manage long-term memory with strict user/cohort isolation."""

    def __init__(self) -> None:
        """Initialize the memory service lazily."""
        self._memory: AsyncMemory | None = None

    @staticmethod
    def _memory_llm_model() -> str:
        """Resolve a Gemini model for Mem0's memory extraction step.

        Older project configuration used ``gpt-5-nano`` with Gemini's
        OpenAI-compatible endpoint. Mem0's OpenAI provider sends parameters
        that Gemini does not support (for example ``store``), so long-term
        memory now uses Mem0's native Gemini provider.

        Prefer LONG_TERM_MEMORY_MODEL when it is already a Gemini model.
        Otherwise fall back to the application's configured Gemini model.
        """
        configured = str(settings.LONG_TERM_MEMORY_MODEL or "").strip()

        if configured.lower().startswith("gemini"):
            return configured

        default_model = str(settings.DEFAULT_LLM_MODEL or "").strip()

        if default_model.lower().startswith("gemini"):
            logger.warning(
                "long_term_memory_model_fallback",
                configured_model=configured or None,
                fallback_model=default_model,
                reason="memory_model_must_use_native_gemini_provider",
            )
            return default_model

        # Final safe fallback for this Gemini-based project.
        fallback = "gemini-3.6-flash"
        logger.warning(
            "long_term_memory_model_fallback",
            configured_model=configured or None,
            default_model=default_model or None,
            fallback_model=fallback,
            reason="no_gemini_memory_model_configured",
        )
        return fallback

    @staticmethod
    def _memory_embedder_model() -> str:
        """Normalize the Gemini embedding model name for Mem0."""
        model = str(
            settings.LONG_TERM_MEMORY_EMBEDDER_MODEL
            or "gemini-embedding-001"
        ).strip()

        if model.startswith("models/"):
            return model

        return f"models/{model}"

    async def _get_memory(self) -> AsyncMemory:
        """Create the shared Mem0 instance on first use."""
        if self._memory is not None:
            return self._memory

        if not settings.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is required for long-term memory."
            )

        llm_model = self._memory_llm_model()
        embedder_model = self._memory_embedder_model()

        self._memory = await AsyncMemory.from_config(
            config_dict={
                "vector_store": {
                    "provider": "pgvector",
                    "config": {
                        "collection_name": (
                            settings.LONG_TERM_MEMORY_COLLECTION_NAME
                        ),
                        "embedding_model_dims": _MEMORY_EMBEDDING_DIMS,
                        "dbname": settings.POSTGRES_DB,
                        "user": settings.POSTGRES_USER,
                        "password": settings.POSTGRES_PASSWORD,
                        "host": settings.POSTGRES_HOST,
                        "port": settings.POSTGRES_PORT,
                    },
                },
                "llm": {
                    "provider": "gemini",
                    "config": {
                        "model": llm_model,
                        "api_key": settings.GOOGLE_API_KEY,
                        # Keep memory extraction deterministic.
                        "temperature": 0.1,
                    },
                },
                "embedder": {
                    "provider": "gemini",
                    "config": {
                        "model": embedder_model,
                        "api_key": settings.GOOGLE_API_KEY,
                        # Keep compatibility with the existing 1536-dim
                        # pgvector long-term-memory collection.
                        "embedding_dims": _MEMORY_EMBEDDING_DIMS,
                    },
                },
            }
        )

        logger.info(
            "memory_service_configured",
            llm_provider="gemini",
            llm_model=llm_model,
            embedder_provider="gemini",
            embedder_model=embedder_model,
            embedding_dims=_MEMORY_EMBEDDING_DIMS,
        )

        return self._memory

    async def initialize(self) -> None:
        """Pre-warm the Mem0 instance and its pgvector connection."""
        await self._get_memory()
        logger.info("memory_service_initialized")

    async def search(
        self,
        user_id: str | None,
        query: str,
        cohort_id: str | None = None,
    ) -> str:
        """Search memories for one user, strictly scoped to a cohort."""
        if user_id is None:
            return ""

        try:
            cache_scope = (
                f"{cohort_id}:{user_id}"
                if cohort_id
                else str(user_id)
            )
            key = cache_key("memory", cache_scope, query)

            cached = await cache_service.get(key)
            if cached is not None:
                logger.debug(
                    "memory_search_cache_hit",
                    user_id=user_id,
                    cohort_id=cohort_id,
                )
                return cached

            memory = await self._get_memory()

            filters: dict[str, str] = {}
            if cohort_id:
                filters["cohort_id"] = cohort_id

            results = await memory.search(
                user_id=str(user_id),
                query=query,
                filters=filters or None,
            )

            filtered_results: list[str] = []

            for result in results.get("results", []):
                if not isinstance(result, dict):
                    continue

                metadata = result.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}

                record_cohort = metadata.get("cohort_id")

                # Strict defense in depth: when a cohort is requested,
                # memories with a different OR missing cohort are rejected.
                if cohort_id and record_cohort != cohort_id:
                    logger.warning(
                        "cross_cohort_memory_blocked",
                        user_id=user_id,
                        requested_cohort=cohort_id,
                        record_cohort=record_cohort,
                    )
                    continue

                memory_text = result.get("memory")
                if isinstance(memory_text, str) and memory_text.strip():
                    filtered_results.append(
                        f"* {memory_text.strip()}"
                    )

            result_text = "\n".join(filtered_results)

            if result_text:
                await cache_service.set(key, result_text)

            return result_text

        except Exception as exc:
            logger.exception(
                "failed_to_get_relevant_memory",
                error=str(exc),
                user_id=user_id,
                cohort_id=cohort_id,
                query=query,
            )
            return ""

    async def add(
        self,
        user_id: str | None,
        messages: list[dict],
        metadata: dict | None = None,
        cohort_id: str | None = None,
    ) -> None:
        """Add conversation facts to memory with cohort metadata."""
        if user_id is None:
            return

        try:
            memory = await self._get_memory()

            # Copy instead of mutating a caller-owned dictionary.
            payload_metadata = dict(metadata or {})

            if cohort_id:
                payload_metadata["cohort_id"] = cohort_id

            await memory.add(
                messages,
                user_id=str(user_id),
                metadata=payload_metadata,
            )

            logger.info(
                "long_term_memory_updated_successfully",
                user_id=user_id,
                cohort_id=cohort_id,
            )

        except Exception as exc:
            # Long-term memory is supplementary; a memory failure must not
            # break the learner's primary chat request.
            logger.exception(
                "failed_to_update_long_term_memory",
                user_id=user_id,
                cohort_id=cohort_id,
                error=str(exc),
            )


memory_service = MemoryService()