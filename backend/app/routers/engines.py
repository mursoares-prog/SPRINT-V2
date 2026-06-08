"""Endpoints do espelho Python dos engines (geração autoritativa + validação)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..engines.sequence_engine import generate_schedule
from ..validation import validate_schedule

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class ScheduleRequest(BaseModel):
    inputs: dict


class ValidateRequest(BaseModel):
    inputs: dict
    schedule: list = []


@router.post("")
def post_schedule(req: ScheduleRequest):
    """Gera o cronograma autoritativo a partir dos inputs (fonte canônica no servidor)."""
    try:
        schedule = generate_schedule(req.inputs)
    except KeyError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Input obrigatório ausente: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Falha ao gerar cronograma: {e}")
    return {"schedule": schedule, "count": len(schedule)}


@router.post("/validate")
def post_validate(req: ValidateRequest):
    """Compara o cronograma enviado com o que o engine produz dos mesmos inputs."""
    return validate_schedule(req.inputs, req.schedule)
