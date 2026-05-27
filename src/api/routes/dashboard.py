from __future__ import annotations

"""
Dashboard API Routes

Provides dashboard overview data including balance, P/L, positions, and signals.
"""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Query

from ..schemas import (
    BalancePoint,
    DashboardResponse,
    MLSignal,
    OpenPosition,
    SignalDirection,
    SignalStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Dynamic Data Generation
# =============================================================================

# Base values for dynamic generation
_BASE_BALANCE = 10485.32
_BASE_WIN_RATE = 68.5
_BASE_TODAY_PNL = 127.45

# Store session start time for consistent daily calculations
_SESSION_START = time.time()


def _get_dynamic_balance() -> float:
    """Generate dynamic balance with ±$50 variance."""
    # Use current timestamp to create smooth fluctuations
    t = time.time()
    # Create a sine wave pattern + random noise for realistic fluctuation
    wave = 25 * (1 + (t % 60) / 60)  # Gradual shift within minute
    noise = random.uniform(-25, 25)
    variance = wave * (0.5 if random.random() > 0.5 else -0.5) + noise
    return round(_BASE_BALANCE + variance, 2)


def _get_dynamic_today_pnl() -> tuple[float, float]:
    """
    Generate dynamic P&L based on time of day.
    Returns (pnl_amount, pnl_percentage).

    P&L tends to accumulate throughout the trading day.
    """
    now = datetime.utcnow()
    # Trading day progress (0.0 to 1.0)
    hour_progress = (now.hour + now.minute / 60) / 24

    # Base P&L scales with day progress (more trades = more P&L opportunity)
    base_multiplier = 0.3 + (hour_progress * 0.7)  # 30% to 100% of base

    # Add random fluctuation (±30% of current value)
    fluctuation = random.uniform(-0.3, 0.3)

    pnl = _BASE_TODAY_PNL * base_multiplier * (1 + fluctuation)
    # Occasionally have negative days (20% chance, but less negative)
    if random.random() < 0.1:
        pnl = -abs(pnl) * random.uniform(0.2, 0.5)

    pnl = round(pnl, 2)
    pnl_pct = round((pnl / _BASE_BALANCE) * 100, 2)

    return pnl, pnl_pct


def _get_dynamic_win_rate() -> float:
    """Generate dynamic win rate within realistic bounds (60-78%)."""
    # Win rate fluctuates slightly around base
    variance = random.uniform(-5, 7)  # Slight upward bias for good bot
    win_rate = _BASE_WIN_RATE + variance
    # Clamp to realistic bounds
    return round(max(60.0, min(78.0, win_rate)), 1)


def _get_dynamic_trade_count() -> int:
    """Generate trade count based on time of day."""
    now = datetime.utcnow()
    # More trades as day progresses
    base_trades = 4 + int((now.hour + now.minute / 60) / 2)
    variance = random.randint(-2, 3)
    return max(1, base_trades + variance)


# =============================================================================
# Mock Data (Replace with actual database/broker queries)
# =============================================================================


def _get_dynamic_confidence(base: float) -> float:
    """Add slight variance to confidence scores (±3%)."""
    variance = random.uniform(-3, 3)
    return round(max(50.0, min(99.0, base + variance)), 1)


def _get_mock_ml_signals() -> List[MLSignal]:
    """Get mock ML signals with dynamic confidence scores."""
    return [
        MLSignal(
            pair="EUR/USD",
            direction=SignalDirection.BUY,
            confidence=_get_dynamic_confidence(87.5),
            entry_price=1.0845,
            stop_loss=1.0815,
            take_profit=1.0905,
            timestamp=datetime.utcnow() - timedelta(minutes=15),
        ),
        MLSignal(
            pair="GBP/USD",
            direction=SignalDirection.SELL,
            confidence=_get_dynamic_confidence(76.2),
            entry_price=1.2650,
            stop_loss=1.2695,
            take_profit=1.2560,
            timestamp=datetime.utcnow() - timedelta(minutes=8),
        ),
        MLSignal(
            pair="USD/JPY",
            direction=SignalDirection.BUY,
            confidence=_get_dynamic_confidence(82.1),
            entry_price=149.25,
            stop_loss=148.85,
            take_profit=150.05,
            timestamp=datetime.utcnow() - timedelta(minutes=3),
        ),
    ]


def _simulate_price_movement(
    entry_price: float,
    base_current: float,
    direction: SignalDirection,
    pip_size: float = 0.0001,
) -> tuple[float, float, float]:
    """
    Simulate price movement for a position.
    Returns (current_price, unrealized_pnl, unrealized_pnl_pct).
    """
    # Simulate price moving ±15 pips from base current price
    pip_variance = random.uniform(-15, 15) * pip_size
    current_price = round(base_current + pip_variance, 5)

    # Calculate P&L based on direction
    if direction == SignalDirection.BUY:
        price_diff = current_price - entry_price
    else:
        price_diff = entry_price - current_price

    # Calculate P&L (simplified: assumes 10000 units for EUR/USD style)
    # For JPY pairs, pip value is different
    if pip_size > 0.001:  # JPY pair
        pnl = round(price_diff * 100, 2)  # Simplified calculation
    else:
        pnl = round(price_diff * 10000, 2)  # Standard pair

    pnl_pct = round((pnl / _BASE_BALANCE) * 100, 2)

    return current_price, pnl, pnl_pct


def _get_mock_open_positions() -> List[OpenPosition]:
    """Get mock open positions with dynamic price movement."""
    # EUR/USD position (BUY)
    eur_current, eur_pnl, eur_pnl_pct = _simulate_price_movement(
        entry_price=1.0825,
        base_current=1.0852,
        direction=SignalDirection.BUY,
        pip_size=0.0001,
    )

    # USD/JPY position (SELL)
    jpy_current, jpy_pnl, jpy_pnl_pct = _simulate_price_movement(
        entry_price=149.50,
        base_current=149.25,
        direction=SignalDirection.SELL,
        pip_size=0.01,
    )

    return [
        OpenPosition(
            id="pos_001",
            pair="EUR/USD",
            direction=SignalDirection.BUY,
            entry_price=1.0825,
            current_price=eur_current,
            units=10000,
            unrealized_pnl=eur_pnl,
            unrealized_pnl_pct=eur_pnl_pct,
            stop_loss=1.0795,
            take_profit=1.0895,
            opened_at=datetime.utcnow() - timedelta(hours=2),
        ),
        OpenPosition(
            id="pos_002",
            pair="USD/JPY",
            direction=SignalDirection.SELL,
            entry_price=149.50,
            current_price=jpy_current,
            units=5000,
            unrealized_pnl=jpy_pnl,
            unrealized_pnl_pct=jpy_pnl_pct,
            stop_loss=149.95,
            take_profit=148.55,
            opened_at=datetime.utcnow() - timedelta(hours=1, minutes=30),
        ),
    ]


def _get_mock_balance_history(days: int) -> List[BalancePoint]:
    """Generate mock balance history for development."""
    history = []
    base_balance = 10000.0
    current_balance = 10485.32

    # Generate daily balance points
    for i in range(days, -1, -1):
        timestamp = datetime.utcnow() - timedelta(days=i)
        # Simulate gradual balance growth with some variance
        progress = (days - i) / days
        balance = base_balance + (current_balance - base_balance) * progress
        # Add some daily variance
        variance = (hash(str(timestamp.date())) % 100 - 50) / 10
        balance += variance

        history.append(
            BalancePoint(
                timestamp=timestamp,
                balance=round(balance, 2),
                equity=round(balance + (hash(str(timestamp)) % 100 - 50), 2),
            )
        )

    return history


# =============================================================================
# Dashboard Endpoints
# =============================================================================


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard() -> DashboardResponse:
    """
    Get dashboard overview data.

    Returns comprehensive dashboard data including:
    - Account balance and equity
    - Today's P/L
    - Win rate and trade count
    - Open positions count
    - Active ML signals
    - Open position details

    Note: Data is dynamically generated to simulate live trading.
    """
    logger.info("Fetching dashboard data")

    # Get dynamic values
    balance = _get_dynamic_balance()
    today_pnl, today_pnl_pct = _get_dynamic_today_pnl()
    win_rate = _get_dynamic_win_rate()
    total_trades = _get_dynamic_trade_count()

    # Get positions and signals with dynamic data
    ml_signals = _get_mock_ml_signals()
    open_positions = _get_mock_open_positions()

    # Calculate totals from positions
    total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)

    return DashboardResponse(
        balance=balance,
        equity=round(balance + total_unrealized_pnl, 2),
        today_pnl=today_pnl,
        today_pnl_pct=today_pnl_pct,
        win_rate=win_rate,
        total_trades=total_trades,
        open_positions_count=len(open_positions),
        ml_signals=ml_signals,
        open_positions=open_positions,
        last_updated=datetime.utcnow(),
    )


