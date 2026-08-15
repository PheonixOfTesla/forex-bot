from __future__ import annotations

"""
ATROPOS - Multiplayer Social Deduction Engine

Named for the eldest Moira: the Fate who chooses the manner of an ending and
cuts the thread. A mafia variant built for a room full of people holding phones
- summer camp, dorm lounge, family table.

Roles
    ATROPOS   - cuts one thread each Loom. Wins with NYX.
    LACHESIS  - measures one thread each Loom, learns ATROPOS / NOT ATROPOS.
    NYX       - knows Atropos, holds no shears, wins with Atropos.
    MORTAL    - no power but judgement. Wins by casting every Atropos out.

ATROPOS is a mantle, not a person - whoever draws it wears the name, the same
way "Kira" was an alias rather than a body. All copy stays neutral.

Phase loop
    LOBBY -> LOOM -> DECREE -> AGORA -> VERDICT -> (LOOM | OVER)

The DECREE phase is what makes this a party game rather than a browser game.
The cut player is told privately that they have forty seconds, and is handed an
instruction to carry out loud, in the actual room. The instruction is published
to every screen with no name attached, so everyone watches to see who obeys.
Then the thread snaps and the identity lands.

Dying is not an exit. Shades see every role and get one anonymous Omen to spend
on the living, which keeps eliminated players louder than the survivors.

Design constraints for a mixed-age camp audience:
  - No free-text chat. Discussion happens out loud in the room; the phone
    carries only secret actions, votes, and a fixed list of table calls. Nothing
    unmoderated can reach another player's screen.
  - Every manner of death is mythic and bloodless.
  - Every screen carries a plain-language instruction next to the flavour.

This module is transport-agnostic; the WebSocket plumbing lives in
routes/game.py.
"""

import asyncio
import logging
import math
import random
import re
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Ambiguous glyphs removed so a code survives being shouted across a mess hall.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5

MIN_PLAYERS = 4
MAX_PLAYERS = 16
MAX_NAME_LENGTH = 14
MAX_LOG_ENTRIES = 160

# Phase durations in seconds. Tuned so a whole game runs about seven minutes.
LOOM_SECONDS = 40
DECREE_SECONDS = 40
AGORA_SECONDS = 105
VERDICT_SECONDS = 10
OVER_SECONDS = 90

# Rooms with nobody connected for this long are reaped.
ROOM_IDLE_TIMEOUT = 3600

# Every ending is mythic and bloodless. Nothing here needs a content warning.
MANNERS = [
    "the thread ran out",
    "a long sleep",
    "the sea took them",
    "the ground opened",
    "a fever, sudden",
    "a door that would not open",
    "the wind, and nothing else",
    "a star fell on them",
]

# Decrees are performed out loud, in the room. That is the entire point of them.
# Fixed list: nothing a player types can ever reach another player's screen.
DECREES = [
    "Stand up and accuse someone.",
    "Say 'I am not Atropos' three times.",
    "Compliment the person you suspect most.",
    "Laugh out loud at nothing.",
    "Swap seats with someone.",
    "Whisper to the person on your left.",
    "Point at someone. Say nothing.",
    "Stay silent for the whole Agora.",
    "Do your best evil laugh.",
    "Speak only in questions this round.",
    "Clap three times, slowly.",
    "Tell the room your favourite animal. Sound deadly serious.",
]

# Table calls let a quiet player join the argument without typing anything.
CALLS = [
    "It's you. I know it.",
    "I'm clean, I swear.",
    "They're too quiet.",
    "That was a lie.",
    "Trust me this once.",
    "I saw something.",
    "I'm changing my vote.",
    "Nobody move.",
]

# A Shade's one anonymous message to the living.
OMENS = [
    "One of you is lying right now.",
    "You are looking the wrong way.",
    "The quiet one is quiet for a reason.",
    "You had it right, and you let go.",
    "Count the votes again.",
    "Two of them are working together.",
]

REACTIONS = ["eye", "flame", "hand", "skull"]

EMOTES = ["wave", "dance", "point", "sit", "cheer", "shrug"]

