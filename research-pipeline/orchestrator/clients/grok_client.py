"""
orchestrator.clients.grok_client
================================

Wraps the xAI Grok API. xAI exposes an OpenAI-compatible REST surface at
https://api.x.ai/v1/chat/completions plus a `search_parameters` field that
enables live web + X search ("DeepSearch" equivalent in our pipeline).

We use httpx directly rather than the openai SDK pointed at the xAI base
URL because:
    1. The xAI-specific `search_parameters` field isn't in the OpenAI SDK
       types and would require monkey-patching.
    2. We want full control over the request body to add fields as xAI
       evolves the API.
    3. One direct dependency is easier to reason about than two SDKs
       fighting over the same client.

Like OpenAIClient, this respects dry_run and tracks cost.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .pricing import estimate_cost_usd

_API_URL = "https://api.x.ai/v1/chat/completions"


@dataclass
class GrokResult:
    """Uniform return type for grok calls. Matches CallResult shape."""

    content: str
    raw: dict[str, Any]
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    dry_run: bool
    sources_used: list[dict[str, Any]]   # for citation hardening


class GrokClient:
    def __init__(
        self,
        api_key: str,
        *,
        dry_run: bool = False,
        timeout_seconds: int = 60 * 5,
    ):
        self.api_key = api_key
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        # One persistent client per instance for connection pooling.
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=15.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "GrokClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    # ------------------------------------------------------- live search

    async def deep_search(
        self,
        prompt: str,
        *,
        model: str,
        sources: list[str] | None = None,
        max_tokens: int = 8192,
    ) -> GrokResult:
        """
        Call Grok with live web + X search enabled.

        Args:
            prompt: full system+user prompt as one string.
            model: typically "grok-4".
            sources: list of source types to enable. Defaults to
                     ["web", "x", "news"]. Pass ["x"] for X-only.
            max_tokens: cap on output length.
        """
        if self.dry_run:
            return self._stub(prompt, model)

        # Per xAI docs, search_parameters.mode=on forces a search even if
        # the model thinks the prompt doesn't need one. Good for our use
        # case since we explicitly want grounded responses.
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
            "search_parameters": {
                "mode": "on",
                "return_citations": True,
                "sources": sources or [
                    {"type": "web"},
                    {"type": "x"},
                    {"type": "news"},
                ],
            },
        }

        start = time.monotonic()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=60),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        ):
            with attempt:
                response = await self._http.post(_API_URL, json=body)
                response.raise_for_status()
                raw = response.json()

        latency_ms = int((time.monotonic() - start) * 1000)

        content = raw["choices"][0]["message"]["content"]
        usage = raw.get("usage", {})
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = estimate_cost_usd(model, tokens_in, tokens_out)

        # xAI adds a citation surcharge per source consulted; we add a
        # rough $0.005 per cited source as a safety margin in our ledger.
        # The true cost is in the billing portal; this just keeps our
        # cost-cap arithmetic conservative.
        citations = raw.get("citations") or []
        cost += 0.005 * len(citations)

        return GrokResult(
            content=content,
            raw=raw,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            dry_run=False,
            sources_used=citations if isinstance(citations, list) else [],
        )

    # ---------------------------------------------------- chat (no search)

    async def chat_complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> GrokResult:
        """Plain chat completion without live search; used for red-team
        passes that grade an already-drafted article."""
        if self.dry_run:
            return self._stub(f"{system}\n\n{user}", model)

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start = time.monotonic()
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        ):
            with attempt:
                response = await self._http.post(_API_URL, json=body)
                response.raise_for_status()
                raw = response.json()

        latency_ms = int((time.monotonic() - start) * 1000)
        content = raw["choices"][0]["message"]["content"]
        usage = raw.get("usage", {})
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = estimate_cost_usd(model, tokens_in, tokens_out)

        return GrokResult(
            content=content,
            raw=raw,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            dry_run=False,
            sources_used=[],
        )

    # ---------------------------------------------------------- utilities

    def _stub(self, prompt: str, model: str) -> GrokResult:
        stub = (
            "DRY RUN - Grok stub.\n"
            f"Model: {model}\n"
            f"Prompt length: {len(prompt)} chars\n"
        )
        return GrokResult(
            content=stub,
            raw={},
            model=model,
            tokens_in=len(prompt) // 4,
            tokens_out=150,
            latency_ms=80,
            cost_usd=0.0,
            dry_run=True,
            sources_used=[],
        )

    async def probe(self, model: str) -> dict[str, Any]:
        """Preflight check - one cheap call to confirm credentials work."""
        if self.dry_run:
            return {"ok": True, "dry_run": True, "model": model}
        try:
            body = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with: ok"}],
                "max_tokens": 4,
                "temperature": 0,
            }
            response = await self._http.post(_API_URL, json=body)
            response.raise_for_status()
            return {
                "ok": True,
                "model": model,
                "reply": response.json()["choices"][0]["message"]["content"],
            }
        except Exception as e:
            return {"ok": False, "model": model, "error": str(e)}