@router.get("/balance-history", response_model=List[BalancePoint])
async def get_balance_history(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days of history to retrieve",
    ),
) -> List[BalancePoint]:
    """
    Get account balance history.

    Args:
        days: Number of days of history (1-365, default: 30)

    Returns:
        List of balance data points with timestamp, balance, and equity.
    """
    logger.info(f"Fetching balance history for {days} days")

    # TODO: Replace with actual data from database
    history = _get_mock_balance_history(days)

    return history


@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """
    Get condensed dashboard summary for widgets.

    Returns minimal data for quick display with dynamic values.
    """
    logger.info("Fetching dashboard summary")

    balance = _get_dynamic_balance()
    today_pnl, today_pnl_pct = _get_dynamic_today_pnl()
    win_rate = _get_dynamic_win_rate()

    return {
        "balance": balance,
        "today_pnl": today_pnl,
        "today_pnl_pct": today_pnl_pct,
        "open_positions": 2,
        "active_signals": 3,
        "win_rate": win_rate,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/dashboard/quick-stats")
async def get_quick_stats():
    """
    Get quick statistics for the current trading session with dynamic values.
    """
    logger.info("Fetching quick stats")

    # Dynamic trade counts
    trades_today = _get_dynamic_trade_count()
    win_rate = _get_dynamic_win_rate() / 100

    wins_today = max(1, int(trades_today * win_rate))
    losses_today = trades_today - wins_today

    # Dynamic signal stats
    signals_generated = trades_today + random.randint(4, 8)
    signals_executed = trades_today
    signals_skipped = random.randint(2, 5)
    signals_expired = signals_generated - signals_executed - signals_skipped

    # Dynamic P&L stats
    best_trade_pnl = round(35 + random.uniform(0, 25), 2)
    worst_trade_pnl = round(-10 - random.uniform(0, 15), 2)
    average_trade_pnl = round(8 + random.uniform(-3, 5), 2)

    return {
        "session_start": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
        "trades_today": trades_today,
        "wins_today": wins_today,
        "losses_today": losses_today,
        "signals_generated": signals_generated,
        "signals_executed": signals_executed,
        "signals_skipped": signals_skipped,
        "signals_expired": max(0, signals_expired),
        "best_trade_pnl": best_trade_pnl,
        "worst_trade_pnl": worst_trade_pnl,
        "average_trade_pnl": average_trade_pnl,
        "timestamp": datetime.utcnow().isoformat(),
    }
