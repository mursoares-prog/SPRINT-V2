"""Validação de cronograma usando o espelho Python do engine.

Compara o cronograma salvo (vindo do front) com o que o sequenceEngine produz a
partir dos mesmos `inputs`. Útil para detectar (a) edições manuais na etapa 2/3 e
(b) drift entre o projeto salvo e a versão atual do engine. É sempre informativo —
nunca bloqueia um save.
"""
from __future__ import annotations

from .engines.sequence_engine import generate_schedule


def validate_schedule(inputs: dict | None, schedule: list | None) -> dict:
    """Recalcula o cronograma dos inputs e compara a sequência de pacotes."""
    if not inputs:
        return {"ok": False, "error": "inputs ausentes"}
    try:
        server = generate_schedule(inputs)
    except Exception as e:  # nunca propaga — validação é best-effort
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    server_ids = [i["packageId"] for i in server]
    client_ids = [i.get("packageId") for i in (schedule or [])]

    first = None
    for idx in range(max(len(server_ids), len(client_ids))):
        sv = server_ids[idx] if idx < len(server_ids) else None
        cv = client_ids[idx] if idx < len(client_ids) else None
        if sv != cv:
            first = {"index": idx, "server": sv, "client": cv}
            break

    return {
        "ok": True,
        "identical": server_ids == client_ids,
        "serverCount": len(server_ids),
        "clientCount": len(client_ids),
        "firstDivergence": first,
    }
