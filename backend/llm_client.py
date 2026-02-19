"""
Diavgeia-Watch: LLM Client Abstraction

Supports multiple backends through a unified interface:
- Ollama (local, default)
- Groq (free tier, cloud)
- Any OpenAI-compatible API

Switch backends by changing config — zero code changes needed.

Usage:
    # Local Ollama
    llm = LLMClient(backend="ollama", model="llama3.1:8b")

    # Groq cloud
    llm = LLMClient(backend="groq", model="llama-3.1-8b-instant", api_key="gsk_...")

    # Any OpenAI-compatible endpoint
    llm = LLMClient(backend="openai", base_url="https://...", api_key="...")

    response = llm.chat("Translate this to SQL: ...")
"""

import json
import logging
from typing import Optional
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

BACKEND_DEFAULTS = {
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "llama3.1:8b",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
    },
}


@dataclass
class LLMResponse:
    """Structured response from any LLM backend."""
    content: str
    model: str
    backend: str
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class LLMClientError(Exception):
    """Raised when LLM communication fails."""
    pass


class LLMClient:
    """
    Unified LLM client that works with Ollama, Groq, and OpenAI-compatible APIs.

    All backends are normalized to the OpenAI chat completions format.
    Ollama natively supports this at /v1/chat/completions.
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        timeout: int = 300,
    ):
        self.backend = backend
        defaults = BACKEND_DEFAULTS.get(backend, {})

        self.model = model or defaults.get("model", "llama3.1:8b")
        self.base_url = (base_url or defaults.get("base_url", "")).rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        self.session = requests.Session()
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers["Content-Type"] = "application/json"

        logger.info(
            f"LLM client initialized: backend={backend} model={self.model} "
            f"url={self.base_url}"
        )

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            user_message: The user's message/query
            system_prompt: System instructions for the model
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: Request JSON output (supported by most models)

        Returns:
            LLMResponse with the model's response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        return self._chat_completions(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            json_mode=json_mode,
        )

    def chat_multi(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Send a multi-turn chat completion request.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
        """
        return self._chat_completions(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            json_mode=json_mode,
        )

    def _chat_completions(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMResponse:
        """Internal: call the chat completions endpoint."""

        # Build the endpoint URL
        if self.backend == "ollama":
            url = f"{self.base_url}/v1/chat/completions"
        else:
            url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        logger.debug(f"LLM request: model={self.model} messages={len(messages)}")

        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            raise LLMClientError(
                f"Cannot connect to {self.backend} at {self.base_url}. "
                f"Is {'Ollama' if self.backend == 'ollama' else 'the API server'} running?"
            )
        except requests.exceptions.Timeout:
            raise LLMClientError(
                f"LLM request timed out after {self.timeout}s. "
                f"Try a smaller model or increase timeout."
            )
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = resp.json().get("error", {}).get("message", resp.text[:300])
            except Exception:
                error_detail = resp.text[:300]
            raise LLMClientError(f"LLM API error ({resp.status_code}): {error_detail}") from e

        # Parse response (OpenAI format)
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError) as e:
            raise LLMClientError(f"Unexpected LLM response format: {e}")

        return LLMResponse(
            content=content.strip(),
            model=data.get("model", self.model),
            backend=self.backend,
            usage=usage,
            raw=data,
        )

    # -----------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------

    def is_available(self) -> bool:
        """Check if the LLM backend is reachable."""
        try:
            if self.backend == "ollama":
                resp = self.session.get(
                    f"{self.base_url}/api/tags", timeout=5
                )
                return resp.status_code == 200
            else:
                # For OpenAI-compatible APIs, try a minimal request
                resp = self.session.get(
                    f"{self.base_url}/models", timeout=5
                )
                return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def list_models(self) -> list[str]:
        """List available models (Ollama only)."""
        if self.backend != "ollama":
            return [self.model]
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
            return []