from __future__ import annotations

"""
Dashboard API Routes

Provides dashboard overview data including balance, P/L, positions, and signals.
"""

import logging
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
# Mock Data (Replace with actual database/broker queries)
# =============================================================================


def _get_mock_ml_signals() -> List[MLSignal]:
    """Get mock ML signals for development."""
    return [
        MLSignal(
            pair="EUR/USD",
            direction=SignalDirection.BUY,
            confidence=87.5,
            entry_price=1.0845,
            stop_loss=1.0815,
            take_profit=1.0905,
            timestamp=datetime.utcnow() - timedelta(minutes=15),
        ),
        MLSignal(
            pair="GBP/USD",
            direction=SignalDirection.SELL,
            confidence=76.2,
            entry_price=1.2650,
            stop_loss=1.2695,
            take_profit=1.2560,
            timestamp=datetime.utcnow() - timedelta(minutes=8),
        ),
        MLSignal(
            pair="USD/JPY",
            direction=SignalDirection.BUY,
            confidence=82.1,
            entry_price=149.25,
            stop_loss=148.85,
            take_profit=150.05,
            timestamp=datetime.utcnow() - timedelta(minutes=3),
        ),
    ]


def _get_mock_open_positions() -> List[OpenPosition]:
    """Get mock open positions for development."""
    return [
        OpenPosition(
            id="pos_001",
            pair="EUR/USD",
            direction=SignalDirection.BUY,
            entry_price=1.0825,
            current_price=1.0852,
            units=10000,
            unrealized_pnl=27.0,
            unrealized_pnl_pct=0.25,
            stop_loss=1.0795,
            take_profit=1.0895,
            opened_at=datetime.utcnow() - timedelta(hours=2),
        ),
        OpenPosition(
            id="pos_002",
            pair="USD/JPY",
            direction=SignalDirection.SELL,
            entry_price=149.50,
            current_price=149.25,
            units=5000,
            unrealized_pnl=16.75,
            unrealized_pnl_pct=0.17,
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
    """
    logger.info("Fetching dashboard data")

    # TODO: Replace with actual data from database/broker
    ml_signals = _get_mock_ml_signals()
    open_positions = _get_mock_open_positions()

    # Calculate totals from positions
    total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)

    return DashboardResponse(
        balance=10485.32,
        equity=10485.32 + total_unrealized_pnl,
        today_pnl=127.45,
        today_pnl_pct=1.23,
        win_rate=68.5,
        total_trades=12,
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

    Returns minimal data for quick display.
    """
    logger.info("Fetching dashboard summary")

    return {
        "balance": 10485.32,
        "today_pnl": 127.45,
        "today_pnl_pct": 1.23,
        "open_positions": 2,
        "active_signals": 3,
        "win_rate": 68.5,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/dashboard/quick-stats")
async def get_quick_stats():
    """
    Get quick statistics for the current trading session.
    """
    logger.info("Fetching quick stats")

    return {
        "session_start": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
        "trades_today": 12,
        "wins_today": 8,
        "losses_today": 4,
        "signals_generated": 18,
        "signals_executed": 12,
        "signals_skipped": 4,
        "signals_expired": 2,
        "best_trade_pnl": 45.20,
        "worst_trade_pnl": -18.50,
        "average_trade_pnl": 10.62,
        "timestamp": datetime.utcnow().isoformat(),
    }
