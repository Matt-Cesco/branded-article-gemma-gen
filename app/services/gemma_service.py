"""Small Ollama/Gemma client with model-independent interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import httpx

from app.config import get_settings


class LLMError(RuntimeError):
    pass


@dataclass
class LLMGeneration:
    content: str
    provider: str
    model: str
    metrics: dict[str, int | float | str]


class LLMService(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneration:
        raise NotImplementedError


class OllamaGemmaService(LLMService):
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneration:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise LLMError("Ollama is not running or cannot be reached at the configured URL.") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Ollama took too long to respond. Try a shorter article or increase OLLAMA_TIMEOUT.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Ollama returned a connection error while generating the article.") from exc

        if response.status_code >= 400:
            raise LLMError(f"Ollama returned HTTP {response.status_code}. Check that the configured model is available.")
        try:
            data = response.json()
            content = data["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("Ollama returned an unexpected response format.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Ollama returned an empty generation.")
        metric_keys = [
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        ]
        metrics = {key: data[key] for key in metric_keys if key in data}
        return LLMGeneration(content=content, provider="ollama", model=self.model, metrics=metrics)
