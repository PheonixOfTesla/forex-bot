from __future__ import annotations

"""
Data Access Layer (Repository Pattern) for forex trading system.
Provides async CRUD operations for all trading entities.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Trade,
    Position,
    DailyPerformance,
    StrategyPerformance,
    FailurePattern,
    TradeDirection,
)


class TradeRepository:
    """
    Repository for Trade entity operations.
    Handles all trade-related database queries.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_trade(self, trade: Trade) -> int:
        """
        Save a new trade to the database.

        Args:
            trade: Trade entity to save

        Returns:
            int: The ID of the saved trade
        """
        self.session.add(trade)
        await self.session.flush()
        await self.session.refresh(trade)
        return trade.id

    async def get_trades(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
        asset: Optional[str] = None,
        direction: Optional[TradeDirection] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Trade]:
        """
        Get trades with optional filters.

        Args:
            days: Number of days to look back (default 30)
            strategy: Filter by strategy name
            asset: Filter by asset (e.g., 'EUR/USD')
            direction: Filter by trade direction
            limit: Maximum number of trades to return
            offset: Number of trades to skip

        Returns:
            List[Trade]: List of matching trades
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = select(Trade).where(Trade.timestamp >= cutoff_date)

        if strategy:
            query = query.where(Trade.strategy == strategy)
        if asset:
            query = query.where(Trade.asset == asset)
        if direction:
            query = query.where(Trade.direction == direction)

        query = query.order_by(Trade.timestamp.desc())

        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_trade_by_id(self, trade_id: int) -> Optional[Trade]:
        """
        Get a trade by its ID.

        Args:
            trade_id: The trade ID

        Returns:
            Trade or None if not found
        """
        result = await self.session.execute(
            select(Trade).where(Trade.id == trade_id)
        )
        return result.scalar_one_or_none()

    async def get_trade_by_order_id(self, order_id: str) -> Optional[Trade]:
        """
        Get a trade by its broker order ID.

        Args:
            order_id: The broker order ID

        Returns:
            Trade or None if not found
        """
        result = await self.session.execute(
            select(Trade).where(Trade.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_win_rate(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
        asset: Optional[str] = None,
    ) -> float:
        """
        Calculate win rate for the specified period.

        Args:
            days: Number of days to look back
            strategy: Filter by strategy
            asset: Filter by asset

        Returns:
            float: Win rate as percentage (0-100)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Build filter conditions
        conditions = [
            Trade.timestamp >= cutoff_date,
            Trade.pnl.isnot(None),
        ]
        if strategy:
            conditions.append(Trade.strategy == strategy)
        if asset:
            conditions.append(Trade.asset == asset)

        # Count total trades
        total_query = select(func.count(Trade.id)).where(and_(*conditions))
        total_result = await self.session.execute(total_query)
        total_trades = total_result.scalar() or 0

        if total_trades == 0:
            return 0.0

        # Count winning trades
        win_conditions = conditions + [Trade.pnl > 0]
        wins_query = select(func.count(Trade.id)).where(and_(*win_conditions))
        wins_result = await self.session.execute(wins_query)
        wins = wins_result.scalar() or 0

        return (wins / total_trades) * 100

    async def get_pnl(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
        asset: Optional[str] = None,
    ) -> float:
        """
        Calculate total P&L for the specified period.

        Args:
            days: Number of days to look back
            strategy: Filter by strategy
            asset: Filter by asset

        Returns:
            float: Total P&L
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        conditions = [
            Trade.timestamp >= cutoff_date,
            Trade.pnl.isnot(None),
        ]
        if strategy:
            conditions.append(Trade.strategy == strategy)
        if asset:
            conditions.append(Trade.asset == asset)

        query = select(func.sum(Trade.pnl)).where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar() or 0.0

    async def get_trade_stats(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive trade statistics.

        Args:
            days: Number of days to look back
            strategy: Filter by strategy

        Returns:
            Dict with total_trades, wins, losses, win_rate, total_pnl, avg_pnl
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        conditions = [
            Trade.timestamp >= cutoff_date,
            Trade.pnl.isnot(None),
        ]
        if strategy:
            conditions.append(Trade.strategy == strategy)

        # Get aggregate stats
        query = select(
            func.count(Trade.id).label("total"),
            func.sum(func.cast(Trade.pnl > 0, Integer)).label("wins"),
            func.sum(Trade.pnl).label("total_pnl"),
            func.avg(Trade.pnl).label("avg_pnl"),
        ).where(and_(*conditions))

        # Use raw SQL for the boolean cast
        from sqlalchemy import Integer, case

        query = select(
            func.count(Trade.id).label("total"),
            func.sum(case((Trade.pnl > 0, 1), else_=0)).label("wins"),
            func.sum(Trade.pnl).label("total_pnl"),
            func.avg(Trade.pnl).label("avg_pnl"),
        ).where(and_(*conditions))

        result = await self.session.execute(query)
        row = result.one()

        total = row.total or 0
        wins = row.wins or 0
        losses = total - wins

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0.0,
            "total_pnl": row.total_pnl or 0.0,
            "avg_pnl": row.avg_pnl or 0.0,
        }

    async def update_trade(self, trade_id: int, **kwargs) -> bool:
        """
        Update a trade by ID.

        Args:
            trade_id: The trade ID
            **kwargs: Fields to update

        Returns:
            bool: True if updated, False if not found
        """
        result = await self.session.execute(
            update(Trade).where(Trade.id == trade_id).values(**kwargs)
        )
        return result.rowcount > 0

    async def delete_trade(self, trade_id: int) -> bool:
        """
        Delete a trade by ID.

        Args:
            trade_id: The trade ID

        Returns:
            bool: True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(Trade).where(Trade.id == trade_id)
        )
        return result.rowcount > 0


