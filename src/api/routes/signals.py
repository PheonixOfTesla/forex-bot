from __future__ import annotations

"""
Signals API Routes

Provides endpoints for ML trading signals - listing, details, execution, and skipping.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query

from ..schemas import (
    ExecutionRequest,
    ExecutionResponse,
    SignalDetailResponse,
    SignalDirection,
    SignalFeatures,
    SignalResponse,
    SignalStatus,
    SkipResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Mock Data Store (Replace with actual database)
# =============================================================================


# In-memory signal store for development
_signals_store: dict = {}


def _init_mock_signals():
    """Initialize mock signals for development."""
    global _signals_store

    if _signals_store:
        return

    mock_signals = [
        {
            "id": "sig_001",
            "pair": "EUR/USD",
            "direction": SignalDirection.BUY,
            "confidence": 87.5,
            "entry_price": 1.0845,
            "stop_loss": 1.0815,
            "take_profit": 1.0905,
            "risk_reward_ratio": 2.0,
            "status": SignalStatus.ACTIVE,
            "strategy": "momentum_breakout",
            "created_at": datetime.utcnow() - timedelta(minutes=15),
            "expires_at": datetime.utcnow() + timedelta(minutes=45),
            "features": {
                "rsi": 65.3,
                "macd": 0.0025,
                "macd_signal": 0.0018,
                "bb_position": 0.75,
                "atr": 0.0045,
                "volume_ratio": 1.35,
                "trend_strength": 72.5,
                "support_level": 1.0800,
                "resistance_level": 1.0920,
            },
            "model_version": "v2.3.1",
            "feature_importance": {
                "rsi": 0.18,
                "macd": 0.22,
                "trend_strength": 0.25,
                "volume_ratio": 0.15,
                "bb_position": 0.12,
                "atr": 0.08,
            },
            "similar_historical_trades": 45,
            "historical_win_rate": 71.2,
        },
        {
            "id": "sig_002",
            "pair": "GBP/USD",
            "direction": SignalDirection.SELL,
            "confidence": 76.2,
            "entry_price": 1.2650,
            "stop_loss": 1.2695,
            "take_profit": 1.2560,
            "risk_reward_ratio": 2.0,
            "status": SignalStatus.ACTIVE,
            "strategy": "mean_reversion",
            "created_at": datetime.utcnow() - timedelta(minutes=8),
            "expires_at": datetime.utcnow() + timedelta(minutes=52),
            "features": {
                "rsi": 78.5,
                "macd": -0.0015,
                "macd_signal": 0.0005,
                "bb_position": 0.92,
                "atr": 0.0062,
                "volume_ratio": 0.85,
                "trend_strength": 45.2,
                "support_level": 1.2540,
                "resistance_level": 1.2680,
            },
            "model_version": "v2.3.1",
            "feature_importance": {
                "rsi": 0.28,
                "bb_position": 0.25,
                "macd": 0.18,
                "trend_strength": 0.12,
                "volume_ratio": 0.10,
                "atr": 0.07,
            },
            "similar_historical_trades": 32,
            "historical_win_rate": 65.8,
        },
        {
            "id": "sig_003",
            "pair": "USD/JPY",
            "direction": SignalDirection.BUY,
            "confidence": 82.1,
            "entry_price": 149.25,
            "stop_loss": 148.85,
            "take_profit": 150.05,
            "risk_reward_ratio": 2.0,
            "status": SignalStatus.ACTIVE,
            "strategy": "trend_following",
            "created_at": datetime.utcnow() - timedelta(minutes=3),
            "expires_at": datetime.utcnow() + timedelta(minutes=57),
            "features": {
                "rsi": 58.2,
                "macd": 0.15,
                "macd_signal": 0.08,
                "bb_position": 0.55,
                "atr": 0.42,
                "volume_ratio": 1.15,
                "trend_strength": 78.3,
                "support_level": 148.50,
                "resistance_level": 150.25,
            },
            "model_version": "v2.3.1",
            "feature_importance": {
                "trend_strength": 0.30,
                "macd": 0.22,
                "rsi": 0.18,
                "volume_ratio": 0.12,
                "bb_position": 0.10,
                "atr": 0.08,
            },
            "similar_historical_trades": 58,
            "historical_win_rate": 73.5,
        },
    ]

    for sig in mock_signals:
        _signals_store[sig["id"]] = sig


# Initialize mock data
_init_mock_signals()


# =============================================================================
# Helper Functions
# =============================================================================


def _signal_to_response(signal: dict) -> SignalResponse:
    """Convert signal dict to SignalResponse."""
    return SignalResponse(
        id=signal["id"],
        pair=signal["pair"],
        direction=signal["direction"],
        confidence=signal["confidence"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        risk_reward_ratio=signal["risk_reward_ratio"],
        status=signal["status"],
        strategy=signal["strategy"],
        created_at=signal["created_at"],
        expires_at=signal.get("expires_at"),
    )


def _signal_to_detail_response(signal: dict) -> SignalDetailResponse:
    """Convert signal dict to SignalDetailResponse."""
    return SignalDetailResponse(
        id=signal["id"],
        pair=signal["pair"],
        direction=signal["direction"],
        confidence=signal["confidence"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        risk_reward_ratio=signal["risk_reward_ratio"],
        status=signal["status"],
        strategy=signal["strategy"],
        created_at=signal["created_at"],
        expires_at=signal.get("expires_at"),
        features=SignalFeatures(**signal["features"]),
        model_version=signal["model_version"],
        feature_importance=signal["feature_importance"],
        similar_historical_trades=signal["similar_historical_trades"],
        historical_win_rate=signal.get("historical_win_rate"),
        notes=signal.get("notes"),
    )


# =============================================================================
# Signal Endpoints
# =============================================================================


@router.get("/signals", response_model=List[SignalResponse])
async def get_active_signals(
    status: Optional[SignalStatus] = Query(
        default=None,
        description="Filter by signal status",
    ),
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair",
    ),
    min_confidence: Optional[float] = Query(
        default=None,
        ge=0,
        le=100,
        description="Minimum confidence threshold",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of signals to return",
    ),
) -> List[SignalResponse]:
    """
    Get list of trading signals.

    Args:
        status: Filter by signal status (active, executed, skipped, expired)
        pair: Filter by trading pair (e.g., EUR/USD)
        min_confidence: Minimum confidence threshold (0-100)
        limit: Maximum number of signals to return (1-100)

    Returns:
        List of signal summaries matching the filters.
    """
    logger.info(
        f"Fetching signals: status={status}, pair={pair}, "
        f"min_confidence={min_confidence}, limit={limit}"
    )

    # Filter signals
    signals = list(_signals_store.values())

    if status:
        signals = [s for s in signals if s["status"] == status]

    if pair:
        signals = [s for s in signals if s["pair"].upper() == pair.upper()]

    if min_confidence is not None:
        signals = [s for s in signals if s["confidence"] >= min_confidence]

    # Sort by created_at descending (newest first)
    signals.sort(key=lambda s: s["created_at"], reverse=True)

    # Apply limit
    signals = signals[:limit]

    return [_signal_to_response(s) for s in signals]


@router.get("/signals/{signal_id}", response_model=SignalDetailResponse)
async def get_signal_detail(
    signal_id: str = Path(..., description="Signal ID"),
) -> SignalDetailResponse:
    """
    Get detailed information about a specific signal.

    Args:
        signal_id: The unique signal identifier

    Returns:
        Detailed signal information including ML features and historical data.

    Raises:
        404: Signal not found
    """
    logger.info(f"Fetching signal detail: {signal_id}")

    signal = _signals_store.get(signal_id)
    if not signal:
        raise HTTPException(
            status_code=404,
            detail=f"Signal not found: {signal_id}",
        )

    return _signal_to_detail_response(signal)


@router.post("/signals/{signal_id}/execute", response_model=ExecutionResponse)
async def execute_signal(
    signal_id: str = Path(..., description="Signal ID"),
    request: Optional[ExecutionRequest] = None,
) -> ExecutionResponse:
    """
    Execute a trading signal.

    Places a trade based on the signal parameters. Optionally override
    position size, stop loss, or take profit.

    Args:
        signal_id: The signal to execute
        request: Optional execution parameters

    Returns:
        Execution result with trade details.

    Raises:
        404: Signal not found
        400: Signal cannot be executed (already executed, expired, etc.)
    """
    logger.info(f"Executing signal: {signal_id}")

    signal = _signals_store.get(signal_id)
    if not signal:
        raise HTTPException(
            status_code=404,
            detail=f"Signal not found: {signal_id}",
        )

    # Check if signal can be executed
    if signal["status"] != SignalStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Signal cannot be executed: status is {signal['status'].value}",
        )

    # Check if signal is expired
    if signal.get("expires_at") and signal["expires_at"] < datetime.utcnow():
        signal["status"] = SignalStatus.EXPIRED
        raise HTTPException(
            status_code=400,
            detail="Signal has expired",
        )

    # TODO: Actually execute the trade via broker
    # For now, simulate execution

    # Apply overrides from request
    executed_price = signal["entry_price"]
    if request:
        # In real implementation, these would be used for order placement
        pass

    # Simulate some slippage
    slippage = 0.0001 if signal["direction"] == SignalDirection.BUY else -0.0001
    executed_price += slippage

    # Generate trade ID
    trade_id = f"trd_{uuid4().hex[:8]}"

    # Update signal status
    signal["status"] = SignalStatus.EXECUTED

    logger.info(f"Signal {signal_id} executed: trade_id={trade_id}")

    return ExecutionResponse(
        success=True,
        signal_id=signal_id,
        trade_id=trade_id,
        executed_price=executed_price,
        slippage=slippage,
        message=f"Trade executed successfully at {executed_price}",
        executed_at=datetime.utcnow(),
    )


@router.post("/signals/{signal_id}/skip", response_model=SkipResponse)
async def skip_signal(
    signal_id: str = Path(..., description="Signal ID"),
) -> SkipResponse:
    """
    Skip a trading signal.

    Marks the signal as skipped without executing a trade.

    Args:
        signal_id: The signal to skip

    Returns:
        Skip confirmation.

    Raises:
        404: Signal not found
        400: Signal cannot be skipped (already executed, etc.)
    """
    logger.info(f"Skipping signal: {signal_id}")

    signal = _signals_store.get(signal_id)
    if not signal:
        raise HTTPException(
            status_code=404,
            detail=f"Signal not found: {signal_id}",
        )

    # Check if signal can be skipped
    if signal["status"] == SignalStatus.EXECUTED:
        raise HTTPException(
            status_code=400,
            detail="Cannot skip an executed signal",
        )

    # Update signal status
    signal["status"] = SignalStatus.SKIPPED

    logger.info(f"Signal {signal_id} skipped")

    return SkipResponse(
        success=True,
        signal_id=signal_id,
        message="Signal skipped successfully",
    )


@router.get("/signals/stats/summary")
async def get_signals_summary():
    """
    Get summary statistics for signals.
    """
    signals = list(_signals_store.values())

    active = len([s for s in signals if s["status"] == SignalStatus.ACTIVE])
    executed = len([s for s in signals if s["status"] == SignalStatus.EXECUTED])
    skipped = len([s for s in signals if s["status"] == SignalStatus.SKIPPED])
    expired = len([s for s in signals if s["status"] == SignalStatus.EXPIRED])

    avg_confidence = (
        sum(s["confidence"] for s in signals) / len(signals)
        if signals
        else 0
    )

    return {
        "total": len(signals),
        "active": active,
        "executed": executed,
        "skipped": skipped,
        "expired": expired,
        "average_confidence": round(avg_confidence, 2),
        "execution_rate": round(executed / len(signals) * 100, 2) if signals else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }
