from __future__ import annotations

"""
WebSocket Handler for Real-Time Updates

Provides WebSocket endpoint for streaming real-time data to React Native clients:
- Price updates
- New signals
- Position changes
- Balance updates
- Engine status
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .schemas import (
    EngineStatus,
    OpenPosition,
    SignalDirection,
    SignalResponse,
    SignalStatus,
    WSBalanceUpdate,
    WSEngineStatus,
    WSError,
    WSHeartbeat,
    WSMessageType,
    WSPositionMessage,
    WSPriceUpdate,
    WSSignalMessage,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Connection Manager
# =============================================================================


class ConnectionManager:
    """
    WebSocket connection manager.

    Handles multiple client connections and message broadcasting.
    """

    def __init__(self):
        # Active connections
        self.active_connections: List[WebSocket] = []

        # Subscription management
        self.subscriptions: Dict[str, Set[WebSocket]] = {
            "prices": set(),
            "signals": set(),
            "positions": set(),
            "balance": set(),
            "engine": set(),
            "all": set(),
        }

        # Background tasks
        self._heartbeat_task: asyncio.Task = None
        self._price_stream_task: asyncio.Task = None

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Subscribe to all by default
        self.subscriptions["all"].add(websocket)

        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

        # Send welcome message
        await self._send_json(websocket, {
            "type": "connected",
            "message": "Connected to Lightning Bot WebSocket",
            "timestamp": datetime.utcnow().isoformat(),
        })

    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Remove from all subscriptions
        for subscribers in self.subscriptions.values():
            subscribers.discard(websocket)

        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, channels: List[str]):
        """Subscribe a connection to specific channels."""
        for channel in channels:
            if channel in self.subscriptions:
                self.subscriptions[channel].add(websocket)
                logger.debug(f"WebSocket subscribed to: {channel}")

    async def unsubscribe(self, websocket: WebSocket, channels: List[str]):
        """Unsubscribe a connection from specific channels."""
        for channel in channels:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(websocket)
                logger.debug(f"WebSocket unsubscribed from: {channel}")

    async def broadcast(self, channel: str, data: dict):
        """Broadcast message to all subscribers of a channel."""
        subscribers = self.subscriptions.get(channel, set()) | self.subscriptions.get("all", set())

        disconnected = []
        for connection in subscribers:
            try:
                await self._send_json(connection, data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_all(self, data: dict):
        """Broadcast message to all connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await self._send_json(connection, data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, data: dict):
        """Send message to a specific connection."""
        try:
            await self._send_json(websocket, data)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def _send_json(self, websocket: WebSocket, data: dict):
        """Send JSON data to a WebSocket."""
        await websocket.send_json(data)

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


# =============================================================================
# Message Handlers
# =============================================================================


