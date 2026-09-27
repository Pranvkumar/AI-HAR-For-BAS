"""
Experiments router — CRUD plus derived live progress.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_session
from schemas.dto import ExperimentCreate, ExperimentProgressOut
from services.experiment_service import ExperimentService

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


@router.get("", response_model=List[ExperimentProgressOut])
def list_experiments(db: Session = Depends(get_session)):
    """List all experiments with steps and live progress."""
    return [
        ExperimentService.with_progress(db, experiment)
        for experiment in ExperimentService.get_all(db)
    ]


@router.get("/{identifier}", response_model=ExperimentProgressOut)
def get_experiment(identifier: str, db: Session = Depends(get_session)):
    """Get one experiment by numeric id or by code (e.g. BAS-EXP-001)."""
    experiment = ExperimentService.resolve(db, identifier)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentService.with_progress(db, experiment)


@router.post("", response_model=ExperimentProgressOut, status_code=status.HTTP_201_CREATED)
def create_experiment(experiment_in: ExperimentCreate, db: Session = Depends(get_session)):
    """Create an experiment along with its ordered steps."""
    if ExperimentService.get_by_code(db, experiment_in.code):
        raise HTTPException(status_code=409, detail="Experiment code already exists")

    experiment = ExperimentService.create(db, experiment_in)
    return ExperimentService.with_progress(db, experiment)


@router.put("/{experiment_id}", response_model=ExperimentProgressOut)
def update_experiment(
    experiment_id: int,
    experiment_in: ExperimentCreate,
    db: Session = Depends(get_session),
):
    """Update an experiment; supplying steps replaces the existing ones."""
    existing = ExperimentService.get_by_code(db, experiment_in.code)
    if existing and existing.id != experiment_id:
        raise HTTPException(status_code=409, detail="Experiment code already exists")

    experiment = ExperimentService.update(db, experiment_id, experiment_in)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentService.with_progress(db, experiment)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: int, db: Session = Depends(get_session)):
    """Delete an experiment and its steps, sessions and logs."""
    if not ExperimentService.delete(db, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return None
