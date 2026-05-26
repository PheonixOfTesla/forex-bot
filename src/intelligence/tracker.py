from __future__ import annotations

"""
Trade Performance Tracker

Records and retrieves trade history with comprehensive filtering
and aggregation capabilities for performance analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from .models import (
    DrawdownEvent,
    DrawdownEventDB,
    PerformanceSnapshot,
    PerformanceSnapshotDB,
    TradeDirection,
    TradeRecord,
    TradeRecordDB,
)

logger = logging.getLogger(__name__)


class TradeTracker:
    """
    Trade Performance Tracker

    Records every trade and provides comprehensive querying
    capabilities for performance analysis and learning.
    """

    def __init__(self, session_factory):
        """
        Initialize the trade tracker.

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory
        self._equity_peak: float = 0.0
        self._current_drawdown: Optional[DrawdownEvent] = None

    # =========================================================================
    # Trade Recording
    # =========================================================================

    def record_trade(
        self,
        trade_id: str,
        asset: str,
        strategy: str,
        direction: TradeDirection,
        entry_price: float,
        confidence: float,
        features_snapshot: Optional[Dict[str, Any]] = None,
        market_conditions: Optional[Dict[str, Any]] = None,
        session: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[float] = None,
    ) -> TradeRecord:
        """
        Record a new trade entry.

        Args:
            trade_id: Unique identifier for the trade
            asset: Trading instrument (e.g., EUR_USD)
            strategy: Strategy name that generated the signal
            direction: Trade direction (long/short)
            entry_price: Entry price
            confidence: Model confidence (0-100)
            features_snapshot: Feature values at entry time
            market_conditions: Market state at entry
            session: Trading session (london, new_york, asia, overlap)
            stop_loss: Stop loss price if set
            take_profit: Take profit price if set
            position_size: Position size

        Returns:
            TradeRecord: The recorded trade
        """
        trade = TradeRecord(
            id=trade_id,
            timestamp=datetime.utcnow(),
            asset=asset,
            strategy=strategy,
            direction=direction,
            entry_price=entry_price,
            confidence=confidence,
            features_snapshot=features_snapshot or {},
            market_conditions=market_conditions or {},
            session=session,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
        )

        with self.session_factory() as session:
            db_trade = trade.to_db()
            session.add(db_trade)
            session.commit()
            logger.info(f"Recorded trade entry: {trade_id} - {asset} {direction.value}")

        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        was_stopped_out: bool = False,
        hit_target: bool = False,
        notes: Optional[str] = None,
    ) -> Optional[TradeRecord]:
        """
        Record trade exit and calculate PnL.

        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            was_stopped_out: Whether stop loss was hit
            hit_target: Whether take profit was hit
            notes: Optional notes about the trade

        Returns:
            TradeRecord: Updated trade record, or None if not found
        """
        with self.session_factory() as session:
            db_trade = session.query(TradeRecordDB).filter_by(id=trade_id).first()

            if not db_trade:
                logger.error(f"Trade not found for close: {trade_id}")
                return None

            closed_at = datetime.utcnow()
            duration = int((closed_at - db_trade.timestamp).total_seconds() / 60)

            # Calculate PnL
            if db_trade.direction == TradeDirection.LONG:
                pnl_percent = ((exit_price - db_trade.entry_price) / db_trade.entry_price) * 100
            else:
                pnl_percent = ((db_trade.entry_price - exit_price) / db_trade.entry_price) * 100

            # Calculate absolute PnL if position size is known
            pnl = None
            if db_trade.position_size:
                pnl = (pnl_percent / 100) * db_trade.position_size * db_trade.entry_price

            # Update record
            db_trade.exit_price = exit_price
            db_trade.pnl = pnl
            db_trade.pnl_percent = pnl_percent
            db_trade.closed_at = closed_at
            db_trade.duration_minutes = duration
            db_trade.was_stopped_out = was_stopped_out
            db_trade.hit_target = hit_target
            db_trade.notes = notes

            session.commit()

            trade = TradeRecord.from_db(db_trade)
            logger.info(
                f"Closed trade: {trade_id} - PnL: {pnl_percent:.2f}% "
                f"({'stopped out' if was_stopped_out else 'target hit' if hit_target else 'manual'})"
            )

            # Update drawdown tracking
            self._update_drawdown_tracking(session, trade)

            return trade

    # =========================================================================
    # Trade History Queries
    # =========================================================================

    def get_trade_history(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
        asset: Optional[str] = None,
        session_filter: Optional[str] = None,
        closed_only: bool = True,
    ) -> List[TradeRecord]:
        """
        Get trade history with optional filters.

        Args:
            days: Number of days to look back
            strategy: Filter by strategy name
            asset: Filter by asset
            session_filter: Filter by trading session
            closed_only: Only return closed trades

        Returns:
            List of TradeRecord objects
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self.session_factory() as session:
            query = session.query(TradeRecordDB).filter(
                TradeRecordDB.timestamp >= cutoff
            )

            if strategy:
                query = query.filter(TradeRecordDB.strategy == strategy)
            if asset:
                query = query.filter(TradeRecordDB.asset == asset)
            if session_filter:
                query = query.filter(TradeRecordDB.session == session_filter)
            if closed_only:
                query = query.filter(TradeRecordDB.exit_price.isnot(None))

            query = query.order_by(desc(TradeRecordDB.timestamp))
            db_trades = query.all()

            return [TradeRecord.from_db(t) for t in db_trades]

    def get_trade_by_id(self, trade_id: str) -> Optional[TradeRecord]:
        """Get a specific trade by ID."""
        with self.session_factory() as session:
            db_trade = session.query(TradeRecordDB).filter_by(id=trade_id).first()
            return TradeRecord.from_db(db_trade) if db_trade else None

    def get_open_trades(self) -> List[TradeRecord]:
        """Get all currently open trades."""
        with self.session_factory() as session:
            db_trades = session.query(TradeRecordDB).filter(
                TradeRecordDB.exit_price.is_(None)
            ).all()
            return [TradeRecord.from_db(t) for t in db_trades]

    def get_recent_trades(self, limit: int = 50) -> List[TradeRecord]:
        """Get most recent trades."""
        with self.session_factory() as session:
            db_trades = (
                session.query(TradeRecordDB)
                .filter(TradeRecordDB.exit_price.isnot(None))
                .order_by(desc(TradeRecordDB.closed_at))
                .limit(limit)
                .all()
            )
            return [TradeRecord.from_db(t) for t in db_trades]

    # =========================================================================
    # Performance Metrics
    # =========================================================================

    def get_win_rate(
        self,
        strategy: Optional[str] = None,
        asset: Optional[str] = None,
        timeframe: Optional[str] = None,
        days: int = 30,
    ) -> float:
        """
        Calculate win rate with optional filters.

        Args:
            strategy: Filter by strategy
            asset: Filter by asset
            timeframe: Filter by timeframe (e.g., "7d", "30d", "90d")
            days: Fallback days if timeframe not specified

        Returns:
            Win rate as percentage (0-100)
        """
        if timeframe:
            if timeframe.endswith("d"):
                days = int(timeframe[:-1])
            elif timeframe.endswith("w"):
                days = int(timeframe[:-1]) * 7
            elif timeframe.endswith("m"):
                days = int(timeframe[:-1]) * 30

        cutoff = datetime.utcnow() - timedelta(days=days)

        with self.session_factory() as session:
            query = session.query(TradeRecordDB).filter(
                and_(
                    TradeRecordDB.timestamp >= cutoff,
                    TradeRecordDB.exit_price.isnot(None),
                )
            )

            if strategy:
                query = query.filter(TradeRecordDB.strategy == strategy)
            if asset:
                query = query.filter(TradeRecordDB.asset == asset)

            trades = query.all()

            if not trades:
                return 0.0

            wins = sum(1 for t in trades if t.pnl and t.pnl > 0)
            return (wins / len(trades)) * 100

    def get_avg_pnl(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
        pnl_type: str = "percent",
    ) -> float:
        """
        Calculate average PnL.

        Args:
            strategy: Filter by strategy
            days: Number of days to look back
            pnl_type: "percent" or "absolute"

        Returns:
            Average PnL value
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self.session_factory() as session:
            query = session.query(TradeRecordDB).filter(
                and_(
                    TradeRecordDB.timestamp >= cutoff,
                    TradeRecordDB.exit_price.isnot(None),
                )
            )

            if strategy:
                query = query.filter(TradeRecordDB.strategy == strategy)

            trades = query.all()

            if not trades:
                return 0.0

            if pnl_type == "percent":
                values = [t.pnl_percent for t in trades if t.pnl_percent is not None]
            else:
                values = [t.pnl for t in trades if t.pnl is not None]

            return sum(values) / len(values) if values else 0.0

    def get_total_pnl(
        self,
        days: Optional[int] = None,
        strategy: Optional[str] = None,
    ) -> float:
        """Get total PnL for the specified period."""
        with self.session_factory() as session:
            query = session.query(func.sum(TradeRecordDB.pnl)).filter(
                TradeRecordDB.exit_price.isnot(None)
            )

            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(TradeRecordDB.timestamp >= cutoff)

            if strategy:
                query = query.filter(TradeRecordDB.strategy == strategy)

            result = query.scalar()
            return result or 0.0

    def get_profit_factor(self, days: int = 30) -> float:
        """
        Calculate profit factor (gross profit / gross loss).

        A profit factor > 1 indicates profitability.
        """
        trades = self.get_trade_history(days=days)

        gross_profit = sum(t.pnl for t in trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl and t.pnl < 0))

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def get_sharpe_ratio(self, days: int = 30, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe Ratio.

        Args:
            days: Period for calculation
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sharpe ratio (annualized)
        """
        trades = self.get_trade_history(days=days)

        if len(trades) < 2:
            return 0.0

        returns = [t.pnl_percent for t in trades if t.pnl_percent is not None]

        if not returns:
            return 0.0

        import numpy as np

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualize (assuming ~252 trading days)
        daily_rf = risk_free_rate / 252
        trades_per_day = len(trades) / days
        annualization_factor = np.sqrt(252 * trades_per_day)

        sharpe = ((mean_return - daily_rf) / std_return) * annualization_factor
        return sharpe

    def get_sortino_ratio(self, days: int = 30, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino Ratio (focuses on downside deviation).
        """
        trades = self.get_trade_history(days=days)

        if len(trades) < 2:
            return 0.0

        returns = [t.pnl_percent for t in trades if t.pnl_percent is not None]

        if not returns:
            return 0.0

        import numpy as np

        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            return float("inf") if mean_return > 0 else 0.0

        downside_std = np.std(downside_returns)

        if downside_std == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        trades_per_day = len(trades) / days
        annualization_factor = np.sqrt(252 * trades_per_day)

        sortino = ((mean_return - daily_rf) / downside_std) * annualization_factor
        return sortino

    # =========================================================================
    # Drawdown Tracking
    # =========================================================================

    def get_drawdown_history(
        self,
        days: int = 90,
        min_drawdown_pct: float = 1.0,
    ) -> List[DrawdownEvent]:
        """
        Get history of drawdown events.

        Args:
            days: Days to look back
            min_drawdown_pct: Minimum drawdown percentage to include

        Returns:
            List of DrawdownEvent objects
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self.session_factory() as session:
            db_events = (
                session.query(DrawdownEventDB)
                .filter(
                    and_(
                        DrawdownEventDB.start_timestamp >= cutoff,
                        DrawdownEventDB.drawdown_percent >= min_drawdown_pct,
                    )
                )
                .order_by(desc(DrawdownEventDB.start_timestamp))
                .all()
            )

            return [
                DrawdownEvent(
                    start_timestamp=e.start_timestamp,
                    end_timestamp=e.end_timestamp,
                    peak_equity=e.peak_equity,
                    trough_equity=e.trough_equity,
                    drawdown_percent=e.drawdown_percent,
                    duration_hours=e.duration_hours,
                    recovery_time_hours=e.recovery_time_hours,
                    is_active=e.is_active,
                    contributing_trades=e.contributing_trades or [],
                )
                for e in db_events
            ]

    def get_max_drawdown(self, days: int = 30) -> Tuple[float, Optional[datetime]]:
        """
        Get maximum drawdown and when it occurred.

        Returns:
            Tuple of (max drawdown percentage, timestamp)
        """
        drawdowns = self.get_drawdown_history(days=days)

        if not drawdowns:
            return 0.0, None

        max_dd = max(drawdowns, key=lambda d: d.drawdown_percent or 0)
        return max_dd.drawdown_percent or 0.0, max_dd.start_timestamp

    def _update_drawdown_tracking(self, session: Session, trade: TradeRecord) -> None:
        """Update drawdown tracking after a trade closes."""
        # Calculate cumulative PnL as proxy for equity
        total_pnl = (
            session.query(func.sum(TradeRecordDB.pnl))
            .filter(TradeRecordDB.exit_price.isnot(None))
            .scalar() or 0.0
        )

        # Update peak if new high
        if total_pnl > self._equity_peak:
            self._equity_peak = total_pnl

            # Close any active drawdown
            if self._current_drawdown and self._current_drawdown.is_active:
                self._close_drawdown_event(session, total_pnl)

        elif self._equity_peak > 0:
            # We're in drawdown
            drawdown_pct = ((self._equity_peak - total_pnl) / self._equity_peak) * 100

            if drawdown_pct > 1.0:  # Minimum 1% drawdown to track
                if not self._current_drawdown or not self._current_drawdown.is_active:
                    # Start new drawdown event
                    self._current_drawdown = DrawdownEvent(
                        start_timestamp=datetime.utcnow(),
                        peak_equity=self._equity_peak,
                        trough_equity=total_pnl,
                        drawdown_percent=drawdown_pct,
                        contributing_trades=[trade.id],
                    )
                    self._save_drawdown_event(session, self._current_drawdown)
                else:
                    # Update existing drawdown
                    self._current_drawdown.trough_equity = min(
                        self._current_drawdown.trough_equity or total_pnl,
                        total_pnl,
                    )
                    self._current_drawdown.drawdown_percent = (
                        (self._equity_peak - self._current_drawdown.trough_equity)
                        / self._equity_peak
                    ) * 100
                    self._current_drawdown.contributing_trades.append(trade.id)

    def _save_drawdown_event(self, session: Session, event: DrawdownEvent) -> None:
        """Save drawdown event to database."""
        db_event = DrawdownEventDB(
            start_timestamp=event.start_timestamp,
            peak_equity=event.peak_equity,
            trough_equity=event.trough_equity,
            drawdown_percent=event.drawdown_percent,
            is_active=True,
            contributing_trades=event.contributing_trades,
        )
        session.add(db_event)
        session.commit()

    def _close_drawdown_event(self, session: Session, recovery_equity: float) -> None:
        """Close active drawdown event."""
        if not self._current_drawdown:
            return

        # Find active event in DB
        db_event = (
            session.query(DrawdownEventDB)
            .filter(DrawdownEventDB.is_active == True)
            .order_by(desc(DrawdownEventDB.start_timestamp))
            .first()
        )

        if db_event:
            now = datetime.utcnow()
            duration = (now - db_event.start_timestamp).total_seconds() / 3600

            db_event.end_timestamp = now
            db_event.is_active = False
            db_event.duration_hours = duration
            db_event.recovery_time_hours = duration  # Simplified

            session.commit()

        self._current_drawdown = None

    # =========================================================================
    # Strategy Performance
    # =========================================================================

    def get_strategy_performance(
        self,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get performance breakdown by strategy.

        Returns:
            Dict mapping strategy name to performance metrics
        """
        trades = self.get_trade_history(days=days)

        strategies: Dict[str, List[TradeRecord]] = {}
        for trade in trades:
            if trade.strategy not in strategies:
                strategies[trade.strategy] = []
            strategies[trade.strategy].append(trade)

        performance = {}
        for strategy, strategy_trades in strategies.items():
            wins = [t for t in strategy_trades if t.is_win]
            losses = [t for t in strategy_trades if not t.is_win]

            total_pnl = sum(t.pnl or 0 for t in strategy_trades)
            avg_win = (
                sum(t.pnl or 0 for t in wins) / len(wins) if wins else 0
            )
            avg_loss = (
                sum(t.pnl or 0 for t in losses) / len(losses) if losses else 0
            )

            performance[strategy] = {
                "total_trades": len(strategy_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": (len(wins) / len(strategy_trades)) * 100 if strategy_trades else 0,
                "total_pnl": total_pnl,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float("inf"),
                "avg_confidence": sum(t.confidence for t in strategy_trades) / len(strategy_trades),
            }

        return performance

    def get_best_worst_strategies(
        self,
        days: int = 30,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get best and worst performing strategies."""
        performance = self.get_strategy_performance(days=days)

        if not performance:
            return None, None

        # Filter to strategies with at least 5 trades
        qualified = {k: v for k, v in performance.items() if v["total_trades"] >= 5}

        if not qualified:
            return None, None

        best = max(qualified.items(), key=lambda x: x[1]["total_pnl"])[0]
        worst = min(qualified.items(), key=lambda x: x[1]["total_pnl"])[0]

        return best, worst

    # =========================================================================
    # Snapshots
    # =========================================================================

    def create_performance_snapshot(self) -> PerformanceSnapshot:
        """
        Create a point-in-time performance snapshot.

        Returns:
            PerformanceSnapshot with current metrics
        """
        now = datetime.utcnow()

        # Calculate metrics
        win_rate_7d = self.get_win_rate(days=7)
        win_rate_30d = self.get_win_rate(days=30)
        total_pnl = self.get_total_pnl()
        total_pnl_7d = self.get_total_pnl(days=7)
        total_pnl_30d = self.get_total_pnl(days=30)
        sharpe = self.get_sharpe_ratio(days=30)
        sortino = self.get_sortino_ratio(days=30)
        profit_factor = self.get_profit_factor(days=30)
        max_dd, _ = self.get_max_drawdown(days=30)

        best, worst = self.get_best_worst_strategies(days=30)
        strategy_perf = self.get_strategy_performance(days=30)

        trades_7d = len(self.get_trade_history(days=7))
        trades_30d = len(self.get_trade_history(days=30))

        # Calculate averages
        trades = self.get_trade_history(days=30)
        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]
        avg_win = sum(t.pnl or 0 for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl or 0 for t in losses) / len(losses) if losses else 0

        snapshot = PerformanceSnapshot(
            timestamp=now,
            win_rate_7d=win_rate_7d,
            win_rate_30d=win_rate_30d,
            total_pnl=total_pnl,
            total_pnl_7d=total_pnl_7d,
            total_pnl_30d=total_pnl_30d,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_strategy=best,
            worst_strategy=worst,
            strategy_performance=strategy_perf,
            total_trades=len(trades),
            trades_7d=trades_7d,
            trades_30d=trades_30d,
        )

        # Persist snapshot
        self._save_snapshot(snapshot)

        return snapshot

    def _save_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Save performance snapshot to database."""
        with self.session_factory() as session:
            db_snapshot = PerformanceSnapshotDB(
                timestamp=snapshot.timestamp,
                win_rate_7d=snapshot.win_rate_7d,
                win_rate_30d=snapshot.win_rate_30d,
                total_pnl=snapshot.total_pnl,
                total_pnl_7d=snapshot.total_pnl_7d,
                total_pnl_30d=snapshot.total_pnl_30d,
                sharpe_ratio=snapshot.sharpe_ratio,
                sortino_ratio=snapshot.sortino_ratio,
                max_drawdown=snapshot.max_drawdown,
                profit_factor=snapshot.profit_factor,
                avg_win=snapshot.avg_win,
                avg_loss=snapshot.avg_loss,
                best_strategy=snapshot.best_strategy,
                worst_strategy=snapshot.worst_strategy,
                total_trades=snapshot.total_trades,
                recommended_actions=snapshot.recommended_actions,
            )
            session.add(db_snapshot)
            session.commit()

    def get_snapshot_history(self, days: int = 30) -> List[PerformanceSnapshot]:
        """Get historical performance snapshots."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self.session_factory() as session:
            db_snapshots = (
                session.query(PerformanceSnapshotDB)
                .filter(PerformanceSnapshotDB.timestamp >= cutoff)
                .order_by(desc(PerformanceSnapshotDB.timestamp))
                .all()
            )

            return [
                PerformanceSnapshot(
                    timestamp=s.timestamp,
                    win_rate_7d=s.win_rate_7d,
                    win_rate_30d=s.win_rate_30d,
                    total_pnl=s.total_pnl,
                    total_pnl_7d=s.total_pnl_7d,
                    total_pnl_30d=s.total_pnl_30d,
                    sharpe_ratio=s.sharpe_ratio,
                    sortino_ratio=s.sortino_ratio,
                    max_drawdown=s.max_drawdown,
                    profit_factor=s.profit_factor,
                    avg_win=s.avg_win,
                    avg_loss=s.avg_loss,
                    best_strategy=s.best_strategy,
                    worst_strategy=s.worst_strategy,
                    total_trades=s.total_trades,
                    recommended_actions=s.recommended_actions or [],
                )
                for s in db_snapshots
            ]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_trade_count(
        self,
        days: Optional[int] = None,
        strategy: Optional[str] = None,
    ) -> int:
        """Get total number of trades."""
        with self.session_factory() as session:
            query = session.query(func.count(TradeRecordDB.id)).filter(
                TradeRecordDB.exit_price.isnot(None)
            )

            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(TradeRecordDB.timestamp >= cutoff)

            if strategy:
                query = query.filter(TradeRecordDB.strategy == strategy)

            return query.scalar() or 0

    def get_unique_strategies(self) -> List[str]:
        """Get list of all strategies with recorded trades."""
        with self.session_factory() as session:
            strategies = (
                session.query(TradeRecordDB.strategy)
                .distinct()
                .all()
            )
            return [s[0] for s in strategies]

    def get_unique_assets(self) -> List[str]:
        """Get list of all assets with recorded trades."""
        with self.session_factory() as session:
            assets = (
                session.query(TradeRecordDB.asset)
                .distinct()
                .all()
            )
            return [a[0] for a in assets]
