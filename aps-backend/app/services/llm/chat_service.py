from __future__ import annotations

import threading
from typing import AsyncGenerator, Dict, Generator, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from app.config import get_logger, LLMConfig, settings

logger = get_logger(__name__)

# Default timeout for LLM requests (seconds). Guards against stalled inference.
_LLM_TIMEOUT_SECONDS = 120


class ChatServiceError(Exception):
    """Custom exception for ChatService errors."""
    pass


class ChatService:
    def __init__(self, config: Optional[LLMConfig] = None, config_name: Optional[str] = None):
        if config:
            self.config = config
        elif config_name:
            self.config = settings.LLM.get_llm_config(config_name)
        else:
            self.config = settings.LLM.get_llm_config("no_think")

        api_base = self.config.api_url.rsplit("/chat/completions", 1)[0]

        self.llm = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            streaming=self.config.streaming,
            openai_api_base=api_base,
            openai_api_key="EMPTY",
            extra_body={"chat_template_kwargs": {"enable_thinking": self.config.thinking}},
            stream_usage=True,
            request_timeout=_LLM_TIMEOUT_SECONDS,
        )
        logger.info("ChatService initialized: name=%s model=%s", self.config.name, self.config.model_name)

    def stream(self, messages: List[Dict | BaseMessage]) -> Generator[str, None, None]:
        try:
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error("ChatService stream error: %s", e)
            raise ChatServiceError(str(e)) from e

    async def astream(self, messages: List[Dict | BaseMessage]) -> AsyncGenerator[str, None]:
        try:
            async for chunk in self.llm.astream(messages):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
        except Exception as e:
            logger.error("ChatService astream error: %s", e)
            raise ChatServiceError(str(e)) from e

    async def invoke(self, messages: List[Dict | BaseMessage]) -> str:
        """Non-streaming: collect full response. Raises ChatServiceError on empty result."""
        result = []
        async for chunk in self.astream(messages):
            result.append(chunk)
        text = "".join(result)
        if not text.strip():
            raise ChatServiceError("LLM returned empty response")
        return text

    async def health_check(self) -> Dict[str, str]:
        """Async health check — safe to call from async context (FastAPI event loop)."""
        try:
            await self.invoke([{"role": "user", "content": "ping"}])
            return {"status": "healthy", "config": self.config.name}
        except Exception as e:
            logger.error("ChatService health check failed: %s", e)
            return {"status": "unhealthy", "error": str(e), "config": self.config.name}


# Module-level cache: config_name → ChatService instance.
# Double-checked locking prevents duplicate construction under concurrent cold starts.
_cache: Dict[str, ChatService] = {}
_cache_lock = threading.Lock()


def get_cached_chat_service(config_name: str = "no_think") -> ChatService:
    if config_name not in _cache:           # fast path — no lock needed after warm-up
        with _cache_lock:
            if config_name not in _cache:   # double-checked: re-test inside lock
                _cache[config_name] = ChatService(config_name=config_name)
    return _cache[config_name]


def warmup_cached_chat_services(config_names: list[str] | None = None) -> None:
    """Eagerly build commonly used ChatService clients.

    Prevents first-request latency spikes during scenario switches after API restart.
    """
    for name in (config_names or ["no_think", "think"]):
        try:
            get_cached_chat_service(name)
        except Exception:
            logger.exception("ChatService warmup failed for config=%s", name)
