"""Anthropic-Client — Block-Antwort + Streaming, mit Modus-Annotation.

Vier-Modus-Engine: der Response-String enthält *manchmal* einen Marker
am Ende `[[MODE:PRÄSENZ]]` o.ä., den der Client wegfiltern + zurückgeben kann.
Wir bitten Anthropic im Prompt-Skelett nicht explizit darum — die Spec
sagt "intern, nicht zu Mira sagen". Wir leiten den Modus deshalb per
Heuristik aus dem Output ab.

Tool-Use (Schritt 4):
    respond_block_with_tools() — Multi-Turn-Loop. Solange das Modell mit
    stop_reason='tool_use' antwortet, führen wir die Tool-Calls in
    services.tools_runtime aus, hängen die Ergebnisse an die Messages und
    rufen Anthropic erneut. Maximale Iterationen: 5 (Spec 11).
    Streaming-Variante kommt in 4.4.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import MessageParam
from sqlalchemy.orm import Session as DBSession

from ..settings import get_settings

log = logging.getLogger("shiksha.anthropic")

# Spec 11 — harte Obergrenze pro Mira-Nachricht.
MAX_TOOL_ITERATIONS = 5


@dataclass
class ChatResult:
    text: str
    mode: str | None
    tokens_used: int
    # Tool-Use-Metadaten (Schritt 4) — nur intern, nie an Mira-UI.
    tool_iterations: int = 0
    tool_calls: list[dict] = field(default_factory=list)


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


# ===================================================================
# Tool-Use Multi-Turn-Loop (Schritt 4.2)
# ===================================================================

def respond_block_with_tools(
    *,
    system_prompt: str,
    messages: list[MessageParam],
    operator,            # Operator-Model
    shiksha_session,     # Session-Model (SHIKSHA-Session, nicht DB-Session)
    db: DBSession,
    max_tokens: int | None = None,
) -> ChatResult:
    """Multi-Turn-Loop: Tool-Calls werden hier ausgeführt, bis Modell mit Text endet.

    Wichtig: Tools schreiben in `db`. Der Aufrufer (Chat-Router) committet
    am Ende — entweder den ganzen erfolgreichen Run, oder rollback wenn die
    Anthropic-API einen unrecoverable Fehler wirft. Audit-Logs der Tool-Calls
    überleben Rollback (eigene SessionLocal, siehe tools_runtime).

    Loop-Limit: MAX_TOOL_ITERATIONS = 5. Beim Hitzschlag wird das Modell mit
    einem zusätzlichen System-Hinweis "no more tools available, finalize"
    erneut gefragt — siehe _force_terminal_response.
    """
    # Lokaler Import damit der Anthropic-Client ohne tools_runtime importierbar
    # bleibt (z.B. in Tests, die Tools wegmocken).
    from .tools_runtime import execute_tool, list_tools_for_anthropic

    settings = get_settings()
    client = _client_sync()
    tools_definition = list_tools_for_anthropic(operator)

    tokens_total = 0
    tool_calls_log: list[dict] = []
    # `messages` wird im Loop in-place erweitert — wir wollen den Aufrufer
    # nicht verändern, deshalb arbeiten wir auf einer Kopie.
    working_messages: list[MessageParam] = list(messages)

    for iteration in range(MAX_TOOL_ITERATIONS):
        kwargs: dict[str, Any] = {
            "model":      settings.anthropic_model,
            "max_tokens": max_tokens or settings.anthropic_max_tokens,
            "system":     system_prompt,
            "messages":   working_messages,
        }
        if tools_definition:
            kwargs["tools"] = tools_definition

        resp = client.messages.create(**kwargs)
        tokens_total += (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0)

        # Erfolgsfall: Modell ist mit Text fertig.
        if resp.stop_reason != "tool_use":
            text = _extract_text(resp.content)
            return ChatResult(
                text=text,
                mode=_detect_mode(text),
                tokens_used=tokens_total,
                tool_iterations=iteration,
                tool_calls=tool_calls_log,
            )

        # Tool-Use: Assistant-Content kopieren (incl. tool_use-Blöcke),
        # dann pro Tool-Use-Block ausführen und Result als user-content anhängen.
        working_messages.append({
            "role":    "assistant",
            "content": _serialize_assistant_content(resp.content),
        })

        tool_results: list[dict] = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tool_name = block.name
            tool_args = block.input or {}
            tool_use_id = block.id

            result_block = execute_tool(
                name=tool_name,
                args=tool_args,
                tool_use_id=tool_use_id,
                operator=operator,
                shiksha_session=shiksha_session,
                db=db,
            )
            tool_results.append(result_block)
            tool_calls_log.append({
                "tool":     tool_name,
                "args":     tool_args,
                "is_error": bool(result_block.get("is_error")),
            })

        working_messages.append({
            "role":    "user",
            "content": tool_results,
        })
        # Nächste Iteration — Modell sieht jetzt Tool-Results.

    # Loop-Guard: Modell hat 5x Tools angefordert ohne abzuschließen.
    log.warning(
        "Tool-Loop hit MAX_TOOL_ITERATIONS=%d for operator=%s session=%s",
        MAX_TOOL_ITERATIONS, operator.id, shiksha_session.id,
    )
    return _force_terminal_response(
        client=client,
        settings=settings,
        system_prompt=system_prompt,
        working_messages=working_messages,
        max_tokens=max_tokens,
        tokens_total=tokens_total,
        tool_calls_log=tool_calls_log,
    )


def _force_terminal_response(
    *,
    client: Anthropic,
    settings,
    system_prompt: str,
    working_messages: list[MessageParam],
    max_tokens: int | None,
    tokens_total: int,
    tool_calls_log: list[dict],
) -> ChatResult:
    """Letzter Versuch: ohne tools, mit verstärktem System-Hinweis."""
    forced_system = (
        system_prompt
        + "\n\nWICHTIG: Du hast die maximale Anzahl Werkzeug-Aufrufe erreicht. "
        + "Antworte jetzt nur noch mit einem normalen Text-Satz in Deiner Stimme."
    )
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens or settings.anthropic_max_tokens,
        system=forced_system,
        messages=working_messages,
    )
    tokens_total += (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0)
    text = _extract_text(resp.content)
    return ChatResult(
        text=text,
        mode=_detect_mode(text),
        tokens_used=tokens_total,
        tool_iterations=MAX_TOOL_ITERATIONS,
        tool_calls=tool_calls_log,
    )


def _extract_text(content_blocks) -> str:
    """Holt nur die Text-Blöcke aus einer Anthropic-Response."""
    return "".join(
        b.text for b in content_blocks if getattr(b, "type", None) == "text"
    ).strip()


def _serialize_assistant_content(content_blocks) -> list[dict]:
    """Konvertiert Anthropic-Response-Content-Blöcke in das dict-Format,
    das wir bei der nächsten Anfrage als assistant-message zurückschicken.

    Wir behalten text + tool_use Blöcke. Andere Block-Typen werden derzeit
    ignoriert (keine in Phase 4 erwartet).
    """
    out: list[dict] = []
    for b in content_blocks:
        btype = getattr(b, "type", None)
        if btype == "text":
            out.append({"type": "text", "text": b.text})
        elif btype == "tool_use":
            out.append({
                "type":  "tool_use",
                "id":    b.id,
                "name":  b.name,
                "input": b.input,
            })
        # Sonstige Block-Typen werden in Phase 4 nicht erwartet.
    return out
