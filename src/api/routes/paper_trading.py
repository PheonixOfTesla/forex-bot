from __future__ import annotations

"""
Paper Trading API Routes

Provides endpoints for paper trading simulation and performance tracking.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Path

from ...models.paper_trade import (
    PaperTrade,
    PaperPosition,
    TradingMetrics,
    PaperTradeStatus,
    TradeDirection,
    ExecuteTradeRequest,
    CloseTradeRequest,
    PaperBalanceResponse,
    PaperPositionsResponse,
    PaperHistoryResponse,
    ExecuteTradeResponse,
    ResetAccountResponse,
)
from ...services.paper_trading import get_paper_trading_engine
from ...services.learning_engine import get_learning_engine

logger = logging.getLogger(__name__)


def _record_trade_to_learning(trade: PaperTrade, signal_data: dict = None) -> None:
    """
    Record a closed trade to the learning engine for feedback.

    This wires the paper trading results to the learning system
    so we can track what's working and adjust future signals.
    """
    try:
        learning = get_learning_engine()

        # Determine outcome
        if trade.pnl is None:
            return  # Trade not closed yet

        if trade.pnl > 0:
            outcome = "win"
        elif trade.pnl < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # Get indicator info from signal if available
        indicators_used = signal_data.get("indicators_used", []) if signal_data else []
        indicator_values = signal_data.get("indicator_values", {}) if signal_data else {}
        strategy = signal_data.get("strategy", "unknown") if signal_data else "unknown"
        timeframe = signal_data.get("timeframe", "1H") if signal_data else "1H"
        confidence = signal_data.get("confidence", 75.0) if signal_data else 75.0

        # Track the prediction outcome
        learning.track_prediction(
            signal_id=trade.signal_id or trade.id,
            predicted_direction=trade.direction.value,
            predicted_confidence=confidence,
            actual_outcome=outcome,
            pair=trade.pair,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            entry_timestamp=trade.opened_at,
            exit_timestamp=trade.closed_at,
            indicators_used=indicators_used,
            indicator_values=indicator_values,
            strategy=strategy,
            timeframe=timeframe,
        )

        logger.info(f"Recorded trade {trade.id} to learning engine: {outcome}")

    except Exception as e:
        logger.error(f"Failed to record trade to learning engine: {e}")
router = APIRouter()


# =============================================================================
# Balance & Account Endpoints
# =============================================================================


@router.get("/paper/balance", response_model=PaperBalanceResponse)
async def get_paper_balance() -> PaperBalanceResponse:
    """
    Get virtual balance and trading metrics.

    Returns the current paper trading account balance, equity,
    unrealized P&L, and performance metrics.

    Returns:
        PaperBalanceResponse with balance info and metrics
    """
    logger.info("Fetching paper trading balance")

    engine = get_paper_trading_engine()
    info = engine.get_balance_info()

    return PaperBalanceResponse(
        initial_balance=info["initial_balance"],
        balance=info["balance"],
        equity=info["equity"],
        unrealized_pnl=info["unrealized_pnl"],
        open_positions_count=info["open_positions_count"],
        open_positions_value=info["open_positions_value"],
        metrics=info["metrics"],
        peak_balance=info["peak_balance"],
        created_at=info["created_at"],
        last_updated=info["last_updated"],
    )


@router.get("/paper/metrics", response_model=TradingMetrics)
async def get_paper_metrics() -> TradingMetrics:
    """
    Get trading performance metrics.

    Returns detailed performance metrics including win rate,
    total P&L, average profit, max drawdown, etc.

    Returns:
        TradingMetrics with performance data
    """
    logger.info("Fetching paper trading metrics")

    engine = get_paper_trading_engine()
    return engine.metrics


@router.get("/paper/summary")
async def get_paper_summary():
    """
    Get a quick summary of the paper trading account.

    Returns a lightweight summary with key metrics.
    """
    logger.info("Fetching paper trading summary")

    engine = get_paper_trading_engine()
    return engine.get_summary()


# =============================================================================
# Positions Endpoints
# =============================================================================


@router.get("/paper/positions", response_model=PaperPositionsResponse)
async def get_paper_positions() -> PaperPositionsResponse:
    """
    Get current open positions.

    Returns all open paper trading positions with current
    unrealized P&L.

    Returns:
        PaperPositionsResponse with positions list
    """
    logger.info("Fetching paper trading positions")

    engine = get_paper_trading_engine()
    positions = engine.get_open_positions()

    total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)

    return PaperPositionsResponse(
        positions=positions,
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        positions_count=len(positions),
    )


@router.get("/paper/positions/{trade_id}", response_model=PaperPosition)
async def get_paper_position(
    trade_id: str = Path(..., description="Trade ID"),
) -> PaperPosition:
    """
    Get a specific open position.

    Args:
        trade_id: The trade ID to look up

    Returns:
        PaperPosition details

    Raises:
        404: Position not found
    """
    logger.info(f"Fetching paper position: {trade_id}")

    engine = get_paper_trading_engine()
    positions = engine.get_open_positions()

    for position in positions:
        if position.trade_id == trade_id:
            return position

    raise HTTPException(
        status_code=404,
        detail=f"Position not found: {trade_id}",
    )


# =============================================================================
# Trade History Endpoints
# =============================================================================


@router.get("/paper/history", response_model=PaperHistoryResponse)
async def get_paper_history(
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
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair",
    ),
) -> PaperHistoryResponse:
    """
    Get paper trade history.

    Returns closed trades with pagination support.

    Args:
        limit: Maximum number of trades to return (1-500)
        offset: Number of trades to skip for pagination
        pair: Optional filter by trading pair

    Returns:
        PaperHistoryResponse with trades list
    """
    logger.info(f"Fetching paper trade history: limit={limit}, offset={offset}, pair={pair}")

    engine = get_paper_trading_engine()
    trades = engine.get_trade_history(limit=limit, offset=offset, pair=pair)

    # Calculate totals
    all_trades = engine.closed_trades
    if pair:
        all_trades = [t for t in all_trades if t.pair.upper() == pair.upper()]

    total_pnl = sum(t.pnl or 0 for t in all_trades)
    winning = len([t for t in all_trades if t.pnl and t.pnl > 0])
    losing = len([t for t in all_trades if t.pnl and t.pnl < 0])

    return PaperHistoryResponse(
        trades=trades,
        total_trades=len(all_trades),
        total_pnl=round(total_pnl, 2),
        winning_trades=winning,
        losing_trades=losing,
    )


@router.get("/paper/history/{trade_id}", response_model=PaperTrade)
async def get_paper_trade(
    trade_id: str = Path(..., description="Trade ID"),
) -> PaperTrade:
    """
    Get a specific trade from history.

    Args:
        trade_id: The trade ID to look up

    Returns:
        PaperTrade details

    Raises:
        404: Trade not found
    """
    logger.info(f"Fetching paper trade: {trade_id}")

    engine = get_paper_trading_engine()

    # Check open trades first
    for trade in engine.open_positions:
        if trade.id == trade_id:
            return trade

    # Check closed trades
    for trade in engine.closed_trades:
        if trade.id == trade_id:
            return trade

    raise HTTPException(
        status_code=404,
        detail=f"Trade not found: {trade_id}",
    )


# =============================================================================
# Trade Execution Endpoints
# =============================================================================


@router.post("/paper/execute", response_model=ExecuteTradeResponse)
async def execute_paper_trade(
    request: ExecuteTradeRequest,
) -> ExecuteTradeResponse:
    """
    Execute a paper trade.

    Opens a new paper trading position based on the provided parameters.

    Args:
        request: Trade execution request with pair, direction, price, etc.

    Returns:
        ExecuteTradeResponse with trade details

    Raises:
        400: Insufficient balance or invalid parameters
    """
    logger.info(
        f"Executing paper trade: {request.direction.value} {request.pair} @ {request.entry_price}"
    )

    engine = get_paper_trading_engine()
    success, message, trade = engine.execute_trade(request)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return ExecuteTradeResponse(
        success=True,
        trade_id=trade.id if trade else None,
        message=message,
        trade=trade,
        new_balance=engine.balance,
    )


@router.post("/paper/positions/{trade_id}/close", response_model=ExecuteTradeResponse)
async def close_paper_position(
    trade_id: str = Path(..., description="Trade ID"),
    request: CloseTradeRequest = None,
) -> ExecuteTradeResponse:
    """
    Close an open paper position.

    Automatically records the trade outcome to the learning engine
    for feedback and model improvement.

    Args:
        trade_id: ID of the trade to close
        request: Close request with exit price

    Returns:
        ExecuteTradeResponse with closed trade details

    Raises:
        404: Trade not found
        400: Trade cannot be closed
    """
    logger.info(f"Closing paper position: {trade_id}")

    if request is None:
        raise HTTPException(
            status_code=400,
            detail="Exit price is required",
        )

    engine = get_paper_trading_engine()
    success, message, trade = engine.close_trade(
        trade_id=trade_id,
        exit_price=request.exit_price,
        notes=request.notes,
    )

    if not success:
        raise HTTPException(status_code=404, detail=message)

    # Record to learning engine for feedback
    if trade:
        # Get signal metadata if available
        signal_data = _signal_metadata_store.pop(trade_id, None)
        _record_trade_to_learning(trade, signal_data)

    return ExecuteTradeResponse(
        success=True,
        trade_id=trade.id if trade else None,
        message=message,
        trade=trade,
        new_balance=engine.balance,
    )


@router.post("/paper/close-all")
async def close_all_paper_positions(
    exit_prices: dict = None,
):
    """
    Close all open paper positions.

    Automatically records each trade outcome to the learning engine.

    Args:
        exit_prices: Dict mapping pair to exit price (optional)

    Returns:
        Summary of closed positions
    """
    logger.info("Closing all paper positions")

    engine = get_paper_trading_engine()

    if not engine.open_positions:
        return {
            "success": True,
            "message": "No open positions to close",
            "closed_count": 0,
            "new_balance": engine.balance,
        }

    # Use provided prices or current entry prices as fallback
    prices = exit_prices or {}
    for trade in engine.open_positions:
        if trade.pair not in prices:
            # Simulate slight price movement for unspecified pairs
            prices[trade.pair] = trade.entry_price * 1.001

    closed_trades = engine.close_all_positions(prices)

    # Record each closed trade to the learning engine
    for trade in closed_trades:
        signal_data = _signal_metadata_store.pop(trade.id, None)
        _record_trade_to_learning(trade, signal_data)

    total_pnl = sum(t.pnl or 0 for t in closed_trades)

    return {
        "success": True,
        "message": f"Closed {len(closed_trades)} positions",
        "closed_count": len(closed_trades),
        "total_pnl": round(total_pnl, 2),
        "new_balance": engine.balance,
        "closed_trades": [t.id for t in closed_trades],
    }


# =============================================================================
# Account Management Endpoints
# =============================================================================


@router.post("/paper/reset", response_model=ResetAccountResponse)
async def reset_paper_account(
    new_balance: Optional[float] = Query(
        default=None,
        gt=0,
        description="New starting balance (defaults to $10,000)",
    ),
) -> ResetAccountResponse:
    """
    Reset the paper trading account.

    Clears all trades and resets balance to the initial amount.

    Args:
        new_balance: Optional new starting balance (default: $10,000)

    Returns:
        ResetAccountResponse with reset details
    """
    logger.info(f"Resetting paper trading account (new_balance={new_balance})")

    engine = get_paper_trading_engine()
    result = engine.reset_account(new_balance=new_balance)

    return ResetAccountResponse(
        success=result["success"],
        message=result["message"],
        new_balance=result["new_balance"],
        previous_balance=result["previous_balance"],
        previous_total_pnl=result["previous_total_pnl"],
    )


# =============================================================================
# Signal Integration Endpoint
# =============================================================================


# Store signal metadata for learning when trades close
_signal_metadata_store: Dict[str, dict] = {}


@router.post("/paper/execute-signal/{signal_id}")
async def execute_signal_paper(
    signal_id: str = Path(..., description="Signal ID to execute"),
    quantity: Optional[float] = Query(
        default=None,
        gt=0,
        description="Override position size",
    ),
):
    """
    Execute a trading signal in paper mode.

    This endpoint fetches signal details and executes a paper trade.
    Stores signal metadata for learning feedback when the trade closes.

    Args:
        signal_id: Signal ID to execute
        quantity: Optional position size override

    Returns:
        Trade execution result
    """
    logger.info(f"Executing signal in paper mode: {signal_id}")

    # Import here to avoid circular imports
    from .signals import _get_signals_store

    # Get the signal
    signals = _get_signals_store()
    signal = signals.get(signal_id)

    if not signal:
        raise HTTPException(
            status_code=404,
            detail=f"Signal not found: {signal_id}",
        )

    # Map signal direction to trade direction
    direction_map = {
        "buy": TradeDirection.BUY,
        "sell": TradeDirection.SELL,
        "long": TradeDirection.LONG,
        "short": TradeDirection.SHORT,
    }

    direction = direction_map.get(
        signal["direction"].value,
        TradeDirection.BUY,
    )

    # Create trade request from signal
    request = ExecuteTradeRequest(
        signal_id=signal_id,
        pair=signal["pair"],
        direction=direction,
        entry_price=signal["entry_price"],
        quantity=quantity,
        stop_loss=signal.get("stop_loss"),
        take_profit=signal.get("take_profit"),
        notes=f"From signal: {signal_id} ({signal['strategy']})",
    )

    engine = get_paper_trading_engine()
    success, message, trade = engine.execute_trade(request)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Store signal metadata for learning when trade closes
    if trade:
        _signal_metadata_store[trade.id] = {
            "signal_id": signal_id,
            "confidence": signal.get("confidence", 75.0),
            "strategy": signal.get("strategy", "unknown"),
            "timeframe": signal.get("timeframe", "1H"),
            "indicators_used": list(signal.get("features", {}).keys()),
            "indicator_values": signal.get("features", {}),
        }

    return {
        "success": True,
        "message": message,
        "signal_id": signal_id,
        "trade_id": trade.id if trade else None,
        "trade": trade,
        "new_balance": engine.balance,
    }
