from __future__ import annotations

"""
Paper Trading Models

Pydantic models for paper trading simulation.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PaperTradeStatus(str, Enum):
    """Paper trade status."""
    OPEN = "open"
    CLOSED = "closed"


class TradeDirection(str, Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


# =============================================================================
# Core Models
# =============================================================================


class PaperTrade(BaseModel):
    """
    Represents a paper trade (either open position or closed trade).

    Attributes:
        id: Unique trade identifier
        signal_id: Optional signal ID that triggered this trade
        pair: Trading pair (e.g., EUR/USD, BTCUSDT)
        direction: Trade direction (buy/sell)
        entry_price: Entry price
        exit_price: Exit price (None if still open)
        quantity: Position size
        pnl: Realized P&L (None if still open)
        status: Trade status (open/closed)
        opened_at: When the trade was opened
        closed_at: When the trade was closed (None if still open)
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
    """
    id: str = Field(default_factory=lambda: f"pt_{uuid4().hex[:12]}")
    signal_id: Optional[str] = Field(None, description="Signal ID that triggered this trade")
    pair: str = Field(..., description="Trading pair (e.g., EUR/USD)")
    direction: TradeDirection = Field(..., description="Trade direction")
    entry_price: float = Field(..., description="Entry price")
    exit_price: Optional[float] = Field(None, description="Exit price")
    quantity: float = Field(..., description="Position size")
    pnl: Optional[float] = Field(None, description="Realized P&L")
    pnl_pct: Optional[float] = Field(None, description="P&L percentage")
    status: PaperTradeStatus = Field(default=PaperTradeStatus.OPEN)
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = Field(None, description="Close timestamp")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    fees: float = Field(default=0.0, description="Trading fees")
    notes: Optional[str] = Field(None, description="Trade notes")

    def calculate_pnl(self, exit_price: float) -> tuple[float, float]:
        """
        Calculate P&L for a given exit price.

        Returns:
            Tuple of (pnl_amount, pnl_percentage)
        """
        if self.direction in (TradeDirection.BUY, TradeDirection.LONG):
            pnl = (exit_price - self.entry_price) * self.quantity
        else:
            pnl = (self.entry_price - exit_price) * self.quantity

        # Subtract fees
        pnl -= self.fees

        # Calculate percentage
        position_value = self.entry_price * self.quantity
        pnl_pct = (pnl / position_value * 100) if position_value > 0 else 0

        return round(pnl, 2), round(pnl_pct, 2)

    def close(self, exit_price: float) -> None:
        """Close the trade at the given exit price."""
        self.exit_price = exit_price
        self.pnl, self.pnl_pct = self.calculate_pnl(exit_price)
        self.status = PaperTradeStatus.CLOSED
        self.closed_at = datetime.utcnow()


class PaperPosition(BaseModel):
    """
    Current open position summary.

    Attributes:
        trade_id: Reference to the PaperTrade
        pair: Trading pair
        direction: Position direction
        entry_price: Entry price
        current_price: Current market price
        quantity: Position size
        unrealized_pnl: Unrealized P&L
        unrealized_pnl_pct: Unrealized P&L percentage
        opened_at: Position open time
        stop_loss: Stop loss price
        take_profit: Take profit price
    """
    trade_id: str = Field(..., description="Trade ID")
    pair: str = Field(..., description="Trading pair")
    direction: TradeDirection = Field(..., description="Position direction")
    entry_price: float = Field(..., description="Entry price")
    current_price: float = Field(..., description="Current market price")
    quantity: float = Field(..., description="Position size")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    unrealized_pnl_pct: float = Field(..., description="Unrealized P&L percentage")
    opened_at: datetime = Field(..., description="Position open time")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")


class TradingMetrics(BaseModel):
    """
    Trading performance metrics.

    Attributes:
        win_rate: Percentage of winning trades (0-100)
        total_pnl: Total realized P&L
        trades_count: Total number of closed trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        avg_profit: Average profit per trade
        avg_win: Average winning trade amount
        avg_loss: Average losing trade amount
        max_drawdown: Maximum drawdown amount
        max_drawdown_pct: Maximum drawdown percentage
        profit_factor: Gross profit / Gross loss
        largest_win: Largest winning trade
        largest_loss: Largest losing trade
        consecutive_wins: Current consecutive wins
        consecutive_losses: Current consecutive losses
        max_consecutive_wins: Maximum consecutive wins
        max_consecutive_losses: Maximum consecutive losses
    """
    win_rate: float = Field(0.0, ge=0, le=100, description="Win rate percentage")
    total_pnl: float = Field(0.0, description="Total realized P&L")
    trades_count: int = Field(0, ge=0, description="Total closed trades")
    winning_trades: int = Field(0, ge=0, description="Number of winning trades")
    losing_trades: int = Field(0, ge=0, description="Number of losing trades")
    avg_profit: float = Field(0.0, description="Average profit per trade")
    avg_win: float = Field(0.0, description="Average winning trade")
    avg_loss: float = Field(0.0, description="Average losing trade")
    max_drawdown: float = Field(0.0, description="Maximum drawdown amount")
    max_drawdown_pct: float = Field(0.0, description="Maximum drawdown percentage")
    profit_factor: Optional[float] = Field(None, description="Gross profit / Gross loss")
    largest_win: float = Field(0.0, description="Largest winning trade")
    largest_loss: float = Field(0.0, description="Largest losing trade (negative)")
    consecutive_wins: int = Field(0, ge=0, description="Current consecutive wins")
    consecutive_losses: int = Field(0, ge=0, description="Current consecutive losses")
    max_consecutive_wins: int = Field(0, ge=0, description="Maximum consecutive wins")
    max_consecutive_losses: int = Field(0, ge=0, description="Maximum consecutive losses")


class PaperAccountState(BaseModel):
    """
    Complete paper account state for persistence.

    Attributes:
        initial_balance: Starting balance
        balance: Current available balance
        equity: Balance + unrealized P&L
        open_trades: List of open trades
        closed_trades: List of closed trades
        metrics: Trading performance metrics
        peak_balance: Highest balance achieved
        created_at: Account creation time
        last_updated: Last update time
    """
    initial_balance: float = Field(default=10000.0, description="Initial balance")
    balance: float = Field(default=10000.0, description="Current available balance")
    equity: float = Field(default=10000.0, description="Balance + unrealized P&L")
    open_trades: List[PaperTrade] = Field(default_factory=list)
    closed_trades: List[PaperTrade] = Field(default_factory=list)
    metrics: TradingMetrics = Field(default_factory=TradingMetrics)
    peak_balance: float = Field(default=10000.0, description="Peak balance for drawdown")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API Request/Response Models
# =============================================================================


class ExecuteTradeRequest(BaseModel):
    """Request to execute a paper trade."""
    signal_id: Optional[str] = Field(None, description="Signal ID to execute")
    pair: str = Field(..., description="Trading pair")
    direction: TradeDirection = Field(..., description="Trade direction")
    entry_price: float = Field(..., gt=0, description="Entry price")
    quantity: Optional[float] = Field(None, gt=0, description="Position size (auto-calculated if not provided)")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    notes: Optional[str] = Field(None, description="Trade notes")


class CloseTradeRequest(BaseModel):
    """Request to close a paper trade."""
    exit_price: float = Field(..., gt=0, description="Exit price")
    notes: Optional[str] = Field(None, description="Close notes")


class PaperBalanceResponse(BaseModel):
    """Response for balance endpoint."""
    initial_balance: float = Field(..., description="Starting balance")
    balance: float = Field(..., description="Current available balance")
    equity: float = Field(..., description="Balance + unrealized P&L")
    unrealized_pnl: float = Field(..., description="Total unrealized P&L")
    open_positions_count: int = Field(..., description="Number of open positions")
    open_positions_value: float = Field(..., description="Total value of open positions")
    metrics: TradingMetrics = Field(..., description="Trading metrics")
    peak_balance: float = Field(..., description="Peak balance achieved")
    created_at: datetime = Field(..., description="Account creation time")
    last_updated: datetime = Field(..., description="Last update time")


class PaperPositionsResponse(BaseModel):
    """Response for positions endpoint."""
    positions: List[PaperPosition] = Field(default_factory=list)
    total_unrealized_pnl: float = Field(0.0, description="Total unrealized P&L")
    positions_count: int = Field(0, description="Number of open positions")


class PaperHistoryResponse(BaseModel):
    """Response for trade history endpoint."""
    trades: List[PaperTrade] = Field(default_factory=list)
    total_trades: int = Field(0, description="Total number of trades")
    total_pnl: float = Field(0.0, description="Total realized P&L")
    winning_trades: int = Field(0, description="Number of winning trades")
    losing_trades: int = Field(0, description="Number of losing trades")


class ExecuteTradeResponse(BaseModel):
    """Response for trade execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    trade_id: Optional[str] = Field(None, description="Trade ID if successful")
    message: str = Field(..., description="Execution message")
    trade: Optional[PaperTrade] = Field(None, description="Trade details")
    new_balance: float = Field(..., description="Balance after execution")


class ResetAccountResponse(BaseModel):
    """Response for account reset."""
    success: bool = Field(..., description="Whether reset succeeded")
    message: str = Field(..., description="Reset message")
    new_balance: float = Field(..., description="New balance after reset")
    previous_balance: float = Field(..., description="Balance before reset")
    previous_total_pnl: float = Field(..., description="Total P&L before reset")
    reset_at: datetime = Field(default_factory=datetime.utcnow)
