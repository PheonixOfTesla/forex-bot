from __future__ import annotations

"""
Trailing Stop Manager

Manages trailing stops for open positions, automatically
adjusting stop loss levels as price moves in favor of
the trade using ATR-based calculations.

Author: HERMES Trading System
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from .models import Position

# Configure logging
logger = logging.getLogger(__name__)


class ExecutorProtocol(Protocol):
    """Protocol for OrderExecutor interface."""

    async def modify_stop_loss(
        self,
        position_id: str,
        new_stop: float,
        broker: str,
    ) -> bool:
        """Modify stop loss for a position."""
        ...


@dataclass
class TrailConfig:
    """
    Configuration for trailing stop behavior.

    Attributes:
        atr_multiplier: Multiplier for ATR-based trail distance
        activation_profit_pct: Min profit % before trailing activates
        step_size: Minimum price movement before updating stop
        breakeven_trigger_pct: Profit % to move stop to breakeven
        lock_in_profit_pct: Profit % to lock in with stop
    """
    atr_multiplier: float = 1.5
    activation_profit_pct: float = 0.5  # 0.5% profit before trailing
    step_size: float = 0.0001  # Minimum step (1 pip for forex)
    breakeven_trigger_pct: float = 1.0  # Move to breakeven at 1% profit
    lock_in_profit_pct: float = 0.5  # Lock in 0.5% when moving to breakeven


@dataclass
class TrailState:
    """
    State tracking for a trailed position.

    Attributes:
        position_id: Position identifier
        instrument: Trading instrument
        broker: Broker name
        entry_price: Original entry price
        current_stop: Current stop loss level
        highest_profit: Highest profit reached
        lowest_price: Lowest price seen (for shorts)
        highest_price: Highest price seen (for longs)
        trail_active: Whether trailing is active
        last_update: Last stop update time
        update_count: Number of stop updates
    """
    position_id: str
    instrument: str
    broker: str
    entry_price: float
    current_stop: float
    is_long: bool
    highest_profit: float = 0.0
    lowest_price: float = float('inf')
    highest_price: float = 0.0
    trail_active: bool = False
    last_update: datetime = field(default_factory=datetime.utcnow)
    update_count: int = 0


class TrailingStopManager:
    """
    Manages trailing stops for open positions.

    Uses ATR (Average True Range) to dynamically adjust stop loss
    levels as price moves in favor of the trade. Supports both
    forex and crypto positions.

    Features:
        - ATR-based trail distance calculation
        - Activation threshold (only trail after minimum profit)
        - Breakeven stop (move to entry after certain profit)
        - Step-based updates (avoid excessive modifications)
        - Multi-position tracking

    Example:
        ```python
        manager = TrailingStopManager(executor)

        # In price update loop
        await manager.update_trailing_stops(
            positions=open_positions,
            current_prices={"EUR_USD": 1.1050, "BTCUSDT": 42000},
        )
        ```
    """

    def __init__(
        self,
        executor: ExecutorProtocol,
        config: Optional[TrailConfig] = None,
        on_stop_updated: Optional[Callable[[str, float, float], None]] = None,
    ):
        """
        Initialize TrailingStopManager.

        Args:
            executor: OrderExecutor for modifying stops
            config: Trail configuration (uses defaults if not provided)
            on_stop_updated: Callback when stop is updated (position_id, old_stop, new_stop)
        """
        self.executor = executor
        self.config = config or TrailConfig()
        self.on_stop_updated = on_stop_updated

        # Track state for each position
        self._trail_states: Dict[str, TrailState] = {}

        # ATR cache (instrument -> ATR value)
        self._atr_cache: Dict[str, float] = {}

        logger.info(
            f"TrailingStopManager initialized - "
            f"ATR multiplier: {self.config.atr_multiplier}, "
            f"Activation: {self.config.activation_profit_pct}%"
        )

    async def update_trailing_stops(
        self,
        positions: List[Position],
        current_prices: Dict[str, float],
    ) -> List[str]:
        """
        Update trailing stops for all positions.

        Iterates through positions, checks if trailing conditions
        are met, and updates stops accordingly.

        Args:
            positions: List of open positions
            current_prices: Current prices by instrument

        Returns:
            List of position IDs that had stops updated
        """
        updated_positions: List[str] = []

        for position in positions:
            instrument = position.instrument
            current_price = current_prices.get(instrument)

            if current_price is None:
                logger.debug(f"No price available for {instrument}")
                continue

            # Get or create trail state
            state = self._get_or_create_state(position)

            # Check if we should trail
            if not self.should_trail(position, current_price):
                continue

            # Get ATR for this instrument
            atr = self._atr_cache.get(instrument, 0.0)

            if atr <= 0:
                # Use default trail distance if no ATR
                atr = self._estimate_atr(instrument, current_price)

            # Calculate new stop level
            new_stop = self.calculate_new_stop(
                position=position,
                current_price=current_price,
                atr=atr,
                trail_atr_multiplier=self.config.atr_multiplier,
            )

            if new_stop is None:
                continue

            # Check if new stop is better than current
            old_stop = state.current_stop

            # For longs, new stop must be higher
            # For shorts, new stop must be lower
            if position.is_long:
                should_update = new_stop > old_stop + self.config.step_size
            else:
                should_update = new_stop < old_stop - self.config.step_size

            if should_update:
                # Update stop via executor
                success = await self.executor.modify_stop_loss(
                    position_id=position.position_id,
                    new_stop=new_stop,
                    broker=position.broker,
                )

                if success:
                    # Update state
                    state.current_stop = new_stop
                    state.last_update = datetime.utcnow()
                    state.update_count += 1

                    updated_positions.append(position.position_id)

                    logger.info(
                        f"Trailing stop updated: {instrument} "
                        f"{old_stop:.5f} -> {new_stop:.5f}"
                    )

                    # Callback notification
                    if self.on_stop_updated:
                        if asyncio.iscoroutinefunction(self.on_stop_updated):
                            await self.on_stop_updated(
                                position.position_id, old_stop, new_stop
                            )
                        else:
                            self.on_stop_updated(
                                position.position_id, old_stop, new_stop
                            )
                else:
                    logger.warning(
                        f"Failed to update trailing stop for {position.position_id}"
                    )

            # Update price tracking
            if position.is_long:
                state.highest_price = max(state.highest_price, current_price)
            else:
                state.lowest_price = min(state.lowest_price, current_price)

            # Track highest profit
            profit_pct = self._calculate_profit_pct(position, current_price)
            state.highest_profit = max(state.highest_profit, profit_pct)

        return updated_positions

    def calculate_new_stop(
        self,
        position: Position,
        current_price: float,
        atr: float,
        trail_atr_multiplier: float = 1.5,
    ) -> Optional[float]:
        """
        Calculate new trailing stop level.

        Uses ATR to determine trail distance, ensuring the stop
        is placed at a reasonable distance from current price.

        Args:
            position: Position to calculate stop for
            current_price: Current market price
            atr: Average True Range value
            trail_atr_multiplier: Multiplier for ATR (default 1.5)

        Returns:
            New stop price, or None if no update needed
        """
        # Calculate trail distance
        trail_distance = atr * trail_atr_multiplier

        if trail_distance <= 0:
            return None

        # Calculate new stop based on position direction
        if position.is_long:
            new_stop = current_price - trail_distance

            # Ensure new stop is above entry (profit locked in)
            if new_stop <= position.entry_price:
                # Check if we should move to breakeven
                profit_pct = self._calculate_profit_pct(position, current_price)
                if profit_pct >= self.config.breakeven_trigger_pct:
                    # Move to breakeven plus small buffer
                    buffer = position.entry_price * (self.config.lock_in_profit_pct / 100)
                    new_stop = position.entry_price + buffer
                else:
                    return None

            # Ensure new stop is above current stop
            if position.stop_loss and new_stop <= position.stop_loss:
                return None

        else:  # Short position
            new_stop = current_price + trail_distance

            # Ensure new stop is below entry (profit locked in)
            if new_stop >= position.entry_price:
                profit_pct = self._calculate_profit_pct(position, current_price)
                if profit_pct >= self.config.breakeven_trigger_pct:
                    buffer = position.entry_price * (self.config.lock_in_profit_pct / 100)
                    new_stop = position.entry_price - buffer
                else:
                    return None

            # Ensure new stop is below current stop
            if position.stop_loss and new_stop >= position.stop_loss:
                return None

        return round(new_stop, 5)

    def should_trail(
        self,
        position: Position,
        current_price: float,
    ) -> bool:
        """
        Determine if position should have trailing stop updated.

        Trailing is only activated after minimum profit threshold
        is reached to avoid premature stop tightening.

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            True if trailing should be applied
        """
        # Calculate current profit percentage
        profit_pct = self._calculate_profit_pct(position, current_price)

        # Only trail if position is in profit by minimum amount
        if profit_pct < self.config.activation_profit_pct:
            return False

        # Check state for this position
        state = self._trail_states.get(position.position_id)

        if state:
            # Activate trailing if not already active
            if not state.trail_active:
                state.trail_active = True
                logger.info(
                    f"Trailing activated for {position.instrument} "
                    f"at {profit_pct:.2f}% profit"
                )

        return True

    def set_atr(self, instrument: str, atr: float) -> None:
        """
        Set ATR value for an instrument.

        Called by strategy or market data handler to provide
        current ATR values for trail distance calculation.

        Args:
            instrument: Trading instrument
            atr: ATR value
        """
        self._atr_cache[instrument] = atr
        logger.debug(f"ATR updated for {instrument}: {atr:.5f}")

    def set_atr_batch(self, atr_values: Dict[str, float]) -> None:
        """
        Set ATR values for multiple instruments.

        Args:
            atr_values: Dictionary of instrument -> ATR
        """
        self._atr_cache.update(atr_values)
        logger.debug(f"ATR batch updated for {len(atr_values)} instruments")

    def get_trail_state(self, position_id: str) -> Optional[TrailState]:
        """Get trailing state for a position."""
        return self._trail_states.get(position_id)

    def remove_position(self, position_id: str) -> None:
        """
        Remove position from trailing management.

        Called when position is closed.

        Args:
            position_id: Position to remove
        """
        if position_id in self._trail_states:
            del self._trail_states[position_id]
            logger.debug(f"Removed trailing state for {position_id}")

    def clear_all(self) -> None:
        """Clear all trailing states."""
        self._trail_states.clear()
        logger.info("All trailing states cleared")

    def _get_or_create_state(self, position: Position) -> TrailState:
        """Get or create trail state for position."""
        if position.position_id not in self._trail_states:
            self._trail_states[position.position_id] = TrailState(
                position_id=position.position_id,
                instrument=position.instrument,
                broker=position.broker,
                entry_price=position.entry_price,
                current_stop=position.stop_loss or 0.0,
                is_long=position.is_long,
            )

        return self._trail_states[position.position_id]

    def _calculate_profit_pct(
        self,
        position: Position,
        current_price: float,
    ) -> float:
        """Calculate profit percentage for position."""
        if position.entry_price == 0:
            return 0.0

        if position.is_long:
            profit_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        else:
            profit_pct = ((position.entry_price - current_price) / position.entry_price) * 100

        return profit_pct

    def _estimate_atr(self, instrument: str, current_price: float) -> float:
        """
        Estimate ATR when actual value not available.

        Uses typical volatility percentages for forex vs crypto.

        Args:
            instrument: Trading instrument
            current_price: Current price

        Returns:
            Estimated ATR value
        """
        # Forex pairs typically have 0.5-1% daily range
        # Crypto typically has 2-5% daily range
        is_crypto = "USDT" in instrument or "BTC" in instrument

        if is_crypto:
            volatility_pct = 0.03  # 3% estimated daily volatility
        else:
            volatility_pct = 0.007  # 0.7% estimated daily volatility

        # ATR is approximately 1/3 of daily range on H1
        atr = current_price * volatility_pct / 3

        logger.debug(f"Estimated ATR for {instrument}: {atr:.5f}")
        return atr

    @property
    def active_trails(self) -> int:
        """Get count of positions with active trailing."""
        return sum(1 for s in self._trail_states.values() if s.trail_active)

    @property
    def stats(self) -> Dict[str, Any]:
        """Get trailing stop statistics."""
        total_updates = sum(s.update_count for s in self._trail_states.values())

        return {
            "tracked_positions": len(self._trail_states),
            "active_trails": self.active_trails,
            "total_stop_updates": total_updates,
            "atr_instruments": len(self._atr_cache),
        }
