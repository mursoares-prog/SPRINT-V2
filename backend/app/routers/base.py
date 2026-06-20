"""Edição da base das linhas dos pacotes (texto + placeholders) via overrides."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..base_data import invalid_tokens, line_text, merged_package_lines, package_lines, valid_token_fields
from ..database import get_db
from ..models import ChangeLogEntry, LineOverride, PackageLinesOverride, PackageMeta

router = APIRouter(prefix="/api/base", tags=["base"])


def _is_bundle_pkg(pkg_id: str) -> bool:
    """True se o pacote existe na base empacotada (nome travado, não apagável)."""
    return pkg_id in package_lines()


# Patch parcial: cada campo None = "não alterar este campo". `text` é o único que,
# quando presente, valida tokens. rec/pad são detalhes (mesclados no front).
class LineEdit(BaseModel):
    text: str | None = None
    duration: float | None = None
    rec: str | None = None
    pad: str | None = None
    owFase: str | None = None
    owAtividade: str | None = None
    owOperacao: str | None = None
    owEtapa: str | None = None


# Campos editáveis do override: nome no payload (front) → atributo do modelo.
_FIELD_ATTR = {
    "text": "text", "duration": "duration", "rec": "rec", "pad": "pad",
    "owFase": "ow_fase", "owAtividade": "ow_atividade",
    "owOperacao": "ow_operacao", "owEtapa": "ow_etapa",
}


def _override_dict(o: LineOverride) -> dict:
    """Serializa um override (camelCase, para o front)."""
    return {
        "pkgId": o.pkg_id, "lineIndex": o.line_index,
        "text": o.text, "duration": o.duration, "rec": o.rec, "pad": o.pad,
        "owFase": o.ow_fase, "owAtividade": o.ow_atividade,
        "owOperacao": o.ow_operacao, "owEtapa": o.ow_etapa,
        "author": o.author, "updatedAt": o.updated_at,
    }


def _overrides_map(db: Session) -> dict[tuple[str, int], dict]:
    """(pkg_id, line_index) → dict de campos (chaves do modelo) p/ merged_package_lines."""
    rows = db.execute(select(LineOverride)).scalars().all()
    return {
        (o.pkg_id, o.line_index): {
            "text": o.text, "duration": o.duration,
            "ow_fase": o.ow_fase, "ow_atividade": o.ow_atividade,
            "ow_operacao": o.ow_operacao, "ow_etapa": o.ow_etapa,
        }
        for o in rows
    }


def _pkg_overrides_map(db: Session) -> dict[str, list]:
    """pkg_id → array completo de linhas (PackageLinesOverride), p/ merged_package_lines."""
    rows = db.execute(select(PackageLinesOverride)).scalars().all()
    return {o.pkg_id: o.lines for o in rows}


def _log_change(db: Session, pkg_id: str, linha: int | None, tipo: str, resumo: str,
                antes: str, depois: str, author: str) -> None:
    next_id = (db.execute(select(func.max(ChangeLogEntry.id))).scalar() or 0) + 1
    db.add(ChangeLogEntry(
        id=next_id, data=date.today().isoformat(), pacote=pkg_id, linha=linha,
        tipo=tipo, resumo=resumo, antes=antes, depois=depois, author=author,
    ))


@router.get("/package-lines")
def get_package_lines(db: Session = Depends(get_db)):
    """Base mesclada (bundled + overrides de linha e de pacote). Boot do front."""
    return merged_package_lines(_overrides_map(db), _pkg_overrides_map(db))


@router.get("/overrides")
def get_overrides(db: Session = Depends(get_db)):
    """Overrides por linha (legado). Mantido para compatibilidade."""
    rows = db.execute(select(LineOverride)).scalars().all()
    return [_override_dict(o) for o in rows]


@router.get("/package-overrides")
def get_package_overrides(db: Session = Depends(get_db)):
    """Arrays completos de linhas por pacote editado (14 campos por linha).
    O front usa para preencher os stores de linhas e de detalhes (rec/pad)."""
    rows = db.execute(select(PackageLinesOverride)).scalars().all()
    return [{"pkgId": o.pkg_id, "lines": o.lines, "author": o.author,
             "updatedAt": o.updated_at} for o in rows]


@router.get("/packages")
def get_custom_packages(db: Session = Depends(get_db)):
    """Metas dos pacotes customizados (criados/duplicados no Admin)."""
    rows = db.execute(select(PackageMeta)).scalars().all()
    return [{"pkgId": m.pkg_id, "name": m.name, "category": m.category,
             "technology": m.technology, "author": m.author, "updatedAt": m.updated_at}
            for m in rows]


@router.get("/fields")
def get_fields():
    """Campos válidos para tokens {{campo=glifo}} (para o seletor do editor)."""
    return sorted(valid_token_fields())


def _check(pkg_id: str, index: int) -> str:
    original = line_text(pkg_id, index)
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pacote/linha inexistente")
    return original


# Metadados dos campos editáveis: payload → (atributo do modelo, chave bundled, rótulo).
# bundled=None → campo só vive no override (rec/pad), sem valor de base no backend.
_EDIT_FIELDS = [
    ("text",        "text",         "text",        "Texto"),
    ("duration",    "duration",     "duration",    "Duração (h)"),
    ("rec",         "rec",          None,          "Recomendações"),
    ("pad",         "pad",          None,          "Padrões"),
    ("owFase",      "ow_fase",      "owFase",      "OW Fase"),
    ("owAtividade", "ow_atividade", "owAtividade", "OW Atividade"),
    ("owOperacao",  "ow_operacao",  "owOperacao",  "OW Operação"),
    ("owEtapa",     "ow_etapa",     "owEtapa",     "OW Etapa"),
]


def _bundled_line(pkg_id: str, index: int) -> dict:
    return package_lines().get(pkg_id, [])[index]


@router.put("/package-lines/{pkg_id}/{line_index}")
def edit_line(pkg_id: str, line_index: int, payload: LineEdit,
              db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Salva um override parcial de uma linha (admin). Cada campo enviado (não-None)
    substitui o da base; campos omitidos ficam inalterados. Valida tokens quando o
    texto muda e registra os campos alterados no log."""
    _check(pkg_id, line_index)
    if payload.text is not None:
        bad = invalid_tokens(payload.text)
        if bad:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tokens com campo desconhecido: {', '.join(bad)}")

    existing = db.get(LineOverride, (pkg_id, line_index))
    bundled = _bundled_line(pkg_id, line_index)

    def current(model_attr: str, bundled_key: str | None):
        if existing is not None and getattr(existing, model_attr) is not None:
            return getattr(existing, model_attr)
        return bundled.get(bundled_key) if bundled_key else None

    # Detecta os campos efetivamente alterados.
    changed: list[tuple[str, str, str, object, object]] = []  # (attr, label, payload_name, antes, depois)
    for name, attr, bkey, label in _EDIT_FIELDS:
        new = getattr(payload, name)
        if new is None:
            continue
        old = current(attr, bkey)
        if new != old:
            changed.append((attr, label, name, old, new))

    if not changed:
        return {"pkgId": pkg_id, "lineIndex": line_index, "unchanged": True}

    # `text` é NOT NULL: ao criar o override, preserva o texto efetivo atual quando
    # a edição não toca no texto.
    if existing is None:
        existing = LineOverride(
            pkg_id=pkg_id, line_index=line_index,
            text=payload.text if payload.text is not None else (line_text(pkg_id, line_index) or ""),
        )
        db.add(existing)
    for attr, _label, _name, _old, new in changed:
        setattr(existing, attr, new)
    existing.author = user["username"]

    def fmt(v: object) -> str:
        return "" if v is None else str(v)

    antes = "\n".join(f"{label}: {fmt(old)}" for _a, label, _n, old, _new in changed)
    depois = "\n".join(f"{label}: {fmt(new)}" for _a, label, _n, _old, new in changed)
    resumo = (f"Edição da linha {line_index + 1} do pacote {pkg_id}: "
              + ", ".join(label for _a, label, _n, _o, _new in changed))
    _log_change(db, pkg_id, line_index + 1, "edição", resumo, antes, depois, user["username"])
    db.commit()
    return {"pkgId": pkg_id, "lineIndex": line_index, **_override_dict(existing)}


@router.delete("/package-lines/{pkg_id}/{line_index}")
def reset_line(pkg_id: str, line_index: int,
               db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Remove o override (reverte a linha ao texto original). Registra no log."""
    original = _check(pkg_id, line_index)
    existing = db.get(LineOverride, (pkg_id, line_index))
    if not existing:
        return {"pkgId": pkg_id, "lineIndex": line_index, "text": original, "reverted": False}

    antes = existing.text
    db.delete(existing)
    _log_change(db, pkg_id, line_index + 1, "reestruturação",
                f"Revertida a linha {line_index + 1} do pacote {pkg_id} ao original",
                antes, original, user["username"])
    db.commit()
    return {"pkgId": pkg_id, "lineIndex": line_index, "text": original, "reverted": True}


# ── Edição estrutural por pacote (linhas completas) + pacotes customizados ──────

class PackageLinesEdit(BaseModel):
    lines: list[dict]


class PackageCreate(BaseModel):
    name: str
    category: str = ""
    technology: str = "none"
    lines: list[dict] = []


class PackageMetaEdit(BaseModel):
    name: str | None = None
    category: str | None = None
    technology: str | None = None


def _validate_line_tokens(lines: list[dict]) -> None:
    bad: set[str] = set()
    for ln in lines:
        bad.update(invalid_tokens(ln.get("text") or ""))
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Tokens com campo desconhecido: {', '.join(sorted(bad))}")


def _next_custom_id(db: Session) -> str:
    """Próximo id livre 'ABAN NNN' sem colisão com bundle nem customizados existentes."""
    used: set[int] = set()
    for pid in package_lines():
        m = re.match(r'^ABAN\s+(\d+)', pid)
        if m:
            used.add(int(m.group(1)))
    for meta in db.execute(select(PackageMeta)).scalars().all():
        m = re.match(r'^ABAN\s+(\d+)', meta.pkg_id)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"ABAN {n:03d}"


@router.put("/packages/{pkg_id}/lines")
def save_package_lines(pkg_id: str, payload: PackageLinesEdit,
                       db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Grava o array COMPLETO de linhas de um pacote (estrutural: add/del/reorder).
    Vale para pacotes do bundle e customizados. Valida tokens e registra no log."""
    if not _is_bundle_pkg(pkg_id) and db.get(PackageMeta, pkg_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pacote inexistente")
    _validate_line_tokens(payload.lines)

    existing = db.get(PackageLinesOverride, pkg_id)
    antes = str(len(existing.lines)) if existing else None
    if existing:
        existing.lines = payload.lines
        existing.author = user["username"]
    else:
        db.add(PackageLinesOverride(pkg_id=pkg_id, lines=payload.lines, author=user["username"]))

    # Sai do regime legado por índice para este pacote.
    for o in db.execute(select(LineOverride).where(LineOverride.pkg_id == pkg_id)).scalars().all():
        db.delete(o)

    _log_change(db, pkg_id, None, "edição",
                f"Edição das linhas do pacote {pkg_id} ({len(payload.lines)} linhas)",
                f"{antes} linha(s)" if antes is not None else "(bundle)",
                f"{len(payload.lines)} linha(s)", user["username"])
    db.commit()
    return {"pkgId": pkg_id, "lines": payload.lines}


@router.delete("/packages/{pkg_id}/lines")
def reset_package_lines(pkg_id: str, db: Session = Depends(get_db),
                        user: dict = Depends(require_admin)):
    """Reverte as linhas de um pacote do BUNDLE ao original (remove o override)."""
    if not _is_bundle_pkg(pkg_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Pacote customizado: use DELETE /packages/{id} para apagá-lo")
    existing = db.get(PackageLinesOverride, pkg_id)
    if existing:
        db.delete(existing)
    for o in db.execute(select(LineOverride).where(LineOverride.pkg_id == pkg_id)).scalars().all():
        db.delete(o)
    _log_change(db, pkg_id, None, "reestruturação",
                f"Revertidas as linhas do pacote {pkg_id} ao original", "", "", user["username"])
    db.commit()
    return {"pkgId": pkg_id, "reverted": True}


@router.post("/packages")
def create_package(payload: PackageCreate, db: Session = Depends(get_db),
                   user: dict = Depends(require_admin)):
    """Cria um pacote customizado (em branco ou duplicando linhas enviadas)."""
    if not payload.name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nome obrigatório")
    _validate_line_tokens(payload.lines)
    pkg_id = _next_custom_id(db)
    db.add(PackageMeta(pkg_id=pkg_id, name=payload.name.strip(), category=payload.category,
                       technology=payload.technology, author=user["username"]))
    db.add(PackageLinesOverride(pkg_id=pkg_id, lines=payload.lines, author=user["username"]))
    _log_change(db, pkg_id, None, "inclusão",
                f"Criação do pacote customizado {pkg_id} — {payload.name.strip()}",
                "", f"{len(payload.lines)} linha(s)", user["username"])
    db.commit()
    return {"pkgId": pkg_id, "name": payload.name.strip(), "category": payload.category,
            "technology": payload.technology, "lines": payload.lines}


@router.patch("/packages/{pkg_id}")
def update_package_meta(pkg_id: str, payload: PackageMetaEdit,
                        db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Edita nome/categoria/tecnologia de um pacote customizado (bundle é travado)."""
    if _is_bundle_pkg(pkg_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pacote do bundle: metadados travados")
    meta = db.get(PackageMeta, pkg_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pacote customizado inexistente")
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nome obrigatório")
        meta.name = payload.name.strip()
    if payload.category is not None:
        meta.category = payload.category
    if payload.technology is not None:
        meta.technology = payload.technology
    meta.author = user["username"]
    _log_change(db, pkg_id, None, "metadado",
                f"Edição de metadados do pacote {pkg_id}", "", meta.name, user["username"])
    db.commit()
    return {"pkgId": pkg_id, "name": meta.name, "category": meta.category, "technology": meta.technology}


class PackageImportItem(BaseModel):
    pkgId: str
    name: str
    category: str = "Geral"
    technology: str = "none"
    lines: list[dict] = []


class PackageImportPayload(BaseModel):
    packages: list[PackageImportItem]


@router.post("/import")
def import_packages(payload: PackageImportPayload, db: Session = Depends(get_db),
                    user: dict = Depends(require_admin)):
    """Importa um batch de pacotes do sistema externo (formato ProjectFacts enriquecido).

    Por pacote:
    - pkgId já existe no bundle → cria/atualiza PackageLinesOverride (override)
    - pkgId já existe como customizado → atualiza linhas e metadados
    - pkgId novo → cria PackageMeta + PackageLinesOverride

    Não valida tokens: o texto vem resolvido da etapa 3; placeholders adicionados
    no enrich são intencionais e renderizam o glifo como fallback quando não mapeados.
    """
    if not payload.packages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Lista de pacotes vazia")

    results = []
    for item in payload.packages:
        pkg_id = item.pkgId.strip()
        if not pkg_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "pkgId obrigatório em todos os pacotes")

        is_bundle = _is_bundle_pkg(pkg_id)
        meta = db.get(PackageMeta, pkg_id)

        if not is_bundle and meta is None:
            # Novo pacote customizado — cria meta e linhas
            db.add(PackageMeta(
                pkg_id=pkg_id, name=item.name.strip() or pkg_id,
                category=item.category, technology=item.technology,
                author=user["username"],
            ))
            db.add(PackageLinesOverride(pkg_id=pkg_id, lines=item.lines, author=user["username"]))
            tipo = "inclusão"
            resumo = f"Import: criação do pacote {pkg_id} — {item.name}"
            antes, depois = "", f"{len(item.lines)} linha(s)"
        elif not is_bundle and meta is not None:
            # Pacote customizado existente — atualiza meta e linhas
            meta.name = item.name.strip() or meta.name
            meta.category = item.category
            meta.technology = item.technology
            meta.author = user["username"]
            existing_lines = db.get(PackageLinesOverride, pkg_id)
            if existing_lines:
                antes = f"{len(existing_lines.lines)} linha(s)"
                existing_lines.lines = item.lines
                existing_lines.author = user["username"]
            else:
                antes = "(sem override)"
                db.add(PackageLinesOverride(pkg_id=pkg_id, lines=item.lines, author=user["username"]))
            tipo = "edição"
            resumo = f"Import: atualização do pacote customizado {pkg_id}"
            depois = f"{len(item.lines)} linha(s)"
        else:
            # Pacote do bundle — cria/atualiza override estrutural
            existing_lines = db.get(PackageLinesOverride, pkg_id)
            if existing_lines:
                antes = f"{len(existing_lines.lines)} linha(s)"
                existing_lines.lines = item.lines
                existing_lines.author = user["username"]
            else:
                antes = "(bundle)"
                db.add(PackageLinesOverride(pkg_id=pkg_id, lines=item.lines, author=user["username"]))
            tipo = "edição"
            resumo = f"Import: override do pacote bundle {pkg_id}"
            depois = f"{len(item.lines)} linha(s)"

        _log_change(db, pkg_id, None, tipo, resumo, antes, depois, user["username"])
        results.append({"pkgId": pkg_id, "tipo": tipo, "lines": len(item.lines)})

    db.commit()
    return {"imported": len(results), "packages": results}


@router.delete("/packages/{pkg_id}")
def delete_package(pkg_id: str, db: Session = Depends(get_db),
                   user: dict = Depends(require_admin)):
    """Apaga um pacote customizado (meta + linhas). Bundle não é apagável."""
    if _is_bundle_pkg(pkg_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pacote do bundle não pode ser apagado")
    meta = db.get(PackageMeta, pkg_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pacote customizado inexistente")
    name = meta.name
    db.delete(meta)
    lines = db.get(PackageLinesOverride, pkg_id)
    if lines:
        db.delete(lines)
    _log_change(db, pkg_id, None, "remoção",
                f"Remoção do pacote customizado {pkg_id} — {name}", name, "", user["username"])
    db.commit()
    return {"pkgId": pkg_id, "deleted": True}
