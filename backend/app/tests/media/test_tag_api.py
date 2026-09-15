from app.models import Tag
from app.tests.conftest import auth_headers, login, setup_admin


def _seed_tag(db, name: str) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _admin_headers(client, setup_paths) -> dict:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def test_get_tags_empty(client, setup_paths):
    headers = _admin_headers(client, setup_paths)
    response = client.get("/tags/", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_tags_three_seeded(client, db, setup_paths):
    rows = [_seed_tag(db, n) for n in ["science", "math", "history"]]
    headers = _admin_headers(client, setup_paths)
    response = client.get("/tags/", headers=headers)
    assert response.status_code == 200
    got = {(t["id"], t["name"]) for t in response.json()}
    assert got == {(r.id, r.name) for r in rows}


def test_get_tags_unauthenticated_401(client):
    response = client.get("/tags/")
    assert response.status_code == 401
