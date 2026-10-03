# app/websocket_manager.py
import uuid
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """
    Tracks websocket connections per room (queue).  A singleton instance
    called `manager` is exported at the module level so routers can
    simply import it.
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room: str) -> None:
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)

    async def disconnect(self, websocket: WebSocket, room: str) -> None:
        try:
            self.active_connections[room].remove(websocket)
        except ValueError:
            pass
        if not self.active_connections[room]:
            del self.active_connections[room]

    async def broadcast(self, room: str, message: dict) -> None:
        """Send a JSON message to every websocket in *room*."""
        for connection in self.active_connections.get(room, []):
            await connection.send_json(message)

    async def send_to_client(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)

    def generate_queue_id(self) -> str:
        """Convenient unique id used by the routers."""
        return str(uuid.uuid4())


# Export a singleton instance – import it as `manager`
manager = ConnectionManager()