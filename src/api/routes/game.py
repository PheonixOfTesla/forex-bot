from __future__ import annotations

"""
ATROPOS - Transport

REST for opening and inspecting a room, WebSocket for playing in it.

    POST /api/v1/game/rooms            -> open a room, get the share link
    GET  /api/v1/game/rooms/{code}     -> does this room exist, who is in it
    WS   /api/v1/game/ws/{code}        -> play

The room's phase clock runs as one asyncio task per room, started when the first
socket connects and cancelled when the last one leaves. State is in memory by
design: a game is worthless ten minutes after it ends, and a camp router is not
a database.
"""

import asyncio
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from ..atropos import MAX_PLAYERS, Phase, Room, registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/game", tags=["Atropos"])

TICK_SECONDS = 0.05
# Movement frames go out every 3 ticks - about 7 a second, which is smooth once
# the client interpolates between them and stays cheap on a camp network.
POSITION_EVERY = 3


# =============================================================================
# Helpers
# =============================================================================


def share_url(request: Request, code: str) -> str:
    """The link a host AirDrops or texts to the room."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/play/{code}"


async def broadcast(room: Room) -> None:
    """Send every connected player their own personalised view of the room."""
    if not room.sockets:
        return
    dead_sockets = []
    for pid, socket in list(room.sockets.items()):
        player = room.players.get(pid)
        try:
            await socket.send_json(room.snapshot_for(player))
        except Exception:
            dead_sockets.append(pid)
    for pid in dead_sockets:
        room.sockets.pop(pid, None)
        if pid in room.players:
            room.players[pid].connected = False


async def broadcast_positions(room: Room) -> None:
    """
    The movement frame.

    Walking is sent far more often than anything else, so it travels on its own
    tiny message instead of riding a full state snapshot - a snapshot carries
    the log, the roster and every per-player secret, and is far too heavy to
    send eight times a second.
    """
    if not room.sockets:
        return
    frame = {"t": "pos", "players": room.positions()}
    for pid, socket in list(room.sockets.items()):
        try:
            await socket.send_json(frame)
        except Exception:
            pass


async def send_eidolons(room: Room) -> None:
    """Faces change rarely, so they are pushed on their own when they do."""
    if not room.sockets:
        return
    message = {"t": "eidolons", "map": room.eidolons()}
    for socket in list(room.sockets.values()):
        try:
            await socket.send_json(message)
        except Exception:
            pass


async def clock(room: Room) -> None:
    """Advance the room whenever its phase expires or every action is already in."""
    ticks = 0
    try:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            ticks += 1
            if not room.sockets:
                # Nobody is watching. Park the clock; the socket handler restarts it.
                room.task = None
                return

            # Movement runs on its own cadence, in the lobby as well as in game -
            # milling around the square before the start is half the fun.
            if ticks % POSITION_EVERY == 0:
                await broadcast_positions(room)

            if room.phase is Phase.LOBBY:
                continue

            expired = time.time() >= room.phase_ends_at
            if expired or room.everyone_acted():
                room.advance()
                await broadcast(room)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("atropos: clock failed for room %s", room.code)
        room.task = None


def ensure_clock(room: Room) -> None:
    if room.task is None or room.task.done():
        room.task = asyncio.create_task(clock(room))


# =============================================================================
# REST
# =============================================================================


@router.post("/rooms")
async def open_room(request: Request) -> Dict[str, Any]:
    """Open a room and hand back the link to share."""
    room = registry.create()
    return {
        "code": room.code,
        "url": share_url(request, room.code),
        "maxPlayers": MAX_PLAYERS,
    }


@router.get("/rooms/{code}")
async def peek_room(code: str, request: Request) -> Dict[str, Any]:
    room = registry.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="No room with that code.")
    return {
        "code": room.code,
        "url": share_url(request, room.code),
        "phase": room.phase.value,
        "players": len(room.players),
        "maxPlayers": MAX_PLAYERS,
        "open": room.phase is Phase.LOBBY and len(room.players) < MAX_PLAYERS,
    }


# =============================================================================
# WebSocket
# =============================================================================


@router.websocket("/ws/{code}")
async def play(
    websocket: WebSocket,
    code: str,
    name: str = Query(default="", max_length=40),
    secret: str = Query(default=""),
) -> None:
    """
    Join or rejoin a room.

    A returning player passes the secret their browser stored, which restores
    their seat and role - a dropped phone at camp should not end someone's game.
    """
    await websocket.accept()

    room = registry.get(code)
    if not room:
        await websocket.send_json({"t": "error", "code": "no_room", "message": "That room is gone."})
        await websocket.close()
        return

    player = room.player_by_secret(secret)

    if not player:
        if room.phase is not Phase.LOBBY:
            await websocket.send_json(
                {"t": "error", "code": "in_progress", "message": "That game already started."}
            )
            await websocket.close()
            return
        if len(room.players) >= MAX_PLAYERS:
            await websocket.send_json(
                {"t": "error", "code": "full", "message": "That room is full."}
            )
            await websocket.close()
            return
        player = room.add_player(name)
        await websocket.send_json({"t": "welcome", "pid": player.pid, "secret": player.secret})

    # A second tab for the same player replaces the first.
    old = room.sockets.get(player.pid)
    if old is not None and old is not websocket:
        try:
            await old.close()
        except Exception:
            pass

    player.connected = True
    room.sockets[player.pid] = websocket
    room.last_seen = time.time()
    ensure_clock(room)
    await broadcast(room)
    await send_eidolons(room)   # a joiner needs every face already in the room

    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            handled = await handle(room, player, message, websocket)
            if handled:
                room.last_seen = time.time()

                await broadcast(room)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("atropos: socket failed in room %s", room.code)
    finally:
        if room.sockets.get(player.pid) is websocket:
            room.sockets.pop(player.pid, None)
            player.connected = False
            # A player who drops before the game starts gives up their seat.
            if room.phase is Phase.LOBBY:
                room.remove_player(player.pid)
            try:
                await broadcast(room)
            except Exception:
                pass


async def handle(room: Room, player: Any, message: Dict[str, Any], websocket: WebSocket) -> bool:
    """Apply one client message. Returns True when the room should be rebroadcast."""
    kind = message.get("t")
    target: str = message.get("target") or ""

    if kind == "ping":
        await websocket.send_json({"t": "pong"})
        return False

    if kind == "start":
        if not player.is_host or room.phase is not Phase.LOBBY:
            return False
        try:
            room.start()
        except ValueError as exc:
            await websocket.send_json({"t": "error", "code": "too_few", "message": str(exc)})
            return False
        ensure_clock(room)
        return True

    if kind == "again":
        if player.is_host and room.phase is Phase.OVER:
            room.reset_to_lobby()
            return True
        return False

    if kind == "cut":
        room.act_cut(player, target, message.get("manner"), message.get("decree"))
        return True

    if kind == "measure":
        room.act_measure(player, target)
        return True

    if kind == "obey":
        room.act_obey(player)
        return True

    if kind == "vote":
        room.act_vote(player, target)
        return True

    if kind == "say":
        room.act_say(player, message.get("text"))
        return True

    if kind == "call":
        room.act_call(player, message.get("index"))
        return True

    if kind == "omen":
        room.act_omen(player, message.get("index"))
        return True

    if kind == "react":
        room.act_react(player, message.get("symbol") or "")
        return True

    # Walking is high frequency and rides the movement frame, so it must not
    # trigger a full state rebroadcast.
    if kind == "move":
        room.act_move(player, message.get("x"), message.get("z"),
                      message.get("a"), message.get("m"))
        return False

    if kind == "emote":
        room.act_emote(player, message.get("name"))
        return False

    if kind == "eidolon":
        room.act_eidolon(player, message.get("face"), message.get("colors"))
        await send_eidolons(room)
        return True

    return False
