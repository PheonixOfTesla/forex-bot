"""
Engine API Routes

Provides endpoints for monitoring and controlling the trading engine.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..schemas import (
    EngineComponent,
    EngineComponentStatus,
    EngineStatus,
    EngineStatusResponse,
    StatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Engine State (Replace with actual engine state management)
# =============================================================================


class EngineState:
    """In-memory engine state for development."""

    def __init__(self):
        self.status: EngineStatus = EngineStatus.RUNNING
        self.started_at: datetime = datetime.utcnow()
        self.last_pause_at: Optional[datetime] = None
        self.last_emergency_stop_at: Optional[datetime] = None

        # Component states
        self.components = {
            "websocket_feed": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Connected to OANDA price stream",
                "metrics": {
                    "messages_received": 15243,
                    "last_price_update": datetime.utcnow().isoformat(),
                    "latency_ms": 12,
                },
            },
            "feature_engine": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Computing features for 8 pairs",
                "metrics": {
                    "features_computed": 8456,
                    "avg_computation_ms": 3.2,
                    "cache_hit_rate": 0.92,
                },
            },
            "ml_classifier": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Model v2.3.1 loaded",
                "metrics": {
                    "predictions_made": 1024,
                    "avg_inference_ms": 8.5,
                    "model_version": "v2.3.1",
                },
            },
            "risk_manager": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Risk limits within bounds",
                "metrics": {
                    "current_exposure_pct": 12.5,
                    "daily_loss_pct": 0.8,
                    "max_drawdown_pct": 3.2,
                    "positions_checked": 847,
                },
            },
            "order_executor": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Connected to OANDA execution API",
                "metrics": {
                    "orders_placed": 12,
                    "orders_filled": 12,
                    "avg_fill_time_ms": 45,
                    "slippage_avg": 0.1,
                },
            },
            "logger": {
                "status": EngineComponentStatus.RUNNING,
                "last_heartbeat": datetime.utcnow(),
                "message": "Logging to PostgreSQL and file",
                "metrics": {
                    "logs_written": 45632,
                    "errors_logged": 3,
                    "warnings_logged": 18,
                },
            },
        }

        # Activity metrics
        self.signals_generated_today = 18
        self.trades_executed_today = 12
        self.errors_today = 3
        self.last_signal_at = datetime.utcnow() - timedelta(minutes=3)
        self.last_trade_at = datetime.utcnow() - timedelta(minutes=15)


# Global engine state
_engine_state = EngineState()


# =============================================================================
# Helper Functions
# =============================================================================


def _get_component(name: str) -> EngineComponent:
    """Get engine component as EngineComponent model."""
    comp = _engine_state.components.get(name, {})
    return EngineComponent(
        name=name,
        status=comp.get("status", EngineComponentStatus.STOPPED),
        last_heartbeat=comp.get("last_heartbeat"),
        message=comp.get("message"),
        metrics=comp.get("metrics", {}),
    )


def _update_component_status(name: str, status: EngineComponentStatus, message: str = None):
    """Update a component's status."""
    if name in _engine_state.components:
        _engine_state.components[name]["status"] = status
        _engine_state.components[name]["last_heartbeat"] = datetime.utcnow()
        if message:
            _engine_state.components[name]["message"] = message


# =============================================================================
# Engine Endpoints
# =============================================================================


@router.get("/engine/status", response_model=EngineStatusResponse)
async def get_engine_status() -> EngineStatusResponse:
    """
    Get comprehensive engine status.

    Returns status of all engine components:
    - WebSocket price feed
    - Feature computation engine
    - ML classifier
    - Risk manager
    - Order executor
    - Logger

    Also includes activity metrics like signals generated and trades executed.
    """
    logger.info("Fetching engine status")

    uptime = int((datetime.utcnow() - _engine_state.started_at).total_seconds())

    return EngineStatusResponse(
        status=_engine_state.status,
        uptime_seconds=uptime,
        started_at=_engine_state.started_at,
        websocket_feed=_get_component("websocket_feed"),
        feature_engine=_get_component("feature_engine"),
        ml_classifier=_get_component("ml_classifier"),
        risk_manager=_get_component("risk_manager"),
        order_executor=_get_component("order_executor"),
        logger=_get_component("logger"),
        signals_generated_today=_engine_state.signals_generated_today,
        trades_executed_today=_engine_state.trades_executed_today,
        errors_today=_engine_state.errors_today,
        last_signal_at=_engine_state.last_signal_at,
        last_trade_at=_engine_state.last_trade_at,
    )


