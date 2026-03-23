import pytest

from app.services.sensitive_ai_check import guardrail_input_as_text


def test_guardrail_input_as_text_string():
    assert guardrail_input_as_text("hello") == "hello"


def test_guardrail_input_as_text_empty():
    assert guardrail_input_as_text("") == ""
    assert guardrail_input_as_text(None) == ""


def test_guardrail_input_as_text_list_of_dicts():
    items = [
        {"content": "part a"},
        {"content": [{"text": "part b"}]},
    ]
    out = guardrail_input_as_text(items)
    assert "part a" in out
    assert "part b" in out
