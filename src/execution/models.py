from __future__ import annotations

"""
Execution Data Models

Data classes for order execution system including requests,
results, and status tracking.

Author: HERMES Trading System
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4


class OrderStatusEnum(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class SignalType(str, Enum):
    """Trading signal type."""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    SCALE_IN = "SCALE_IN"
    SCALE_OUT = "SCALE_OUT"


@dataclass
class Signal:
    """
    Trading signal from strategy.

    Attributes:
        signal_type: Type of signal (BUY, SELL, CLOSE, etc.)
        instrument: Trading instrument (e.g., EUR_USD, BTCUSDT)
        broker: Target broker (oanda, binance)
        entry_price: Suggested entry price
        stop_loss: Stop loss level
        take_profit: Take profit level
        confidence: Signal confidence (0.0 to 1.0)
        strategy_name: Name of strategy that generated signal
        timeframe: Timeframe of analysis
        indicators: Supporting indicator values
        metadata: Additional signal metadata
        timestamp: Signal generation time
    """
    signal_type: SignalType
    instrument: str
    broker: Literal["oanda", "binance"]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = 0.5
    strategy_name: str = ""
    timeframe: str = "H1"
    indicators: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_buy(self) -> bool:
        """Check if signal is bullish."""
        return self.signal_type in (SignalType.BUY, SignalType.SCALE_IN)

    @property
    def is_sell(self) -> bool:
        """Check if signal is bearish."""
        return self.signal_type == SignalType.SELL

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk-reward ratio."""
        if self.entry_price == 0 or self.stop_loss == self.entry_price:
            return 0.0

        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)

        return reward / risk if risk > 0 else 0.0

    @property
    def side(self) -> str:
        """Get order side (BUY or SELL)."""
        if self.signal_type in (SignalType.BUY, SignalType.SCALE_IN):
            return "BUY"
        return "SELL"


