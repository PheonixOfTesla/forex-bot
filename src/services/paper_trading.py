from __future__ import annotations

"""
Paper Trading Engine

Simulates trades and tracks performance without risking real capital.
Uses JSON file storage for persistence.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

from ..models.paper_trade import (
    PaperAccountState,
    PaperPosition,
    PaperTrade,
    PaperTradeStatus,
    TradeDirection,
    TradingMetrics,
    ExecuteTradeRequest,
    CloseTradeRequest,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_INITIAL_BALANCE = 10000.0
DEFAULT_POSITION_SIZE_PCT = 2.0  # 2% of balance per trade
DEFAULT_FEE_PCT = 0.1  # 0.1% fee per trade

# Data file path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PAPER_TRADES_FILE = DATA_DIR / "paper_trades.json"


# =============================================================================
# Paper Trading Engine
# =============================================================================


class PaperTradingEngine:
    """
    Paper trading engine that simulates trades and tracks performance.

    Features:
    - Virtual balance tracking
    - Execute virtual trades based on signals
    - Track open positions and closed trades
    - Calculate metrics: win rate, average profit, max drawdown
    - JSON file persistence
    """

    def __init__(
        self,
        initial_balance: float = DEFAULT_INITIAL_BALANCE,
        position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
        fee_pct: float = DEFAULT_FEE_PCT,
        data_file: Optional[Path] = None,
    ):
        """
        Initialize the paper trading engine.

        Args:
            initial_balance: Starting balance (default: $10,000)
            position_size_pct: Default position size as percentage of balance
            fee_pct: Trading fee percentage per trade
            data_file: Custom path for data persistence
        """
        self.initial_balance = initial_balance
        self.position_size_pct = position_size_pct
        self.fee_pct = fee_pct
        self.data_file = data_file or PAPER_TRADES_FILE

        # Thread safety
        self._lock = Lock()

        # Account state
        self._state: PaperAccountState = PaperAccountState(
            initial_balance=initial_balance,
            balance=initial_balance,
            equity=initial_balance,
            peak_balance=initial_balance,
        )

        # Ensure data directory exists
        self._ensure_data_dir()

        # Load existing state
        self._load_state()

        logger.info(
            f"PaperTradingEngine initialized: balance=${self._state.balance:,.2f}, "
            f"open_positions={len(self._state.open_trades)}, "
            f"closed_trades={len(self._state.closed_trades)}"
        )

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> None:
        """Load state from JSON file."""
        if not self.data_file.exists():
            logger.info("No existing paper trades file found, starting fresh")
            return

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)

            self._state = PaperAccountState(**data)
            logger.info(f"Loaded paper trading state from {self.data_file}")

        except Exception as e:
            logger.error(f"Failed to load paper trading state: {e}")
            # Start fresh on error
            self._state = PaperAccountState(
                initial_balance=self.initial_balance,
                balance=self.initial_balance,
                equity=self.initial_balance,
                peak_balance=self.initial_balance,
            )

    def _save_state(self) -> None:
        """Save state to JSON file."""
        try:
            self._state.last_updated = datetime.utcnow()

            # Convert to dict with datetime serialization
            data = json.loads(self._state.model_dump_json())

            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Saved paper trading state to {self.data_file}")

        except Exception as e:
            logger.error(f"Failed to save paper trading state: {e}")

    # =========================================================================
    # Balance & Account Methods
    # =========================================================================

    @property
    def balance(self) -> float:
        """Get current available balance."""
        return self._state.balance

    @property
    def equity(self) -> float:
        """Get current equity (balance + unrealized P&L)."""
        return self._state.equity

    @property
    def open_positions(self) -> List[PaperTrade]:
        """Get list of open trades."""
        return self._state.open_trades

    @property
    def closed_trades(self) -> List[PaperTrade]:
        """Get list of closed trades."""
        return self._state.closed_trades

    @property
    def metrics(self) -> TradingMetrics:
        """Get trading metrics."""
        return self._state.metrics

    def get_balance_info(self) -> Dict:
        """Get comprehensive balance information."""
        with self._lock:
            unrealized_pnl = sum(
                self._calculate_unrealized_pnl(t)
                for t in self._state.open_trades
            )

            open_positions_value = sum(
                t.entry_price * t.quantity
                for t in self._state.open_trades
            )

            return {
                "initial_balance": self._state.initial_balance,
                "balance": self._state.balance,
                "equity": self._state.balance + unrealized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "open_positions_count": len(self._state.open_trades),
                "open_positions_value": open_positions_value,
                "metrics": self._state.metrics,
                "peak_balance": self._state.peak_balance,
                "created_at": self._state.created_at,
                "last_updated": self._state.last_updated,
            }

    def _calculate_unrealized_pnl(self, trade: PaperTrade) -> float:
        """Calculate unrealized P&L for an open trade using a simulated current price."""
        # In a real implementation, you'd fetch the current market price
        # For now, simulate a small price movement
        current_price = trade.entry_price * 1.001  # Simulate 0.1% move

        pnl, _ = trade.calculate_pnl(current_price)
        return pnl

    # =========================================================================
    # Trade Execution Methods
    # =========================================================================

    def execute_trade(
        self,
        request: ExecuteTradeRequest,
    ) -> Tuple[bool, str, Optional[PaperTrade]]:
        """
        Execute a paper trade.

        Args:
            request: Trade execution request

        Returns:
            Tuple of (success, message, trade)
        """
        with self._lock:
            # Calculate position size if not provided
            quantity = request.quantity
            if quantity is None:
                # Use default position sizing (percentage of balance)
                position_value = self._state.balance * (self.position_size_pct / 100)
                quantity = position_value / request.entry_price

            # Calculate required margin/value
            position_value = request.entry_price * quantity

            # Check if we have enough balance
            if position_value > self._state.balance:
                return (
                    False,
                    f"Insufficient balance: need ${position_value:,.2f}, have ${self._state.balance:,.2f}",
                    None,
                )

            # Calculate fees
            fees = position_value * (self.fee_pct / 100)

            # Create the trade
            trade = PaperTrade(
                signal_id=request.signal_id,
                pair=request.pair,
                direction=request.direction,
                entry_price=request.entry_price,
                quantity=quantity,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                fees=fees,
                notes=request.notes,
            )

            # Deduct from balance (margin requirement)
            self._state.balance -= position_value

            # Add to open trades
            self._state.open_trades.append(trade)

            # Update equity
            self._update_equity()

            # Save state
            self._save_state()

            logger.info(
                f"Paper trade executed: {trade.id} {trade.direction.value} "
                f"{trade.quantity} {trade.pair} @ {trade.entry_price}"
            )

            return (
                True,
                f"Trade executed: {trade.direction.value} {trade.quantity:.4f} {trade.pair} @ ${trade.entry_price:,.4f}",
                trade,
            )

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[PaperTrade]]:
        """
        Close an open paper trade.

        Args:
            trade_id: ID of the trade to close
            exit_price: Exit price
            notes: Optional close notes

        Returns:
            Tuple of (success, message, trade)
        """
        with self._lock:
            # Find the trade
            trade = None
            trade_index = None
            for i, t in enumerate(self._state.open_trades):
                if t.id == trade_id:
                    trade = t
                    trade_index = i
                    break

            if trade is None:
                return (False, f"Trade not found: {trade_id}", None)

            # Close the trade
            trade.close(exit_price)
            if notes:
                trade.notes = (trade.notes or "") + f"\n{notes}"

            # Calculate position value to return
            position_value = trade.entry_price * trade.quantity

            # Return position value + P&L to balance
            self._state.balance += position_value + trade.pnl

            # Remove from open trades, add to closed trades
            self._state.open_trades.pop(trade_index)
            self._state.closed_trades.append(trade)

            # Update metrics
            self._update_metrics()

            # Update peak balance and drawdown
            self._update_drawdown()

            # Update equity
            self._update_equity()

            # Save state
            self._save_state()

            logger.info(
                f"Paper trade closed: {trade.id} {trade.pair} "
                f"P&L: ${trade.pnl:,.2f} ({trade.pnl_pct:.2f}%)"
            )

            return (
                True,
                f"Trade closed: {trade.pair} @ ${exit_price:,.4f}, P&L: ${trade.pnl:,.2f} ({trade.pnl_pct:.2f}%)",
                trade,
            )

    def close_all_positions(self, exit_prices: Dict[str, float]) -> List[PaperTrade]:
        """
        Close all open positions.

        Args:
            exit_prices: Dict mapping pair to exit price

        Returns:
            List of closed trades
        """
        closed = []
        for trade in list(self._state.open_trades):
            exit_price = exit_prices.get(trade.pair, trade.entry_price)
            success, _, closed_trade = self.close_trade(trade.id, exit_price)
            if success and closed_trade:
                closed.append(closed_trade)
        return closed

    # =========================================================================
    # Position & History Methods
    # =========================================================================

    def get_open_positions(
        self,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[PaperPosition]:
        """
        Get open positions with current P&L.

        Args:
            current_prices: Optional dict mapping pair to current price

        Returns:
            List of PaperPosition objects
        """
        positions = []

        for trade in self._state.open_trades:
            # Get current price (use entry price + small random if not provided)
            if current_prices and trade.pair in current_prices:
                current_price = current_prices[trade.pair]
            else:
                # Simulate slight price movement for demo
                current_price = trade.entry_price * 1.001

            # Calculate unrealized P&L
            pnl, pnl_pct = trade.calculate_pnl(current_price)

            position = PaperPosition(
                trade_id=trade.id,
                pair=trade.pair,
                direction=trade.direction,
                entry_price=trade.entry_price,
                current_price=current_price,
                quantity=trade.quantity,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                opened_at=trade.opened_at,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
            )
            positions.append(position)

        return positions

    def get_trade_history(
        self,
        limit: int = 50,
        offset: int = 0,
        pair: Optional[str] = None,
    ) -> List[PaperTrade]:
        """
        Get trade history with pagination.

        Args:
            limit: Maximum number of trades to return
            offset: Number of trades to skip
            pair: Filter by trading pair

        Returns:
            List of closed trades
        """
        trades = self._state.closed_trades

        # Filter by pair if provided
        if pair:
            trades = [t for t in trades if t.pair.upper() == pair.upper()]

        # Sort by closed_at descending (newest first)
        trades = sorted(
            trades,
            key=lambda t: t.closed_at or datetime.min,
            reverse=True,
        )

        # Apply pagination
        return trades[offset : offset + limit]

    # =========================================================================
    # Metrics & Analytics Methods
    # =========================================================================

    def _update_metrics(self) -> None:
        """Update trading metrics based on closed trades."""
        closed = self._state.closed_trades

        if not closed:
            self._state.metrics = TradingMetrics()
            return

        # Basic counts
        total = len(closed)
        winners = [t for t in closed if t.pnl and t.pnl > 0]
        losers = [t for t in closed if t.pnl and t.pnl < 0]

        winning_count = len(winners)
        losing_count = len(losers)

        # Calculate metrics
        total_pnl = sum(t.pnl or 0 for t in closed)
        win_rate = (winning_count / total * 100) if total > 0 else 0

        avg_profit = total_pnl / total if total > 0 else 0

        avg_win = (
            sum(t.pnl for t in winners) / winning_count
            if winning_count > 0
            else 0
        )
        avg_loss = (
            sum(t.pnl for t in losers) / losing_count
            if losing_count > 0
            else 0
        )

        largest_win = max((t.pnl or 0 for t in closed), default=0)
        largest_loss = min((t.pnl or 0 for t in closed), default=0)

        # Profit factor
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 0
        profit_factor = (
            gross_profit / gross_loss if gross_loss > 0 else None
        )

        # Calculate consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_streak = 0
        last_was_win = None

        for trade in sorted(closed, key=lambda t: t.closed_at or datetime.min):
            is_win = (trade.pnl or 0) > 0

            if last_was_win is None:
                current_streak = 1
            elif is_win == last_was_win:
                current_streak += 1
            else:
                current_streak = 1

            if is_win:
                consecutive_wins = current_streak
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_streak)
            else:
                consecutive_losses = current_streak
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_streak)

            last_was_win = is_win

        self._state.metrics = TradingMetrics(
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            trades_count=total,
            winning_trades=winning_count,
            losing_trades=losing_count,
            avg_profit=round(avg_profit, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            max_drawdown=self._state.metrics.max_drawdown,
            max_drawdown_pct=self._state.metrics.max_drawdown_pct,
            profit_factor=round(profit_factor, 2) if profit_factor else None,
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
        )

    def _update_drawdown(self) -> None:
        """Update peak balance and maximum drawdown."""
        current_equity = self._state.balance + sum(
            self._calculate_unrealized_pnl(t)
            for t in self._state.open_trades
        )

        # Update peak if current is higher
        if current_equity > self._state.peak_balance:
            self._state.peak_balance = current_equity

        # Calculate current drawdown
        if self._state.peak_balance > 0:
            drawdown = self._state.peak_balance - current_equity
            drawdown_pct = (drawdown / self._state.peak_balance) * 100

            # Update max drawdown if current is worse
            if drawdown > self._state.metrics.max_drawdown:
                self._state.metrics.max_drawdown = round(drawdown, 2)
                self._state.metrics.max_drawdown_pct = round(drawdown_pct, 2)

    def _update_equity(self) -> None:
        """Update equity value."""
        unrealized_pnl = sum(
            self._calculate_unrealized_pnl(t)
            for t in self._state.open_trades
        )
        self._state.equity = self._state.balance + unrealized_pnl

    # =========================================================================
    # Account Management Methods
    # =========================================================================

    def reset_account(
        self,
        new_balance: Optional[float] = None,
    ) -> Dict:
        """
        Reset the paper trading account.

        Args:
            new_balance: New starting balance (uses initial_balance if not provided)

        Returns:
            Dict with reset details
        """
        with self._lock:
            previous_balance = self._state.balance
            previous_total_pnl = self._state.metrics.total_pnl

            balance = new_balance or self.initial_balance

            self._state = PaperAccountState(
                initial_balance=balance,
                balance=balance,
                equity=balance,
                peak_balance=balance,
            )

            self._save_state()

            logger.info(f"Paper trading account reset to ${balance:,.2f}")

            return {
                "success": True,
                "message": f"Account reset to ${balance:,.2f}",
                "new_balance": balance,
                "previous_balance": previous_balance,
                "previous_total_pnl": previous_total_pnl,
            }

    def get_summary(self) -> Dict:
        """Get a summary of the paper trading account."""
        with self._lock:
            positions = self.get_open_positions()
            total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)

            return {
                "balance": self._state.balance,
                "equity": self._state.balance + total_unrealized_pnl,
                "unrealized_pnl": total_unrealized_pnl,
                "open_positions": len(self._state.open_trades),
                "closed_trades": len(self._state.closed_trades),
                "total_pnl": self._state.metrics.total_pnl,
                "win_rate": self._state.metrics.win_rate,
                "max_drawdown": self._state.metrics.max_drawdown,
                "max_drawdown_pct": self._state.metrics.max_drawdown_pct,
            }


# =============================================================================
# Singleton Instance
# =============================================================================

_paper_trading_engine: Optional[PaperTradingEngine] = None


def get_paper_trading_engine() -> PaperTradingEngine:
    """Get or create the singleton PaperTradingEngine instance."""
    global _paper_trading_engine

    if _paper_trading_engine is None:
        _paper_trading_engine = PaperTradingEngine()

    return _paper_trading_engine


def reset_paper_trading_engine() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _paper_trading_engine
    _paper_trading_engine = None
