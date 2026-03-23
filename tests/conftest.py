"""
Test setup: dummy API key for config import, isolated SQLite file per session.
"""
import os
import tempfile

import pytest

# Config import requires this before any app package loads config
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-not-used-in-unit-tests")
os.environ.setdefault("DISABLE_AI_SENSITIVE_CHECK", "1")

import app.db.database as _database_module

_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
_database_module.DB_PATH = _TEST_DB_PATH

from fastapi.testclient import TestClient
from app.main import app  # noqa: E402 — import after DB_PATH patch; init_db() runs in main


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def empty_agents_table():
    from app.db.database import get_connection

    conn = get_connection()
    try:
        conn.execute("DELETE FROM agent_handoffs")
        conn.execute("DELETE FROM agents")
        conn.commit()
    finally:
        conn.close()
    yield


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass
