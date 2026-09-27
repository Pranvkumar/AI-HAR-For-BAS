"""
Monitoring service — owns active inference sessions and the AI pipeline loop.

Each session runs an asyncio task that pushes frames through
CV -> HAR -> FSM -> persistence -> WebSocket broadcast. In DEMO_MODE the
activity labels come from a scripted scenario so demos are reproducible;
otherwise they come from the HAR model over the frame buffer.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from sqlalchemy.orm import Session

from ai_engine.activity_recognition.base import FrameBuffer
from ai_engine.activity_recognition.temporal_har import TemporalHAR
from ai_engine.computer_vision.object_detector import MockDetector
from ai_engine.computer_vision.pose_estimator import MockPoseEstimator
from ai_engine.computer_vision.tracker import MockTracker
from ai_engine.experiment_engine.fsm import ExperimentFSM
from ai_engine.experiment_engine.validator import ExperimentValidator
from ai_engine.nlp.template_fallback import TemplateLLM

from config import settings
from db import models
from db.session import SessionLocal
from schemas.dto import ValidationStatus, WebSocketPayload
from services.scenarios import SCENARIO_NAMES, build_scenario
from services.merkle_ledger import flight_merkle_ledger
from services.ccsds_formatter import ccsds_formatter, APID
from services.aerospace_safety import (
    thermal_governor,
    hardware_watchdog,
    glare_detector,
    immobility_detector,
    kalman_tracker,
    drift_detector,
    slosh_guard,
    eco_governor,
    cognitive_stall_detector,
)
from services.object_registry import dynamic_object_registry
from services.video_recorder import session_video_recorder
from services.biometric_service import biometric_manager
from services.voice_alert import tts_worker
import math

# Placeholder frame: used when camera device is absent or starting up.
MOCK_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)

import threading
import time

class CameraCaptureManager:
    """Manages OpenCV webcam capture for real-time video feed."""
    def __init__(self, source: int = 0):
        self.source = source
        self._cap = None
        self._lock = threading.Lock()
        self._running = False
        self._latest_raw_frame = None

    def start(self):
        if self._running:
            return
        try:
            import cv2
            self._cap = cv2.VideoCapture(self.source)
            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self._running = True
                threading.Thread(target=self._capture_loop, daemon=True, name="camera-capture").start()
                logger.info(f"Connected to local camera device {self.source}")
        except Exception as exc:
            logger.warning(f"Could not initialize camera {self.source}: {exc}")

    def _capture_loop(self):
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_raw_frame = frame
                time.sleep(0.01)
            else:
                time.sleep(0.03)

    def read_frame(self) -> Optional[np.ndarray]:
        if not self._running:
            self.start()
        with self._lock:
            if self._latest_raw_frame is not None:
                return self._latest_raw_frame.copy()
        return None

    def stop(self):
        self._running = False
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

camera_manager = CameraCaptureManager(0)

# Frames held per scripted step, so a demo viewer can read each transition.
FRAMES_PER_SCENARIO_STEP = 3

BroadcastCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class ActiveSession:
    """Runtime state for one active monitoring session."""

    def __init__(
        self,
        session_id: int,
        experiment_id: int,
        expected_sequence: List[str],
        scenario: str = "nominal",
    ):
        self.session_id = session_id
        self.experiment_id = experiment_id
        self.scenario = scenario
        self.scenario_steps = build_scenario(expected_sequence, scenario)
        self.started_at = datetime.now(timezone.utc)
        self.frames_processed = 0
        self.activities_recorded = 0
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.latest_guidance: str = ""

        self.frame_buffer = FrameBuffer(max_size=settings.FRAME_BUFFER_SIZE)
        self.detector = MockDetector()
        self.pose_estimator = MockPoseEstimator()
        self.tracker = MockTracker()
        self.har = TemporalHAR(
            self.frame_buffer,
            confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        )
        self.fsm = ExperimentFSM(
            expected_sequence,
            confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        )
        self.validator = ExperimentValidator()
        self.llm = TemplateLLM()


class MonitoringService:
    """Starts and stops inference sessions; fans payloads out to WebSocket clients."""

    def __init__(self):
        self.active_sessions: Dict[int, ActiveSession] = {}
        self.broadcast_callbacks: List[BroadcastCallback] = []
        self.last_payload: Optional[WebSocketPayload] = None
        self.latest_jpeg: Optional[bytes] = None

    # ── broadcast plumbing ────────────────────────────────────────────────────

    def register_broadcast_callback(self, callback: BroadcastCallback) -> None:
        if callback not in self.broadcast_callbacks:
            self.broadcast_callbacks.append(callback)

    def unregister_broadcast_callback(self, callback: BroadcastCallback) -> None:
        if callback in self.broadcast_callbacks:
            self.broadcast_callbacks.remove(callback)

    async def _broadcast(self, payload: WebSocketPayload) -> None:
        self.last_payload = payload
        message = payload.model_dump()

        for callback in list(self.broadcast_callbacks):
            try:
                await callback(message)
            except Exception as exc:
                logger.warning(f"Dropping broadcast callback after failure: {exc}")
                self.unregister_broadcast_callback(callback)

    # ── session lifecycle ─────────────────────────────────────────────────────

    async def start_session(
        self,
        db: Session,
        experiment_id: int,
        astronaut_id: Optional[int],
        scenario: str = "nominal",
    ) -> models.ExperimentSession:
        """Create the session row and launch its inference loop."""
        steps = (
            db.query(models.ExperimentStep)
            .filter(models.ExperimentStep.experiment_id == experiment_id)
            .order_by(models.ExperimentStep.step_number)
            .all()
        )
        expected_sequence = [step.expected_activity for step in steps]

        db_session = models.ExperimentSession(
            experiment_id=experiment_id,
            astronaut_id=astronaut_id,
            status="IN_PROGRESS",
            started_at=datetime.now(timezone.utc),
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        active = ActiveSession(
            session_id=db_session.id,
            experiment_id=experiment_id,
            expected_sequence=expected_sequence,
            scenario=scenario,
        )
        self.active_sessions[db_session.id] = active

        active.running = True
        active.task = asyncio.create_task(self._inference_loop(active))

        # Aerospace extensions: video recording, Merkle chain entry, TTS cue
        session_video_recorder.start_recording(db_session.id, (480, 640, 3))
        flight_merkle_ledger.record_transition(f"EXP_{experiment_id}", "START", "SESSION", "IN_PROGRESS")
        tts_worker.speak(f"Experiment session {db_session.id} initiated.")

        logger.info(f"Session {db_session.id} started (scenario={scenario})")
        return db_session

    async def stop_session(
        self,
        db: Session,
        session_id: int,
    ) -> Optional[models.ExperimentSession]:
        """Cancel the inference loop and close out the session row."""
        active = self.active_sessions.pop(session_id, None)
        if active is None:
            return None

        active.running = False
        if active.task and not active.task.done():
            active.task.cancel()
            try:
                await active.task
            except asyncio.CancelledError:
                pass

        # Aerospace extensions: finalize video recording, Merkle chain record, TTS cue
        session_video_recorder.stop_recording()
        flight_merkle_ledger.record_transition(f"EXP_{active.experiment_id}", "STOP", "SESSION", "COMPLETED")
        tts_worker.speak("Experiment session completed.")

        db_session = (
            db.query(models.ExperimentSession)
            .filter(models.ExperimentSession.id == session_id)
            .first()
        )
        if db_session:
            db_session.status = "COMPLETED" if active.fsm.is_complete() else "ABORTED"
            db_session.ended_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_session)

        logger.info(f"Session {session_id} stopped ({db_session.status if db_session else 'unknown'})")
        return db_session

    async def stop_all(self) -> None:
        """Cancel every running loop — used on application shutdown."""
        for session_id in list(self.active_sessions):
            active = self.active_sessions.pop(session_id)
            active.running = False
            if active.task and not active.task.done():
                active.task.cancel()
                try:
                    await active.task
                except asyncio.CancelledError:
                    pass

    # ── inference loop ────────────────────────────────────────────────────────

    async def _inference_loop(self, active: ActiveSession) -> None:
        """
        Drive frames at a fixed interval until the session is stopped.

        The loop owns its own DB session for its whole lifetime — a request-scoped
        session would be closed as soon as the start_session response returned.
        """
        interval = settings.INFERENCE_INTERVAL_MS / 1000.0
        db = SessionLocal()

        try:
            while active.running:
                try:
                    await self._process_frame(active, db)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    db.rollback()
                    logger.error(f"Frame processing failed (session {active.session_id}): {exc}")

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        finally:
            db.close()

    async def _process_frame(self, active: ActiveSession, db: Session) -> None:
        """Run one frame through the pipeline and broadcast the result."""
        hardware_watchdog.feed()
        thermal_governor.check()

        raw_frame = camera_manager.read_frame()
        frame_to_process = raw_frame if raw_frame is not None else MOCK_FRAME

        # SWaP-C Eco-Governor evaluation
        should_process = eco_governor.process(raw_frame)
        if not should_process:
            if raw_frame is not None:
                session_video_recorder.write_frame(raw_frame)
            return

        # Optical glare detection
        is_blinded, glare_sat = glare_detector.evaluate(raw_frame)

        detections = active.detector.detect(frame_to_process)
        poses = active.pose_estimator.estimate_pose(frame_to_process)
        tracks = active.tracker.update(frame_to_process, detections)

        # Dynamic Object Registry: check novel registered items via ORB
        expected_act = active.fsm.current_expected_activity()
        if expected_act and raw_frame is not None:
            for obj_meta in dynamic_object_registry.list_objects():
                slug = obj_meta.get("slug", "")
                if slug and (slug in expected_act.lower() or expected_act.lower() in slug):
                    if dynamic_object_registry.detect_object(raw_frame, slug):
                        detections.append({
                            "bbox": [0.35, 0.45, 0.65, 0.75],
                            "class_name": slug,
                            "confidence": 0.91,
                        })
                        break

        # Kalman temporal smoothing and velocity calculation
        kalman_detections = kalman_tracker.update(detections)

        # Extract hand & target spatial points
        hand_point = None
        hand_present = False
        target_point = None
        held_vx, held_vy = 0.0, 0.0

        for d in detections:
            cname = str(d.get("class_name", "")).lower()
            bbox = d.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2]) / 2.0 * 640
            cy = (bbox[1] + bbox[3]) / 2.0 * 480
            if "hand" in cname:
                hand_point = (cx, cy)
                hand_present = True
            elif target_point is None:
                target_point = (cx, cy)
                held_vx = d.get("vx", 0.0) * 10
                held_vy = d.get("vy", 0.0) * 10

        # Immobility detection
        is_immobile = immobility_detector.update(hand_point)
        if is_immobile and not getattr(active, "_immobility_alerted", False):
            active._immobility_alerted = True
            tts_worker.speak("Alert. Crew immobility safety trigger.")

        # Slosh guard jerk calculation
        jerk_val, slosh_alert = slosh_guard.update(held_vx, held_vy)
        if slosh_alert and not getattr(active, "_slosh_alerted", False):
            active._slosh_alerted = True
            tts_worker.speak("Caution. Microgravity slosh hazard.")
        elif not slosh_alert:
            active._slosh_alerted = False

        # Unsecured drift & FOD collision vector projection
        fod_res = drift_detector.evaluate(kalman_detections, hand_present)
        if fod_res["fod_active"] and not getattr(active, "_fod_alerted", False):
            active._fod_alerted = True
            tts_worker.speak(f"Warning. Unsecured drift on {fod_res['fod_object']}.")
        elif not fod_res["fod_active"]:
            active._fod_alerted = False

        # Cognitive stall detection
        hand_vel = math.sqrt(held_vx**2 + held_vy**2)
        is_hesitating, dwell_ms = cognitive_stall_detector.update(hand_point, target_point, hand_vel)

        active.frame_buffer.add_frame(
            detector_output=detections,
            pose_output=poses,
            tracker_output=tracks,
        )
        active.frames_processed += 1

        # Motion features need at least two frames to mean anything.
        if len(active.frame_buffer) < 2:
            return

        if settings.DEMO_MODE:
            activity, confidence = self._scripted_activity(active)
        else:
            activity, confidence = active.har.predict()

        result = active.validator.validate(active.fsm, activity, confidence)
        context = result["context"]

        guidance = await active.llm.generate_guidance(active.fsm.get_context())
        active.latest_guidance = guidance

        # Contextual assistance cue on cognitive hesitation
        if is_hesitating and not getattr(active, "_hesitation_cued", False):
            active._hesitation_cued = True
            tts_worker.speak(f"Operator assistance: {guidance[:60]}")
        elif not is_hesitating:
            active._hesitation_cued = False

        db_activity = models.Activity(
            session_id=active.session_id,
            detected_activity=activity,
            confidence=confidence,
        )
        db.add(db_activity)
        db.flush()

        db.add(models.ExperimentLog(
            session_id=active.session_id,
            step_number=context.get("step_number"),
            activity_id=db_activity.id,
            validation_status=result["status"],
        ))

        # Check and record step transitions in Merkle ledger
        curr_step = context.get("step_number", 0)
        last_step = getattr(active, "_last_merkle_step", None)
        if curr_step != last_step:
            flight_merkle_ledger.record_transition(
                step_id=f"STEP_{curr_step}",
                action=activity,
                obj=str(active.fsm.current_expected_activity() or "CONTAINER"),
                outcome=result["status"],
            )
            active._last_merkle_step = curr_step

        # Pack binary CCSDS space packet
        ccsds_formatter.pack_slosh_guard(jerk_val, slosh_alert)
        ccsds_formatter.pack_eco_governor(1 if eco_governor.is_standby else 0, eco_governor.target_fps, eco_governor.frames_skipped)
        ccsds_stats = ccsds_formatter.get_stats()

        alert_payload = None
        if result["alert_required"]:
            db_alert = models.Alert(
                session_id=active.session_id,
                severity=result["severity"],
                message=result["message"],
            )
            db.add(db_alert)
            db.flush()
            alert_payload = {
                "id": db_alert.id,
                "severity": result["severity"],
                "message": result["message"],
            }

        db.commit()
        active.activities_recorded += 1

        payload = WebSocketPayload(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=active.session_id,
            experiment_id=active.experiment_id,
            detected_activity=activity,
            confidence=round(confidence, 3),
            expected_step=active.fsm.current_expected_activity(),
            step_number=context.get("step_number", 0),
            total_steps=context.get("total_steps", 0),
            status=ValidationStatus(result["status"]),
            bounding_boxes=[
                {
                    "bbox": d["bbox"],
                    "class_name": d["class_name"],
                    "confidence": d["confidence"],
                }
                for d in detections
            ],
            pose_keypoints=[{"keypoints": p["keypoints"]} for p in poses],
            alert=alert_payload,
            fsm_state=active.fsm.state.value,
            progress=round(active.fsm.progress() * 100, 1),
            guidance=guidance,
            completed_activities=list(active.fsm.completed_steps),
            # Aerospace telemetry
            merkle_hash=flight_merkle_ledger.get_short_hash(),
            merkle_chain_length=flight_merkle_ledger.chain_length,
            slosh_jerk=jerk_val,
            slosh_alert=slosh_alert,
            eco_mode=eco_governor.mode,
            eco_fps=eco_governor.target_fps,
            eco_frames_saved=eco_governor.frames_skipped,
            thermal_status="HOT" if thermal_governor.thermal_level == 2 else ("WARM" if thermal_governor.thermal_level == 1 else "COOL"),
            cpu_percent=thermal_governor.cpu_percent,
            is_blinded=is_blinded,
            glare_saturation=glare_sat,
            is_immobile=is_immobile,
            fod_active=fod_res["fod_active"],
            fod_object=fod_res["fod_object"],
            fod_eta=fod_res["fod_eta"],
            predicted_impact=list(fod_res["predicted_impact"]) if fod_res["predicted_impact"] else None,
            hesitation_active=is_hesitating,
            hesitation_dwell_ms=dwell_ms,
            ccsds_last_hex=ccsds_stats["last_hex"],
            ccsds_total_packets=ccsds_stats["total_packets"],
            hand_pos=list(hand_point) if hand_point else None,
        )

        # Record video frame
        if raw_frame is not None:
            session_video_recorder.write_frame(raw_frame)

        step_str = f"STEP {context.get('step_number', 0)}/{context.get('total_steps', 0)}"
        self.latest_jpeg = self._render_frame_jpeg(detections, activity, confidence, result["status"], step_str, base_frame=raw_frame)

        await self._broadcast(payload)

        if active.fsm.is_complete():
            # Mark the session complete in the DB, then stop driving frames.
            db_session = (
                db.query(models.ExperimentSession)
                .filter(models.ExperimentSession.id == active.session_id)
                .first()
            )
            if db_session:
                db_session.status = "COMPLETED"
                db_session.ended_at = datetime.now(timezone.utc)
                db.commit()

            active.running = False
            self.active_sessions.pop(active.session_id, None)
            logger.info(f"Session {active.session_id} completed its sequence")

    def _scripted_activity(self, active: ActiveSession) -> Tuple[str, float]:
        """Next (activity, confidence) from the scenario script."""
        steps = active.scenario_steps
        if not steps:
            return "IDLE", 0.0

        index = min(
            active.activities_recorded // FRAMES_PER_SCENARIO_STEP,
            len(steps) - 1,
        )
        return steps[index]

    # ── queries ───────────────────────────────────────────────────────────────

    def get_active_session_count(self) -> int:
        return len(self.active_sessions)

    def get_session(self, session_id: int) -> Optional[ActiveSession]:
        return self.active_sessions.get(session_id)

    def get_any_session(self) -> Optional[ActiveSession]:
        """Any active session — used when the UI has no explicit session id."""
        return next(iter(self.active_sessions.values()), None)

    def is_session_active(self, session_id: int) -> bool:
        return session_id in self.active_sessions

    def _render_frame_jpeg(
        self,
        detections: List[Dict[str, Any]],
        activity: str,
        confidence: float,
        status: str,
        step_str: str,
        base_frame: Optional[np.ndarray] = None,
    ) -> Optional[bytes]:
        try:
            import cv2
            if base_frame is not None:
                frame = cv2.resize(base_frame, (640, 480))
            else:
                raw = camera_manager.read_frame()
                if raw is not None:
                    frame = cv2.resize(raw, (640, 480))
                else:
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    frame[:] = (18, 24, 34)
                    for x in range(0, 640, 40):
                        cv2.line(frame, (x, 0), (x, 480), (28, 38, 52), 1)
                    for y in range(0, 480, 40):
                        cv2.line(frame, (0, y), (640, y), (28, 38, 52), 1)

            h, w = frame.shape[:2]
            # HUD header
            cv2.putText(frame, f"AEGIS AI-HAR // {step_str}", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 210, 255), 2)
            status_color = (80, 220, 100) if status == "CORRECT" else (0, 180, 255) if status == "WARNING" else (60, 60, 240)
            cv2.putText(frame, f"ACTIVITY: {activity} ({confidence:.0%}) - {status}", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)

            # Render bounding boxes
            for d in detections:
                box = d.get("bbox", [])
                if len(box) == 4:
                    x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 160, 0), 2)
                    label = f"{d.get('class_name', '').upper()} {d.get('confidence', 0):.0%}"
                    cv2.rectangle(frame, (x1, max(y1 - 20, 0)), (x1 + len(label) * 9, y1), (255, 160, 0), -1)
                    cv2.putText(frame, label, (x1 + 3, max(y1 - 5, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1)

            ok, enc = cv2.imencode(".jpg", frame)
            if ok:
                return enc.tobytes()
        except Exception:
            pass
        return None

    def get_latest_jpeg(self) -> Optional[bytes]:
        # If an active session is running and has generated an inference overlay frame, prioritize it
        if self.active_sessions and self.latest_jpeg:
            return self.latest_jpeg

        raw = camera_manager.read_frame()
        if raw is not None:
            try:
                import cv2
                frame = cv2.resize(raw, (640, 480))
                now_str = datetime.now(timezone.utc).strftime("%H:%M:%S") + " UTC"
                cv2.putText(frame, f"CAM-01 [OPTICAL SENSOR] // {now_str}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1, cv2.LINE_AA)
                cv2.putText(frame, "AEGIS BAS TELEMETRY // OPTICAL FEED READY", (15, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1, cv2.LINE_AA)
                ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    return enc.tobytes()
            except Exception:
                pass

        if self.latest_jpeg:
            return self.latest_jpeg

        try:
            import cv2
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (14, 18, 26)
            cv2.putText(frame, "AEGIS AI-HAR // OPTICAL STREAM STANDBY", (120, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 140, 180), 2)
            cv2.putText(frame, "Start an experiment session to begin live inference telemetry", (110, 265), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 100, 130), 1)
            ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                return enc.tobytes()
        except Exception:
            pass
        return None

    @property
    def scenario_names(self) -> Tuple[str, ...]:
        return SCENARIO_NAMES


monitoring_service = MonitoringService()
