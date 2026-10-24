"""One provider interface, two OpenAI-compatible endpoints.

Swapping `base_url` and `model_id` is the only change needed, which is what question 5.11 asks for.
Every test here runs against `httpx.MockTransport`, so the number of real LLM calls is exactly zero.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import httpx

# Two configurations pointing at different hosts and model ids, same request contract.
PROVIDER_A = {
    "name": "provider_a",
    "base_url": "https://api.provider-a.example/v1",
    "model_id": "chat-a-large",
}
PROVIDER_B = {
    "name": "provider_b",
    "base_url": "https://api.provider-b.example/v1",
    "model_id": "chat-b-mini",
}


@dataclass
class ProviderResult:
    text: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    endpoint: str


class ChatProvider:
    """Minimal chat-completions client over a shared request contract."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        # The key is injected, never read from the environment here, and never logged.
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def build_request(self, question: str, max_tokens: int = 100) -> dict[str, Any]:
        return {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": question}],
        }

    def complete(self, question: str, max_tokens: int = 100) -> ProviderResult:
        response = self._client.post("/chat/completions", json=self.build_request(question, max_tokens))
        response.raise_for_status()
        body = response.json()
        usage = body.get("usage", {})
        return ProviderResult(
            text=body["choices"][0]["message"]["content"],
            model_id=body.get("model", self.model_id),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            endpoint=str(response.request.url),
        )

    def close(self) -> None:
        self._client.close()


def mock_endpoint(recorded: list[dict], *, status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    """Reflect a canned completion and record the request so the contract can be asserted."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content or b"{}")
        recorded.append(
            {
                "url": str(request.url),
                "method": request.method,
                "model": payload.get("model"),
                "auth": request.headers.get("authorization", ""),
                "messages": payload.get("messages"),
            }
        )
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "scripted failure"}})
        return httpx.Response(
            200,
            json={
                "model": payload.get("model"),
                "choices": [{"message": {"content": "canned answer"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            },
        )

    return handler
