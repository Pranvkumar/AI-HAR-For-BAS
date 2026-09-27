"""
Service layer for experiment CRUD and derived progress.
"""
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm import Session, selectinload

from db import models
from schemas import dto
from services.monitoring_service import monitoring_service

# UI-facing status vocabulary (matches the frontend's ExperimentStatus union).
STATUS_ACTIVE = "Active"
STATUS_COMPLETED = "Completed"
STATUS_SCHEDULED = "Scheduled"
STATUS_PAUSED = "Paused"


class ExperimentService:
    """Persistence operations for experiments and their ordered steps."""

    @staticmethod
    def get_all(db: Session) -> List[models.Experiment]:
        return (
            db.query(models.Experiment)
            .options(selectinload(models.Experiment.steps))
            .order_by(models.Experiment.code)
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, experiment_id: int) -> Optional[models.Experiment]:
        return (
            db.query(models.Experiment)
            .options(selectinload(models.Experiment.steps))
            .filter(models.Experiment.id == experiment_id)
            .first()
        )

    @staticmethod
    def get_by_code(db: Session, code: str) -> Optional[models.Experiment]:
        return (
            db.query(models.Experiment)
            .options(selectinload(models.Experiment.steps))
            .filter(models.Experiment.code == code)
            .first()
        )

    @staticmethod
    def resolve(db: Session, identifier: str) -> Optional[models.Experiment]:
        """
        Look up by numeric id or by code.

        The UI routes on the human-readable code (BAS-EXP-001), so accept both.
        """
        if identifier.isdigit():
            found = ExperimentService.get_by_id(db, int(identifier))
            if found:
                return found
        return ExperimentService.get_by_code(db, identifier)

    @staticmethod
    def _add_steps(
        db: Session,
        experiment_id: int,
        steps: Sequence[dto.ExperimentStepIn],
    ) -> None:
        """Insert steps, numbering any that omit an explicit step_number."""
        for index, step in enumerate(steps, start=1):
            db.add(models.ExperimentStep(
                experiment_id=experiment_id,
                step_number=step.step_number or index,
                title=step.title or step.expected_activity.replace("_", " ").title(),
                expected_activity=step.expected_activity,
                description=step.description,
                safety_critical=step.safety_critical,
            ))

    @staticmethod
    def create(db: Session, experiment_in: dto.ExperimentCreate) -> models.Experiment:
        steps = experiment_in.steps or []

        experiment = models.Experiment(
            title=experiment_in.title,
            code=experiment_in.code,
            description=experiment_in.description,
            category=experiment_in.category,
            environment=experiment_in.environment,
            estimated_duration=experiment_in.estimated_duration,
            total_steps=len(steps),
        )
        db.add(experiment)
        db.flush()  # assigns experiment.id for the step rows

        ExperimentService._add_steps(db, experiment.id, steps)

        db.commit()
        db.refresh(experiment)
        return experiment

    @staticmethod
    def update(
        db: Session,
        experiment_id: int,
        experiment_in: dto.ExperimentCreate,
    ) -> Optional[models.Experiment]:
        experiment = ExperimentService.get_by_id(db, experiment_id)
        if not experiment:
            return None

        experiment.title = experiment_in.title
        experiment.code = experiment_in.code
        experiment.description = experiment_in.description
        experiment.category = experiment_in.category
        experiment.environment = experiment_in.environment
        experiment.estimated_duration = experiment_in.estimated_duration

        # Steps are replaced wholesale so step_number stays contiguous.
        if experiment_in.steps is not None:
            db.query(models.ExperimentStep).filter(
                models.ExperimentStep.experiment_id == experiment_id
            ).delete(synchronize_session=False)

            ExperimentService._add_steps(db, experiment_id, experiment_in.steps)
            experiment.total_steps = len(experiment_in.steps)

        db.commit()
        db.refresh(experiment)
        return experiment

    @staticmethod
    def delete(db: Session, experiment_id: int) -> bool:
        experiment = ExperimentService.get_by_id(db, experiment_id)
        if not experiment:
            return False

        db.delete(experiment)
        db.commit()
        return True

    # ── derived progress ──────────────────────────────────────────────────────

    @staticmethod
    def latest_session(
        db: Session,
        experiment_id: int,
    ) -> Optional[models.ExperimentSession]:
        return (
            db.query(models.ExperimentSession)
            .filter(models.ExperimentSession.experiment_id == experiment_id)
            .order_by(models.ExperimentSession.created_at.desc())
            .first()
        )

    @staticmethod
    def with_progress(
        db: Session,
        experiment: models.Experiment,
    ) -> dto.ExperimentProgressOut:
        """
        Attach live progress to an experiment.

        A running session reads progress straight from its FSM; a finished one
        is reconstructed from the CORRECT log rows so history survives restarts.
        """
        total_steps = len(experiment.steps)
        session = ExperimentService.latest_session(db, experiment.id)

        status = STATUS_SCHEDULED
        current_step = 0
        completed: List[str] = []

        if session is not None:
            active = monitoring_service.get_session(session.id)

            if active is not None:
                context = active.fsm.get_context()
                completed = list(context.get("completed_steps", []))
                current_step = context.get("current_step", 0)
                status = STATUS_ACTIVE
            else:
                # Rebuild from persisted logs: each CORRECT row is one confirmed step.
                correct_rows = (
                    db.query(models.Activity.detected_activity)
                    .join(
                        models.ExperimentLog,
                        models.ExperimentLog.activity_id == models.Activity.id,
                    )
                    .filter(
                        models.ExperimentLog.session_id == session.id,
                        models.ExperimentLog.validation_status == "CORRECT",
                    )
                    .order_by(models.ExperimentLog.timestamp)
                    .all()
                )
                completed = [row[0] for row in correct_rows]
                current_step = min(len(completed) + 1, total_steps) if total_steps else 0

                if session.status == "COMPLETED":
                    status = STATUS_COMPLETED
                    current_step = total_steps
                elif session.status == "ABORTED":
                    status = STATUS_PAUSED
                else:
                    status = STATUS_ACTIVE

        progress = (len(completed) / total_steps * 100) if total_steps else 0.0

        return dto.ExperimentProgressOut(
            id=experiment.id,
            title=experiment.title,
            code=experiment.code,
            description=experiment.description,
            category=experiment.category,
            environment=experiment.environment,
            estimated_duration=experiment.estimated_duration,
            total_steps=total_steps,
            created_at=experiment.created_at,
            steps=[dto.ExperimentStepOut.model_validate(s) for s in experiment.steps],
            status=status,
            current_step=current_step,
            progress=round(progress, 1),
            latest_session_id=session.id if session else None,
            completed_activities=completed,
        )
