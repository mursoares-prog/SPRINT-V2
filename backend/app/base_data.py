"""Base das linhas dos pacotes (packageLines) + merge de overrides + validação de tokens.

A base bundled vem de app/data/package_lines.json (dump do front). Os overrides
(tabela line_override) substituem o `text` de linhas específicas. Tokens novos só
podem referenciar campos conhecidos (placeholders.py + campos já usados na base).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .engines.placeholders import ALWAYS_HP, HP_PREFIX_FLAG, PLAN_KEYS

_DATA = Path(__file__).resolve().parent / "data"
_PACKAGE_LINES: dict | None = None

_TOKEN_FIELD_RE = re.compile(r"\{\{(\w+)=")
_SYNTHETIC = {"_bopBaixa", *ALWAYS_HP.keys(), *HP_PREFIX_FLAG.keys()}


def package_lines() -> dict:
    """Base bundled (carregada uma vez)."""
    global _PACKAGE_LINES
    if _PACKAGE_LINES is None:
        _PACKAGE_LINES = json.loads((_DATA / "package_lines.json").read_text(encoding="utf-8"))
    return _PACKAGE_LINES


def line_text(pkg_id: str, index: int) -> str | None:
    """Texto original (bundled) de uma linha, ou None se fora do intervalo."""
    lines = package_lines().get(pkg_id)
    if not lines or index < 0 or index >= len(lines):
        return None
    return lines[index].get("text", "")


# Campos do LineOverride legado (chave) → chave em package_lines (valor).
# rec/pad NÃO entram: pertencem aos detalhes (packageLineDetails), mesclados no front.
_MERGED_FIELDS = {
    "text": "text",
    "duration": "duration",
    "ow_fase": "owFase",
    "ow_atividade": "owAtividade",
    "ow_operacao": "owOperacao",
    "ow_etapa": "owEtapa",
}

# Campos de package_lines (12) — usados ao projetar o array completo de um
# PackageLinesOverride (descarta rec/pad, que viram detalhes no front).
PACKAGE_LINE_FIELDS = (
    "text", "duration", "bop", "compensando", "isContingency", "isParallel",
    "owFase", "owAtividade", "owOperacao", "owEtapa", "genOperacao", "genOperacaoDual",
)


def _project_package_line(ln: dict) -> dict:
    """Mantém só os 12 campos de package_lines de uma linha do PackageLinesOverride."""
    return {k: ln.get(k) for k in PACKAGE_LINE_FIELDS}


def merged_package_lines(
    line_overrides: dict[tuple[str, int], dict] | None = None,
    pkg_overrides: dict[str, list[dict]] | None = None,
) -> dict:
    """Base bundled + overrides aplicados. Precedência por pacote:

    1. `pkg_overrides[pkg]` (array completo) — usado inteiro (estrutural; cobre
       add/del/reorder e pacotes customizados que não existem no bundle);
    2. `line_overrides` por (pkg, índice) — patch campo-a-campo (legado);
    3. bundle.
    """
    line_overrides = line_overrides or {}
    pkg_overrides = pkg_overrides or {}
    if not line_overrides and not pkg_overrides:
        return package_lines()

    bundle = package_lines()
    out: dict = {}
    # União: pacotes do bundle + customizados (só em pkg_overrides).
    for pkg_id in list(bundle.keys()) + [p for p in pkg_overrides if p not in bundle]:
        if pkg_id in pkg_overrides:
            out[pkg_id] = [_project_package_line(ln) for ln in pkg_overrides[pkg_id]]
            continue
        new_lines = []
        for i, ln in enumerate(bundle.get(pkg_id, [])):
            ov = line_overrides.get((pkg_id, i))
            if ov is None:
                new_lines.append(ln)
                continue
            patch = {dst: ov[src] for src, dst in _MERGED_FIELDS.items()
                     if ov.get(src) is not None}
            new_lines.append({**ln, **patch})
        out[pkg_id] = new_lines
    return out


def valid_token_fields() -> set[str]:
    """Campos que um token {{campo=...}} pode referenciar.

    = campos já usados em qualquer linha da base ∪ chaves de plano ∪ sintéticos.
    Criar campo novo (inexistente) é mudança de código — fora do escopo de edição.
    """
    used: set[str] = set()
    for lines in package_lines().values():
        for ln in lines:
            t = ln.get("text")
            if t:
                used.update(_TOKEN_FIELD_RE.findall(t))
    return used | set(PLAN_KEYS) | _SYNTHETIC


def invalid_tokens(text: str) -> list[str]:
    """Campos de token presentes no texto que NÃO são reconhecidos (lista vazia = ok)."""
    valid = valid_token_fields()
    return sorted({f for f in _TOKEN_FIELD_RE.findall(text) if f not in valid})
