from __future__ import annotations

from agents.guardrail import GuardrailFunctionOutput, input_guardrail

from app.services.security import SENSITIVE_REFUSAL_MESSAGE, user_requests_sensitive_disclosure
from app.services.sensitive_ai_check import (
    ai_detects_sensitive_disclosure_request,
    guardrail_input_as_text,
)


@input_guardrail(name="no_credential_disclosure", run_in_parallel=False)
async def no_credential_disclosure_guardrail(context, agent, input):
    """
    Block credential/secret exfiltration: fast regex first, then LLM for paraphrases
    and indirect requests that keywords miss.
    """
    text = guardrail_input_as_text(input)

    if user_requests_sensitive_disclosure(text):
        return GuardrailFunctionOutput(
            output_info={"error": SENSITIVE_REFUSAL_MESSAGE},
            tripwire_triggered=True,
        )

    if await ai_detects_sensitive_disclosure_request(text):
        return GuardrailFunctionOutput(
            output_info={"error": SENSITIVE_REFUSAL_MESSAGE},
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info={"ok": True},
        tripwire_triggered=False,
    )
