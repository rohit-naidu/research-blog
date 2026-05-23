"""
orchestrator.clients.openai_client
==================================

Wraps the OpenAI SDK with the three patterns we use repeatedly:

1. `deep_research()`   - long-running autonomous browsing call. We use the
                         Responses API with a reasoning model + the
                         `web_search_preview` tool. The call can take
                         20-40 minutes; we stream progress where possible
                         and respect a timeout.

2. `chat_complete()`   - one-shot GPT-5 call for drafting / red-team /
                         revision / utility tasks. No browsing. Standard
                         chat completion with optional JSON-mode output.

3. `dry_run`           - any call routes to a stub that returns canned
                         output without spending money. Activated when the
                         orchestrator is started with --dry-run.

Why a hand-rolled wrapper instead of just calling openai directly:
    - Uniform retry behavior (exponential backoff via tenacity).
    - Uniform cost logging that funnels into the state DB.
    - One place to flip dry-run on/off.
    - One place to change the API surface when OpenAI ships a new version.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .pricing import estimate_cost_usd


@dataclass
class CallResult:
    """Uniform return type for both deep_research and chat_complete."""

    content: str                # the main textual output
    raw: dict[str, Any]         # full response dict for debugging / archival
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    dry_run: bool


class OpenAIClient:
    """Async OpenAI client with cost tracking + dry-run + retries."""

    def __init__(
        self,
        api_key: str,
        *,
        dry_run: bool = False,
        timeout_seconds: int = 60 * 60,  # 1 hour - Deep Research can be slow
    ):
        # The official SDK handles connection pooling and SSE streaming.
        # We give it a long timeout because Deep Research calls genuinely
        # take 20-40 minutes.
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------- deep research

    async def deep_research(
        self,
        prompt: str,
        *,
        model: str,
        max_output_tokens: int = 16384,
    ) -> CallResult:
        """
        Fire a Deep Research call via the Responses API.

        We use the Responses API with the web_search_preview tool enabled.
        This is OpenAI's recommended path for autonomous browsing-and-
        reasoning workflows.

        The call can run for 20-40 minutes. The caller is responsible for
        providing the outer asyncio.gather() that lets multiple Deep
        Research calls run in parallel.

        Args:
            prompt: the full prompt text (system + user, concatenated;
                    the Responses API takes a single input string).
            model: which reasoning model to use. Typically "o3-deep-research"
                   or "gpt-5" as a fallback.
            max_output_tokens: hard cap on output length.

        Returns:
            CallResult with content, usage, and cost.
        """
        if self.dry_run:
            return await self._stub_deep_research(prompt, model)

        start = time.monotonic()

        # Retry with exponential backoff on transient errors only.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=60),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        ):
            with attempt:
                response = await self._client.responses.create(
                    model=model,
                    input=prompt,
                    tools=[{"type": "web_search_preview"}],
                    max_output_tokens=max_output_tokens,
                )

        latency_ms = int((time.monotonic() - start) * 1000)

        # The Responses API returns output as a list of segments; we join
        # the text portions into the final content string.
        content = self._extract_text(response)
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "input_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "output_tokens", 0) if usage else 0
        cost = estimate_cost_usd(model, tokens_in, tokens_out)

        return CallResult(
            content=content,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            dry_run=False,
        )

    # -------------------------------------------------------- chat complete

    async def chat_complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 8192,
        json_mode: bool = False,
    ) -> CallResult:
        """
        One-shot GPT-5 chat completion. Used for drafting, red-team,
        revision, and small utility calls.
        """
        if self.dry_run:
            return await self._stub_chat(system, user, model)

        start = time.monotonic()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        ):
            with attempt:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await self._client.chat.completions.create(**kwargs)

        latency_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""
        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost = estimate_cost_usd(model, tokens_in, tokens_out)

        return CallResult(
            content=content,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            dry_run=False,
        )

    # --------------------------------------------------------- utilities

    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Pull the textual content out of a Responses API response.

        The Responses API returns a list of output items, which may include
        web_search tool calls, reasoning traces, and message segments. We
        want the assistant's final textual message(s).
        """
        # Prefer the convenience accessor when available.
        text = getattr(response, "output_text", None)
        if text:
            return text

        # Fall back to scanning output items.
        out: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", None) == "output_text":
                        out.append(c.text)
        return "\n".join(out)

    async def _stub_deep_research(self, prompt: str, model: str) -> CallResult:
        """Dry-run stub. Returns a placeholder result without hitting the API."""
        await asyncio.sleep(0.1)  # tiny delay so callers see realistic ordering
        stub = (
            "## DRY RUN — Deep Research stub\n\n"
            f"Model: {model}\n"
            f"Prompt length: {len(prompt)} chars\n\n"
            "Real research output would appear here. To run for real, "
            "remove the --dry-run flag.\n"
        )
        return CallResult(
            content=stub,
            raw={},
            model=model,
            tokens_in=len(prompt) // 4,
            tokens_out=200,
            latency_ms=100,
            cost_usd=0.0,
            dry_run=True,
        )

    async def _stub_chat(self, system: str, user: str, model: str) -> CallResult:
        await asyncio.sleep(0.05)
        stub = (
            "DRY RUN — chat completion stub.\n"
            f"Model: {model}\n"
            f"System length: {len(system)} chars\n"
            f"User length: {len(user)} chars\n"
        )
        return CallResult(
            content=stub,
            raw={},
            model=model,
            tokens_in=(len(system) + len(user)) // 4,
            tokens_out=100,
            latency_ms=50,
            cost_usd=0.0,
            dry_run=True,
        )

    # --------------------------------------------------- preflight probe

    async def probe(self, model: str) -> dict[str, Any]:
        """
        Cheap connectivity probe used by the preflight check. Sends a 1-token
        request and returns success / error info without spending real money.
        """
        if self.dry_run:
            return {"ok": True, "dry_run": True, "model": model}
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_tokens=4,
                temperature=0,
            )
            return {
                "ok": True,
                "model": model,
                "reply": response.choices[0].message.content,
            }
        except Exception as e:  # broad on purpose - preflight should report any error
            return {"ok": False, "model": model, "error": str(e)}
