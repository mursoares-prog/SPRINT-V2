"""Testes de autenticação e papéis (login, token, gating admin)."""
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app.auth import hash_password, require_admin
from app.routers.auth import router as auth_router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    users = {
        "ed": {"passwordHash": hash_password("ed-pass"), "role": "admin"},
        "vw": {"passwordHash": hash_password("vw-pass"), "role": "projetista"},
    }
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps(users), encoding="utf-8")
    monkeypatch.setenv("AUTH_USERS_FILE", str(users_file))

    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/api/protected")
    def protected(user: dict = Depends(require_admin)):
        return {"hello": user["username"]}

    return TestClient(app)


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "ed", "password": "ed-pass"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin" and body["username"] == "ed" and body["token"]


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "ed", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_me_with_token(client):
    token = client.post("/api/auth/login", json={"username": "vw", "password": "vw-pass"}).json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["role"] == "projetista"


def test_me_without_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_admin_gate_allows_admin(client):
    token = client.post("/api/auth/login", json={"username": "ed", "password": "ed-pass"}).json()["token"]
    r = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["hello"] == "ed"


def test_admin_gate_blocks_projetista(client):
    token = client.post("/api/auth/login", json={"username": "vw", "password": "vw-pass"}).json()["token"]
    r = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_gate_blocks_anonymous(client):
    assert client.get("/api/protected").status_code == 401


def test_token_tamper_rejected(client):
    token = client.post("/api/auth/login", json={"username": "ed", "password": "ed-pass"}).json()["token"]
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert auth_mod.parse_token(tampered) is None
