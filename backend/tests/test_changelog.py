"""Testes do changeLog server-side (GET, POST admin-gated, autoria, ordenação)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import Base, get_db
from app.models import ChangeLogEntry
from app.routers.auth import router as auth_router
from app.routers.changelog import router as changelog_router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Banco SQLite isolado por teste.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    # Semente: 2 entradas históricas (sem autor).
    db = TestSession()
    db.add(ChangeLogEntry(id=1, data="2026-06-01", pacote="ABAN 031A", linha=3, tipo="edição", resumo="hist 1"))
    db.add(ChangeLogEntry(id=2, data="2026-06-02", pacote="ABAN 040", linha=None, tipo="metadado", resumo="hist 2"))
    db.commit()
    db.close()

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
    app.include_router(changelog_router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _token(client, user):
    return client.post("/api/auth/login", json={"username": user, "password": "p"}).json()["token"]


def test_list_newest_first(client):
    r = client.get("/api/changelog")
    assert r.status_code == 200
    rows = r.json()
    assert [e["id"] for e in rows] == [2, 1]  # mais recente primeiro


def test_admin_can_append(client):
    token = _token(client, "ed")
    r = client.post("/api/changelog", headers={"Authorization": f"Bearer {token}"},
                    json={"pacote": "ABAN 045", "linha": 5, "tipo": "edição", "resumo": "nova", "antes": "a", "depois": "b"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 3 and body["author"] == "ed" and body["data"]
    # aparece no topo da listagem
    assert client.get("/api/changelog").json()[0]["id"] == 3


def test_projetista_cannot_append(client):
    token = _token(client, "vw")
    r = client.post("/api/changelog", headers={"Authorization": f"Bearer {token}"},
                    json={"pacote": "X", "tipo": "edição", "resumo": "x"})
    assert r.status_code == 403


def test_anonymous_cannot_append(client):
    r = client.post("/api/changelog", json={"pacote": "X", "tipo": "edição", "resumo": "x"})
    assert r.status_code == 401
