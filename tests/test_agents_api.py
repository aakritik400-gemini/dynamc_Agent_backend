import uuid

import pytest


def _agent_body(name_suffix=""):
    return {
        "name": f"t-agent-{uuid.uuid4().hex[:8]}{name_suffix}",
        "prompt": "You are a test agent.",
        "type": "normal",
        "data_file": None,
    }


def test_create_list_get_agent(client):
    body = _agent_body()
    r = client.post("/agents", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("message") == "Agent created"
    aid = data["id"]

    r = client.get("/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) == 1
    assert agents[0]["id"] == aid
    assert agents[0]["name"] == body["name"]

    r = client.get(f"/agents/{aid}")
    assert r.status_code == 200
    payload = r.json()
    assert "error" not in payload
    assert payload["agent"]["name"] == body["name"]
    assert payload["child_agent_ids"] == []


def test_edit_agent(client):
    body = _agent_body()
    aid = client.post("/agents", json=body).json()["id"]

    new_name = f"renamed-{uuid.uuid4().hex[:8]}"
    r = client.put(
        f"/agents/{aid}",
        json={**body, "name": new_name, "prompt": "updated prompt"},
    )
    assert r.status_code == 200
    assert r.json() == {"message": "Agent updated", "id": aid}

    got = client.get(f"/agents/{aid}").json()["agent"]
    assert got["name"] == new_name
    assert got["prompt"] == "updated prompt"


def test_get_edit_agent_not_found(client):
    r = client.get("/agents/999999")
    assert r.status_code == 200
    assert r.json().get("error") == "Agent not found"

    r = client.put("/agents/999999", json=_agent_body())
    assert r.status_code == 200
    assert r.json().get("error") == "Agent not found"


def test_duplicate_agent_name(client):
    body = _agent_body()
    client.post("/agents", json=body)
    r = client.post("/agents", json=body)
    assert r.status_code == 200
    assert "error" in r.json()


def test_create_agent_validation_error(client):
    r = client.post("/agents", json={"name": "only-name"})
    assert r.status_code == 422
    err = r.json()
    assert err.get("error") == "Invalid request body"


def test_handoffs_add_dedupe_and_unknown(client):
    a = client.post("/agents", json=_agent_body()).json()["id"]
    b = client.post("/agents", json=_agent_body()).json()["id"]

    r = client.post(f"/agents/{a}/handoffs", json={"child_agent_ids": [b, b]})
    assert r.status_code == 200
    assert r.json().get("message") == "Handoffs added"

    kids = client.get(f"/agents/{a}").json()["child_agent_ids"]
    assert kids == [b]

    r = client.post(f"/agents/{a}/handoffs", json={"child_agent_ids": [999999]})
    assert r.status_code == 200
    assert "Unknown agent id" in r.json().get("error", "")


def test_handoffs_self_not_allowed(client):
    a = client.post("/agents", json=_agent_body()).json()["id"]
    r = client.post(f"/agents/{a}/handoffs", json={"child_agent_ids": [a]})
    assert r.status_code == 200
    assert "same agent" in r.json().get("error", "").lower()


def test_handoffs_parent_not_found(client):
    r = client.post("/agents/999999/handoffs", json={"child_agent_ids": [1]})
    assert r.status_code == 200
    assert r.json().get("error") == "Agent not found"


def test_set_handoffs_replace(client):
    a = client.post("/agents", json=_agent_body()).json()["id"]
    b = client.post("/agents", json=_agent_body()).json()["id"]
    c = client.post("/agents", json=_agent_body()).json()["id"]

    client.post(f"/agents/{a}/handoffs", json={"child_agent_ids": [b]})
    r = client.put(f"/agents/{a}/handoffs", json={"child_agent_ids": [c]})
    assert r.status_code == 200
    assert r.json()["child_agent_ids"] == [c]
    assert client.get(f"/agents/{a}").json()["child_agent_ids"] == [c]


def test_clear_database(client):
    client.post("/agents", json=_agent_body())
    r = client.delete("/agents")
    assert r.status_code == 200
    assert r.json().get("message")

    listed = client.get("/agents").json().get("agents", [])
    assert listed == []
