"""
SQLAlchemy engine, session factory and declarative base.
"""
from typing import Any, Dict, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings

# SQLite needs check_same_thread off because the inference loop runs on a
# different thread than the request that started it. Pooling args are
# PostgreSQL-only and would be rejected by the SQLite dialect.
engine_kwargs: Dict[str, Any] = {"pool_pre_ping": True}
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
