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


def merged_package_lines(overrides: dict[tuple[str, int], str]) -> dict:
    """Base + overrides aplicados ao campo text (cópia rasa por linha alterada)."""
    if not overrides:
        return package_lines()
    out: dict = {}
    for pkg_id, lines in package_lines().items():
        new_lines = []
        for i, ln in enumerate(lines):
            ov = overrides.get((pkg_id, i))
            new_lines.append({**ln, "text": ov} if ov is not None else ln)
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
