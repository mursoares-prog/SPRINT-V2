"""Paridade do port Python de nippleDepth contra o golden gerado pelo TS real.

As fixtures (tests/fixtures/nipple_depth.json) são produzidas por
abandono-app/scripts/genNippleFixtures.ts rodando o engine TypeScript de verdade.
Aqui rodamos a porta Python sobre as mesmas entradas e exigimos saída idêntica.
"""
import json
from pathlib import Path

import pytest

from app.engines.nipple_depth import (
    nipple_depth_for_bha, camisao_dhsv_fields, gabarito_fields, bha_derived_depth,
)

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "nipple_depth.json").read_text(encoding="utf-8"))


def _run(case: dict):
    fn = case["fn"]
    name = case["name"]
    data = case["data"]
    if fn == "nippleDepthForBha":
        return nipple_depth_for_bha(name, data)
    if fn == "camisaoDhsvFields":
        return camisao_dhsv_fields({"packageName": name}, data)
    if fn == "gabaritoFields":
        return gabarito_fields({"packageName": name}, data)
    if fn == "bhaDerivedDepth":
        return bha_derived_depth({"packageName": name, "technology": case["technology"] or "none"}, data)
    raise ValueError(f"fn desconhecida: {fn}")


@pytest.mark.parametrize("case", FIXTURES, ids=[c["id"] for c in FIXTURES])
def test_nipple_depth_parity(case):
    assert _run(case) == case["expected"]
