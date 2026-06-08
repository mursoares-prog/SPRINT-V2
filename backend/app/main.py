"""App FastAPI do SPRINT ABAN — backend de persistência."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — registra os modelos no metadata
from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import projects, engines, auth

# Dev: cria as tabelas na subida. Em produção, migrar para Alembic.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SPRINT ABAN API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(engines.router)
app.include_router(auth.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "service": "sprint-aban-api"}
