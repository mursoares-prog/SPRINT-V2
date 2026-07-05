"""Testes do versionamento de escopos de lógica (snapshots + restauração)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import Base, get_db
from app.routers.auth import router as auth_router
from app.routers.logic import router as logic_router, MAX_VERSIONS_PER_SCOPE


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    users = {"ed": {"passwordHash": hash_password("p"), "role": "admin"},
             "vw": {"passwordHash": hash_password("p"), "role": "projetista"}}
    uf = tmp_path / "users.json"
    uf.write_text(json.dumps(users), encoding="utf-8")
    monkeypatch.setenv("AUTH_USERS_FILE", str(uf))

    def override_get_db():
        d = TestSession()
        try:
            yield d
        finally:
            d.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(logic_router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _token(client, user="ed"):
    return client.post("/api/auth/login", json={"username": user, "password": "p"}).json()["token"]


def _auth(client, user="ed"):
    return {"Authorization": f"Bearer {_token(client, user)}"}


def _sections(n):
    return [{"id": f"s{i}", "label": f"Seção {i}", "phase": "Fase 0", "color": "gray", "decisions": []}
            for i in range(n)]


def test_save_creates_version(client):
    h = _auth(client)
    client.put("/api/logic/scopes/FSU_TT_FT", headers=h, json={"sections": _sections(1)})
    client.put("/api/logic/scopes/FSU_TT_FT", headers=h, json={"sections": _sections(2)})

    r = client.get("/api/logic/scopes/FSU_TT_FT/versions")
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) == 2
    # Mais recente primeiro; o snapshot guarda o nº de seções daquele save.
    assert versions[0]["sectionCount"] == 2
    assert versions[1]["sectionCount"] == 1
    assert versions[0]["author"] == "ed"


def test_get_version_returns_sections(client):
    h = _auth(client)
    client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(3)})
    vid = client.get("/api/logic/scopes/S1/versions").json()[0]["id"]

    r = client.get(f"/api/logic/scopes/S1/versions/{vid}")
    assert r.status_code == 200
    assert len(r.json()["sections"]) == 3


def test_restore_is_non_destructive(client):
    h = _auth(client)
    client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(1)})  # v1
    client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(5)})  # v2 (atual)

    v1 = client.get("/api/logic/scopes/S1/versions").json()[-1]["id"]
    r = client.post(f"/api/logic/scopes/S1/versions/{v1}/restore", headers=h)
    assert r.status_code == 200
    assert r.json()["sectionCount"] == 1

    # O override atual voltou ao conteúdo de v1…
    assert len(client.get("/api/logic/scopes/S1").json()["sections"]) == 1
    # …e uma nova versão (restauração) foi adicionada, preservando o histórico (v1, v2, restore).
    versions = client.get("/api/logic/scopes/S1/versions").json()
    assert len(versions) == 3
    assert versions[0]["sectionCount"] == 1
    assert "Restaura" in (versions[0]["note"] or "")


def test_retention_prunes_old_versions(client):
    h = _auth(client)
    for i in range(MAX_VERSIONS_PER_SCOPE + 5):
        client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(i % 3 + 1)})
    versions = client.get("/api/logic/scopes/S1/versions").json()
    assert len(versions) == MAX_VERSIONS_PER_SCOPE


def test_versions_isolated_per_scope(client):
    h = _auth(client)
    client.put("/api/logic/scopes/A", headers=h, json={"sections": _sections(1)})
    client.put("/api/logic/scopes/B", headers=h, json={"sections": _sections(1)})
    assert len(client.get("/api/logic/scopes/A/versions").json()) == 1
    assert len(client.get("/api/logic/scopes/B/versions").json()) == 1


def test_restore_requires_admin(client):
    h = _auth(client)
    client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(1)})
    vid = client.get("/api/logic/scopes/S1/versions").json()[0]["id"]
    r = client.post(f"/api/logic/scopes/S1/versions/{vid}/restore", headers=_auth(client, "vw"))
    assert r.status_code == 403


def test_get_missing_version_404(client):
    h = _auth(client)
    client.put("/api/logic/scopes/S1", headers=h, json={"sections": _sections(1)})
    assert client.get("/api/logic/scopes/S1/versions/nope").status_code == 404
