from __future__ import annotations

"""
Core Risk Manager
Central risk management system coordinating all risk controls.
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from .circuit_breaker import CircuitBreaker
from .kelly import KellyCalculator
from .models import (
    DailyStats,
    Position,
    RiskAssessment,
    RiskConfig,
    Signal,
    TradeDirection,
)

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Core risk management system for forex trading.

    Coordinates position sizing, trade validation, and risk controls
    using Kelly criterion and circuit breaker protection.

    Hardcoded spec values:
    - MAX_RISK_PER_TRADE = 0.02 (2%)
    - MAX_DAILY_LOSS = 0.06 (6%)
    - MAX_LEVERAGE_USED = 10
    - MIN_ML_CONFIDENCE = 0.70
    - MIN_REWARD_RISK = 2.0
    - MAX_OPEN_TRADES = 3
    - SPREAD_MAX_PIPS = 2.0
    - TRAILING_STOP = True
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        kelly_calculator: Optional[KellyCalculator] = None,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        """
        Initialize the Risk Manager.

        Args:
            config: Risk configuration (uses defaults if not provided)
            kelly_calculator: Kelly criterion calculator
            circuit_breaker: Circuit breaker for emergency controls
        """
        self.config = config or RiskConfig()

        self.kelly = kelly_calculator or KellyCalculator(
            max_kelly=0.25,
            min_trades_required=30
        )

        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            daily_loss_limit=self.config.max_daily_loss,
            consecutive_loss_limit=self.config.consecutive_loss_limit
        )

        # Historical stats for Kelly calculation
        self._daily_stats = DailyStats()
        self._historical_win_rate: float = 0.50  # Start with no edge assumption
        self._historical_avg_win: float = 0.0
        self._historical_avg_loss: float = 0.0
        self._total_historical_trades: int = 0

    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        leverage: float = 1.0,
        ml_confidence: float = 1.0
    ) -> float:
        """
        Calculate the appropriate position size for a trade.

        Uses Kelly criterion with risk limits to determine optimal size.

        Args:
            account_balance: Current account balance
            entry_price: Planned entry price
            stop_loss: Stop loss price
            leverage: Leverage to use (capped at config max)
            ml_confidence: ML model confidence for this signal

        Returns:
            Position size in base currency units
        """
        if account_balance <= 0:
            return 0.0

        # Calculate pip distance to stop
        pip_distance = abs(entry_price - stop_loss)
        if pip_distance == 0:
            logger.warning("Stop loss equals entry price, cannot calculate position size")
            return 0.0

        # Cap leverage at configured maximum
        effective_leverage = min(leverage, self.config.max_leverage)

        # Calculate max risk amount
        max_risk_amount = account_balance * self.config.max_risk_per_trade

        # Get Kelly fraction if we have historical data
        kelly_fraction = 0.0
        if self._total_historical_trades >= 30:
            kelly_fraction, _ = self.kelly.get_optimal_fraction(
                win_rate=self._historical_win_rate,
                avg_win=self._historical_avg_win,
                avg_loss=self._historical_avg_loss,
                current_drawdown=self._calculate_current_drawdown(),
                ml_confidence=ml_confidence,
                trade_count=self._total_historical_trades,
                use_half_kelly=self.config.use_half_kelly
            )

        # Use Kelly or max risk, whichever is smaller
        if kelly_fraction > 0:
            kelly_risk_amount = account_balance * kelly_fraction
            risk_amount = min(max_risk_amount, kelly_risk_amount)
        else:
            # Not enough data for Kelly, use max risk
            risk_amount = max_risk_amount

        # Calculate position size
        # Position size = Risk Amount / (Pip Distance * Pip Value)
        # For simplicity, assuming pip value = 1 for calculation
        # Real implementation would adjust for currency pair
        position_size = (risk_amount / pip_distance) * effective_leverage

        return round(position_size, 2)

    def validate_trade(
        self,
        signal: Signal,
        current_positions: List[Position],
        daily_pnl: float,
        current_spread: Optional[float] = None,
        account_balance: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Validate whether a trade should be allowed based on risk rules.

        Args:
            signal: The trading signal to validate
            current_positions: List of currently open positions
            daily_pnl: Current daily P&L
            current_spread: Current spread in pips (optional)
            account_balance: Current account balance (optional)

        Returns:
            Tuple of (allowed, reason)
        """
        # Check circuit breaker first
        if self.circuit_breaker.is_tripped():
            status = self.circuit_breaker.get_status()
            return False, f"Circuit breaker tripped: {status.reason}"

        # Check if circuit breaker should trip
        is_tripped, trip_reason = self.circuit_breaker.check_and_trip(
            daily_pnl=daily_pnl,
            consecutive_losses=self._daily_stats.consecutive_losses,
            account_balance=account_balance
        )
        if is_tripped:
            return False, f"Circuit breaker triggered: {trip_reason}"

        # Check max positions
        allowed, reason = self._check_max_positions(len(current_positions))
        if not allowed:
            return False, reason

        # Check ML confidence
        if signal.confidence < self.config.min_confidence:
            return False, (
                f"ML confidence {signal.confidence:.2f} below minimum "
                f"{self.config.min_confidence:.2f}"
            )

        # Check reward:risk ratio
        allowed, reason = self._check_reward_risk(
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            signal.direction
        )
        if not allowed:
            return False, reason

        # Check spread if provided
        if current_spread is not None:
            allowed, reason = self._check_spread(
                current_spread,
                self.config.max_spread_pips
            )
            if not allowed:
                return False, reason

        # Check daily loss limit
        if account_balance and account_balance > 0:
            allowed, reason = self._check_daily_limit(daily_pnl, account_balance)
            if not allowed:
                return False, reason

        # Check for duplicate symbol positions
        for pos in current_positions:
            if pos.symbol == signal.symbol:
                return False, f"Already have open position in {signal.symbol}"

        return True, "All risk checks passed"

    def assess_trade(
        self,
        signal: Signal,
        current_positions: List[Position],
        daily_pnl: float,
        account_balance: float,
        current_spread: Optional[float] = None
    ) -> RiskAssessment:
        """
        Perform comprehensive risk assessment for a trade.

        Args:
            signal: The trading signal to assess
            current_positions: List of currently open positions
            daily_pnl: Current daily P&L
            account_balance: Current account balance
            current_spread: Current spread in pips (optional)

        Returns:
            RiskAssessment with full details
        """
        # Validate the trade
        allowed, reason = self.validate_trade(
            signal=signal,
            current_positions=current_positions,
            daily_pnl=daily_pnl,
            current_spread=current_spread,
            account_balance=account_balance
        )

        # Calculate position size
        position_size = 0.0
        kelly_fraction = None

        if allowed:
            position_size = self.calculate_position_size(
                account_balance=account_balance,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                ml_confidence=signal.confidence
            )

            if self._total_historical_trades >= 30:
                kelly_fraction, _ = self.kelly.get_optimal_fraction(
                    win_rate=self._historical_win_rate,
                    avg_win=self._historical_avg_win,
                    avg_loss=self._historical_avg_loss,
                    current_drawdown=self._calculate_current_drawdown(),
                    ml_confidence=signal.confidence,
                    trade_count=self._total_historical_trades,
                    use_half_kelly=self.config.use_half_kelly
                )

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            signal=signal,
            current_positions=current_positions,
            daily_pnl=daily_pnl,
            account_balance=account_balance,
            current_spread=current_spread
        )

        return RiskAssessment(
            allowed=allowed,
            reason=reason,
            suggested_position_size=position_size,
            risk_score=risk_score,
            kelly_fraction=kelly_fraction,
            reward_risk_ratio=signal.reward_risk_ratio
        )

    def check_daily_limit(self, daily_pnl: float, account_balance: float) -> bool:
        """
        Check if daily loss limit has been reached.

        Args:
            daily_pnl: Current daily P&L
            account_balance: Current account balance

        Returns:
            True if within limit, False if limit exceeded
        """
        allowed, _ = self._check_daily_limit(daily_pnl, account_balance)
        return allowed

    def _check_daily_limit(
        self,
        daily_pnl: float,
        account_balance: float
    ) -> Tuple[bool, str]:
        """Internal daily limit check with reason."""
        if account_balance <= 0:
            return False, "Invalid account balance"

        loss_percentage = abs(min(0, daily_pnl)) / account_balance

        if loss_percentage >= self.config.max_daily_loss:
            return False, (
                f"Daily loss limit reached: {loss_percentage:.1%} >= "
                f"{self.config.max_daily_loss:.1%}"
            )

        return True, "Within daily limit"

    def check_max_positions(self, current_count: int) -> bool:
        """
        Check if maximum position count has been reached.

        Args:
            current_count: Number of currently open positions

        Returns:
            True if can open more, False if at limit
        """
        allowed, _ = self._check_max_positions(current_count)
        return allowed

    def _check_max_positions(self, current_count: int) -> Tuple[bool, str]:
        """Internal max positions check with reason."""
        if current_count >= self.config.max_open_trades:
            return False, (
                f"Maximum positions reached: {current_count} >= "
                f"{self.config.max_open_trades}"
            )
        return True, "Position count OK"

    def check_spread(self, current_spread: float, max_spread: float) -> bool:
        """
        Check if spread is acceptable.

        Args:
            current_spread: Current spread in pips
            max_spread: Maximum acceptable spread

        Returns:
            True if spread acceptable, False if too wide
        """
        allowed, _ = self._check_spread(current_spread, max_spread)
        return allowed

    def _check_spread(
        self,
        current_spread: float,
        max_spread: float
    ) -> Tuple[bool, str]:
        """Internal spread check with reason."""
        if current_spread > max_spread:
            return False, (
                f"Spread too wide: {current_spread:.1f} pips > "
                f"{max_spread:.1f} pips max"
            )
        return True, "Spread acceptable"

    def check_reward_risk(
        self,
        entry: float,
        stop: float,
        target: float,
        direction: TradeDirection = TradeDirection.LONG
    ) -> bool:
        """
        Check if reward:risk ratio meets minimum.

        Args:
            entry: Entry price
            stop: Stop loss price
            target: Take profit price
            direction: Trade direction

        Returns:
            True if ratio acceptable, False if too low
        """
        allowed, _ = self._check_reward_risk(entry, stop, target, direction)
        return allowed

    def _check_reward_risk(
        self,
        entry: float,
        stop: float,
        target: float,
        direction: TradeDirection = TradeDirection.LONG
    ) -> Tuple[bool, str]:
        """Internal reward:risk check with reason."""
        if direction == TradeDirection.LONG:
            risk = entry - stop
            reward = target - entry
        else:
            risk = stop - entry
            reward = entry - target

        if risk <= 0:
            return False, "Invalid stop loss (no risk)"

        ratio = reward / risk

        if ratio < self.config.min_reward_risk - 0.001:  # Small epsilon for float comparison
            return False, (
                f"Reward:Risk ratio {ratio:.2f} below minimum "
                f"{self.config.min_reward_risk:.2f}"
            )

        return True, f"Reward:Risk ratio {ratio:.2f} OK"

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        direction: str
    ) -> float:
        """
        Calculate trailing stop price.

        Uses ATR-based trailing stop that locks in profits as price moves favorably.

        Args:
            entry_price: Original entry price
            current_price: Current market price
            atr: Current ATR value
            direction: "long" or "short"

        Returns:
            Trailing stop price
        """
        if not self.config.use_trailing_stop:
            return 0.0

        # ATR multiplier for trailing stop distance
        trail_distance = atr * self.config.atr_multiplier

        if direction.lower() == "long":
            # For long positions, trail below current price
            # But never below entry price once in profit
            trailing_stop = current_price - trail_distance

            # Only trail if we're in profit
            if current_price > entry_price:
                # Don't let trailing stop go below entry (break-even)
                return max(trailing_stop, entry_price)
            else:
                # Not in profit yet, no trailing
                return 0.0
        else:
            # For short positions, trail above current price
            trailing_stop = current_price + trail_distance

            # Only trail if we're in profit
            if current_price < entry_price:
                # Don't let trailing stop go above entry (break-even)
                return min(trailing_stop, entry_price)
            else:
                # Not in profit yet, no trailing
                return 0.0

    def update_trailing_stop(
        self,
        position: Position,
        current_price: float,
        atr: float
    ) -> Optional[float]:
        """
        Update trailing stop for an existing position.

        Args:
            position: The position to update
            current_price: Current market price
            atr: Current ATR value

        Returns:
            New trailing stop price if updated, None if no update needed
        """
        if not self.config.use_trailing_stop:
            return None

        direction = "long" if position.direction == TradeDirection.LONG else "short"

        new_trailing = self.calculate_trailing_stop(
            entry_price=position.entry_price,
            current_price=current_price,
            atr=atr,
            direction=direction
        )

        if new_trailing == 0.0:
            return None

        # Only update if it's better than current trailing stop
        if position.trailing_stop is None:
            return new_trailing

        if direction == "long":
            # For long, new trailing must be higher
            if new_trailing > position.trailing_stop:
                return new_trailing
        else:
            # For short, new trailing must be lower
            if new_trailing < position.trailing_stop:
                return new_trailing

        return None

    def record_trade_result(
        self,
        is_win: bool,
        pnl: float,
        risk_amount: Optional[float] = None
    ) -> None:
        """
        Record a completed trade for statistics tracking.

        Args:
            is_win: Whether the trade was profitable
            pnl: Profit/loss amount
            risk_amount: Amount risked on the trade (optional)
        """
        # Update daily stats
        self._daily_stats.total_trades += 1

        if is_win:
            self._daily_stats.winning_trades += 1
            self._daily_stats.gross_profit += pnl
            self._daily_stats.consecutive_losses = 0
        else:
            self._daily_stats.losing_trades += 1
            self._daily_stats.gross_loss += abs(pnl)
            self._daily_stats.consecutive_losses += 1

        # Update circuit breaker
        self.circuit_breaker.record_trade_result(is_win, pnl)

        # Update historical stats
        self._total_historical_trades += 1
        self._update_historical_stats(is_win, pnl, risk_amount)

    def _update_historical_stats(
        self,
        is_win: bool,
        pnl: float,
        risk_amount: Optional[float]
    ) -> None:
        """Update historical statistics for Kelly calculation."""
        # Use exponential moving average for recent performance weighting
        alpha = 2 / (min(self._total_historical_trades, 100) + 1)

        # Update win rate (EMA)
        win_value = 1.0 if is_win else 0.0
        self._historical_win_rate = (
            alpha * win_value + (1 - alpha) * self._historical_win_rate
        )

        # Update average win/loss
        if is_win:
            if self._historical_avg_win == 0:
                self._historical_avg_win = pnl
            else:
                self._historical_avg_win = (
                    alpha * pnl + (1 - alpha) * self._historical_avg_win
                )
        else:
            abs_pnl = abs(pnl)
            if self._historical_avg_loss == 0:
                self._historical_avg_loss = abs_pnl
            else:
                self._historical_avg_loss = (
                    alpha * abs_pnl + (1 - alpha) * self._historical_avg_loss
                )

    def _calculate_current_drawdown(self) -> float:
        """Calculate current drawdown for Kelly adjustment."""
        if self._daily_stats.net_pnl >= 0:
            return 0.0

        # Simple drawdown based on daily loss
        # Real implementation would track peak equity
        return abs(self._daily_stats.net_pnl) / max(1, self._daily_stats.gross_profit + abs(self._daily_stats.net_pnl))

    def _calculate_risk_score(
        self,
        signal: Signal,
        current_positions: List[Position],
        daily_pnl: float,
        account_balance: float,
        current_spread: Optional[float]
    ) -> float:
        """
        Calculate overall risk score for a trade (0-1, higher = riskier).

        Args:
            signal: Trading signal
            current_positions: Current positions
            daily_pnl: Daily P&L
            account_balance: Account balance
            current_spread: Current spread

        Returns:
            Risk score between 0 and 1
        """
        scores = []

        # Position count risk (more positions = higher risk)
        position_risk = len(current_positions) / self.config.max_open_trades
        scores.append(position_risk)

        # Daily P&L risk (closer to limit = higher risk)
        if account_balance > 0:
            daily_loss_ratio = abs(min(0, daily_pnl)) / account_balance
            pnl_risk = daily_loss_ratio / self.config.max_daily_loss
            scores.append(min(1.0, pnl_risk))

        # Confidence inverse risk (lower confidence = higher risk)
        confidence_risk = 1 - signal.confidence
        scores.append(confidence_risk)

        # Reward:risk inverse (lower R:R = higher risk)
        rr_ratio = signal.reward_risk_ratio
        rr_risk = 1 - min(1.0, rr_ratio / (self.config.min_reward_risk * 2))
        scores.append(rr_risk)

        # Spread risk
        if current_spread is not None:
            spread_risk = current_spread / self.config.max_spread_pips
            scores.append(min(1.0, spread_risk))

        # Consecutive losses risk
        loss_risk = self._daily_stats.consecutive_losses / self.config.consecutive_loss_limit
        scores.append(min(1.0, loss_risk))

        # Average all risk factors
        return sum(scores) / len(scores) if scores else 0.5

    def reset_daily_stats(self) -> None:
        """Reset daily statistics for a new trading day."""
        self._daily_stats = DailyStats()
        self.circuit_breaker.reset_daily()

    def get_daily_stats(self) -> DailyStats:
        """Get current daily statistics."""
        return self._daily_stats

    def get_risk_summary(self, account_balance: float) -> dict:
        """
        Get a summary of current risk state.

        Args:
            account_balance: Current account balance

        Returns:
            Dictionary with risk summary
        """
        circuit_status = self.circuit_breaker.get_status()

        daily_loss_pct = 0.0
        if account_balance > 0:
            daily_loss_pct = abs(min(0, self._daily_stats.net_pnl)) / account_balance

        return {
            "config": {
                "max_risk_per_trade": self.config.max_risk_per_trade,
                "max_daily_loss": self.config.max_daily_loss,
                "max_leverage": self.config.max_leverage,
                "min_confidence": self.config.min_confidence,
                "min_reward_risk": self.config.min_reward_risk,
                "max_open_trades": self.config.max_open_trades,
                "max_spread_pips": self.config.max_spread_pips,
                "use_trailing_stop": self.config.use_trailing_stop
            },
            "daily_stats": {
                "total_trades": self._daily_stats.total_trades,
                "winning_trades": self._daily_stats.winning_trades,
                "losing_trades": self._daily_stats.losing_trades,
                "win_rate": self._daily_stats.win_rate,
                "net_pnl": self._daily_stats.net_pnl,
                "daily_loss_percentage": daily_loss_pct,
                "consecutive_losses": self._daily_stats.consecutive_losses
            },
            "historical_stats": {
                "total_trades": self._total_historical_trades,
                "win_rate": self._historical_win_rate,
                "avg_win": self._historical_avg_win,
                "avg_loss": self._historical_avg_loss
            },
            "circuit_breaker": circuit_status.to_dict(),
            "can_trade": circuit_status.can_trade
        }
