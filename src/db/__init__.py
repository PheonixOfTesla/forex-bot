"""
Database layer for forex-bot trading system.
Provides async SQLAlchemy models, repositories, and connection management.
"""

from .models import (
    Base,
    Trade,
    Position,
    DailyPerformance,
    StrategyPerformance,
    FailurePattern,
    TradeDirection,
)
from .connection import Database, DatabasePool
from .repository import (
    TradeRepository,
    PositionRepository,
    PerformanceRepository,
    FailurePatternRepository,
)

__all__ = [
    # Models
    "Base",
    "Trade",
    "Position",
    "DailyPerformance",
    "StrategyPerformance",
    "FailurePattern",
    "TradeDirection",
    # Connection
    "Database",
    "DatabasePool",
    # Repositories
    "TradeRepository",
    "PositionRepository",
    "PerformanceRepository",
    "FailurePatternRepository",
]