# The village players walk around in, in world units.
VILLAGE_RADIUS = 26.0
SPAWN_RADIUS = 7.0

# A face thumbnail is relayed to every player, so it is hard-capped. The client
# sends roughly a 128px cel-shaded JPEG, which lands near 6 KB.
MAX_EIDOLON_BYTES = 24000

# The shape of an Eidolon, mirroring web/atropos/avatar.js. Kept as explicit
# whitelists so a client cannot inject arbitrary strings into other players'
# renderers.
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
EIDOLON_COLOR_KEYS = ("skin", "hair", "shirt", "pants", "shoes", "hatColor")
EIDOLON_STYLE_KEYS = {
    "hairStyle": {"crop", "buzz", "bob", "long", "ponytail", "curls", "bun", "topknot"},
    "eyes": {"round", "almond", "wide", "happy", "sleepy", "wink"},
    "brows": {"soft", "flat", "arched", "thick"},
    "mouth": {"smile", "grin", "smirk", "open", "calm"},
    "hatStyle": {"cap", "capBack"},
}


class Phase(str, Enum):
    LOBBY = "lobby"
    LOOM = "loom"
    DECREE = "decree"
    AGORA = "agora"
    VERDICT = "verdict"
    OVER = "over"


class Role(str, Enum):
    ATROPOS = "atropos"
    LACHESIS = "lachesis"
    NYX = "nyx"
    MORTAL = "mortal"


ROLE_TITLES = {
    Role.ATROPOS: "ATROPOS",
    Role.LACHESIS: "LACHESIS",
    Role.NYX: "NYX",
    Role.MORTAL: "MORTAL",
}

# Flavour first, then the plain-language version an eight-year-old can act on.
ROLE_BLURBS = {
    Role.ATROPOS: "You hold the shears.",
    Role.LACHESIS: "You measure what others only guess at.",
    Role.NYX: "You are the dark they work under.",
    Role.MORTAL: "You have no gift. Only the room.",
}

ROLE_HOWTO = {
    Role.ATROPOS: "Each night, pick one player to cut and an order for them to obey. Don't get caught.",
    Role.LACHESIS: "Each night, pick one player. You'll be told if they are Atropos. Nobody else finds out.",
    Role.NYX: "You already know who Atropos is. You can't cut anyone. Lie for them and stay alive.",
    Role.MORTAL: "You have no night action. Listen, argue out loud, and vote for who you think is Atropos.",
}


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def clean_name(value: Any) -> str:
    """Collapse whitespace, strip control characters, clamp length, uppercase."""
    if not isinstance(value, str):
        return ""
    kept = "".join(ch for ch in value if ch.isprintable())
    return " ".join(kept.split())[:MAX_NAME_LENGTH].upper()


def pick(options: List[str], index: Any) -> str:
    """Resolve a client-supplied index into a fixed list. Falls back to random."""
    if isinstance(index, int) and 0 <= index < len(options):
        return options[index]
    return random.choice(options)


# =============================================================================
# Players
# =============================================================================


@dataclass
class Player:
    pid: str
    secret: str
    name: str
    seat: int
    is_host: bool = False
    role: Role = Role.MORTAL
    alive: bool = True
    connected: bool = True

    # Per-round scratch state.
    vote: Optional[str] = None
    obeyed: bool = False
    reaction: Optional[str] = None

    # Where they are standing in the village, and which way they face.
    x: float = 0.0
    z: float = 0.0
    angle: float = 0.0
    moving: bool = False
    emote: Optional[str] = None

    # Their Eidolon: a cel-shaded face thumbnail plus the colours pulled from it.
    eidolon: Optional[Dict[str, Any]] = None

    # Lachesis findings: round -> {"pid", "name", "atropos"}
    findings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # One anonymous message from beyond, per game.
    omen_spent: bool = False

    # How they went, once they have.
    manner: Optional[str] = None
    death_round: Optional[int] = None
    cast_out: bool = False

    @property
    def with_atropos(self) -> bool:
        return self.role in (Role.ATROPOS, Role.NYX)


