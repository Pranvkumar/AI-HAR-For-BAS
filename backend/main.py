"""
FastAPI application entrypoint for SIH26174 Space Monitoring.

Run from the backend/ directory:
    uvicorn main:app --reload
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
SRC_DIR = REPO_ROOT / "src"

for p in (BACKEND_DIR, REPO_ROOT, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from loguru import logger  # noqa: E402

from config import settings  # noqa: E402
from db import models  # noqa: E402,F401 — registers ORM models on Base
from db.seed_data import SEED_EXPERIMENTS  # noqa: E402
from db.session import Base, SessionLocal, engine  # noqa: E402
from routers import (  # noqa: E402
    alerts,
    assistant,
    dashboard,
    experiments,
    logs,
    monitoring,
    system,
    websocket,
    objects,
    recordings,
    aerospace,
)
from services.monitoring_service import monitoring_service  # noqa: E402


def seed_experiments() -> None:
    """Insert any seed experiment whose code is not already present."""
    db = SessionLocal()
    try:
        existing_codes = {
            code for (code,) in db.query(models.Experiment.code).all()
        }

        added = 0
        for spec in SEED_EXPERIMENTS:
            if spec["code"] in existing_codes:
                continue

            experiment = models.Experiment(
                title=spec["title"],
                code=spec["code"],
                description=spec["description"],
                category=spec["category"],
                environment=spec["environment"],
                estimated_duration=spec["estimated_duration"],
                total_steps=len(spec["steps"]),
            )
            db.add(experiment)
            db.flush()

            for number, step in enumerate(spec["steps"], start=1):
                db.add(models.ExperimentStep(
                    experiment_id=experiment.id,
                    step_number=number,
                    title=step["title"],
                    expected_activity=step["expected_activity"],
                    description=step["description"],
                    safety_critical=step["safety_critical"],
                ))
            added += 1

        db.commit()
        if added:
            logger.info(f"Seeded {added} experiment(s)")
    except Exception as exc:
        db.rollback()
        logger.warning(f"Could not seed experiments: {exc}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed demo data; keep serving if the DB is unreachable."""
    logger.info(f"Starting {settings.APP_NAME} (demo_mode={settings.DEMO_MODE})")

    try:
        Base.metadata.create_all(bind=engine)
        seed_experiments()
        logger.info("Database ready")
    except Exception as exc:
        logger.warning(f"Database unavailable at startup: {exc}")
        logger.warning("API is up; check DATABASE_URL for persistence")

    yield

    # Cancel any inference loops so shutdown does not leave orphaned tasks.
    await monitoring_service.stop_all()
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-based onboard human activity recognition and experiment monitoring for BAS",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(experiments.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(logs.router)
app.include_router(assistant.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(objects.router)
app.include_router(recordings.router)
app.include_router(aerospace.router)


@app.get("/health", tags=["health"])
def health_check():
    """Liveness probe."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "demo_mode": settings.DEMO_MODE,
    }


DIST_DIR = REPO_ROOT / "frontend" / "dist"
if (DIST_DIR / "assets").exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = DIST_DIR / full_path
        if target.is_file():
            return FileResponse(target)
        index = DIST_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"status": "ok", "service": settings.APP_NAME}

