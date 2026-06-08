"""Paridade do port Python de sequenceEngine contra o golden gerado pelo TS real.

Golden: tests/fixtures/sequence_engine.json (de abandono-app/scripts/genSequenceFixtures.ts),
62 cronogramas (11 escopos × ANC/DP × Generalista/LWO + variações de opções).
Compara item a item TODOS os campos de domínio, exceto `uid` (determinístico para
itens normais, mas aleatório para auto-inseridos — não é saída de domínio).
"""
import json
from pathlib import Path

import pytest

from app.engines.sequence_engine import generate_schedule

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "sequence_engine.json").read_text(encoding="utf-8"))

# Campos comparados. Opcionais ausentes no JSON viram None; normalizamos os dois lados.
_FIELDS = ["packageId", "packageName", "category", "technology", "transitionTechnology",
           "phase", "duration", "isContingency", "contingencyReason", "startDay", "endDay"]


def _norm(item: dict) -> tuple:
    base = tuple(item.get(f) for f in _FIELDS)
    # Booleanos opcionais (omitidos quando falsy no golden TS): comparar por verdade.
    return base + (bool(item.get("autoInserted")), bool(item.get("annularBore")))


@pytest.mark.parametrize("fx", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_schedule_parity(fx):
    got = generate_schedule(fx["inputs"])
    expected = fx["schedule"]
    assert len(got) == len(expected), (
        f"{fx['id']}: nº de itens difere — py={len(got)} ts={len(expected)}"
    )
    for i, (g, e) in enumerate(zip(got, expected)):
        assert _norm(g) == _norm(e), (
            f"{fx['id']} item {i}: py={_norm(g)} != ts={_norm(e)}"
        )