# =============================================================================
# Room
# =============================================================================


class Room:
    """One game. Its phase clock is driven by a task in routes/game.py."""

    def __init__(self, code: str):
        self.code = code
        self.players: Dict[str, Player] = {}
        self.order: List[str] = []  # seating order, stable across the game
        self.phase: Phase = Phase.LOBBY
        self.round: int = 0
        self.phase_ends_at: float = 0.0
        self.log: List[Dict[str, Any]] = []
        self.winner: Optional[str] = None
        self.created_at: float = time.time()
        self.last_seen: float = time.time()

        # Loom bookkeeping.
        self.cut: Optional[str] = None
        self.cut_manner: Optional[str] = None
        self.cut_decree: Optional[str] = None
        self.decree_done: bool = False
        self.last_cut: Optional[Dict[str, Any]] = None
        self.last_verdict: Optional[Dict[str, Any]] = None

        # Transport - populated by routes/game.py.
        self.sockets: Dict[str, Any] = {}
        self.task: Optional[asyncio.Task] = None

    # -- membership ---------------------------------------------------------

    @property
    def seated(self) -> List[Player]:
        return [self.players[pid] for pid in self.order if pid in self.players]

    @property
    def living(self) -> List[Player]:
        return [p for p in self.seated if p.alive]

    def player_by_secret(self, secret: str) -> Optional[Player]:
        if not secret:
            return None
        for player in self.players.values():
            if secrets.compare_digest(player.secret, secret):
                return player
        return None

    def unique_name(self, wanted: str) -> str:
        base = clean_name(wanted) or "NAMELESS"
        taken = {p.name for p in self.players.values()}
        if base not in taken:
            return base
        for n in range(2, 100):
            candidate = f"{base} {n}"
            if candidate not in taken:
                return candidate
        return base

    def add_player(self, name: str) -> Player:
        pid = secrets.token_hex(6)
        player = Player(
            pid=pid,
            secret=secrets.token_urlsafe(24),
            name=self.unique_name(name),
            seat=len(self.order),
            is_host=not self.players,
        )
        self.players[pid] = player
        self.order.append(pid)
        self.write_log("join", f"{player.name} takes a thread.")
        return player

    def remove_player(self, pid: str) -> None:
        """Only used in the lobby. A mid-game leaver keeps their seat and thread."""
        player = self.players.pop(pid, None)
        if not player:
            return
        self.order = [x for x in self.order if x != pid]
        for index, other in enumerate(self.order):
            self.players[other].seat = index
        if player.is_host and self.order:
            self.players[self.order[0]].is_host = True
        self.write_log("leave", f"{player.name} let go.")

    # -- log ----------------------------------------------------------------

    def write_log(self, kind: str, text: str, **extra: Any) -> None:
        self.log.append({"kind": kind, "text": text, "round": self.round, "at": time.time(), **extra})
        del self.log[:-MAX_LOG_ENTRIES]

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        count = len(self.players)
        if count < MIN_PLAYERS:
            raise ValueError(f"Atropos needs at least {MIN_PLAYERS} threads.")

        pool = list(self.players.values())
        random.shuffle(pool)

        shears = 2 if count >= 11 else 1
        assignments: List[Role] = [Role.ATROPOS] * shears
        assignments.append(Role.LACHESIS)
        if count >= 7:
            assignments.append(Role.NYX)
        assignments += [Role.MORTAL] * (count - len(assignments))

        for player, role in zip(pool, assignments):
            player.role = role
            player.alive = True
            player.vote = None
            player.manner = None
            player.death_round = None
            player.cast_out = False
            player.findings = {}
            player.omen_spent = False

        self.round = 0
        self.winner = None
        self.log = []
        self.spawn_positions()
        self.write_log("system", "The shears have found a hand. Nobody knows whose.")
        self.begin_loom()

    def begin_loom(self) -> None:
        self.round += 1
        self.phase = Phase.LOOM
        self.phase_ends_at = time.time() + LOOM_SECONDS
        self.cut = None
        self.cut_manner = None
        self.cut_decree = None
        self.decree_done = False
        self.last_cut = None
        self.last_verdict = None
        for player in self.players.values():
            player.vote = None
            player.obeyed = False
            player.reaction = None
        self.write_log("phase", f"Loom {self.round}. The lights go down.")

    def begin_decree(self) -> None:
        self.phase = Phase.DECREE
        self.phase_ends_at = time.time() + DECREE_SECONDS
        self.write_log("phase", "A thread is held. Forty seconds.")
        if self.cut_decree:
            self.write_log("decree", self.cut_decree, anonymous=True)

    def begin_agora(self) -> None:
        self.phase = Phase.AGORA
        self.phase_ends_at = time.time() + AGORA_SECONDS
        for player in self.players.values():
            player.vote = None
        self.write_log("phase", f"Agora {self.round}. Speak, and be counted.")

    def begin_verdict(self) -> None:
        self.phase = Phase.VERDICT
        self.phase_ends_at = time.time() + VERDICT_SECONDS

    def finish(self, winner: str) -> None:
        self.phase = Phase.OVER
        self.winner = winner
        self.phase_ends_at = time.time() + OVER_SECONDS
        if winner == "atropos":
            self.write_log("system", "The room is quiet. The shears are kept.")
        else:
            self.write_log("system", "The shears are broken. The thread runs on.")

    # -- actions ------------------------------------------------------------

    def act_cut(self, actor: Player, target_pid: str, manner_index: Any, decree_index: Any) -> None:
        if self.phase is not Phase.LOOM or actor.role is not Role.ATROPOS or not actor.alive:
            return
        target = self.players.get(target_pid)
        if not target or not target.alive or target.pid == actor.pid:
            return
        self.cut = target.pid
        self.cut_manner = pick(MANNERS, manner_index)
        self.cut_decree = pick(DECREES, decree_index)

    def act_measure(self, actor: Player, target_pid: str) -> None:
        if self.phase is not Phase.LOOM or actor.role is not Role.LACHESIS or not actor.alive:
            return
        if str(self.round) in actor.findings:
            return
        target = self.players.get(target_pid)
        if not target or target.pid == actor.pid or not target.alive:
            return
        actor.findings[str(self.round)] = {
            "pid": target.pid,
            "name": target.name,
            "atropos": target.role is Role.ATROPOS,
        }

    def act_obey(self, actor: Player) -> None:
        """The cut player confirms they performed their decree in the room."""
        if self.phase is not Phase.DECREE or actor.pid != self.cut or actor.obeyed:
            return
        actor.obeyed = True
        self.decree_done = True

    def act_call(self, actor: Player, index: Any) -> None:
        """A fixed table call, so a quiet player can still join the argument."""
        if not isinstance(index, int) or not 0 <= index < len(CALLS):
            return
        if not actor.alive:
            self.write_log("shade", CALLS[index], who=actor.name, seat=actor.seat)
        elif self.phase in (Phase.AGORA, Phase.LOBBY, Phase.OVER):
            self.write_log("call", CALLS[index], who=actor.name, seat=actor.seat)

    def act_omen(self, actor: Player, index: Any) -> None:
        """One anonymous message from a Shade to the living, once per game."""
        if actor.alive or actor.omen_spent or self.phase is not Phase.AGORA:
            return
        if not isinstance(index, int) or not 0 <= index < len(OMENS):
            return
        actor.omen_spent = True
        self.write_log("omen", OMENS[index], anonymous=True)

    def act_vote(self, actor: Player, target_pid: str) -> None:
        if self.phase is not Phase.AGORA or not actor.alive:
            return
        if not target_pid:
            actor.vote = None
            return
        target = self.players.get(target_pid)
        if not target or not target.alive:
            return
        # Tapping the same player again takes the vote back.
        actor.vote = None if actor.vote == target.pid else target.pid

    def act_react(self, actor: Player, symbol: str) -> None:
        if symbol in REACTIONS:
            actor.reaction = symbol

    def act_move(self, actor: Player, x: Any, z: Any, angle: Any, moving: Any) -> None:
        """Walk. Clamped to the village so nobody can wander off the island."""
        try:
            nx, nz, na = float(x), float(z), float(angle)
        except (TypeError, ValueError):
            return
        if not all(map(math.isfinite, (nx, nz, na))):
            return
        radius = math.hypot(nx, nz)
        if radius > VILLAGE_RADIUS:
            nx *= VILLAGE_RADIUS / radius
            nz *= VILLAGE_RADIUS / radius
        actor.x, actor.z, actor.angle = nx, nz, na
        actor.moving = bool(moving)

    def act_emote(self, actor: Player, name: Any) -> None:
        actor.emote = name if name in EMOTES else None

    def act_eidolon(self, actor: Player, face: Any, colors: Any) -> None:
        """
        Store a player's Eidolon.

        Everything here is relayed to every other player, so nothing is trusted:
        colours must match a hex pattern, every style must be one of a known
        set, and the optional face thumbnail is both size-capped and required to
        be a data URL. Anything that fails simply does not make it into the
        record.
        """
        safe: Dict[str, Any] = {}

        if isinstance(face, str) and face.startswith("data:image/") and len(face) <= MAX_EIDOLON_BYTES:
            safe["face"] = face

        if isinstance(colors, dict):
            for key in EIDOLON_COLOR_KEYS:
                value = colors.get(key)
                if isinstance(value, str) and HEX_COLOR.fullmatch(value):
                    safe[key] = value
            for key, allowed in EIDOLON_STYLE_KEYS.items():
                value = colors.get(key)
                if isinstance(value, str) and value in allowed:
                    safe[key] = value
            if isinstance(colors.get("glasses"), bool):
                safe["glasses"] = colors["glasses"]

        # A record with nothing valid in it is not worth relaying.
        if safe:
            actor.eidolon = safe

    def spawn_positions(self) -> None:
        """Stand everyone in a ring in the square, facing the middle."""
        seated = self.seated
        for index, player in enumerate(seated):
            a = (index / max(1, len(seated))) * math.tau
            player.x = math.cos(a) * SPAWN_RADIUS
            player.z = math.sin(a) * SPAWN_RADIUS
            player.angle = a + math.pi
            player.moving = False
            player.emote = None

    def positions(self) -> List[List[Any]]:
        """The lightweight movement frame, sent far more often than full state."""
        return [
            [p.pid, round(p.x, 2), round(p.z, 2), round(p.angle, 2),
             1 if p.moving else 0, 1 if p.alive else 0, p.emote or ""]
            for p in self.seated
        ]

    def eidolons(self) -> Dict[str, Any]:
        return {p.pid: p.eidolon for p in self.seated if p.eidolon}

    # -- resolution ---------------------------------------------------------

    def resolve_loom(self) -> None:
        if self.cut:
            self.begin_decree()
        else:
            self.write_log("system", "No thread was taken tonight.")
            self.begin_agora()

    def resolve_decree(self) -> None:
        victim = self.players.get(self.cut or "")
        if victim and victim.alive:
            victim.alive = False
            victim.manner = self.cut_manner
            victim.death_round = self.round
            self.last_cut = {
                "pid": victim.pid,
                "name": victim.name,
                "seat": victim.seat,
                "manner": self.cut_manner,
                "decree": self.cut_decree,
                "obeyed": victim.obeyed,
            }
            tail = "" if victim.obeyed else " They refused, and it made no difference."
            self.write_log(
                "cut",
                f"{victim.name} - {self.cut_manner}.{tail}",
                who=victim.name,
                seat=victim.seat,
            )
        if not self.check_winner():
            self.begin_agora()

    def tally(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for player in self.living:
            if player.vote:
                counts[player.vote] = counts.get(player.vote, 0) + 1
        return counts

    def resolve_agora(self) -> None:
        counts = self.tally()
        chosen: Optional[Player] = None
        if counts:
            top = max(counts.values())
            leaders = [pid for pid, n in counts.items() if n == top]
            # A tie is not a majority. Nobody is cast out on a tie.
            if len(leaders) == 1 and top > len(self.living) / 2:
                chosen = self.players.get(leaders[0])

        if chosen:
            chosen.alive = False
            chosen.cast_out = True
            chosen.manner = "cast out by the Agora"
            chosen.death_round = self.round
            self.last_verdict = {
                "pid": chosen.pid,
                "name": chosen.name,
                "seat": chosen.seat,
                "role": chosen.role.value,
                "title": ROLE_TITLES[chosen.role],
                "votes": counts.get(chosen.pid, 0),
                "correct": chosen.role is Role.ATROPOS,
            }
            self.write_log(
                "verdict",
                f"{chosen.name} is cast out. {self.role_reveal(chosen)}",
                who=chosen.name,
                seat=chosen.seat,
            )
        else:
            self.last_verdict = None
            self.write_log("system", "No majority. The Agora breaks with nothing.")

        self.begin_verdict()

    @staticmethod
    def role_reveal(player: Player) -> str:
        if player.role is Role.ATROPOS:
            return "The shears fall from their hand."
        if player.role is Role.NYX:
            return "They kept the dark for the shears."
        if player.role is Role.LACHESIS:
            return "They were the one who measured."
        return "Their hands were empty."

    def check_winner(self) -> bool:
        living = self.living
        shears = [p for p in living if p.role is Role.ATROPOS]
        theirs = [p for p in living if p.with_atropos]
        ours = [p for p in living if not p.with_atropos]
        if not shears:
            self.finish("mortals")
            return True
        if len(theirs) >= len(ours):
            self.finish("atropos")
            return True
        return False

    def advance(self) -> None:
        """Called when the phase clock expires or every action is in."""
        if self.phase is Phase.LOOM:
            self.resolve_loom()
        elif self.phase is Phase.DECREE:
            self.resolve_decree()
        elif self.phase is Phase.AGORA:
            self.resolve_agora()
        elif self.phase is Phase.VERDICT:
            if not self.check_winner():
                self.begin_loom()
        elif self.phase is Phase.OVER:
            self.reset_to_lobby()

    def reset_to_lobby(self) -> None:
        self.phase = Phase.LOBBY
        self.round = 0
        self.winner = None
        self.cut = None
        self.last_cut = None
        self.last_verdict = None
        self.log = []
        for player in self.players.values():
            player.alive = True
            player.role = Role.MORTAL
            player.vote = None
            player.manner = None
            player.cast_out = False
            player.reaction = None
            player.findings = {}
            player.omen_spent = False
        self.write_log("system", "New thread. Same shears.")

    def everyone_acted(self) -> bool:
        """Lets a phase end early once there is nothing left to wait for."""
        if self.phase is Phase.LOOM:
            shears_done = self.cut is not None or not any(
                p.alive and p.role is Role.ATROPOS for p in self.players.values()
            )
            measurer = next((p for p in self.living if p.role is Role.LACHESIS), None)
            measure_done = measurer is None or str(self.round) in measurer.findings
            return shears_done and measure_done
        if self.phase is Phase.DECREE:
            return self.decree_done
        if self.phase is Phase.AGORA:
            living = self.living
            return bool(living) and all(p.vote for p in living)
        return False

    # -- serialisation ------------------------------------------------------

    def public_players(self) -> List[Dict[str, Any]]:
        over = self.phase is Phase.OVER
        return [
            {
                "pid": p.pid,
                "name": p.name,
                "seat": p.seat,
                "alive": p.alive,
                "connected": p.connected,
                "host": p.is_host,
                "manner": p.manner,
                "castOut": p.cast_out,
                "reaction": p.reaction,
                "hasEidolon": p.eidolon is not None,
                # Roles become public only when the game is over.
                "role": p.role.value if over else None,
                "title": ROLE_TITLES[p.role] if over else None,
            }
            for p in self.seated
        ]

    def snapshot_for(self, viewer: Optional[Player]) -> Dict[str, Any]:
        """Build the personalised view. Secret knowledge is added here and nowhere else."""
        remaining = 0.0
        if self.phase is not Phase.LOBBY:
            remaining = max(0.0, self.phase_ends_at - time.time())

        # Shades read the shade channel; the living never receive it.
        as_shade = viewer is not None and not viewer.alive and self.phase is not Phase.LOBBY
        visible_log = [e for e in self.log[-70:] if e["kind"] != "shade" or as_shade]

        state: Dict[str, Any] = {
            "t": "state",
            "code": self.code,
            "phase": self.phase.value,
            "round": self.round,
            "remaining": round(remaining, 1),
            "duration": self.phase_duration(),
            "players": self.public_players(),
            "winner": self.winner,
            "minPlayers": MIN_PLAYERS,
            "maxPlayers": MAX_PLAYERS,
            "manners": MANNERS,
            "decrees": DECREES,
            "calls": CALLS,
            "omens": OMENS,
            "lastCut": self.last_cut,
            "lastVerdict": self.last_verdict,
            "log": visible_log,
        }

        if self.phase is Phase.AGORA:
            # Votes are public as they land - the pile-on is half the fun.
            state["votes"] = {p.pid: p.vote for p in self.living if p.vote}

        if not viewer:
            return state

        playing = self.phase is not Phase.LOBBY
        me: Dict[str, Any] = {
            "pid": viewer.pid,
            "name": viewer.name,
            "seat": viewer.seat,
            "alive": viewer.alive,
            "host": viewer.is_host,
            "vote": viewer.vote,
            "role": viewer.role.value if playing else None,
            "title": ROLE_TITLES[viewer.role] if playing else None,
            "blurb": ROLE_BLURBS[viewer.role] if playing else None,
            "howto": ROLE_HOWTO[viewer.role] if playing else None,
        }

        if playing:
            if viewer.role is Role.ATROPOS and viewer.alive:
                me["cut"] = self.cut
                me["manner"] = self.cut_manner
                me["decree"] = self.cut_decree
            if viewer.role is Role.LACHESIS:
                me["findings"] = [
                    {"round": rnd, **data} for rnd, data in sorted(viewer.findings.items())
                ]
                me["measured"] = str(self.round) in viewer.findings
            if viewer.role is Role.NYX:
                me["knows"] = [p.pid for p in self.seated if p.role is Role.ATROPOS]
            if not viewer.alive:
                # Dying buys you the truth. It is the whole compensation.
                me["revealed"] = {p.pid: p.role.value for p in self.seated}
                me["omenSpent"] = viewer.omen_spent

        # Only the cut player learns they are cut, and only inside the window.
        if self.phase is Phase.DECREE and viewer.pid == self.cut:
            me["condemned"] = {
                "decree": self.cut_decree,
                "manner": self.cut_manner,
                "obeyed": viewer.obeyed,
            }

        state["me"] = me
        return state

    def phase_duration(self) -> int:
        return {
            Phase.LOOM: LOOM_SECONDS,
            Phase.DECREE: DECREE_SECONDS,
            Phase.AGORA: AGORA_SECONDS,
            Phase.VERDICT: VERDICT_SECONDS,
            Phase.OVER: OVER_SECONDS,
        }.get(self.phase, 0)


# =============================================================================
# Registry
# =============================================================================


class Registry:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create(self) -> Room:
        self.reap()
        for _ in range(20):
            code = new_code()
            if code not in self.rooms:
                room = Room(code)
                self.rooms[code] = room
                logger.info("atropos: room %s opened", code)
                return room
        raise RuntimeError("Could not allocate a room code.")

    def get(self, code: str) -> Optional[Room]:
        return self.rooms.get((code or "").strip().upper())

    def reap(self) -> None:
        now = time.time()
        stale = [
            code
            for code, room in self.rooms.items()
            if not room.sockets and now - room.last_seen > ROOM_IDLE_TIMEOUT
        ]
        for code in stale:
            room = self.rooms.pop(code, None)
            if room and room.task:
                room.task.cancel()
            logger.info("atropos: room %s reaped", code)


registry = Registry()
