"""Autenticação leve com papéis (editor/visualizador) — sem dependências externas.

Usuários ficam num arquivo JSON (AUTH_USERS_FILE, default backend/auth_users.json),
seeded por `seed_auth.py` (sem auto-cadastro). Senhas com PBKDF2-SHA256 (stdlib).
Token de sessão assinado com HMAC-SHA256 (formato base64url(payload).hmac), sem JWT lib.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import Depends, Header, HTTPException, status

SECRET = os.getenv("AUTH_SECRET", "dev-secret-sprint-aban-change-me")
_DEFAULT_USERS = Path(__file__).resolve().parent.parent / "auth_users.json"


# ── Senhas (PBKDF2-SHA256) ────────────────────────────────────────────────────
def hash_password(pw: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── Tokens (HMAC) ─────────────────────────────────────────────────────────────
def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(username: str, role: str, ttl: int = 86_400) -> str:
    payload = {"u": username, "r": role, "exp": int(time.time()) + ttl}
    p = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    return f"{p}.{sig}"


def parse_token(token: str) -> dict | None:
    try:
        p, sig = token.split(".", 1)
        expected = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(p))
        if payload["exp"] < time.time():
            return None
        return {"username": payload["u"], "role": payload["r"]}
    except Exception:
        return None


# ── Store de usuários ─────────────────────────────────────────────────────────
def users_path() -> Path:
    return Path(os.getenv("AUTH_USERS_FILE", str(_DEFAULT_USERS)))


def load_users() -> dict:
    path = users_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def authenticate(username: str, password: str) -> dict | None:
    u = load_users().get(username)
    if not u or not verify_password(password, u["passwordHash"]):
        return None
    return {"username": username, "role": u["role"]}


# ── Dependencies do FastAPI ───────────────────────────────────────────────────
def current_user(authorization: str | None = Header(default=None)) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return parse_token(authorization[7:])


def require_editor(user: dict | None = Depends(current_user)) -> dict:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária")
    if user["role"] != "editor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requer papel de editor")
    return user