class PositionRepository:
    """
    Repository for Position entity operations.
    Handles open position tracking and management.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_position(self, position: Position) -> int:
        """
        Save a new position to the database.

        Args:
            position: Position entity to save

        Returns:
            int: The ID of the saved position
        """
        self.session.add(position)
        await self.session.flush()
        await self.session.refresh(position)
        return position.id

    async def get_open_positions(
        self,
        asset: Optional[str] = None,
        broker: Optional[str] = None,
    ) -> List[Position]:
        """
        Get all open positions.

        Args:
            asset: Filter by asset
            broker: Filter by broker

        Returns:
            List[Position]: List of open positions
        """
        query = select(Position)

        if asset:
            query = query.where(Position.asset == asset)
        if broker:
            query = query.where(Position.broker == broker)

        query = query.order_by(Position.opened_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_position_by_id(self, position_id: int) -> Optional[Position]:
        """
        Get a position by its ID.

        Args:
            position_id: The position ID

        Returns:
            Position or None if not found
        """
        result = await self.session.execute(
            select(Position).where(Position.id == position_id)
        )
        return result.scalar_one_or_none()

    async def close_position(
        self,
        position_id: int,
        exit_price: float,
        pnl: float,
    ) -> Optional[Trade]:
        """
        Close a position and create a completed trade record.

        Args:
            position_id: The position ID to close
            exit_price: The exit price
            pnl: The realized P&L

        Returns:
            Trade: The created trade record, or None if position not found
        """
        position = await self.get_position_by_id(position_id)
        if not position:
            return None

        # Calculate duration
        duration = datetime.utcnow() - position.opened_at
        duration_minutes = int(duration.total_seconds() / 60)

        # Determine if stopped out or hit target
        was_stopped_out = False
        hit_target = False

        if position.stop_loss and position.direction == TradeDirection.LONG:
            was_stopped_out = exit_price <= position.stop_loss
        elif position.stop_loss and position.direction == TradeDirection.SHORT:
            was_stopped_out = exit_price >= position.stop_loss

        if position.take_profit and position.direction == TradeDirection.LONG:
            hit_target = exit_price >= position.take_profit
        elif position.take_profit and position.direction == TradeDirection.SHORT:
            hit_target = exit_price <= position.take_profit

        # Create trade record
        pnl_percent = (pnl / (position.entry_price * position.quantity)) * 100

        trade = Trade(
            timestamp=position.opened_at,
            asset=position.asset,
            strategy="",  # Will need to be set by caller
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            quantity=position.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            duration_minutes=duration_minutes,
            was_stopped_out=was_stopped_out,
            hit_target=hit_target,
            broker=position.broker,
        )
        self.session.add(trade)

        # Delete the position
        await self.session.execute(
            delete(Position).where(Position.id == position_id)
        )

        await self.session.flush()
        await self.session.refresh(trade)

        return trade

    async def update_position(self, position_id: int, **kwargs) -> bool:
        """
        Update a position by ID.

        Args:
            position_id: The position ID
            **kwargs: Fields to update (e.g., current_price, unrealized_pnl)

        Returns:
            bool: True if updated, False if not found
        """
        result = await self.session.execute(
            update(Position).where(Position.id == position_id).values(**kwargs)
        )
        return result.rowcount > 0

    async def update_all_positions_price(
        self,
        asset: str,
        current_price: float,
    ) -> int:
        """
        Update current price for all positions of an asset.

        Args:
            asset: The asset to update
            current_price: The new current price

        Returns:
            int: Number of positions updated
        """
        # Get positions to calculate unrealized P&L
        positions = await self.get_open_positions(asset=asset)

        updated = 0
        for position in positions:
            if position.direction == TradeDirection.LONG:
                unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:
                unrealized_pnl = (position.entry_price - current_price) * position.quantity

            await self.update_position(
                position.id,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
            )
            updated += 1

        return updated

    async def get_total_unrealized_pnl(self) -> float:
        """
        Get total unrealized P&L across all open positions.

        Returns:
            float: Total unrealized P&L
        """
        result = await self.session.execute(
            select(func.sum(Position.unrealized_pnl))
        )
        return result.scalar() or 0.0

    async def delete_position(self, position_id: int) -> bool:
        """
        Delete a position by ID.

        Args:
            position_id: The position ID

        Returns:
            bool: True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(Position).where(Position.id == position_id)
        )
        return result.rowcount > 0


