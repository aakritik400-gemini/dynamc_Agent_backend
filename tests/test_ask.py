import pytest

from agents.exceptions import InputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput, InputGuardrail, InputGuardrailResult


def _tripwire_exc(message: str):
    def _dummy_guardrail_fn(context, agent, input):
        return GuardrailFunctionOutput(None, False)

    gr = InputGuardrail(guardrail_function=_dummy_guardrail_fn, name="test-guardrail")
    out = GuardrailFunctionOutput(output_info={"error": message}, tripwire_triggered=True)
    result = InputGuardrailResult(guardrail=gr, output=out)
    return InputGuardrailTripwireTriggered(result)


def test_ask_agent_not_found(client, monkeypatch):
    import app.routes.ask as ask_mod

    monkeypatch.setattr(ask_mod, "build_agent", lambda agent_id, request_id=None: None)

    r = client.post("/ask/999999", json={"question": "Hello?"})
    assert r.status_code == 200
    assert r.json().get("error") == "Agent not found"


def test_ask_success_mocked(client, monkeypatch):
    import app.routes.ask as ask_mod

    class FakeAgent:
        name = "Responder"
        agent_id = 7

    class FakeResult:
        last_agent = FakeAgent()
        final_output = "Here is the answer."

    async def fake_run(*args, **kwargs):
        return FakeResult()

    monkeypatch.setattr(ask_mod, "build_agent", lambda agent_id, request_id=None: object())
    monkeypatch.setattr(ask_mod.Runner, "run", fake_run)

    r = client.post("/ask/1", json={"question": "What is 2+2?"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("response") == "Here is the answer."
    assert body.get("agent_name") == "Responder"
    assert body.get("agent_id") == 7
    assert "request_id" in body


def test_ask_guardrail_tripwire(client, monkeypatch):
    import app.routes.ask as ask_mod

    msg = "Blocked by policy"

    async def fake_run(*args, **kwargs):
        raise _tripwire_exc(msg)

    monkeypatch.setattr(ask_mod, "build_agent", lambda agent_id, request_id=None: object())
    monkeypatch.setattr(ask_mod.Runner, "run", fake_run)

    r = client.post("/ask/1", json={"question": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("error") == msg
    assert body.get("response") == msg
    assert body.get("agent_name") == "Guardrail"


def test_ask_internal_error(client, monkeypatch):
    import app.routes.ask as ask_mod

    async def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(ask_mod, "build_agent", lambda agent_id, request_id=None: object())
    monkeypatch.setattr(ask_mod.Runner, "run", boom)

    r = client.post("/ask/1", json={"question": "x"})
    assert r.status_code == 200
    assert r.json().get("error") == "Internal server error"
