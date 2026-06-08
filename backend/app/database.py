"""Engine e sessão do SQLAlchemy.

A camada é agnóstica de dialeto: trocar SQLite por Turso/Postgres no deploy
é só mudar DATABASE_URL (o `connect_args` de SQLite é aplicado condicionalmente).
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# check_same_thread só faz sentido (e só é aceito) no SQLite.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency do FastAPI: abre e fecha a sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
