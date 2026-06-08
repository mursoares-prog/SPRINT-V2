"""Endpoints de persistência de projetos."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..schemas import ProjectIn, ProjectSummary

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _parse_saved_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _full(project: Project) -> dict:
    """Documento salvo + id do servidor — formato consumido pelo front."""
    return {**project.data, "id": project.id}


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    rows = db.execute(select(Project).order_by(Project.updated_at.desc())).scalars().all()
    return [
        ProjectSummary(
            id=p.id,
            wellName=p.well_name,
            scopeId=p.scope_id,
            savedAt=p.saved_at,
            updatedAt=p.updated_at,
        )
        for p in rows
    ]


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado")
    return _full(project)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_none=False)
    project = Project(
        well_name=payload.wellName,
        scope_id=payload.scopeId,
        saved_at=_parse_saved_at(payload.savedAt),
        data=data,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _full(project)


@router.put("/{project_id}")
def update_project(project_id: str, payload: ProjectIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado")
    project.well_name = payload.wellName
    project.scope_id = payload.scopeId
    project.saved_at = _parse_saved_at(payload.savedAt)
    project.data = payload.model_dump(exclude_none=False)
    db.commit()
    db.refresh(project)
    return _full(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado")
    db.delete(project)
    db.commit()