@dataclass
class OrderRequest:
    """
    Order request to be processed by execution system.

    Attributes:
        signal: Original trading signal
        broker: Target broker (oanda, binance)
        instrument: Trading instrument
        side: Order side (BUY, SELL)
        quantity: Order quantity/units
        entry_price: Expected entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        leverage: Leverage multiplier (crypto only)
        order_type: Order type (MARKET, LIMIT)
        time_in_force: Time in force (GTC, IOC, FOK)
        request_id: Unique request identifier
        created_at: Request creation time
        metadata: Additional request metadata
    """
    signal: Signal
    broker: Literal["oanda", "binance"]
    instrument: str
    side: Literal["BUY", "SELL"]
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: Optional[int] = None
    order_type: str = "MARKET"
    time_in_force: str = "GTC"
    request_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_crypto(self) -> bool:
        """Check if order is for crypto."""
        return self.broker == "binance"

    @property
    def is_forex(self) -> bool:
        """Check if order is for forex."""
        return self.broker == "oanda"

    @property
    def risk_amount(self) -> float:
        """Calculate risk amount based on stop loss."""
        price_diff = abs(self.entry_price - self.stop_loss)
        return price_diff * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "broker": self.broker,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionResult:
    """
    Result of order execution.

    Attributes:
        success: Whether execution succeeded
        order_id: Broker order ID if successful
        fill_price: Actual fill price
        slippage: Slippage in price units
        slippage_pct: Slippage as percentage
        error: Error message if failed
        timestamp: Execution timestamp
        broker: Broker that executed the order
        instrument: Traded instrument
        side: Order side
        quantity: Filled quantity
        execution_time_ms: Execution latency in milliseconds
        metadata: Additional execution metadata
    """
    success: bool
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    slippage: Optional[float] = None
    slippage_pct: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    broker: Optional[str] = None
    instrument: Optional[str] = None
    side: Optional[str] = None
    quantity: Optional[float] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(
        cls,
        error: str,
        broker: Optional[str] = None,
        instrument: Optional[str] = None,
    ) -> "ExecutionResult":
        """Create a failure result."""
        return cls(
            success=False,
            error=error,
            broker=broker,
            instrument=instrument,
            timestamp=datetime.utcnow(),
        )

    @classmethod
    def from_order(
        cls,
        order_id: str,
        fill_price: float,
        expected_price: float,
        broker: str,
        instrument: str,
        side: str,
        quantity: float,
        execution_time_ms: Optional[float] = None,
    ) -> "ExecutionResult":
        """Create success result from order fill."""
        slippage = fill_price - expected_price
        slippage_pct = (slippage / expected_price) * 100 if expected_price > 0 else 0.0

        return cls(
            success=True,
            order_id=order_id,
            fill_price=fill_price,
            slippage=slippage,
            slippage_pct=slippage_pct,
            broker=broker,
            instrument=instrument,
            side=side,
            quantity=quantity,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "slippage_pct": self.slippage_pct,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "broker": self.broker,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class OrderStatus:
    """
    Current status of a queued order.

    Attributes:
        queue_id: Queue identifier
        request_id: Original request ID
        status: Current status
        position_in_queue: Position in queue (if pending)
        result: Execution result (if completed)
        created_at: When order was queued
        updated_at: Last status update time
        attempts: Number of execution attempts
        error_history: List of errors from failed attempts
    """
    queue_id: str
    request_id: str
    status: OrderStatusEnum
    position_in_queue: Optional[int] = None
    result: Optional[ExecutionResult] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    attempts: int = 0
    error_history: List[str] = field(default_factory=list)

    @property
    def is_pending(self) -> bool:
        """Check if order is still pending."""
        return self.status in (OrderStatusEnum.PENDING, OrderStatusEnum.QUEUED)

    @property
    def is_complete(self) -> bool:
        """Check if order processing is complete."""
        return self.status in (
            OrderStatusEnum.FILLED,
            OrderStatusEnum.CANCELLED,
            OrderStatusEnum.REJECTED,
            OrderStatusEnum.FAILED,
        )

    @property
    def is_successful(self) -> bool:
        """Check if order was successfully filled."""
        return self.status == OrderStatusEnum.FILLED

    def update_status(self, new_status: OrderStatusEnum) -> None:
        """Update status with timestamp."""
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def add_error(self, error: str) -> None:
        """Add error to history."""
        self.error_history.append(f"[{datetime.utcnow().isoformat()}] {error}")
        self.attempts += 1


@dataclass
class CloseResult:
    """
    Result of closing a position.

    Attributes:
        success: Whether close succeeded
        position_id: Position/trade ID
        broker: Broker name
        instrument: Trading instrument
        close_price: Position close price
        pnl: Realized P&L
        error: Error message if failed
        timestamp: Close timestamp
    """
    success: bool
    position_id: str
    broker: str
    instrument: Optional[str] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def failure(
        cls,
        position_id: str,
        broker: str,
        error: str,
    ) -> "CloseResult":
        """Create failure result."""
        return cls(
            success=False,
            position_id=position_id,
            broker=broker,
            error=error,
            timestamp=datetime.utcnow(),
        )


@dataclass
class Position:
    """
    Represents an open trading position.

    This is a unified position model that works across both
    forex (OANDA) and crypto (Binance) brokers.

    Attributes:
        position_id: Unique position identifier
        broker: Broker name (oanda, binance)
        instrument: Trading instrument
        side: Position side (BUY/SELL or LONG/SHORT)
        entry_price: Average entry price
        quantity: Position size
        stop_loss: Current stop loss price
        take_profit: Current take profit price
        unrealized_pnl: Unrealized P&L
        leverage: Leverage multiplier
        opened_at: Position open time
        metadata: Additional position data
    """
    position_id: str
    broker: Literal["oanda", "binance"]
    instrument: str
    side: str
    entry_price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    leverage: int = 1
    opened_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side.upper() in ("BUY", "LONG")

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side.upper() in ("SELL", "SHORT")

    @property
    def notional_value(self) -> float:
        """Calculate notional value."""
        return self.entry_price * self.quantity

    def profit_at_price(self, current_price: float) -> float:
        """Calculate profit at given price."""
        price_diff = current_price - self.entry_price
        if self.is_short:
            price_diff = -price_diff
        return price_diff * self.quantity

    def should_trail_stop(self, current_price: float, trail_distance: float) -> bool:
        """
        Check if stop loss should be trailed.

        Args:
            current_price: Current market price
            trail_distance: Distance to trail stop behind price

        Returns:
            True if stop should be updated
        """
        if self.stop_loss is None:
            return False

        if self.is_long:
            new_stop = current_price - trail_distance
            return new_stop > self.stop_loss
        else:
            new_stop = current_price + trail_distance
            return new_stop < self.stop_loss
