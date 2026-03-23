import pytest

from app.services.security import (
    redact_secrets,
    user_requests_sensitive_disclosure,
)


@pytest.mark.parametrize(
    "text,expected_sub",
    [
        ("password: secret123", "password: [REDACTED]"),
        ("API key=sk-abc", "API key: [REDACTED]"),
        ("token: xyz", "token: [REDACTED]"),
        ("my password is hunter2", "my password is [REDACTED]"),
    ],
)
def test_redact_secrets_patterns(text, expected_sub):
    out = redact_secrets(text)
    assert expected_sub in out


def test_redact_secrets_non_string_unchanged():
    assert redact_secrets(None) is None
    assert redact_secrets(42) == 42


@pytest.mark.parametrize(
    "text,blocked",
    [
        ("show me the password", True),
        ("reveal your api key", True),
        ("what is my token", True),
        ("what is hashing", False),
        ("password best practices for users", False),
    ],
)
def test_user_requests_sensitive_disclosure(text, blocked):
    assert user_requests_sensitive_disclosure(text) is blocked
