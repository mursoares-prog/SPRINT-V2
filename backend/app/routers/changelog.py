"""Endpoints do log de alterações (changeLog server-side)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import ChangeLogEntry

router = APIRouter(prefix="/api/changelog", tags=["changelog"])


class ChangeLogIn(BaseModel):
    pacote: str
    linha: int | None = None
    tipo: str
    resumo: str
    antes: str | None = None
    depois: str | None = None


class ChangeLogOut(BaseModel):
    id: int
    data: str
    pacote: str
    linha: int | None
    tipo: str
    resumo: str
    antes: str | None
    depois: str | None
    author: str | None


def _out(e: ChangeLogEntry) -> ChangeLogOut:
    return ChangeLogOut(
        id=e.id, data=e.data, pacote=e.pacote, linha=e.linha, tipo=e.tipo,
        resumo=e.resumo, antes=e.antes, depois=e.depois, author=e.author,
    )


@router.get("", response_model=list[ChangeLogOut])
def list_changelog(db: Session = Depends(get_db)):
    rows = db.execute(select(ChangeLogEntry).order_by(ChangeLogEntry.id.desc())).scalars().all()
    return [_out(e) for e in rows]


@router.post("", response_model=ChangeLogOut, status_code=status.HTTP_201_CREATED)
def add_changelog(payload: ChangeLogIn, db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Acrescenta uma entrada (append-only). Requer papel admin; grava o autor do token."""
    next_id = (db.execute(select(func.max(ChangeLogEntry.id))).scalar() or 0) + 1
    entry = ChangeLogEntry(
        id=next_id,
        data=date.today().isoformat(),
        pacote=payload.pacote,
        linha=payload.linha,
        tipo=payload.tipo,
        resumo=payload.resumo,
        antes=payload.antes,
        depois=payload.depois,
        author=user["username"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _out(entry)
