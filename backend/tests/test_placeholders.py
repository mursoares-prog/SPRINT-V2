"""Paridade do port Python de placeholders contra o golden gerado pelo TS real.

Golden: tests/fixtures/placeholders.json (de abandono-app/scripts/genPlaceholderFixtures.ts).
Cobre fill_tokens / has_tokens / has_unfilled_tokens por caso, mais os derivados
SLWLFT_HIGH_PKG_IDS e DATA_SUB_FIELDS (este recomputado do mesmo packageLines.json).
"""
import json
from pathlib import Path

import pytest

from app.engines.placeholders import (
    fill_tokens, has_tokens, has_unfilled_tokens,
    SLWLFT_HIGH_PKG_IDS, compute_data_sub_fields,
)

FIX = json.loads((Path(__file__).parent / "fixtures" / "placeholders.json").read_text(encoding="utf-8"))
CASES = FIX["cases"]

# packageLines.json é a fonte do front (repos irmãos sob a pasta pai).
_PKG_LINES_PATH = Path(__file__).parents[2] / "abandono-app" / "src" / "data" / "packageLines.json"
PACKAGE_LINES = json.loads(_PKG_LINES_PATH.read_text(encoding="utf-8-sig"))


def _ctx(case: dict) -> dict:
    return {"data": case["data"], "plan": case["plan"], "pkgId": "", "pkgName": ""}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fill_tokens_parity(case):
    assert fill_tokens(case["template"], _ctx(case)) == case["fill"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_has_tokens_parity(case):
    assert has_tokens(case["template"]) == case["hasTok"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_has_unfilled_tokens_parity(case):
    assert has_unfilled_tokens(case["template"], _ctx(case)) == case["unfilled"]


def test_slwlft_high_pkg_ids_parity():
    assert SLWLFT_HIGH_PKG_IDS == FIX["slwlftHighPkgIds"]


def test_data_sub_fields_parity():
    # Ordem não importa (TS deriva de um Set); compara como conjunto.
    assert compute_data_sub_fields(PACKAGE_LINES) == set(FIX["dataSubFields"])
