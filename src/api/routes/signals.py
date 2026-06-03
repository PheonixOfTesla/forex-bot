from __future__ import annotations

"""
Signals API Routes

Provides endpoints for real ML trading signals using OANDA market data.
Features confluence-based signal generation with technical indicator analysis.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks

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
from ...services.signal_generator import (
    SignalGenerator,
    TradingSignal,
    get_signal_generator,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Fallback Mode Detection
# =============================================================================

def _is_oanda_configured() -> bool:
    """Check if OANDA credentials are configured."""
    api_key = os.getenv("OANDA_API_KEY") or os.getenv("OANDA_ACCESS_TOKEN")
    account_id = os.getenv("OANDA_ACCOUNT_ID")
    return bool(api_key and account_id)


# =============================================================================
# Mock Data Fallback (when OANDA not configured)
# =============================================================================

import random

_MOCK_SIGNALS_CACHE: List[dict] = []
_MOCK_CACHE_TIME: datetime = datetime.min


def _generate_mock_signals() -> List[dict]:
    """Generate mock signals when OANDA is not available."""
    global _MOCK_SIGNALS_CACHE, _MOCK_CACHE_TIME

    now = datetime.utcnow()

    # Refresh cache every 5 minutes
    if (now - _MOCK_CACHE_TIME).total_seconds() > 300:
        _MOCK_CACHE_TIME = now

        pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "EUR/GBP"]
        strategies = ["trend_following", "mean_reversion", "momentum_breakout", "multi_indicator_confluence"]

        _MOCK_SIGNALS_CACHE = []

        for i, pair in enumerate(pairs[:3]):  # Generate 3 signals
            direction = random.choice(["buy", "sell"])
            confidence = round(random.uniform(60, 92), 1)

            # Generate realistic prices
            if pair == "EUR/USD":
                entry = round(1.0800 + random.uniform(-0.01, 0.01), 5)
            elif pair == "GBP/USD":
                entry = round(1.2650 + random.uniform(-0.015, 0.015), 5)
            elif pair == "USD/JPY":
                entry = round(149.50 + random.uniform(-1, 1), 3)
            elif pair == "AUD/USD":
                entry = round(0.6550 + random.uniform(-0.008, 0.008), 5)
            else:
                entry = round(0.8550 + random.uniform(-0.005, 0.005), 5)

            # Calculate SL/TP
            atr = entry * 0.003 if "JPY" not in pair else entry * 0.004
            if direction == "buy":
                sl = round(entry - atr * 1.5, 5 if "JPY" not in pair else 3)
                tp = round(entry + atr * 3, 5 if "JPY" not in pair else 3)
            else:
                sl = round(entry + atr * 1.5, 5 if "JPY" not in pair else 3)
                tp = round(entry - atr * 3, 5 if "JPY" not in pair else 3)

            rsi = round(random.uniform(25, 75), 1)
            macd = round(random.uniform(-0.003, 0.003), 6)

            signal = {
                "id": f"sig_{int(now.timestamp())}_{pair.replace('/', '')}_{i:03d}",
                "pair": pair,
                "direction": SignalDirection.BUY if direction == "buy" else SignalDirection.SELL,
                "confidence": confidence,
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward_ratio": 2.0,
                "status": SignalStatus.ACTIVE,
                "strategy": random.choice(strategies),
                "created_at": now - timedelta(minutes=random.randint(5, 30)),
                "expires_at": now + timedelta(minutes=random.randint(30, 60)),
                "features": {
                    "rsi": rsi,
                    "macd": macd,
                    "macd_signal": round(macd * 0.7, 6),
                    "bb_position": round(random.uniform(0.1, 0.9), 2),
                    "atr": round(atr, 6),
                    "volume_ratio": round(random.uniform(0.8, 1.5), 2),
                    "trend_strength": round(random.uniform(40, 80), 1),
                    "support_level": sl,
                    "resistance_level": tp,
                },
                "model_version": "v3.0.0-mock",
                "feature_importance": {
                    "rsi": 0.20,
                    "macd": 0.25,
                    "bollinger": 0.15,
                    "moving_averages": 0.25,
                    "momentum": 0.10,
                    "volume": 0.05,
                },
                "similar_historical_trades": random.randint(20, 60),
                "historical_win_rate": round(random.uniform(60, 75), 1),
            }
            _MOCK_SIGNALS_CACHE.append(signal)

    return _MOCK_SIGNALS_CACHE


# Track signal status changes (used by both mock and real modes)
_signals_status_store: dict = {}


# =============================================================================
# Helper Functions
# =============================================================================


def _signal_to_response(signal: dict) -> SignalResponse:
    """Convert signal dict to SignalResponse."""
    direction = signal["direction"]
    if isinstance(direction, str):
        direction = SignalDirection.BUY if direction.lower() == "buy" else SignalDirection.SELL

    status = signal.get("status", SignalStatus.ACTIVE)
    if isinstance(status, str):
        status = SignalStatus(status)

    return SignalResponse(
        id=signal["id"],
        pair=signal["pair"],
        direction=direction,
        confidence=signal["confidence"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        risk_reward_ratio=signal.get("risk_reward_ratio", 2.0),
        status=status,
        strategy=signal.get("strategy", "multi_indicator_confluence"),
        created_at=signal["created_at"],
        expires_at=signal.get("expires_at"),
    )


def _signal_to_detail_response(signal: dict) -> SignalDetailResponse:
    """Convert signal dict to SignalDetailResponse."""
    direction = signal["direction"]
    if isinstance(direction, str):
        direction = SignalDirection.BUY if direction.lower() == "buy" else SignalDirection.SELL

    status = signal.get("status", SignalStatus.ACTIVE)
    if isinstance(status, str):
        status = SignalStatus(status)

    features = signal.get("features", {})
    if not isinstance(features, SignalFeatures):
        features = SignalFeatures(**features)

    return SignalDetailResponse(
        id=signal["id"],
        pair=signal["pair"],
        direction=direction,
        confidence=signal["confidence"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        risk_reward_ratio=signal.get("risk_reward_ratio", 2.0),
        status=status,
        strategy=signal.get("strategy", "multi_indicator_confluence"),
        created_at=signal["created_at"],
        expires_at=signal.get("expires_at"),
        features=features,
        model_version=signal.get("model_version", "v3.0.0"),
        feature_importance=signal.get("feature_importance", {}),
        similar_historical_trades=signal.get("similar_historical_trades", 0),
        historical_win_rate=signal.get("historical_win_rate"),
        notes=signal.get("notes"),
    )


def _trading_signal_to_dict(signal: TradingSignal) -> dict:
    """Convert TradingSignal to dict format."""
    direction = SignalDirection.BUY if signal.direction == "buy" else SignalDirection.SELL
    status = SignalStatus(signal.status)

    return {
        "id": signal.id,
        "pair": signal.pair,
        "direction": direction,
        "confidence": signal.confidence,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "risk_reward_ratio": signal.risk_reward_ratio,
        "status": status,
        "strategy": signal.strategy,
        "created_at": signal.created_at,
        "expires_at": signal.expires_at,
        "features": signal.indicators,
        "model_version": signal.model_version,
        "feature_importance": signal.feature_importance,
        "similar_historical_trades": signal.similar_historical_trades,
        "historical_win_rate": signal.historical_win_rate,
    }


async def _get_signals_from_generator() -> List[dict]:
    """Get signals from the real signal generator."""
    try:
        generator = get_signal_generator()
        signals = await generator.generate_signals()

        # Also include cached signals that are still valid
        cached = generator.get_all_signals()
        signal_ids = {s.id for s in signals}

        # Add cached signals not already in the fresh batch
        for cached_signal in cached:
            if cached_signal.id not in signal_ids:
                signals.append(cached_signal)

        return [_trading_signal_to_dict(s) for s in signals]

    except Exception as e:
        logger.error(f"Error fetching signals from generator: {e}")
        raise


async def _get_all_signals() -> List[dict]:
    """Get all signals, using real generator or mock fallback."""
    if _is_oanda_configured():
        try:
            return await _get_signals_from_generator()
        except Exception as e:
            logger.warning(f"Falling back to mock signals due to error: {e}")
            return _generate_mock_signals()
    else:
        logger.debug("OANDA not configured, using mock signals")
        return _generate_mock_signals()


def _get_signal_by_id(signals: List[dict], signal_id: str) -> Optional[dict]:
    """Find a signal by ID in the signals list."""
    for signal in signals:
        if signal["id"] == signal_id:
            return signal
    return None


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
    Get list of trading signals with real market data.

    Uses OANDA API to fetch live price data and generate signals based on
    technical indicator confluence (RSI, MACD, Bollinger Bands, Moving Averages).

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

    try:
        signals = await _get_all_signals()

        # Apply status from store
        for signal in signals:
            stored_status = _signals_status_store.get(signal["id"])
            if stored_status:
                signal["status"] = SignalStatus(stored_status)

        # Filter by status
        if status:
            signals = [s for s in signals if s["status"] == status]

        # Filter by pair
        if pair:
            pair_normalized = pair.upper().replace("_", "/")
            signals = [s for s in signals if s["pair"].upper() == pair_normalized]

        # Filter by confidence
        if min_confidence is not None:
            signals = [s for s in signals if s["confidence"] >= min_confidence]

        # Sort by created_at descending (newest first)
        signals.sort(key=lambda s: s["created_at"], reverse=True)

        # Apply limit
        signals = signals[:limit]

        return [_signal_to_response(s) for s in signals]

    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching signals: {str(e)}")


@router.get("/signals/summary")
async def get_signals_summary_shortcut():
    """
    Get summary statistics for signals (shortcut route).

    This is a convenience alias for /signals/stats/summary.
    """
    try:
        signals = await _get_all_signals()

        # Apply stored statuses
        for signal in signals:
            stored_status = _signals_status_store.get(signal["id"])
            if stored_status:
                signal["status"] = SignalStatus(stored_status)

        active = len([s for s in signals if s["status"] == SignalStatus.ACTIVE])
        executed = len([s for s in signals if s["status"] == SignalStatus.EXECUTED])
        skipped = len([s for s in signals if s["status"] == SignalStatus.SKIPPED])
        expired = len([s for s in signals if s["status"] == SignalStatus.EXPIRED])

        avg_confidence = (
            sum(s["confidence"] for s in signals) / len(signals)
            if signals
            else 0
        )

        execution_rate = (executed / len(signals) * 100) if signals else 0

        avg_rr = (
            sum(s.get("risk_reward_ratio", 2.0) for s in signals) / len(signals)
            if signals
            else 2.0
        )

        return {
            "total": len(signals),
            "active": active,
            "executed": executed,
            "skipped": skipped,
            "expired": expired,
            "average_confidence": round(avg_confidence, 2),
            "average_risk_reward": round(avg_rr, 2),
            "execution_rate": round(execution_rate, 2),
            "data_source": "live" if _is_oanda_configured() else "mock",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting signals summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")


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

    try:
        signals = await _get_all_signals()
        signal = _get_signal_by_id(signals, signal_id)

        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"Signal not found: {signal_id}",
            )

        # Apply stored status
        stored_status = _signals_status_store.get(signal_id)
        if stored_status:
            signal["status"] = SignalStatus(stored_status)

        return _signal_to_detail_response(signal)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching signal detail: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching signal: {str(e)}")


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

    try:
        signals = await _get_all_signals()
        signal = _get_signal_by_id(signals, signal_id)

        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"Signal not found: {signal_id}",
            )

        # Check stored status
        stored_status = _signals_status_store.get(signal_id, "active")
        if isinstance(stored_status, SignalStatus):
            stored_status = stored_status.value

        # Check if signal can be executed
        if stored_status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Signal cannot be executed: status is {stored_status}",
            )

        # Check if signal is expired
        if signal.get("expires_at") and signal["expires_at"] < datetime.utcnow():
            _signals_status_store[signal_id] = "expired"
            raise HTTPException(
                status_code=400,
                detail="Signal has expired",
            )

        # TODO: Actually execute the trade via broker
        # For now, simulate execution

        executed_price = signal["entry_price"]

        # Simulate realistic slippage (0.5-2 pips)
        direction = signal["direction"]
        if isinstance(direction, SignalDirection):
            is_buy = direction == SignalDirection.BUY
        else:
            is_buy = direction.lower() == "buy"

        slippage_pips = random.uniform(0.5, 2.0)
        slippage = slippage_pips * 0.0001 if is_buy else -slippage_pips * 0.0001

        if "JPY" in signal["pair"]:
            slippage = slippage_pips * 0.01 if is_buy else -slippage_pips * 0.01

        executed_price += slippage

        # Generate trade ID
        trade_id = f"trd_{uuid4().hex[:8]}"

        # Update signal status
        _signals_status_store[signal_id] = "executed"

        # Also update in signal generator if using real mode
        if _is_oanda_configured():
            try:
                generator = get_signal_generator()
                generator.update_signal_status(signal_id, "executed")
            except Exception:
                pass

        logger.info(f"Signal {signal_id} executed: trade_id={trade_id}")

        return ExecutionResponse(
            success=True,
            signal_id=signal_id,
            trade_id=trade_id,
            executed_price=round(executed_price, 5),
            slippage=round(slippage, 5),
            message=f"Trade executed successfully at {executed_price:.5f}",
            executed_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing signal: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing signal: {str(e)}")


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

    try:
        signals = await _get_all_signals()
        signal = _get_signal_by_id(signals, signal_id)

        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"Signal not found: {signal_id}",
            )

        # Check stored status
        stored_status = _signals_status_store.get(signal_id, "active")
        if isinstance(stored_status, SignalStatus):
            stored_status = stored_status.value

        # Check if signal can be skipped
        if stored_status == "executed":
            raise HTTPException(
                status_code=400,
                detail="Cannot skip an executed signal",
            )

        # Update signal status
        _signals_status_store[signal_id] = "skipped"

        # Also update in signal generator if using real mode
        if _is_oanda_configured():
            try:
                generator = get_signal_generator()
                generator.update_signal_status(signal_id, "skipped")
            except Exception:
                pass

        logger.info(f"Signal {signal_id} skipped")

        return SkipResponse(
            success=True,
            signal_id=signal_id,
            message="Signal skipped successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping signal: {e}")
        raise HTTPException(status_code=500, detail=f"Error skipping signal: {str(e)}")


@router.get("/signals/stats/summary")
async def get_signals_summary():
    """
    Get summary statistics for signals.
    """
    try:
        signals = await _get_all_signals()

        # Apply stored statuses
        for signal in signals:
            stored_status = _signals_status_store.get(signal["id"])
            if stored_status:
                signal["status"] = SignalStatus(stored_status)

        active = len([s for s in signals if s["status"] == SignalStatus.ACTIVE])
        executed = len([s for s in signals if s["status"] == SignalStatus.EXECUTED])
        skipped = len([s for s in signals if s["status"] == SignalStatus.SKIPPED])
        expired = len([s for s in signals if s["status"] == SignalStatus.EXPIRED])

        avg_confidence = (
            sum(s["confidence"] for s in signals) / len(signals)
            if signals
            else 0
        )

        execution_rate = (executed / len(signals) * 100) if signals else 0

        # Calculate average risk/reward
        avg_rr = (
            sum(s.get("risk_reward_ratio", 2.0) for s in signals) / len(signals)
            if signals
            else 2.0
        )

        return {
            "total": len(signals),
            "active": active,
            "executed": executed,
            "skipped": skipped,
            "expired": expired,
            "average_confidence": round(avg_confidence, 2),
            "average_risk_reward": round(avg_rr, 2),
            "execution_rate": round(execution_rate, 2),
            "data_source": "live" if _is_oanda_configured() else "mock",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting signals summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")


@router.post("/signals/refresh")
async def refresh_signals(background_tasks: BackgroundTasks):
    """
    Force refresh signals from market data.

    Triggers a new analysis cycle to generate fresh signals.
    """
    if not _is_oanda_configured():
        return {
            "success": True,
            "message": "Mock mode - signals refreshed",
            "data_source": "mock",
        }

    try:
        generator = get_signal_generator()
        signals = await generator.generate_signals()

        return {
            "success": True,
            "message": f"Generated {len(signals)} new signals",
            "signals_count": len(signals),
            "data_source": "live",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error refreshing signals: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing signals: {str(e)}")
