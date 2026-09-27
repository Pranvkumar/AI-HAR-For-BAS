"""
WebSocket router — live broadcast of inference payloads to connected clients.
"""
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from services.monitoring_service import monitoring_service

router = APIRouter()

# Interval for keepalive pings when no inference payloads are flowing.
IDLE_PING_SECONDS = 20.0


class ConnectionManager:
    """Tracks open WebSocket connections and fans messages out to them."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                # Client vanished mid-send; drop it rather than failing the loop.
                self.disconnect(connection)

    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


@router.websocket("/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    """
    Stream live monitoring payloads.

    Each connection registers its own send callback with the monitoring service,
    so a disconnect only unregisters that client.
    """
    await manager.connect(websocket)

    async def send_payload(payload: Dict[str, Any]) -> None:
        await websocket.send_json(payload)

    monitoring_service.register_broadcast_callback(send_payload)

    # Replay the latest payload so a client joining mid-session renders immediately.
    if monitoring_service.last_payload is not None:
        try:
            await websocket.send_json(monitoring_service.last_payload.model_dump())
        except Exception:
            pass

    try:
        while True:
            # Client messages are not part of the protocol; the receive call
            # exists to detect disconnects and to keep the socket responsive.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=IDLE_PING_SECONDS)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(f"WebSocket closed with error: {exc}")
    finally:
        monitoring_service.unregister_broadcast_callback(send_payload)
        manager.disconnect(websocket)
