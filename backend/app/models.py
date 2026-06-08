"""Modelos do banco (SQLAlchemy)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """Um projeto de poço salvo.

    O documento completo (ProjectFile do front) fica em `data` como JSON.
    well_name/scope_id/saved_at são copiados para colunas próprias só para
    listagem/ordenação eficientes — a fonte da verdade é `data`.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    well_name: Mapped[str] = mapped_column(String(200), index=True)
    scope_id: Mapped[str] = mapped_column(String(50), index=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    # Documento completo do projeto (inputs, schedule, projectData, fineTuningItems...).
    data: Mapped[dict] = mapped_column(JSON, default=dict)
