"""App FastAPI do SPRINT ABAN — backend de persistência."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401 — registra os modelos no metadata
from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import projects, engines, auth, changelog, base, logic

# Dev: cria as tabelas na subida. Em produção, migrar para Alembic.
Base.metadata.create_all(bind=engine)


def _migrate_line_override() -> None:
    """Micro-migração idempotente: adiciona colunas novas em line_override.

    `create_all` cria tabelas inexistentes, mas NÃO altera tabelas já criadas.
    Bancos antigos têm line_override só com (pkg_id, line_index, text, author,
    updated_at); aqui acrescentamos duration/rec/pad/ow_* via ADD COLUMN (SQLite
    e Postgres suportam). Em DB novo as colunas já vêm do create_all e nada roda.
    """
    insp = inspect(engine)
    if "line_override" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("line_override")}
    new_cols = {
        "duration": "FLOAT", "rec": "TEXT", "pad": "TEXT",
        "ow_fase": "VARCHAR(100)", "ow_atividade": "VARCHAR(150)",
        "ow_operacao": "VARCHAR(200)", "ow_etapa": "VARCHAR(200)",
    }
    missing = {name: typ for name, typ in new_cols.items() if name not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for name, typ in missing.items():
            conn.execute(text(f"ALTER TABLE line_override ADD COLUMN {name} {typ}"))


_migrate_line_override()

app = FastAPI(title="SPRINT ABAN API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Dev: aceita qualquer porta de localhost (Vite pode subir em 5173, 5174, ...).
    # Em produção, restrinja via CORS_ORIGINS (e remova/ajuste o regex).
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(engines.router)
app.include_router(auth.router)
app.include_router(changelog.router)
app.include_router(base.router)
app.include_router(logic.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "service": "sprint-aban-api"}
