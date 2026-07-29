from __future__ import annotations

"""
Autopilot API Routes

Control and monitor the autonomous self-testing engine that paper trades
the system's own signals and feeds outcomes back into the learning engine.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.autopilot import get_autopilot

logger = logging.getLogger(__name__)
router = APIRouter()


class AutopilotConfigRequest(BaseModel):
    """Runtime configuration update for the autopilot."""
    cycle_seconds: Optional[float] = Field(None, gt=0, description="Seconds between cycles")
    scan_every_cycles: Optional[int] = Field(None, ge=1, description="Scan for new trades every N cycles")
    min_confidence: Optional[float] = Field(None, ge=0, le=100, description="Minimum signal confidence to execute")
    max_open_positions: Optional[int] = Field(None, ge=1, le=50, description="Maximum concurrent paper positions")
    max_trade_age_hours: Optional[float] = Field(None, gt=0, description="Force-close trades older than this")
    pair_filter_min_trades: Optional[int] = Field(None, ge=1, description="Trades required before a pair can be filtered")
    pair_filter_win_rate_cutoff: Optional[float] = Field(None, ge=0, le=100, description="Skip pairs below this learned win rate")


@router.get("/autopilot/status")
async def get_autopilot_status():
    """
    Get autopilot status, progress, and the learned configuration.

    Includes cycle counts, trades opened/closed, the paper account summary,
    and the current highest-effect configuration derived from outcomes
    (indicator weights, best pairs, best setups, direction bias).
    """
    return get_autopilot().get_status()


@router.post("/autopilot/start")
async def start_autopilot():
    """Start the autopilot background loop."""
    autopilot = get_autopilot()
    started = autopilot.start()
    return {
        "success": True,
        "message": "Autopilot started" if started else "Autopilot already running",
        "running": True,
        "mode": autopilot.mode,
    }


@router.post("/autopilot/stop")
async def stop_autopilot():
    """Stop the autopilot background loop."""
    autopilot = get_autopilot()
    stopped = await autopilot.stop()
    return {
        "success": True,
        "message": "Autopilot stopped" if stopped else "Autopilot was not running",
        "running": False,
    }


@router.post("/autopilot/config")
async def update_autopilot_config(request: AutopilotConfigRequest):
    """Update autopilot runtime configuration."""
    try:
        config = get_autopilot().update_config(**request.model_dump(exclude_none=True))
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"Failed to update autopilot config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autopilot/cycle")
async def run_single_cycle():
    """
    Run one autopilot cycle immediately (useful for testing).
    """
    autopilot = get_autopilot()
    await autopilot.run_cycle()
    return {
        "success": True,
        "cycle_count": autopilot._cycle_count,
        "trades_opened": autopilot._trades_opened,
        "trades_closed": autopilot._trades_closed,
    }