async def handle_subscribe(websocket: WebSocket, data: dict):
    """Handle subscribe message."""
    channels = data.get("channels", [])
    await manager.subscribe(websocket, channels)
    await manager.send_personal(websocket, {
        "type": "subscribed",
        "channels": channels,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def handle_unsubscribe(websocket: WebSocket, data: dict):
    """Handle unsubscribe message."""
    channels = data.get("channels", [])
    await manager.unsubscribe(websocket, channels)
    await manager.send_personal(websocket, {
        "type": "unsubscribed",
        "channels": channels,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def handle_ping(websocket: WebSocket, data: dict):
    """Handle ping message."""
    await manager.send_personal(websocket, {
        "type": "pong",
        "timestamp": datetime.utcnow().isoformat(),
    })


# Message handler dispatch
MESSAGE_HANDLERS = {
    "subscribe": handle_subscribe,
    "unsubscribe": handle_unsubscribe,
    "ping": handle_ping,
}


# =============================================================================
# Background Tasks
# =============================================================================


async def heartbeat_task():
    """Send periodic heartbeat to all connections."""
    while True:
        try:
            await asyncio.sleep(30)  # Every 30 seconds

            heartbeat = WSHeartbeat(timestamp=datetime.utcnow())
            await manager.broadcast_all(heartbeat.model_dump())

            logger.debug(f"Heartbeat sent to {manager.connection_count} connections")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")


async def mock_price_stream():
    """Mock price stream for development."""
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
    base_prices = {
        "EUR/USD": 1.0850,
        "GBP/USD": 1.2650,
        "USD/JPY": 149.25,
        "AUD/USD": 0.6520,
    }

    import random

    while True:
        try:
            await asyncio.sleep(1)  # Update every second

            for pair in pairs:
                # Add some random movement
                base = base_prices[pair]
                movement = (random.random() - 0.5) * 0.001
                base_prices[pair] = base + movement

                spread = 0.0002 if "JPY" not in pair else 0.02
                bid = base_prices[pair]
                ask = bid + spread

                price_update = WSPriceUpdate(
                    pair=pair,
                    bid=round(bid, 5 if "JPY" not in pair else 3),
                    ask=round(ask, 5 if "JPY" not in pair else 3),
                    timestamp=datetime.utcnow(),
                )

                await manager.broadcast("prices", price_update.model_dump())

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Price stream error: {e}")


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    ## Connection

    Connect to `ws://host:port/ws`

    ## Message Types

    ### Client -> Server

    **Subscribe to channels:**
    ```json
    {
        "type": "subscribe",
        "channels": ["prices", "signals", "positions", "balance", "engine"]
    }
    ```

    **Unsubscribe from channels:**
    ```json
    {
        "type": "unsubscribe",
        "channels": ["prices"]
    }
    ```

    **Ping (keep-alive):**
    ```json
    {"type": "ping"}
    ```

    ### Server -> Client

    **Price Update:**
    ```json
    {
        "type": "price_update",
        "pair": "EUR/USD",
        "bid": 1.0850,
        "ask": 1.0852,
        "timestamp": "2024-01-15T12:00:00Z"
    }
    ```

    **New Signal:**
    ```json
    {
        "type": "signal_new",
        "signal": { ... signal details ... }
    }
    ```

    **Position Update:**
    ```json
    {
        "type": "position_update",
        "position": { ... position details ... }
    }
    ```

    **Balance Update:**
    ```json
    {
        "type": "balance_update",
        "balance": 10485.32,
        "equity": 10512.07,
        "unrealized_pnl": 26.75,
        "timestamp": "2024-01-15T12:00:00Z"
    }
    ```

    **Heartbeat:**
    ```json
    {
        "type": "heartbeat",
        "timestamp": "2024-01-15T12:00:00Z"
    }
    ```
    """
    await manager.connect(websocket)

    # Start background tasks if this is the first connection
    if manager.connection_count == 1:
        asyncio.create_task(heartbeat_task())
        asyncio.create_task(mock_price_stream())

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            message_type = data.get("type", "")
            handler = MESSAGE_HANDLERS.get(message_type)

            if handler:
                await handler(websocket, data)
            else:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "error": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat(),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# =============================================================================
# Broadcast Functions (for use by other modules)
# =============================================================================


async def broadcast_price_update(pair: str, bid: float, ask: float):
    """Broadcast a price update to all subscribers."""
    update = WSPriceUpdate(
        pair=pair,
        bid=bid,
        ask=ask,
        timestamp=datetime.utcnow(),
    )
    await manager.broadcast("prices", update.model_dump())


async def broadcast_new_signal(signal: SignalResponse):
    """Broadcast a new signal to all subscribers."""
    message = WSSignalMessage(
        type=WSMessageType.SIGNAL_NEW,
        signal=signal,
    )
    await manager.broadcast("signals", message.model_dump())


async def broadcast_signal_update(signal: SignalResponse):
    """Broadcast a signal update to all subscribers."""
    message = WSSignalMessage(
        type=WSMessageType.SIGNAL_UPDATE,
        signal=signal,
    )
    await manager.broadcast("signals", message.model_dump())


async def broadcast_position_open(position: OpenPosition):
    """Broadcast a position open to all subscribers."""
    message = WSPositionMessage(
        type=WSMessageType.POSITION_OPEN,
        position=position,
    )
    await manager.broadcast("positions", message.model_dump())


async def broadcast_position_update(position: OpenPosition):
    """Broadcast a position update to all subscribers."""
    message = WSPositionMessage(
        type=WSMessageType.POSITION_UPDATE,
        position=position,
    )
    await manager.broadcast("positions", message.model_dump())


async def broadcast_position_close(position: OpenPosition):
    """Broadcast a position close to all subscribers."""
    message = WSPositionMessage(
        type=WSMessageType.POSITION_CLOSE,
        position=position,
    )
    await manager.broadcast("positions", message.model_dump())


async def broadcast_balance_update(balance: float, equity: float, unrealized_pnl: float):
    """Broadcast a balance update to all subscribers."""
    update = WSBalanceUpdate(
        balance=balance,
        equity=equity,
        unrealized_pnl=unrealized_pnl,
        timestamp=datetime.utcnow(),
    )
    await manager.broadcast("balance", update.model_dump())


async def broadcast_engine_status(status: EngineStatus, message: str = None):
    """Broadcast an engine status update to all subscribers."""
    update = WSEngineStatus(
        status=status,
        message=message,
        timestamp=datetime.utcnow(),
    )
    await manager.broadcast("engine", update.model_dump())


async def broadcast_error(error: str, code: str = None):
    """Broadcast an error to all subscribers."""
    error_msg = WSError(
        error=error,
        code=code,
        timestamp=datetime.utcnow(),
    )
    await manager.broadcast_all(error_msg.model_dump())


# =============================================================================
# WebSocket Statistics Endpoint
# =============================================================================


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    """
    return {
        "active_connections": manager.connection_count,
        "subscriptions": {
            channel: len(subscribers)
            for channel, subscribers in manager.subscriptions.items()
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
