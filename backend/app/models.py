"""Modelos do banco (SQLAlchemy)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
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
    linha: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # posição 1-based; null se N/A
    tipo: Mapped[str] = mapped_column(String(30))
    resumo: Mapped[str] = mapped_column(Text)
    antes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    depois: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LineOverride(Base):
    """Edição (override) de uma linha de pacote, sobre a base bundled.

    Chave (pkg_id, line_index 0-based). A base servida = packageLines + overrides
    aplicados. `text` (texto/placeholders), `duration` (horas) e os 4 campos da
    ontologia OpenWells pertencem a package_lines e são mesclados pelo backend.
    `rec`/`pad` (recomendações/padrões) não existem na base do backend — são
    devolvidos via /overrides e mesclados no front sobre packageLineDetails.json.
    Campos None = "não sobrescreve este campo". Permite editar sem recompilar e
    reverter a linha inteira.
    """

    __tablename__ = "line_override"

    pkg_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    line_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pad: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ow_fase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ow_atividade: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    ow_operacao: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    ow_etapa: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PackageLinesOverride(Base):
    """Override do conjunto COMPLETO de linhas de um pacote (estrutural).

    Chave `pkg_id`. `lines` é o array inteiro de linhas — cada linha autocontida
    com os 12 campos de package_lines (text, duration, bop, compensando,
    isContingency, isParallel, owFase/owAtividade/owOperacao/owEtapa, genOperacao,
    genOperacaoDual) MAIS `rec`/`pad` (detalhes). Permite adicionar/excluir/
    reordenar linhas (o que o LineOverride por índice não cobre). O front monta o
    array (tem os bundles de linhas e detalhes); o backend só o armazena.

    Precedência no merge: PackageLinesOverride > LineOverride (legado) > bundle.
    Também é a fonte das linhas de pacotes CUSTOMIZADOS (que não existem no bundle).
    """

    __tablename__ = "package_lines_override"

    pkg_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PackageMeta(Base):
    """Metadados de um pacote CUSTOMIZADO (criado/duplicado no Admin).

    Só existe para pacotes fora do bundle (os do bundle têm nome travado e não
    aparecem aqui). As linhas do pacote ficam em PackageLinesOverride. Apagar o
    customizado = remover esta linha + o PackageLinesOverride correspondente.
    """

    __tablename__ = "package_meta"

    pkg_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="")
    technology: Mapped[str] = mapped_column(String(30), default="none")
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LogicScopeOverride(Base):
    """Override (ou novo escopo custom) da árvore de decisão da engine de sequenciamento.

    is_custom=False → override de escopo bundle (preserva behaviour; admin pode restaurar).
    is_custom=True  → escopo novo definido inteiramente pelo admin.
    sections armazena LSec[] serializado (mesmo formato do logicSecs.ts).
    """

    __tablename__ = "logic_scope_overrides"

    scope_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    fase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    op_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LogicScopeVersion(Base):
    """Snapshot versionado das seções de um escopo, gravado a cada save.

    Viabiliza retorno a versões anteriores no editor de lógica. Cada save do escopo
    (PUT/POST/restore) cria uma linha com o snapshot completo de `sections` (LSec[]).
    Retenção: mantém as 50 versões mais recentes por scope_id (poda no save).
    `note` guarda um resumo curto (ex.: "Save", "Restauração da versão #12").
    """

    __tablename__ = "logic_scope_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope_id: Mapped[str] = mapped_column(String(50), index=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
