def test_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Dynamic Multi-Agent System Running"}
