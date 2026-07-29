from __future__ import annotations

"""
Strategy Lab API Routes

Monitor and control the mass strategy tester: thousands of candidate
strategy configurations are backtested per batch, the best ones survive
on a leaderboard, and the champion configuration is promoted into the
live signal engine.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.autopilot import get_autopilot
from ...services.strategy_lab import get_strategy_lab

logger = logging.getLogger(__name__)
router = APIRouter()


class LabConfigRequest(BaseModel):
    """Runtime configuration for the strategy lab schedule."""
    lab_enabled: Optional[bool] = Field(None, description="Enable/disable scheduled batches")
    lab_batch_size: Optional[int] = Field(None, ge=10, le=20000, description="Variants per batch")
    lab_interval_minutes: Optional[float] = Field(None, ge=1, description="Minutes between batches")
    lab_auto_apply_champion: Optional[bool] = Field(None, description="Auto-apply champion to the signal engine")


@router.get("/lab/status")
async def get_lab_status():
    """
    Get strategy lab status: totals, throughput, champion, and leaderboard.
    """
    return get_strategy_lab().get_status()


@router.get("/lab/leaderboard")
async def get_lab_leaderboard(
    limit: int = Query(default=20, ge=1, le=20),
):
    """
    Get the current strategy leaderboard (best tested variants first).
    """
    status = get_strategy_lab().get_status()
    return {
        "leaderboard": status["leaderboard"][:limit],
        "champion": status["champion"],
        "total_variants_tested": status["total_variants_tested"],
    }


@router.post("/lab/run")
async def run_lab_batch(
    batch_size: Optional[int] = Query(
        default=None, ge=10, le=20000,
        description="Override batch size for this run",
    ),
):
    """
    Run one strategy lab batch immediately.
    """
    autopilot = get_autopilot()
    original = autopilot.lab_batch_size
    if batch_size:
        autopilot.lab_batch_size = batch_size
    try:
        summary = await autopilot._run_lab_batch()
    finally:
        autopilot.lab_batch_size = original

    if summary is None:
        raise HTTPException(status_code=500, detail=autopilot._last_error or "Batch failed")
    return summary


@router.post("/lab/apply-champion")
async def apply_champion():
    """
    Apply the current champion configuration to the live signal engine.
    """
    lab = get_strategy_lab()
    applied = lab.apply_champion()
    if not applied:
        raise HTTPException(status_code=404, detail="No champion available yet")
    return {"success": True, "champion": lab.get_status()["champion"]}


@router.post("/lab/config")
async def update_lab_config(request: LabConfigRequest):
    """
    Update the lab schedule (accelerate learning, then dial it back down).
    """
    autopilot = get_autopilot()
    config = autopilot.update_config(**request.model_dump(exclude_none=True))
    return {
        "success": True,
        "config": {
            "lab_enabled": autopilot.lab_enabled,
            "lab_batch_size": autopilot.lab_batch_size,
            "lab_interval_minutes": autopilot.lab_interval_minutes,
            "lab_auto_apply_champion": autopilot.lab_auto_apply_champion,
        },
    }
