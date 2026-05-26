from __future__ import annotations

"""
Risk Management Data Models
Defines configuration and assessment structures for the risk management system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class CircuitBreakerState(Enum):
    """State of the circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Tripped, no trading allowed
    HALF_OPEN = "half_open"  # Testing if conditions improved


class TradeDirection(Enum):
    """Direction of a trade."""
    LONG = "long"
    SHORT = "short"


@dataclass
class RiskConfig:
    """
    Risk management configuration with hardcoded spec values as defaults.
    """
    max_risk_per_trade: float = 0.02  # 2% max risk per trade
    max_daily_loss: float = 0.06      # 6% max daily loss
    max_leverage: float = 10.0        # Maximum leverage allowed
    min_confidence: float = 0.70      # Minimum ML confidence threshold
    min_reward_risk: float = 2.0      # Minimum reward:risk ratio
    max_open_trades: int = 3          # Maximum concurrent positions
    max_spread_pips: float = 2.0      # Maximum spread in pips
    use_trailing_stop: bool = True    # Enable trailing stops
    consecutive_loss_limit: int = 5   # Max consecutive losses before circuit breaker
    use_half_kelly: bool = True       # Use half Kelly for position sizing
    atr_multiplier: float = 1.5       # ATR multiplier for trailing stops


@dataclass
class RiskAssessment:
    """
    Result of a risk assessment for a potential trade.
    """
    allowed: bool
    reason: str
    suggested_position_size: float
    risk_score: float  # 0-1, higher = riskier
    kelly_fraction: Optional[float] = None
    reward_risk_ratio: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate risk score is within bounds."""
        if not 0 <= self.risk_score <= 1:
            raise ValueError(f"risk_score must be between 0 and 1, got {self.risk_score}")


@dataclass
class Position:
    """
    Represents an open trading position.
    """
    symbol: str
    direction: TradeDirection
    entry_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    opened_at: datetime = field(default_factory=datetime.utcnow)
    trailing_stop: Optional[float] = None
    unrealized_pnl: float = 0.0

    @property
    def risk_amount(self) -> float:
        """Calculate the risk amount based on stop loss distance."""
        if self.direction == TradeDirection.LONG:
            return (self.entry_price - self.stop_loss) * self.position_size
        else:
            return (self.stop_loss - self.entry_price) * self.position_size


@dataclass
class Signal:
    """
    Trading signal from the ML model or strategy.
    """
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # ML model confidence 0-1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    strategy_name: str = "default"
    metadata: dict = field(default_factory=dict)

    @property
    def reward_risk_ratio(self) -> float:
        """Calculate the reward:risk ratio."""
        if self.direction == TradeDirection.LONG:
            risk = self.entry_price - self.stop_loss
            reward = self.take_profit - self.entry_price
        else:
            risk = self.stop_loss - self.entry_price
            reward = self.entry_price - self.take_profit

        if risk <= 0:
            return 0.0
        return reward / risk


@dataclass
class CircuitBreakerStatus:
    """
    Status information for the circuit breaker.
    """
    state: CircuitBreakerState
    tripped_at: Optional[datetime] = None
    reason: Optional[str] = None
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    can_trade: bool = True
    cooldown_remaining_seconds: int = 0

    def to_dict(self) -> dict:
        """Convert status to dictionary for API responses."""
        return {
            "state": self.state.value,
            "tripped_at": self.tripped_at.isoformat() if self.tripped_at else None,
            "reason": self.reason,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "can_trade": self.can_trade,
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds
        }


@dataclass
class DailyStats:
    """
    Daily trading statistics for risk management.
    """
    date: datetime = field(default_factory=lambda: datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    ))
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    consecutive_losses: int = 0
    max_drawdown: float = 0.0

    @property
    def net_pnl(self) -> float:
        """Calculate net P&L for the day."""
        return self.gross_profit - self.gross_loss

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def avg_win(self) -> float:
        """Calculate average winning trade."""
        if self.winning_trades == 0:
            return 0.0
        return self.gross_profit / self.winning_trades

    @property
    def avg_loss(self) -> float:
        """Calculate average losing trade."""
        if self.losing_trades == 0:
            return 0.0
        return self.gross_loss / self.losing_trades
