"""Multi-Turn-Loop Tests — Anthropic-Mock, Tool-Dispatch-Roundtrip.

Strategie: anthropic_client._client_sync wird gemockt, sodass
client.messages.create() vom Test gesteuerte Responses zurückgibt.

Wir prüfen:
  - Loop endet bei stop_reason=end_turn
  - Tool-Use wird ausgeführt, DB-Row landet
  - Tool-Result fließt in nächste Iteration
  - Loop-Limit MAX_TOOL_ITERATIONS greift
  - Token-Aggregation über Iterationen
  - Gemischter Content (text + tool_use im selben Response)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shiksha_engine.models import MemoryEntry, Observation, Session
from shiksha_engine.services import anthropic_client


# ===================================================================
# Mock-Helpers
# ===================================================================

@dataclass
class FakeBlock:
    """Simuliert ein Anthropic-Content-Block."""
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class FakeResponse:
    stop_reason: str
    content: list[FakeBlock]
    usage: FakeUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = FakeUsage()


def make_text_response(text: str, tokens_in: int = 100, tokens_out: int = 50) -> FakeResponse:
    return FakeResponse(
        stop_reason="end_turn",
        content=[FakeBlock(type="text", text=text)],
        usage=FakeUsage(input_tokens=tokens_in, output_tokens=tokens_out),
    )


def make_tool_use_response(
    tool_name: str,
    tool_input: dict,
    tool_use_id: str = "toolu_test_1",
    preceding_text: str | None = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
) -> FakeResponse:
    blocks = []
    if preceding_text:
        blocks.append(FakeBlock(type="text", text=preceding_text))
    blocks.append(FakeBlock(
        type="tool_use",
        id=tool_use_id,
        name=tool_name,
        input=tool_input,
    ))
    return FakeResponse(
        stop_reason="tool_use",
        content=blocks,
        usage=FakeUsage(input_tokens=tokens_in, output_tokens=tokens_out),
    )


def fake_client_that_returns(*responses: FakeResponse) -> MagicMock:
    """Liefert einen MagicMock-Anthropic-Client, der die Responses in Reihe
    zurückgibt — pro client.messages.create() einer."""
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def ses(db, mira) -> Session:
    s = Session(
        id="ses_loop_test",
        operator_id=mira.id,
        org_id=mira.org_id,
        edition=mira.edition,
        persona="tagesausklang",
    )
    db.add(s)
    db.commit()
    return s


# ===================================================================
# Tests
# ===================================================================

def test_loop_terminates_on_end_turn(db, mira, ses):
    """Modell antwortet direkt mit Text — keine Tools."""
    fake = fake_client_that_returns(
        make_text_response("Ich höre.", tokens_in=80, tokens_out=20),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    assert result.text == "Ich höre."
    assert result.tool_iterations == 0
    assert result.tokens_used == 100  # 80 + 20
    assert fake.messages.create.call_count == 1


def test_loop_executes_tool_and_continues(db, mira, ses):
    """Modell ruft Tool auf, dann antwortet mit Text."""
    fake = fake_client_that_returns(
        make_tool_use_response(
            "log_observation",
            {"text": "Lukas wieder da."},
            tool_use_id="toolu_a",
        ),
        make_text_response("Schön, dass er zurück ist."),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "Lukas ist wieder da."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    db.flush()
    assert result.text == "Schön, dass er zurück ist."
    assert result.tool_iterations == 1
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "log_observation"
    assert fake.messages.create.call_count == 2

    # DB-Row da?
    obs = db.query(Observation).filter_by(session_id=ses.id).all()
    assert len(obs) == 1
    assert obs[0].text == "Lukas wieder da."


def test_loop_two_tools_then_text(db, mira, ses):
    """Modell ruft erst log_observation, dann add_memory, dann antwortet."""
    fake = fake_client_that_returns(
        make_tool_use_response("log_observation", {"text": "Faktum"}, tool_use_id="t1"),
        make_tool_use_response("add_memory", {"text": "Erinnerung"}, tool_use_id="t2"),
        make_text_response("Notiert."),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "..."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    db.flush()
    assert result.text == "Notiert."
    assert result.tool_iterations == 2
    assert len(result.tool_calls) == 2

    assert db.query(Observation).count() == 1
    mems = db.query(MemoryEntry).all()
    assert len(mems) == 1
    assert mems[0].status == "proposed"


def test_loop_hits_max_iterations_and_force_terminates(db, mira, ses):
    """Modell ruft endlos Tools — Loop schlägt nach 5 Iterationen ab und
    erzwingt einen letzten Text-Call."""
    tool_responses = [
        make_tool_use_response(
            "log_observation", {"text": f"x{i}"}, tool_use_id=f"t{i}"
        )
        for i in range(anthropic_client.MAX_TOOL_ITERATIONS)
    ]
    fake = fake_client_that_returns(
        *tool_responses,
        make_text_response("Für heute reicht's."),
    )

    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "..."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    assert result.text == "Für heute reicht's."
    assert result.tool_iterations == anthropic_client.MAX_TOOL_ITERATIONS
    # 5 Loop-Calls + 1 Force-Terminal = 6
    assert fake.messages.create.call_count == anthropic_client.MAX_TOOL_ITERATIONS + 1


def test_loop_aggregates_tokens_across_iterations(db, mira, ses):
    """Tokens werden über alle Iterations summiert."""
    fake = fake_client_that_returns(
        make_tool_use_response(
            "log_observation",
            {"text": "a"},
            tool_use_id="t1",
            tokens_in=100, tokens_out=20,
        ),
        make_text_response("ok", tokens_in=120, tokens_out=10),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "..."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    # Iter 1: 100+20=120; Iter 2: 120+10=130; total 250
    assert result.tokens_used == 250


def test_loop_with_preceding_text_in_tool_use(db, mira, ses):
    """Modell sendet 'Ich denke nach...' + tool_use → assistant-content
    bekommt beides, Loop weiter, final text."""
    fake = fake_client_that_returns(
        make_tool_use_response(
            "log_observation",
            {"text": "x"},
            preceding_text="Einen Moment.",
            tool_use_id="t1",
        ),
        make_text_response("Notiert."),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "..."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    # Der "Einen Moment." Text wird NICHT als finale Antwort genutzt —
    # das macht nur der letzte end_turn-Response.
    assert result.text == "Notiert."

    # Zweite Anfrage prüfen: messages müssen assistant-content mit beiden
    # Blöcken enthalten haben.
    second_call = fake.messages.create.call_args_list[1]
    messages = second_call.kwargs["messages"]
    assistant_msg = next(m for m in messages if m["role"] == "assistant")
    block_types = [b["type"] for b in assistant_msg["content"]]
    assert "text" in block_types
    assert "tool_use" in block_types


def test_loop_handles_tool_error_gracefully(db, mira, ses):
    """Modell ruft Tool mit ungültigen Args. Tool gibt is_error-Result
    zurück, Modell entscheidet sich um und antwortet mit Text."""
    fake = fake_client_that_returns(
        make_tool_use_response(
            "log_friction",
            {"text": "ok", "severity": "extreme_invalid"},  # severity invalid
            tool_use_id="t1",
        ),
        make_text_response("Ist gut."),
    )
    with patch.object(anthropic_client, "_client_sync", return_value=fake):
        result = anthropic_client.respond_block_with_tools(
            system_prompt="test",
            messages=[{"role": "user", "content": "..."}],
            operator=mira,
            shiksha_session=ses,
            db=db,
        )

    assert result.text == "Ist gut."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["is_error"] is True

    # Zweite Anfrage: tool_result mit is_error sollte enthalten sein
    second_call = fake.messages.create.call_args_list[1]
    messages = second_call.kwargs["messages"]
    user_with_result = messages[-1]
    assert user_with_result["role"] == "user"
    tool_results = user_with_result["content"]
    assert any(r.get("is_error") for r in tool_results)
