"""Anthropic-Client — Block-Antwort + Streaming, mit Modus-Annotation.

Vier-Modus-Engine: der Response-String enthält *manchmal* einen Marker
am Ende `[[MODE:PRÄSENZ]]` o.ä., den der Client wegfiltern + zurückgeben kann.
Wir bitten Anthropic im Prompt-Skelett nicht explizit darum — die Spec
sagt "intern, nicht zu Mira sagen". Wir leiten den Modus deshalb per
Heuristik aus dem Output ab.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import MessageParam

from ..settings import get_settings


@dataclass
class ChatResult:
    text: str
    mode: str | None
    tokens_used: int


def _client_sync() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key)


def _client_async() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key)


def _detect_mode(text: str) -> str:
    """Einfache Heuristik aus dem fertigen Output."""
    if not text:
        return "PRÄSENZ"
    has_question = "?" in text
    word_count = len(text.split())

    if has_question and word_count <= 16:
        return "FOKUS"
    if any(w in text.lower() for w in ("nicht zum ersten mal", "kamen zusammen", "passiert nicht zum ersten")):
        return "VERDICHTEN"
    if any(w in text.lower() for w in ("für heute reicht", "wir schauen morgen", "ich nehm's mit")):
        return "AUSKLANG"
    return "PRÄSENZ"


def respond_block(
    *,
    system_prompt: str,
    messages: list[MessageParam],
    max_tokens: int | None = None,
) -> ChatResult:
    """Synchroner Aufruf, gibt komplette Antwort zurück."""
    settings = get_settings()
    client = _client_sync()
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens or settings.anthropic_max_tokens,
        system=system_prompt,
        messages=messages,
    )
    text = "".join(block.text for block in resp.content if block.type == "text").strip()
    tokens_used = (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0)
    return ChatResult(text=text, mode=_detect_mode(text), tokens_used=tokens_used)


async def respond_stream(
    *,
    system_prompt: str,
    messages: list[MessageParam],
    max_tokens: int | None = None,
) -> AsyncIterator[dict]:
    """Async-Generator. Yields:
        {"delta": "Wort"}        — pro Token-Chunk
        {"done": True, "mode": "...", "tokens_used": N, "text": "..."}  — am Ende
    """
    settings = get_settings()
    client = _client_async()

    text_chunks: list[str] = []
    tokens_in = 0
    tokens_out = 0

    async with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=max_tokens or settings.anthropic_max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                delta = getattr(event.delta, "text", None) or ""
                if delta:
                    text_chunks.append(delta)
                    yield {"delta": delta}
            elif event.type == "message_start":
                tokens_in = event.message.usage.input_tokens or 0
            elif event.type == "message_delta":
                tokens_out = event.usage.output_tokens or 0

    text = "".join(text_chunks).strip()
    yield {
        "done": True,
        "mode": _detect_mode(text),
        "tokens_used": tokens_in + tokens_out,
        "text": text,
    }
