"""Edição da base das linhas dos pacotes (texto + placeholders) via overrides."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_editor
from ..base_data import invalid_tokens, line_text, merged_package_lines, package_lines, valid_token_fields
from ..database import get_db
from ..models import ChangeLogEntry, LineOverride

router = APIRouter(prefix="/api/base", tags=["base"])


class LineEdit(BaseModel):
    text: str


def _overrides_map(db: Session) -> dict[tuple[str, int], str]:
    rows = db.execute(select(LineOverride)).scalars().all()
    return {(o.pkg_id, o.line_index): o.text for o in rows}


def _log_change(db: Session, pkg_id: str, index: int, tipo: str, resumo: str,
                antes: str, depois: str, author: str) -> None:
    next_id = (db.execute(select(func.max(ChangeLogEntry.id))).scalar() or 0) + 1
    db.add(ChangeLogEntry(
        id=next_id, data=date.today().isoformat(), pacote=pkg_id, linha=index + 1,
        tipo=tipo, resumo=resumo, antes=antes, depois=depois, author=author,
    ))


@router.get("/package-lines")
def get_package_lines(db: Session = Depends(get_db)):
    """Base mesclada (bundled + overrides). Consumida pelo front no boot."""
    return merged_package_lines(_overrides_map(db))


@router.get("/overrides")
def get_overrides(db: Session = Depends(get_db)):
    rows = db.execute(select(LineOverride)).scalars().all()
    return [
        {"pkgId": o.pkg_id, "lineIndex": o.line_index, "text": o.text,
         "author": o.author, "updatedAt": o.updated_at}
        for o in rows
    ]


@router.get("/fields")
def get_fields():
    """Campos válidos para tokens {{campo=glifo}} (para o seletor do editor)."""
    return sorted(valid_token_fields())


def _check(pkg_id: str, index: int) -> str:
    original = line_text(pkg_id, index)
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pacote/linha inexistente")
    return original


@router.put("/package-lines/{pkg_id}/{line_index}")
def edit_line(pkg_id: str, line_index: int, payload: LineEdit,
              db: Session = Depends(get_db), user: dict = Depends(require_editor)):
    """Salva o override do texto de uma linha (editor). Valida tokens e registra no log."""
    _check(pkg_id, line_index)
    bad = invalid_tokens(payload.text)
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tokens com campo desconhecido: {', '.join(bad)}")

    existing = db.get(LineOverride, (pkg_id, line_index))
    antes = existing.text if existing else (line_text(pkg_id, line_index) or "")
    if payload.text == antes:
        return {"pkgId": pkg_id, "lineIndex": line_index, "text": payload.text, "unchanged": True}

    if existing:
        existing.text = payload.text
        existing.author = user["username"]
    else:
        db.add(LineOverride(pkg_id=pkg_id, line_index=line_index, text=payload.text, author=user["username"]))

    _log_change(db, pkg_id, line_index, "edição",
                f"Edição da linha {line_index + 1} do pacote {pkg_id}",
                antes, payload.text, user["username"])
    db.commit()
    return {"pkgId": pkg_id, "lineIndex": line_index, "text": payload.text}


@router.delete("/package-lines/{pkg_id}/{line_index}")
def reset_line(pkg_id: str, line_index: int,
               db: Session = Depends(get_db), user: dict = Depends(require_editor)):
    """Remove o override (reverte a linha ao texto original). Registra no log."""
    original = _check(pkg_id, line_index)
    existing = db.get(LineOverride, (pkg_id, line_index))
    if not existing:
        return {"pkgId": pkg_id, "lineIndex": line_index, "text": original, "reverted": False}

    antes = existing.text
    db.delete(existing)
    _log_change(db, pkg_id, line_index, "reestruturação",
                f"Revertida a linha {line_index + 1} do pacote {pkg_id} ao original",
                antes, original, user["username"])
    db.commit()
    return {"pkgId": pkg_id, "lineIndex": line_index, "text": original, "reverted": True}
