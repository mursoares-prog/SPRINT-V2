"""Engine de sequenciamento configurável — overrides de escopos e novos escopos custom."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import ChangeLogEntry, LogicScopeOverride

BUNDLE_SCOPE_IDS = {
    'FSU_TT_FT', 'FSU_TT_BDC', 'FSU_Conv_BOP', 'FSU_Conv_RCMA',
    'FSU_Sup_COP', 'FSU_Sup_PWC', 'FS1_Mec',
    'FS2_Conv_BOP', 'FS2_Conv_RCMA', 'FS2_Sup_COP', 'FS2_Sup_PWC',
}

router = APIRouter(prefix="/api/logic", tags=["logic"])


def _log(db: Session, scope_id: str, tipo: str, resumo: str, author: str) -> None:
    next_id = (db.execute(select(func.max(ChangeLogEntry.id))).scalar() or 0) + 1
    db.add(ChangeLogEntry(
        id=next_id, data=date.today().isoformat(), pacote=scope_id,
        linha=None, tipo=tipo, resumo=resumo, antes="", depois="", author=author,
    ))


class ScopeSectionsPayload(BaseModel):
    sections: list[dict]


class ScopeCreatePayload(BaseModel):
    scopeId: str
    label: str
    sections: list[dict] = []


@router.get("/scopes")
def list_scopes(db: Session = Depends(get_db)):
    """Lista todos os overrides de escopo e escopos custom."""
    rows = db.execute(select(LogicScopeOverride)).scalars().all()
    return [
        {
            "scopeId": r.scope_id,
            "isCustom": r.is_custom,
            "label": r.label,
            "sectionCount": len(r.sections),
            "author": r.author,
            "updatedAt": r.updated_at,
        }
        for r in rows
    ]


@router.get("/scopes/{scope_id}")
def get_scope(scope_id: str, db: Session = Depends(get_db)):
    """Retorna as seções (LSec[]) de um escopo override/custom."""
    row = db.get(LogicScopeOverride, scope_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Scope '{scope_id}' não tem override")
    return {"scopeId": row.scope_id, "isCustom": row.is_custom, "label": row.label, "sections": row.sections}


@router.put("/scopes/{scope_id}")
def save_scope(scope_id: str, payload: ScopeSectionsPayload,
               db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Salva LSec[] como override de um escopo (bundle ou custom existente)."""
    if not scope_id.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scopeId inválido")
    row = db.get(LogicScopeOverride, scope_id)
    is_new = row is None
    if is_new:
        is_custom = scope_id not in BUNDLE_SCOPE_IDS
        row = LogicScopeOverride(
            scope_id=scope_id, is_custom=is_custom, sections=payload.sections,
            author=user["username"],
        )
        db.add(row)
        tipo = "inclusão" if is_custom else "edição"
        resumo = f"Criação do escopo {'custom' if is_custom else 'override'} {scope_id}"
    else:
        row.sections = payload.sections
        row.author = user["username"]
        tipo = "edição"
        resumo = f"Atualização das seções do escopo {scope_id} ({len(payload.sections)} seção(ões))"
    _log(db, scope_id, tipo, resumo, user["username"])
    db.commit()
    return {"scopeId": scope_id, "isCustom": row.is_custom, "sectionCount": len(payload.sections)}


@router.post("/scopes")
def create_scope(payload: ScopeCreatePayload,
                 db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Cria um novo escopo customizado."""
    scope_id = payload.scopeId.strip()
    if not scope_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scopeId obrigatório")
    if scope_id in BUNDLE_SCOPE_IDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Use PUT /scopes/{id} para sobrescrever um escopo bundle")
    if db.get(LogicScopeOverride, scope_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Escopo '{scope_id}' já existe")
    if not payload.label.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "label obrigatório")
    row = LogicScopeOverride(
        scope_id=scope_id, is_custom=True, label=payload.label.strip(),
        sections=payload.sections, author=user["username"],
    )
    db.add(row)
    _log(db, scope_id, "inclusão", f"Criação do escopo custom '{scope_id}' — {payload.label}", user["username"])
    db.commit()
    return {"scopeId": scope_id, "isCustom": True, "label": row.label, "sectionCount": len(payload.sections)}


@router.delete("/scopes/{scope_id}")
def delete_scope(scope_id: str, db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Remove um escopo custom ou restaura bundle (remove override)."""
    row = db.get(LogicScopeOverride, scope_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Scope '{scope_id}' não tem override")
    tipo = "remoção" if row.is_custom else "reestruturação"
    resumo = (f"Remoção do escopo custom '{scope_id}'" if row.is_custom
              else f"Restauração do escopo bundle '{scope_id}' ao original")
    db.delete(row)
    _log(db, scope_id, tipo, resumo, user["username"])
    db.commit()
    return {"scopeId": scope_id, "deleted": True, "wasCustom": row.is_custom}
