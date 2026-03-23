import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routes.upload import upload_file


def test_upload_valid_txt(client):
    r = client.post(
        "/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello data"), "text/plain")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "request_id" in data
    assert data["file_size"] == 10
    assert data["file_path"].endswith("notes.txt")


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("data.csv", "text/csv"),
        ("payload.json", "application/json"),
    ],
)
def test_upload_allowed_extensions(client, filename, content_type):
    r = client.post(
        "/upload",
        files={"file": (filename, io.BytesIO(b"x"), content_type)},
    )
    assert r.status_code == 200


def test_upload_rejects_bad_extension(client):
    r = client.post(
        "/upload",
        files={"file": ("hack.exe", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_empty_filename_on_upload_file():
    uf = MagicMock()
    uf.filename = ""
    uf.content_type = "text/plain"
    uf.read = AsyncMock(return_value=b"")
    with pytest.raises(HTTPException) as exc_info:
        await upload_file(uf)
    assert exc_info.value.status_code == 400


def test_ask_missing_question_field_returns_422(client):
    """Covers validation path (same JSON-safe handling as multipart 422)."""
    r = client.post("/ask/1", json={})
    assert r.status_code == 422
    body = r.json()
    assert body.get("error") == "Invalid request body"
    assert isinstance(body.get("details"), list)
