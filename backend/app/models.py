"""Modelos do banco (SQLAlchemy)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
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


class ChangeLogEntry(Base):
    """Registro auditável de alterações na base das linhas dos pacotes.

    Espelha o LogEntry do front (changeLog.json), com `author` (quem editou,
    do token) e `created_at`. Vira a fonte da verdade do log (a aba Log do Admin).
    """

    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[str] = mapped_column(String(10))   # ISO yyyy-mm-dd
    pacote: Mapped[str] = mapped_column(String(50), index=True)
    linha: Mapped[int | None] = mapped_column(Integer, nullable=True)  # posição 1-based; null se N/A
    tipo: Mapped[str] = mapped_column(String(30))
    resumo: Mapped[str] = mapped_column(Text)
    antes: Mapped[str | None] = mapped_column(Text, nullable=True)
    depois: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LineOverride(Base):
    """Edição (override) do texto de uma linha de pacote, sobre a base bundled.

    Chave (pkg_id, line_index 0-based). A base servida = packageLines + overrides
    aplicados ao campo `text`. Permite editar sem recompilar e reverter linha a linha.
    """

    __tablename__ = "line_override"

    pkg_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    line_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
