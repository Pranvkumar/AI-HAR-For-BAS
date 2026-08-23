"""FastAPI MJPEG endpoint backed by a shared annotated-frame queue."""

import queue
import importlib
from typing import Any, Iterator

try:
    FastAPI = importlib.import_module("fastapi").FastAPI
    StreamingResponse = importlib.import_module("fastapi.responses").StreamingResponse
except ImportError:  # pragma: no cover
    FastAPI = None
    StreamingResponse = None


def create_app(frame_queue: queue.Queue[Any]) -> Any:
    if FastAPI is None:
        raise RuntimeError("fastapi is required to serve the stream")
    app = FastAPI(title="AI HAR Stream")

    def frames() -> Iterator[bytes]:
        cv2 = importlib.import_module("cv2")
        while True:
            packet = frame_queue.get()
            success, encoded = cv2.imencode(".jpg", packet.frame)
            if success:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"

    @app.get("/stream")
    def stream() -> Any:
        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
