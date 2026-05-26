from __future__ import annotations

"""
Trade History API Routes

Provides endpoints for trade history and performance analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..schemas import (
    BalancePoint,
    PerformanceByPair,
    PerformanceByStrategy,
    PerformanceMetrics,
    PerformanceResponse,
    SignalDirection,
    SignalFeatures,
    TradeDetailResponse,
    TradeResponse,
    TradeResult,
    TradeStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Mock Data Store (Replace with actual database)
# =============================================================================


def _generate_mock_trades() -> List[dict]:
    """Generate mock trade data for development."""
    trades = [
        {
            "id": "trd_001",
            "pair": "EUR/USD",
            "direction": SignalDirection.BUY,
            "status": TradeStatus.CLOSED,
            "entry_price": 1.0812,
            "exit_price": 1.0865,
            "units": 10000,
            "pnl": 53.0,
            "pnl_pct": 0.49,
            "result": TradeResult.WIN,
            "opened_at": datetime.utcnow() - timedelta(hours=8),
            "closed_at": datetime.utcnow() - timedelta(hours=6),
            "signal_id": "sig_old_001",
            "stop_loss": 1.0780,
            "take_profit": 1.0870,
            "initial_stop_loss": 1.0780,
            "initial_take_profit": 1.0870,
            "max_favorable_excursion": 55.0,
            "max_adverse_excursion": -8.0,
            "slippage": 0.2,
            "fees": 1.20,
            "strategy": "momentum_breakout",
            "signal_confidence": 85.2,
        },
        {
            "id": "trd_002",
            "pair": "GBP/USD",
            "direction": SignalDirection.SELL,
            "status": TradeStatus.CLOSED,
            "entry_price": 1.2680,
            "exit_price": 1.2645,
            "units": 8000,
            "pnl": 28.0,
            "pnl_pct": 0.28,
            "result": TradeResult.WIN,
            "opened_at": datetime.utcnow() - timedelta(hours=7),
            "closed_at": datetime.utcnow() - timedelta(hours=5),
            "signal_id": "sig_old_002",
            "stop_loss": 1.2720,
            "take_profit": 1.2620,
            "initial_stop_loss": 1.2720,
            "initial_take_profit": 1.2620,
            "max_favorable_excursion": 42.0,
            "max_adverse_excursion": -12.0,
            "slippage": 0.3,
            "fees": 0.95,
            "strategy": "mean_reversion",
            "signal_confidence": 78.5,
        },
        {
            "id": "trd_003",
            "pair": "USD/JPY",
            "direction": SignalDirection.BUY,
            "status": TradeStatus.CLOSED,
            "entry_price": 149.15,
            "exit_price": 148.92,
            "units": 5000,
            "pnl": -15.35,
            "pnl_pct": -0.15,
            "result": TradeResult.LOSS,
            "opened_at": datetime.utcnow() - timedelta(hours=6),
            "closed_at": datetime.utcnow() - timedelta(hours=4, minutes=30),
            "signal_id": "sig_old_003",
            "stop_loss": 148.90,
            "take_profit": 149.85,
            "initial_stop_loss": 148.90,
            "initial_take_profit": 149.85,
            "max_favorable_excursion": 18.0,
            "max_adverse_excursion": -23.0,
            "slippage": 0.5,
            "fees": 0.75,
            "strategy": "trend_following",
            "signal_confidence": 72.1,
        },
        {
            "id": "trd_004",
            "pair": "EUR/USD",
            "direction": SignalDirection.BUY,
            "status": TradeStatus.OPEN,
            "entry_price": 1.0825,
            "exit_price": None,
            "units": 10000,
            "pnl": 27.0,  # Unrealized
            "pnl_pct": 0.25,
            "result": None,
            "opened_at": datetime.utcnow() - timedelta(hours=2),
            "closed_at": None,
            "signal_id": "sig_001",
            "stop_loss": 1.0795,
            "take_profit": 1.0895,
            "initial_stop_loss": 1.0795,
            "initial_take_profit": 1.0895,
            "max_favorable_excursion": 32.0,
            "max_adverse_excursion": -5.0,
            "slippage": 0.1,
            "fees": None,
            "strategy": "momentum_breakout",
            "signal_confidence": 87.5,
        },
        {
            "id": "trd_005",
            "pair": "EUR/USD",
            "direction": SignalDirection.SELL,
            "status": TradeStatus.CLOSED,
            "entry_price": 1.0795,
            "exit_price": 1.0830,
            "units": 7500,
            "pnl": -26.25,
            "pnl_pct": -0.33,
            "result": TradeResult.LOSS,
            "opened_at": datetime.utcnow() - timedelta(hours=12),
            "closed_at": datetime.utcnow() - timedelta(hours=10),
            "signal_id": "sig_old_004",
            "stop_loss": 1.0835,
            "take_profit": 1.0720,
            "initial_stop_loss": 1.0835,
            "initial_take_profit": 1.0720,
            "max_favorable_excursion": 12.0,
            "max_adverse_excursion": -35.0,
            "slippage": 0.4,
            "fees": 0.90,
            "strategy": "mean_reversion",
            "signal_confidence": 68.3,
        },
    ]

    # Generate more trades for history
    for i in range(6, 20):
        days_ago = i // 2
        is_win = i % 3 != 0
        pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"]
        strategies = ["momentum_breakout", "mean_reversion", "trend_following"]

        trades.append({
            "id": f"trd_{i:03d}",
            "pair": pairs[i % len(pairs)],
            "direction": SignalDirection.BUY if i % 2 == 0 else SignalDirection.SELL,
            "status": TradeStatus.CLOSED,
            "entry_price": 1.0800 + (i * 0.001),
            "exit_price": 1.0800 + (i * 0.001) + (0.003 if is_win else -0.002),
            "units": 5000 + (i * 500),
            "pnl": 25.0 + (i * 2) if is_win else -(15.0 + i),
            "pnl_pct": 0.25 if is_win else -0.15,
            "result": TradeResult.WIN if is_win else TradeResult.LOSS,
            "opened_at": datetime.utcnow() - timedelta(days=days_ago, hours=i),
            "closed_at": datetime.utcnow() - timedelta(days=days_ago, hours=i-1),
            "signal_id": f"sig_old_{i:03d}",
            "stop_loss": 1.0750,
            "take_profit": 1.0900,
            "initial_stop_loss": 1.0750,
            "initial_take_profit": 1.0900,
            "strategy": strategies[i % len(strategies)],
            "signal_confidence": 70.0 + (i % 20),
        })

    return trades


_trades_store = _generate_mock_trades()


# =============================================================================
# Helper Functions
# =============================================================================


def _trade_to_response(trade: dict) -> TradeResponse:
    """Convert trade dict to TradeResponse."""
    return TradeResponse(
        id=trade["id"],
        pair=trade["pair"],
        direction=trade["direction"],
        status=trade["status"],
        entry_price=trade["entry_price"],
        exit_price=trade.get("exit_price"),
        units=trade["units"],
        pnl=trade.get("pnl"),
        pnl_pct=trade.get("pnl_pct"),
        result=trade.get("result"),
        opened_at=trade["opened_at"],
        closed_at=trade.get("closed_at"),
        signal_id=trade.get("signal_id"),
    )


def _trade_to_detail_response(trade: dict) -> TradeDetailResponse:
    """Convert trade dict to TradeDetailResponse."""
    features = None
    if trade.get("signal_confidence"):
        features = SignalFeatures(
            rsi=65.0,
            macd=0.002,
            bb_position=0.6,
        )

    return TradeDetailResponse(
        id=trade["id"],
        pair=trade["pair"],
        direction=trade["direction"],
        status=trade["status"],
        entry_price=trade["entry_price"],
        exit_price=trade.get("exit_price"),
        units=trade["units"],
        pnl=trade.get("pnl"),
        pnl_pct=trade.get("pnl_pct"),
        result=trade.get("result"),
        opened_at=trade["opened_at"],
        closed_at=trade.get("closed_at"),
        signal_id=trade.get("signal_id"),
        stop_loss=trade.get("stop_loss"),
        take_profit=trade.get("take_profit"),
        initial_stop_loss=trade.get("initial_stop_loss"),
        initial_take_profit=trade.get("initial_take_profit"),
        max_favorable_excursion=trade.get("max_favorable_excursion"),
        max_adverse_excursion=trade.get("max_adverse_excursion"),
        slippage=trade.get("slippage"),
        fees=trade.get("fees"),
        strategy=trade.get("strategy"),
        notes=trade.get("notes"),
        signal_confidence=trade.get("signal_confidence"),
        signal_features=features,
    )


def _calculate_performance(trades: List[dict], days: int) -> PerformanceMetrics:
    """Calculate performance metrics from trades."""
    closed_trades = [t for t in trades if t["status"] == TradeStatus.CLOSED]

    if not closed_trades:
        return PerformanceMetrics()

    wins = [t for t in closed_trades if t.get("result") == TradeResult.WIN]
    losses = [t for t in closed_trades if t.get("result") == TradeResult.LOSS]
    breakevens = [t for t in closed_trades if t.get("result") == TradeResult.BREAKEVEN]

    total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
    total_wins = sum(t.get("pnl", 0) for t in wins)
    total_losses = abs(sum(t.get("pnl", 0) for t in losses))

    return PerformanceMetrics(
        total_trades=len(closed_trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        breakeven_trades=len(breakevens),
        win_rate=len(wins) / len(closed_trades) * 100 if closed_trades else 0,
        profit_factor=total_wins / total_losses if total_losses > 0 else None,
        total_pnl=total_pnl,
        average_win=total_wins / len(wins) if wins else None,
        average_loss=-total_losses / len(losses) if losses else None,
        largest_win=max((t.get("pnl", 0) for t in wins), default=None),
        largest_loss=min((t.get("pnl", 0) for t in losses), default=None),
        average_trade_duration_minutes=90.0,  # Mock value
        max_consecutive_wins=3,  # Mock value
        max_consecutive_losses=2,  # Mock value
        max_drawdown=-85.50,  # Mock value
        max_drawdown_pct=-0.82,  # Mock value
        sharpe_ratio=1.45,  # Mock value
    )


# =============================================================================
# Trade History Endpoints
# =============================================================================


@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    filter: Optional[str] = Query(
        default=None,
        description="Filter: 'wins', 'losses', 'open', 'closed'",
    ),
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair",
    ),
    strategy: Optional[str] = Query(
        default=None,
        description="Filter by strategy",
    ),
    days: Optional[int] = Query(
        default=None,
        ge=1,
        le=365,
        description="Filter to trades within N days",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of trades to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of trades to skip",
    ),
) -> List[TradeResponse]:
    """
    Get trade history with optional filters.

    Args:
        filter: Quick filter (wins, losses, open, closed)
        pair: Filter by trading pair
        strategy: Filter by strategy name
        days: Limit to trades within N days
        limit: Maximum number of trades
        offset: Pagination offset

    Returns:
        List of trades matching the filters.
    """
    logger.info(f"Fetching trades: filter={filter}, pair={pair}, limit={limit}")

    trades = list(_trades_store)

    # Apply filters
    if filter:
        if filter.lower() == "wins":
            trades = [t for t in trades if t.get("result") == TradeResult.WIN]
        elif filter.lower() == "losses":
            trades = [t for t in trades if t.get("result") == TradeResult.LOSS]
        elif filter.lower() == "open":
            trades = [t for t in trades if t["status"] == TradeStatus.OPEN]
        elif filter.lower() == "closed":
            trades = [t for t in trades if t["status"] == TradeStatus.CLOSED]

    if pair:
        trades = [t for t in trades if t["pair"].upper() == pair.upper()]

    if strategy:
        trades = [t for t in trades if t.get("strategy") == strategy]

    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        trades = [t for t in trades if t["opened_at"] >= cutoff]

    # Sort by opened_at descending
    trades.sort(key=lambda t: t["opened_at"], reverse=True)

    # Apply pagination
    trades = trades[offset:offset + limit]

    return [_trade_to_response(t) for t in trades]


@router.get("/trades/{trade_id}", response_model=TradeDetailResponse)
async def get_trade(
    trade_id: str = Path(..., description="Trade ID"),
) -> TradeDetailResponse:
    """
    Get detailed information about a specific trade.

    Args:
        trade_id: The unique trade identifier

    Returns:
        Detailed trade information including execution details and ML data.

    Raises:
        404: Trade not found
    """
    logger.info(f"Fetching trade detail: {trade_id}")

    trade = next((t for t in _trades_store if t["id"] == trade_id), None)
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"Trade not found: {trade_id}",
        )

    return _trade_to_detail_response(trade)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Performance period in days",
    ),
) -> PerformanceResponse:
    """
    Get comprehensive performance analytics.

    Args:
        days: Performance period in days (1-365)

    Returns:
        Performance metrics including win rate, profit factor,
        drawdown, and breakdowns by pair and strategy.
    """
    logger.info(f"Fetching performance for {days} days")

    cutoff = datetime.utcnow() - timedelta(days=days)
    trades = [t for t in _trades_store if t["opened_at"] >= cutoff]

    # Calculate overall metrics
    overall = _calculate_performance(trades, days)

    # Calculate by pair
    pairs = set(t["pair"] for t in trades)
    by_pair = []
    for pair in pairs:
        pair_trades = [t for t in trades if t["pair"] == pair]
        closed = [t for t in pair_trades if t["status"] == TradeStatus.CLOSED]
        wins = [t for t in closed if t.get("result") == TradeResult.WIN]
        total_pnl = sum(t.get("pnl", 0) for t in closed)

        by_pair.append(PerformanceByPair(
            pair=pair,
            total_trades=len(closed),
            win_rate=len(wins) / len(closed) * 100 if closed else 0,
            total_pnl=total_pnl,
            profit_factor=None,  # TODO: Calculate
        ))

    # Calculate by strategy
    strategies = set(t.get("strategy") for t in trades if t.get("strategy"))
    by_strategy = []
    for strategy in strategies:
        strat_trades = [t for t in trades if t.get("strategy") == strategy]
        closed = [t for t in strat_trades if t["status"] == TradeStatus.CLOSED]
        wins = [t for t in closed if t.get("result") == TradeResult.WIN]
        total_pnl = sum(t.get("pnl", 0) for t in closed)

        by_strategy.append(PerformanceByStrategy(
            strategy=strategy,
            total_trades=len(closed),
            win_rate=len(wins) / len(closed) * 100 if closed else 0,
            total_pnl=total_pnl,
            profit_factor=None,  # TODO: Calculate
        ))

    # Generate equity curve
    equity_curve = []
    base_balance = 10000.0
    running_balance = base_balance
    for i in range(days, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_trades = [t for t in trades if t.get("closed_at") and
                      t["closed_at"].date() == day.date()]
        daily_pnl = sum(t.get("pnl", 0) for t in day_trades)
        running_balance += daily_pnl
        equity_curve.append(BalancePoint(
            timestamp=day,
            balance=running_balance,
            equity=running_balance,
        ))

    # Generate daily P/L
    daily_pnl = []
    for i in range(days, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_trades = [t for t in trades if t.get("closed_at") and
                      t["closed_at"].date() == day.date()]
        pnl = sum(t.get("pnl", 0) for t in day_trades)
        daily_pnl.append({
            "date": day.date().isoformat(),
            "pnl": pnl,
            "trades": len(day_trades),
        })

    return PerformanceResponse(
        period_days=days,
        start_date=cutoff,
        end_date=datetime.utcnow(),
        overall=overall,
        by_pair=by_pair,
        by_strategy=by_strategy,
        equity_curve=equity_curve,
        daily_pnl=daily_pnl,
    )


@router.get("/trades/stats/summary")
async def get_trades_summary(
    days: int = Query(default=7, ge=1, le=365),
):
    """
    Get quick trade statistics summary.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    trades = [t for t in _trades_store if t["opened_at"] >= cutoff]
    closed = [t for t in trades if t["status"] == TradeStatus.CLOSED]
    open_trades = [t for t in trades if t["status"] == TradeStatus.OPEN]

    wins = len([t for t in closed if t.get("result") == TradeResult.WIN])

    return {
        "period_days": days,
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "wins": wins,
        "losses": len(closed) - wins,
        "win_rate": wins / len(closed) * 100 if closed else 0,
        "total_pnl": sum(t.get("pnl", 0) for t in closed),
        "unrealized_pnl": sum(t.get("pnl", 0) for t in open_trades),
        "timestamp": datetime.utcnow().isoformat(),
    }
