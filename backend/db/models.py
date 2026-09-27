"""
SQLAlchemy ORM models — mirrors database/schema.sql.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    email = Column(String(255))
    role = Column(String(50), default="researcher")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    sessions = relationship("ExperimentSession", back_populates="astronaut")
    alerts = relationship(
        "Alert",
        back_populates="user",
        foreign_keys="[Alert.astronaut_id]",
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(100), default="General")
    environment = Column(String(100), default="Microgravity")
    estimated_duration = Column(String(20), default="00:00:00")
    total_steps = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    steps = relationship(
        "ExperimentStep",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ExperimentStep.step_number",
    )
    sessions = relationship(
        "ExperimentSession",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ExperimentStep(Base):
    __tablename__ = "experiment_steps"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(
        Integer,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number = Column(Integer, nullable=False)
    title = Column(String(255))
    expected_activity = Column(String(100), nullable=False)
    description = Column(Text)
    safety_critical = Column(Boolean, default=False)

    experiment = relationship("Experiment", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("experiment_id", "step_number", name="uq_experiment_step"),
    )


class ExperimentSession(Base):
    __tablename__ = "experiment_sessions"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(
        Integer,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    astronaut_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50), default="IN_PROGRESS")
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    experiment = relationship("Experiment", back_populates="sessions")
    astronaut = relationship("User", back_populates="sessions")
    activities = relationship(
        "Activity",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    alerts = relationship("Alert", back_populates="session")
    logs = relationship(
        "ExperimentLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("idx_sessions_status", "status"),)


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    detected_activity = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    session = relationship("ExperimentSession", back_populates="activities")
    logs = relationship("ExperimentLog", back_populates="activity")

    __table_args__ = (Index("idx_activities_timestamp", "timestamp"),)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("experiment_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    astronaut_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    acknowledged = Column(Boolean, default=False)

    session = relationship("ExperimentSession", back_populates="alerts")
    user = relationship(
        "User",
        back_populates="alerts",
        foreign_keys=[astronaut_id],
    )

    __table_args__ = (
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_acknowledged", "acknowledged"),
    )


class ExperimentLog(Base):
    __tablename__ = "experiment_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number = Column(Integer)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"))
    validation_status = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    session = relationship("ExperimentSession", back_populates="logs")
    activity = relationship("Activity", back_populates="logs")

    __table_args__ = (Index("idx_logs_session", "session_id"),)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), unique=True, nullable=False)
    version = Column(String(50))
    is_active = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow)
