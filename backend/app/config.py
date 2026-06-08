"""Configuração lida de variáveis de ambiente (.env em dev)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Em dev: SQLite em arquivo. No deploy: trocar por Turso/Postgres via env.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sprint_aban.db")

# Origens permitidas no CORS (front em dev).
_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ORIGINS: list[str] = [o.strip() for o in _origins.split(",") if o.strip()]