class PerformanceRepository:
    """
    Repository for performance tracking entities.
    Handles daily performance and strategy performance.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_daily_performance(self, perf: DailyPerformance) -> int:
        """
        Save or update daily performance record.

        Args:
            perf: DailyPerformance entity to save

        Returns:
            int: The ID of the saved record
        """
        # Check if record exists for this date
        existing = await self.session.execute(
            select(DailyPerformance).where(DailyPerformance.date == perf.date)
        )
        existing_record = existing.scalar_one_or_none()

        if existing_record:
            # Update existing record
            await self.session.execute(
                update(DailyPerformance)
                .where(DailyPerformance.date == perf.date)
                .values(
                    starting_balance=perf.starting_balance,
                    ending_balance=perf.ending_balance,
                    pnl=perf.pnl,
                    pnl_percent=perf.pnl_percent,
                    trades_count=perf.trades_count,
                    wins=perf.wins,
                    losses=perf.losses,
                    win_rate=perf.win_rate,
                    max_drawdown=perf.max_drawdown,
                )
            )
            return existing_record.id
        else:
            self.session.add(perf)
            await self.session.flush()
            await self.session.refresh(perf)
            return perf.id

    async def get_performance_history(
        self,
        days: int = 30,
    ) -> List[DailyPerformance]:
        """
        Get daily performance history.

        Args:
            days: Number of days to look back

        Returns:
            List[DailyPerformance]: Performance records ordered by date
        """
        cutoff_date = date.today() - timedelta(days=days)

        result = await self.session.execute(
            select(DailyPerformance)
            .where(DailyPerformance.date >= cutoff_date)
            .order_by(DailyPerformance.date.asc())
        )
        return list(result.scalars().all())

    async def get_equity_curve(self, days: int = 30) -> List[float]:
        """
        Get equity curve (ending balances over time).

        Args:
            days: Number of days to look back

        Returns:
            List[float]: List of ending balances ordered by date
        """
        history = await self.get_performance_history(days=days)
        return [record.ending_balance for record in history]

    async def get_cumulative_pnl(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get cumulative P&L over time.

        Args:
            days: Number of days to look back

        Returns:
            List of dicts with date and cumulative_pnl
        """
        history = await self.get_performance_history(days=days)

        cumulative = 0.0
        result = []
        for record in history:
            cumulative += record.pnl
            result.append({
                "date": record.date,
                "pnl": record.pnl,
                "cumulative_pnl": cumulative,
            })

        return result

    async def get_max_drawdown(self, days: int = 30) -> float:
        """
        Calculate maximum drawdown over the period.

        Args:
            days: Number of days to look back

        Returns:
            float: Maximum drawdown as percentage
        """
        equity_curve = await self.get_equity_curve(days=days)

        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0

        for balance in equity_curve:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    async def save_strategy_performance(
        self,
        perf: StrategyPerformance,
    ) -> int:
        """
        Save or update strategy performance record.

        Args:
            perf: StrategyPerformance entity to save

        Returns:
            int: The ID of the saved record
        """
        # Check if record exists for this strategy and date
        existing = await self.session.execute(
            select(StrategyPerformance).where(
                and_(
                    StrategyPerformance.strategy_name == perf.strategy_name,
                    StrategyPerformance.date == perf.date,
                )
            )
        )
        existing_record = existing.scalar_one_or_none()

        if existing_record:
            await self.session.execute(
                update(StrategyPerformance)
                .where(StrategyPerformance.id == existing_record.id)
                .values(
                    trades_count=perf.trades_count,
                    wins=perf.wins,
                    losses=perf.losses,
                    pnl=perf.pnl,
                    avg_confidence=perf.avg_confidence,
                    is_active=perf.is_active,
                )
            )
            return existing_record.id
        else:
            self.session.add(perf)
            await self.session.flush()
            await self.session.refresh(perf)
            return perf.id

    async def get_strategy_performance(
        self,
        strategy_name: str,
        days: int = 30,
    ) -> List[StrategyPerformance]:
        """
        Get performance history for a specific strategy.

        Args:
            strategy_name: Name of the strategy
            days: Number of days to look back

        Returns:
            List[StrategyPerformance]: Performance records
        """
        cutoff_date = date.today() - timedelta(days=days)

        result = await self.session.execute(
            select(StrategyPerformance)
            .where(
                and_(
                    StrategyPerformance.strategy_name == strategy_name,
                    StrategyPerformance.date >= cutoff_date,
                )
            )
            .order_by(StrategyPerformance.date.asc())
        )
        return list(result.scalars().all())

    async def get_all_strategies_summary(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get summary performance for all strategies.

        Args:
            days: Number of days to look back

        Returns:
            List of dicts with strategy stats
        """
        cutoff_date = date.today() - timedelta(days=days)

        from sqlalchemy import case

        query = select(
            StrategyPerformance.strategy_name,
            func.sum(StrategyPerformance.trades_count).label("total_trades"),
            func.sum(StrategyPerformance.wins).label("total_wins"),
            func.sum(StrategyPerformance.losses).label("total_losses"),
            func.sum(StrategyPerformance.pnl).label("total_pnl"),
            func.avg(StrategyPerformance.avg_confidence).label("avg_confidence"),
        ).where(
            StrategyPerformance.date >= cutoff_date
        ).group_by(
            StrategyPerformance.strategy_name
        )

        result = await self.session.execute(query)

        summaries = []
        for row in result:
            total_trades = row.total_trades or 0
            total_wins = row.total_wins or 0
            summaries.append({
                "strategy_name": row.strategy_name,
                "total_trades": total_trades,
                "wins": total_wins,
                "losses": row.total_losses or 0,
                "win_rate": (total_wins / total_trades * 100) if total_trades > 0 else 0,
                "total_pnl": row.total_pnl or 0,
                "avg_confidence": row.avg_confidence,
            })

        return summaries


class FailurePatternRepository:
    """
    Repository for failure pattern tracking.
    Helps identify and resolve recurring issues.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_pattern(self, pattern: FailurePattern) -> int:
        """
        Save a new failure pattern.

        Args:
            pattern: FailurePattern entity to save

        Returns:
            int: The ID of the saved pattern
        """
        self.session.add(pattern)
        await self.session.flush()
        await self.session.refresh(pattern)
        return pattern.id

    async def get_unresolved_patterns(self) -> List[FailurePattern]:
        """
        Get all unresolved failure patterns.

        Returns:
            List[FailurePattern]: Unresolved patterns ordered by frequency
        """
        result = await self.session.execute(
            select(FailurePattern)
            .where(FailurePattern.resolved == False)
            .order_by(FailurePattern.frequency.desc())
        )
        return list(result.scalars().all())

    async def get_patterns_by_type(
        self,
        pattern_type: str,
    ) -> List[FailurePattern]:
        """
        Get patterns by type.

        Args:
            pattern_type: The pattern type to filter by

        Returns:
            List[FailurePattern]: Matching patterns
        """
        result = await self.session.execute(
            select(FailurePattern)
            .where(FailurePattern.pattern_type == pattern_type)
            .order_by(FailurePattern.detected_at.desc())
        )
        return list(result.scalars().all())

    async def increment_frequency(self, pattern_id: int) -> bool:
        """
        Increment the frequency count of a pattern.

        Args:
            pattern_id: The pattern ID

        Returns:
            bool: True if updated, False if not found
        """
        result = await self.session.execute(
            update(FailurePattern)
            .where(FailurePattern.id == pattern_id)
            .values(frequency=FailurePattern.frequency + 1)
        )
        return result.rowcount > 0

    async def resolve_pattern(
        self,
        pattern_id: int,
        resolution_note: Optional[str] = None,
    ) -> bool:
        """
        Mark a pattern as resolved.

        Args:
            pattern_id: The pattern ID
            resolution_note: Optional note about resolution

        Returns:
            bool: True if updated, False if not found
        """
        values = {"resolved": True}
        if resolution_note:
            values["suggested_action"] = resolution_note

        result = await self.session.execute(
            update(FailurePattern)
            .where(FailurePattern.id == pattern_id)
            .values(**values)
        )
        return result.rowcount > 0

    async def add_affected_trade(
        self,
        pattern_id: int,
        trade_id: int,
    ) -> bool:
        """
        Add a trade ID to the affected trades list.

        Args:
            pattern_id: The pattern ID
            trade_id: The trade ID to add

        Returns:
            bool: True if updated
        """
        pattern = await self.session.execute(
            select(FailurePattern).where(FailurePattern.id == pattern_id)
        )
        pattern_record = pattern.scalar_one_or_none()

        if not pattern_record:
            return False

        affected = pattern_record.affected_trades or []
        if trade_id not in affected:
            affected.append(trade_id)
            await self.session.execute(
                update(FailurePattern)
                .where(FailurePattern.id == pattern_id)
                .values(affected_trades=affected)
            )

        return True
