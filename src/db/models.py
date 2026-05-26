from __future__ import annotations

"""
SQLAlchemy models for the forex trading system.
All models use async-compatible SQLAlchemy with PostgreSQL support.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    JSON,
    Enum,
    Date,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TradeDirection(PyEnum):
    """Trade direction enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class Trade(Base):
    """
    Represents a completed or ongoing trade.
    Stores all relevant trade data including entry/exit, P&L, and market conditions.
    """
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    asset = Column(String(20), nullable=False, index=True)
    strategy = Column(String(50), nullable=False, index=True)
    direction = Column(Enum(TradeDirection), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    features_snapshot = Column(JSON, nullable=True)
    market_conditions = Column(JSON, nullable=True)
    session = Column(String(20), nullable=True)  # e.g., 'LONDON', 'NEW_YORK', 'TOKYO'
    duration_minutes = Column(Integer, nullable=True)
    was_stopped_out = Column(Boolean, default=False)
    hit_target = Column(Boolean, default=False)
    broker = Column(String(50), nullable=True)
    order_id = Column(String(100), nullable=True, unique=True)

    def __repr__(self) -> str:
        return (
            f"<Trade(id={self.id}, asset={self.asset}, direction={self.direction}, "
            f"pnl={self.pnl})>"
        )


class Position(Base):
    """
    Represents an open trading position.
    Tracks real-time position data including unrealized P&L.
    """
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset = Column(String(20), nullable=False, index=True)
    direction = Column(Enum(TradeDirection), nullable=False)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    broker = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Position(id={self.id}, asset={self.asset}, direction={self.direction}, "
            f"unrealized_pnl={self.unrealized_pnl})>"
        )


class DailyPerformance(Base):
    """
    Tracks daily trading performance metrics.
    Used for performance reporting and equity curve generation.
    """
    __tablename__ = 'daily_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    pnl_percent = Column(Float, nullable=False)
    trades_count = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DailyPerformance(date={self.date}, pnl={self.pnl}, "
            f"win_rate={self.win_rate})>"
        )


class StrategyPerformance(Base):
    """
    Tracks performance metrics per trading strategy.
    Enables strategy comparison and optimization.
    """
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    trades_count = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    pnl = Column(Float, nullable=False, default=0.0)
    avg_confidence = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self) -> str:
        return (
            f"<StrategyPerformance(strategy={self.strategy_name}, date={self.date}, "
            f"pnl={self.pnl})>"
        )


class FailurePattern(Base):
    """
    Records detected failure patterns in trading.
    Used for pattern recognition and strategy improvement.
    """
    __tablename__ = 'failure_patterns'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    frequency = Column(Integer, nullable=False, default=1)
    affected_trades = Column(JSON, nullable=True)
    suggested_action = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<FailurePattern(id={self.id}, type={self.pattern_type}, "
            f"resolved={self.resolved})>"
        )
