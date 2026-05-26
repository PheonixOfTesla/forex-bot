from __future__ import annotations

"""
Circuit Breaker - Emergency Trading Controls
Implements automatic trading halts based on risk thresholds.
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .models import CircuitBreakerState, CircuitBreakerStatus


class CircuitBreaker:
    """
    Emergency control system that halts trading when risk thresholds are breached.

    The circuit breaker monitors:
    - Daily P&L limits
    - Consecutive losses
    - Manual emergency stops

    When tripped, it prevents new trades until conditions improve or
    a manual reset occurs.
    """

    def __init__(
        self,
        daily_loss_limit: float = 0.06,  # 6% max daily loss
        consecutive_loss_limit: int = 5,
        cooldown_minutes: int = 30,
        auto_reset_next_day: bool = True
    ):
        """
        Initialize the circuit breaker.

        Args:
            daily_loss_limit: Maximum daily loss as fraction of account
            consecutive_loss_limit: Max consecutive losses before tripping
            cooldown_minutes: Minutes before auto-reset attempt
            auto_reset_next_day: Automatically reset at start of new trading day
        """
        self.daily_loss_limit = daily_loss_limit
        self.consecutive_loss_limit = consecutive_loss_limit
        self.cooldown_minutes = cooldown_minutes
        self.auto_reset_next_day = auto_reset_next_day

        # State tracking
        self._state = CircuitBreakerState.CLOSED
        self._tripped_at: Optional[datetime] = None
        self._trip_reason: Optional[str] = None
        self._daily_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._last_reset_date: datetime = datetime.utcnow().date()
        self._force_stopped: bool = False

        # Thread safety
        self._lock = threading.RLock()

        # Event callbacks
        self._on_trip_callbacks = []
        self._on_reset_callbacks = []

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state

    def is_tripped(self) -> bool:
        """Check if circuit breaker is currently tripped."""
        with self._lock:
            # Check for day rollover auto-reset
            if self.auto_reset_next_day:
                current_date = datetime.utcnow().date()
                if current_date > self._last_reset_date and not self._force_stopped:
                    self._auto_reset_for_new_day()

            return self._state == CircuitBreakerState.OPEN

    def can_trade(self) -> bool:
        """Check if trading is currently allowed."""
        with self._lock:
            if self._force_stopped:
                return False

            if self._state == CircuitBreakerState.OPEN:
                # Check if cooldown has passed for potential half-open state
                if self._can_attempt_reset():
                    self._state = CircuitBreakerState.HALF_OPEN
                    return True
                return False

            return True

    def check_and_trip(
        self,
        daily_pnl: float,
        consecutive_losses: int,
        account_balance: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Check conditions and trip circuit breaker if thresholds exceeded.

        Args:
            daily_pnl: Current daily P&L (negative for losses)
            consecutive_losses: Current consecutive loss count
            account_balance: Optional account balance for percentage calc

        Returns:
            Tuple of (is_tripped, reason)
        """
        with self._lock:
            self._daily_pnl = daily_pnl
            self._consecutive_losses = consecutive_losses

            # Already tripped
            if self._state == CircuitBreakerState.OPEN:
                return True, self._trip_reason or "Circuit breaker already tripped"

            # Force stopped
            if self._force_stopped:
                return True, "Emergency stop active"

            # Check daily loss limit
            if account_balance and account_balance > 0:
                loss_percentage = abs(min(0, daily_pnl)) / account_balance
            else:
                loss_percentage = abs(min(0, daily_pnl))

            if loss_percentage >= self.daily_loss_limit:
                return self._trip(
                    f"Daily loss limit exceeded: {loss_percentage:.1%} >= {self.daily_loss_limit:.1%}"
                )

            # Check consecutive losses
            if consecutive_losses >= self.consecutive_loss_limit:
                return self._trip(
                    f"Consecutive loss limit exceeded: {consecutive_losses} >= {self.consecutive_loss_limit}"
                )

            return False, "All checks passed"

    def _trip(self, reason: str) -> Tuple[bool, str]:
        """
        Trip the circuit breaker.

        Args:
            reason: Reason for tripping

        Returns:
            Tuple of (True, reason)
        """
        self._state = CircuitBreakerState.OPEN
        self._tripped_at = datetime.utcnow()
        self._trip_reason = reason

        # Notify callbacks
        for callback in self._on_trip_callbacks:
            try:
                callback(reason, self._tripped_at)
            except Exception:
                pass  # Don't let callbacks break the circuit breaker

        return True, reason

    def _can_attempt_reset(self) -> bool:
        """Check if cooldown period has passed."""
        if self._tripped_at is None:
            return True

        cooldown_end = self._tripped_at + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() >= cooldown_end

    def _auto_reset_for_new_day(self) -> None:
        """Reset circuit breaker for new trading day."""
        self._state = CircuitBreakerState.CLOSED
        self._tripped_at = None
        self._trip_reason = None
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._last_reset_date = datetime.utcnow().date()

    def reset_daily(self) -> bool:
        """
        Manually reset the circuit breaker for a new trading day.

        Returns:
            True if reset successful, False if force-stopped
        """
        with self._lock:
            if self._force_stopped:
                return False

            self._auto_reset_for_new_day()

            # Notify callbacks
            for callback in self._on_reset_callbacks:
                try:
                    callback(datetime.utcnow())
                except Exception:
                    pass

            return True

    def reset_after_review(self, reviewed_by: str = "system") -> bool:
        """
        Reset after human review of conditions.

        Args:
            reviewed_by: Identifier of who approved the reset

        Returns:
            True if reset successful
        """
        with self._lock:
            if self._force_stopped:
                # Force stop requires explicit clear
                return False

            self._state = CircuitBreakerState.CLOSED
            self._tripped_at = None
            self._trip_reason = None
            # Keep daily stats for tracking

            return True

    def force_stop_all(self) -> bool:
        """
        Emergency stop - halt all trading immediately.

        This is a manual intervention that requires explicit clearing.
        The system will NOT auto-reset even on a new day.

        Returns:
            True indicating force stop is now active
        """
        with self._lock:
            self._force_stopped = True
            self._state = CircuitBreakerState.OPEN
            self._tripped_at = datetime.utcnow()
            self._trip_reason = "EMERGENCY FORCE STOP"

            # Notify callbacks
            for callback in self._on_trip_callbacks:
                try:
                    callback("EMERGENCY FORCE STOP", self._tripped_at)
                except Exception:
                    pass

            return True

    def clear_force_stop(self, cleared_by: str = "system") -> bool:
        """
        Clear an emergency force stop.

        Args:
            cleared_by: Identifier of who cleared the stop

        Returns:
            True indicating force stop is cleared
        """
        with self._lock:
            self._force_stopped = False
            self._state = CircuitBreakerState.CLOSED
            self._tripped_at = None
            self._trip_reason = None

            return True

    def record_trade_result(self, is_win: bool, pnl: float) -> None:
        """
        Record a trade result for tracking.

        Args:
            is_win: Whether the trade was profitable
            pnl: P&L of the trade
        """
        with self._lock:
            self._daily_pnl += pnl

            if is_win:
                self._consecutive_losses = 0
            else:
                self._consecutive_losses += 1

    def get_status(self) -> CircuitBreakerStatus:
        """
        Get comprehensive status of the circuit breaker.

        Returns:
            CircuitBreakerStatus object with all current state
        """
        with self._lock:
            cooldown_remaining = 0
            if self._tripped_at and self._state == CircuitBreakerState.OPEN:
                cooldown_end = self._tripped_at + timedelta(minutes=self.cooldown_minutes)
                remaining = (cooldown_end - datetime.utcnow()).total_seconds()
                cooldown_remaining = max(0, int(remaining))

            return CircuitBreakerStatus(
                state=self._state,
                tripped_at=self._tripped_at,
                reason=self._trip_reason,
                daily_pnl=self._daily_pnl,
                consecutive_losses=self._consecutive_losses,
                can_trade=self.can_trade(),
                cooldown_remaining_seconds=cooldown_remaining
            )

    def register_trip_callback(self, callback) -> None:
        """
        Register a callback to be called when circuit breaker trips.

        Callback signature: callback(reason: str, tripped_at: datetime)
        """
        self._on_trip_callbacks.append(callback)

    def register_reset_callback(self, callback) -> None:
        """
        Register a callback to be called when circuit breaker resets.

        Callback signature: callback(reset_at: datetime)
        """
        self._on_reset_callbacks.append(callback)

    def update_limits(
        self,
        daily_loss_limit: Optional[float] = None,
        consecutive_loss_limit: Optional[int] = None
    ) -> None:
        """
        Update risk limits dynamically.

        Args:
            daily_loss_limit: New daily loss limit (optional)
            consecutive_loss_limit: New consecutive loss limit (optional)
        """
        with self._lock:
            if daily_loss_limit is not None:
                if not 0 < daily_loss_limit < 1:
                    raise ValueError("daily_loss_limit must be between 0 and 1")
                self.daily_loss_limit = daily_loss_limit

            if consecutive_loss_limit is not None:
                if consecutive_loss_limit < 1:
                    raise ValueError("consecutive_loss_limit must be at least 1")
                self.consecutive_loss_limit = consecutive_loss_limit
