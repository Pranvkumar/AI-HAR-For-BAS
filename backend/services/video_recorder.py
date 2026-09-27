"""
Automatic Session Video Recorder for AEGIS AI-HAR.
Encodes MP4 video streams per experiment session for post-mission audit and replay.
Native Windows support with mp4v / avc1 codec.
"""
import os
import cv2
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RECORDINGS_DIR = BASE_DIR / "storage" / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


class SessionVideoRecorder:
    """Records session frames into MP4 video container."""

    def __init__(self, fps: float = 12.0):
        self.fps = fps
        self._writer: Optional[cv2.VideoWriter] = None
        self._active_session_id: Optional[int] = None
        self._current_path: Optional[Path] = None
        self._frames_written = 0

    def start_recording(self, session_id: int, frame_shape: tuple):
        self.stop_recording()  # close existing if any

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"session_{session_id}_{timestamp}.mp4"
        self._current_path = RECORDINGS_DIR / filename
        h, w = frame_shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self._writer = cv2.VideoWriter(str(self._current_path), fourcc, self.fps, (w, h))
        self._active_session_id = session_id
        self._frames_written = 0
        logger.info(f"SessionVideoRecorder: Started recording session {session_id} -> {filename}")

    def write_frame(self, frame: np.ndarray):
        if self._writer is not None and frame is not None:
            try:
                self._writer.write(frame)
                self._frames_written += 1
            except Exception as exc:
                logger.debug(f"Video writer write error: {exc}")

    def stop_recording(self) -> Optional[Dict[str, Any]]:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
            info = {
                "session_id": self._active_session_id,
                "path": str(self._current_path),
                "filename": self._current_path.name if self._current_path else "",
                "frames_written": self._frames_written,
            }
            logger.info(f"SessionVideoRecorder: Completed recording {info['filename']} ({self._frames_written} frames)")
            self._active_session_id = None
            return info
        return None

    def list_recordings(self) -> List[Dict[str, Any]]:
        recordings = []
        for file in sorted(RECORDINGS_DIR.glob("*.mp4"), reverse=True):
            stat = file.stat()
            recordings.append({
                "filename": file.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                "path": f"/api/v1/recordings/download/{file.name}",
            })
        return recordings

    @property
    def is_recording(self) -> bool:
        return self._writer is not None


session_video_recorder = SessionVideoRecorder()
