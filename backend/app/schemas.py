"""Schemas Pydantic de entrada/saída da API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProjectIn(BaseModel):
    """Payload de criação/atualização: o ProjectFile inteiro vindo do front.

    Campos extras são aceitos e preservados (extra='allow'), de modo que o
    backend não precisa conhecer cada chave de inputs/projectData.
    """

    model_config = ConfigDict(extra="allow")

    wellName: str = Field(min_length=1)
    scopeId: str = Field(min_length=1)
    savedAt: str | None = None
    version: str | None = None


class ProjectSummary(BaseModel):
    """Item da listagem (sem o documento completo)."""

    id: str
    wellName: str
    scopeId: str
    savedAt: datetime
    updatedAt: datetime

    @field_serializer('savedAt', 'updatedAt')
    def _serialize_dt(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')


class ProjectOut(BaseModel):
    """Projeto completo: o documento salvo + o id do servidor."""

    id: str
    data: dict[str, Any]
