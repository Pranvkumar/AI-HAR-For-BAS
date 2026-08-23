"""FastAPI MJPEG endpoint fed by the annotated-frame publisher."""

from __future__ import annotations

import threading
from typing import Any, Iterator


class AnnotatedFrameHub:
    """Keep only the latest rendered frame for local MJPEG clients."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._jpeg: bytes | None = None

    def publish(self, frame: Any) -> None:
        """JPEG-encode and publish a rendered OpenCV frame."""

        import cv2

        ok, encoded = cv2.imencode(".jpg", frame)
        if ok:
            with self._condition:
                self._jpeg = encoded.tobytes()
                self._condition.notify_all()

    def frames(self) -> Iterator[bytes]:
        """Yield the newest frame whenever one is available."""

        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._jpeg is not None)
                jpeg = self._jpeg
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"


def create_app(hub: AnnotatedFrameHub) -> Any:
    """Create the local FastAPI application."""

    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    app = FastAPI(title="Offline HAR Stream")

    @app.get("/stream")
    def stream() -> StreamingResponse:
        return StreamingResponse(hub.frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
