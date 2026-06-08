"""Testes da edição da base de linhas (overrides, validação de tokens, log, papéis)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.base_data import package_lines
from app.database import Base, get_db
from app.models import ChangeLogEntry
from app.routers.auth import router as auth_router
from app.routers.base import router as base_router
from app.routers.changelog import router as changelog_router

# Um pacote/linha real da base bundled.
_PL = package_lines()
PKG = next(k for k, v in _PL.items() if v and v[0].get("text"))
IDX = 0
ORIG = _PL[PKG][0]["text"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    users = {"ed": {"passwordHash": hash_password("p"), "role": "editor"},
             "vw": {"passwordHash": hash_password("p"), "role": "viewer"}}
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
    app.include_router(base_router)
    app.include_router(changelog_router)
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c._session = TestSession  # type: ignore[attr-defined]
    return c


def _token(client, user):
    return client.post("/api/auth/login", json={"username": user, "password": "p"}).json()["token"]


def _hdr(client, user):
    return {"Authorization": f"Bearer {_token(client, user)}"}


def test_get_merged_base(client):
    r = client.get("/api/base/package-lines")
    assert r.status_code == 200
    assert PKG in r.json()


def test_get_fields(client):
    r = client.get("/api/base/fields")
    assert r.status_code == 200
    fields = r.json()
    assert "prof" in fields  # PLAN_KEY


def test_editor_edits_line_and_logs(client):
    new_text = ORIG + " {{prof=XXX}}"  # token valido (prof e' PLAN_KEY)
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": new_text}, headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["text"] == new_text
    # base mesclada reflete a edição
    assert client.get("/api/base/package-lines").json()[PKG][IDX]["text"] == new_text
    # registrou no changelog com autor
    log = client.get("/api/changelog").json()
    assert log and log[0]["pacote"] == PKG and log[0]["author"] == "ed" and log[0]["linha"] == IDX + 1


def test_reject_invalid_token(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}",
                   json={"text": ORIG + " {{zzznaoexiste=XXX}}"}, headers=_hdr(client, "ed"))
    assert r.status_code == 400
    assert "zzznaoexiste" in r.json()["detail"]


def test_viewer_cannot_edit(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " x"}, headers=_hdr(client, "vw"))
    assert r.status_code == 403


def test_anonymous_cannot_edit(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " x"})
    assert r.status_code == 401


def test_reset_reverts(client):
    client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " {{prof=XXX}}"}, headers=_hdr(client, "ed"))
    r = client.delete(f"/api/base/package-lines/{PKG}/{IDX}", headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["reverted"] is True
    assert client.get("/api/base/package-lines").json()[PKG][IDX]["text"] == ORIG


def test_unknown_package_404(client):
    r = client.put("/api/base/package-lines/NAO_EXISTE/0", json={"text": "x"}, headers=_hdr(client, "ed"))
    assert r.status_code == 404