@router.post("/engine/pause", response_model=StatusResponse)
async def pause_engine() -> StatusResponse:
    """
    Pause the trading engine.

    Pauses signal generation and trade execution while keeping
    the price feed and monitoring active.

    Open positions are NOT affected.
    """
    logger.info("Pausing engine")

    if _engine_state.status == EngineStatus.EMERGENCY_STOP:
        raise HTTPException(
            status_code=400,
            detail="Cannot pause engine in emergency stop state. Use resume first.",
        )

    if _engine_state.status == EngineStatus.PAUSED:
        return StatusResponse(
            success=True,
            status=EngineStatus.PAUSED,
            message="Engine is already paused",
            timestamp=datetime.utcnow(),
        )

    # Update state
    _engine_state.status = EngineStatus.PAUSED
    _engine_state.last_pause_at = datetime.utcnow()

    # Update component statuses
    _update_component_status("ml_classifier", EngineComponentStatus.STOPPED, "Paused by user")
    _update_component_status("order_executor", EngineComponentStatus.STOPPED, "Paused by user")

    logger.info("Engine paused successfully")

    return StatusResponse(
        success=True,
        status=EngineStatus.PAUSED,
        message="Engine paused. Signal generation and execution stopped. Monitoring continues.",
        timestamp=datetime.utcnow(),
    )


@router.post("/engine/resume", response_model=StatusResponse)
async def resume_engine() -> StatusResponse:
    """
    Resume the trading engine.

    Resumes signal generation and trade execution from a paused
    or emergency stop state.
    """
    logger.info("Resuming engine")

    if _engine_state.status == EngineStatus.RUNNING:
        return StatusResponse(
            success=True,
            status=EngineStatus.RUNNING,
            message="Engine is already running",
            timestamp=datetime.utcnow(),
        )

    # Update state
    _engine_state.status = EngineStatus.RUNNING

    # Update component statuses
    _update_component_status("ml_classifier", EngineComponentStatus.RUNNING, "Model v2.3.1 loaded")
    _update_component_status("order_executor", EngineComponentStatus.RUNNING, "Connected to OANDA execution API")

    logger.info("Engine resumed successfully")

    return StatusResponse(
        success=True,
        status=EngineStatus.RUNNING,
        message="Engine resumed. Full trading operations active.",
        timestamp=datetime.utcnow(),
    )


@router.post("/engine/emergency-stop", response_model=StatusResponse)
async def emergency_stop() -> StatusResponse:
    """
    Emergency stop the trading engine.

    Immediately stops all trading activity:
    - Cancels all pending orders
    - Closes all open positions (if configured)
    - Stops signal generation
    - Stops order execution

    WARNING: This is an emergency action. Use pause for normal suspension.
    """
    logger.warning("EMERGENCY STOP initiated")

    # Update state
    _engine_state.status = EngineStatus.EMERGENCY_STOP
    _engine_state.last_emergency_stop_at = datetime.utcnow()

    # Stop all components
    for name in _engine_state.components:
        _update_component_status(
            name,
            EngineComponentStatus.STOPPED,
            "Emergency stop"
        )

    # TODO: Actually cancel pending orders
    # TODO: Optionally close all positions

    logger.warning("Emergency stop completed")

    return StatusResponse(
        success=True,
        status=EngineStatus.EMERGENCY_STOP,
        message="EMERGENCY STOP executed. All trading activity halted. Use /engine/resume to restart.",
        timestamp=datetime.utcnow(),
    )


@router.get("/engine/components/{component_name}")
async def get_component_status(component_name: str):
    """
    Get detailed status of a specific engine component.

    Args:
        component_name: Component name (websocket_feed, feature_engine,
                        ml_classifier, risk_manager, order_executor, logger)
    """
    if component_name not in _engine_state.components:
        raise HTTPException(
            status_code=404,
            detail=f"Component not found: {component_name}. "
                   f"Available: {list(_engine_state.components.keys())}",
        )

    return _get_component(component_name)


@router.post("/engine/components/{component_name}/restart")
async def restart_component(component_name: str):
    """
    Restart a specific engine component.

    Args:
        component_name: Component to restart
    """
    if component_name not in _engine_state.components:
        raise HTTPException(
            status_code=404,
            detail=f"Component not found: {component_name}",
        )

    logger.info(f"Restarting component: {component_name}")

    # Simulate restart
    _update_component_status(component_name, EngineComponentStatus.STOPPED, "Restarting...")

    # TODO: Actually restart the component

    _update_component_status(component_name, EngineComponentStatus.RUNNING, "Restarted successfully")

    return {
        "success": True,
        "component": component_name,
        "status": EngineComponentStatus.RUNNING.value,
        "message": f"Component {component_name} restarted successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/engine/health")
async def get_engine_health():
    """
    Get engine health summary.

    Returns a quick health check suitable for monitoring systems.
    """
    # Check component health
    healthy_components = sum(
        1 for c in _engine_state.components.values()
        if c["status"] == EngineComponentStatus.RUNNING
    )
    total_components = len(_engine_state.components)

    # Determine overall health
    if _engine_state.status == EngineStatus.EMERGENCY_STOP:
        health = "critical"
    elif healthy_components == total_components and _engine_state.status == EngineStatus.RUNNING:
        health = "healthy"
    elif healthy_components > total_components // 2:
        health = "degraded"
    else:
        health = "unhealthy"

    return {
        "health": health,
        "status": _engine_state.status.value,
        "components_healthy": healthy_components,
        "components_total": total_components,
        "uptime_seconds": int((datetime.utcnow() - _engine_state.started_at).total_seconds()),
        "errors_today": _engine_state.errors_today,
        "timestamp": datetime.utcnow().isoformat(),
    }
