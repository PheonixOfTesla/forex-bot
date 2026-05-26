from __future__ import annotations

"""
Data Models for the Intelligence Engine

Defines all data structures used for trade tracking, analysis,
and performance monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    Integer,
    JSON,
    String,
    Text,
    Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class TradeDirection(str, Enum):
    """Trade direction enumeration"""
    LONG = "long"
    SHORT = "short"


class PatternType(str, Enum):
    """Types of failure patterns"""
    TIME_BASED = "time_based"
    MARKET_CONDITION = "market_condition"
    STRATEGY_SPECIFIC = "strategy_specific"
    VOLATILITY = "volatility"
    SESSION = "session"
    NEWS_EVENT = "news_event"
    CORRELATION = "correlation"
    TREND_STATE = "trend_state"


class ActionType(str, Enum):
    """Types of suggested actions"""
    DISABLE_STRATEGY = "disable_strategy"
    ADJUST_PARAMETERS = "adjust_parameters"
    REDUCE_POSITION_SIZE = "reduce_position_size"
    INCREASE_CONFIDENCE_THRESHOLD = "increase_confidence_threshold"
    AVOID_SESSION = "avoid_session"
    RETRAIN_MODEL = "retrain_model"
    MANUAL_REVIEW = "manual_review"


# =============================================================================
# SQLAlchemy ORM Models
# =============================================================================


class TradeRecordDB(Base):
    """SQLAlchemy model for persistent trade storage"""

    __tablename__ = "trade_records"

    id = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True, index=True)
    asset = Column(String(20), nullable=False, index=True)
    strategy = Column(String(50), nullable=False, index=True)
    direction = Column(SQLEnum(TradeDirection), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True, index=True)
    pnl_percent = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False)
    features_snapshot = Column(JSON, nullable=True)
    market_conditions = Column(JSON, nullable=True)
    session = Column(String(20), nullable=True, index=True)
    duration_minutes = Column(Integer, nullable=True)
    was_stopped_out = Column(Boolean, default=False)
    hit_target = Column(Boolean, default=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    position_size = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_strategy_timestamp", "strategy", "timestamp"),
        Index("idx_asset_strategy", "asset", "strategy"),
        Index("idx_session_pnl", "session", "pnl"),
    )


class DrawdownEventDB(Base):
    """SQLAlchemy model for drawdown events"""

    __tablename__ = "drawdown_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_timestamp = Column(DateTime, nullable=False, index=True)
    end_timestamp = Column(DateTime, nullable=True)
    peak_equity = Column(Float, nullable=False)
    trough_equity = Column(Float, nullable=True)
    drawdown_percent = Column(Float, nullable=True)
    duration_hours = Column(Float, nullable=True)
    recovery_time_hours = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    contributing_trades = Column(JSON, nullable=True)


class PerformanceSnapshotDB(Base):
    """SQLAlchemy model for performance snapshots"""

    __tablename__ = "performance_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    win_rate_7d = Column(Float, nullable=True)
    win_rate_30d = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    total_pnl_7d = Column(Float, nullable=True)
    total_pnl_30d = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    max_drawdown_duration_hours = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    avg_win = Column(Float, nullable=True)
    avg_loss = Column(Float, nullable=True)
    best_strategy = Column(String(50), nullable=True)
    worst_strategy = Column(String(50), nullable=True)
    total_trades = Column(Integer, nullable=True)
    recommended_actions = Column(JSON, nullable=True)


class FailurePatternDB(Base):
    """SQLAlchemy model for detected failure patterns"""

    __tablename__ = "failure_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, nullable=False, index=True)
    pattern_type = Column(SQLEnum(PatternType), nullable=False)
    description = Column(Text, nullable=False)
    frequency = Column(Float, nullable=False)
    affected_trades_count = Column(Integer, nullable=False)
    affected_trade_ids = Column(JSON, nullable=True)
    suggested_action = Column(SQLEnum(ActionType), nullable=False)
    confidence_score = Column(Float, nullable=False)
    additional_data = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    resolved_at = Column(DateTime, nullable=True)


class FeatureImportanceDB(Base):
    """SQLAlchemy model for tracking feature importance over time"""

    __tablename__ = "feature_importance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    feature_name = Column(String(50), nullable=False, index=True)
    importance_score = Column(Float, nullable=False)
    correlation_with_wins = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False)
    strategy = Column(String(50), nullable=True)


# =============================================================================
# Dataclass Models (for in-memory operations)
# =============================================================================


@dataclass
class TradeRecord:
    """
    Complete record of a single trade.

    This is the fundamental unit of trade history, capturing all
    relevant information for analysis and learning.
    """
    id: str
    timestamp: datetime
    asset: str
    strategy: str
    direction: TradeDirection
    entry_price: float
    confidence: float

    # Optional fields (filled when trade closes)
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    closed_at: Optional[datetime] = None

    # Context
    features_snapshot: Dict[str, Any] = field(default_factory=dict)
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    session: Optional[str] = None

    # Execution details
    duration_minutes: Optional[int] = None
    was_stopped_out: bool = False
    hit_target: bool = False
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None

    # Notes
    notes: Optional[str] = None

    @property
    def is_win(self) -> bool:
        """Check if trade was profitable"""
        return self.pnl is not None and self.pnl > 0

    @property
    def is_closed(self) -> bool:
        """Check if trade has been closed"""
        return self.exit_price is not None

    @classmethod
    def from_db(cls, db_record: TradeRecordDB) -> "TradeRecord":
        """Create TradeRecord from database model"""
        return cls(
            id=db_record.id,
            timestamp=db_record.timestamp,
            asset=db_record.asset,
            strategy=db_record.strategy,
            direction=db_record.direction,
            entry_price=db_record.entry_price,
            exit_price=db_record.exit_price,
            pnl=db_record.pnl,
            pnl_percent=db_record.pnl_percent,
            confidence=db_record.confidence,
            features_snapshot=db_record.features_snapshot or {},
            market_conditions=db_record.market_conditions or {},
            session=db_record.session,
            duration_minutes=db_record.duration_minutes,
            was_stopped_out=db_record.was_stopped_out,
            hit_target=db_record.hit_target,
            stop_loss=db_record.stop_loss,
            take_profit=db_record.take_profit,
            position_size=db_record.position_size,
            closed_at=db_record.closed_at,
            notes=db_record.notes,
        )

    def to_db(self) -> TradeRecordDB:
        """Convert to database model"""
        return TradeRecordDB(
            id=self.id,
            timestamp=self.timestamp,
            asset=self.asset,
            strategy=self.strategy,
            direction=self.direction,
            entry_price=self.entry_price,
            exit_price=self.exit_price,
            pnl=self.pnl,
            pnl_percent=self.pnl_percent,
            confidence=self.confidence,
            features_snapshot=self.features_snapshot,
            market_conditions=self.market_conditions,
            session=self.session,
            duration_minutes=self.duration_minutes,
            was_stopped_out=self.was_stopped_out,
            hit_target=self.hit_target,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            position_size=self.position_size,
            closed_at=self.closed_at,
            notes=self.notes,
        )


@dataclass
class DrawdownEvent:
    """
    Records a drawdown period.

    Tracks when equity dropped from peak to trough and
    the recovery period.
    """
    start_timestamp: datetime
    peak_equity: float

    end_timestamp: Optional[datetime] = None
    trough_equity: Optional[float] = None
    drawdown_percent: Optional[float] = None
    duration_hours: Optional[float] = None
    recovery_time_hours: Optional[float] = None
    is_active: bool = True
    contributing_trades: List[str] = field(default_factory=list)

    def calculate_drawdown(self) -> float:
        """Calculate drawdown percentage"""
        if self.trough_equity is None:
            return 0.0
        return ((self.peak_equity - self.trough_equity) / self.peak_equity) * 100


@dataclass
class FailurePattern:
    """
    Detected pattern in losing trades.

    Identifies recurring conditions or circumstances
    that lead to losses.
    """
    pattern_type: PatternType
    description: str
    frequency: float  # How often this pattern occurs in losses (0-1)
    affected_trades_count: int
    suggested_action: ActionType
    confidence_score: float  # How confident we are in this pattern (0-1)

    affected_trade_ids: List[str] = field(default_factory=list)
    additional_data: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "frequency": self.frequency,
            "affected_trades_count": self.affected_trades_count,
            "suggested_action": self.suggested_action.value,
            "confidence_score": self.confidence_score,
            "additional_data": self.additional_data,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class LossAnalysis:
    """
    Analysis of losing trades.

    Identifies common factors in losses to enable
    learning and avoidance.
    """
    total_losses: int
    total_loss_amount: float
    avg_loss: float

    # Common features in losing trades
    common_features: Dict[str, Any] = field(default_factory=dict)

    # Time patterns
    worst_hours: List[int] = field(default_factory=list)
    worst_days: List[int] = field(default_factory=list)
    worst_sessions: List[str] = field(default_factory=list)

    # Market conditions during losses
    market_conditions: Dict[str, Any] = field(default_factory=dict)

    # Strategy breakdown
    losses_by_strategy: Dict[str, int] = field(default_factory=dict)
    loss_amount_by_strategy: Dict[str, float] = field(default_factory=dict)

    # Identified patterns
    patterns: List[FailurePattern] = field(default_factory=list)

    # Time range
    analysis_start: Optional[datetime] = None
    analysis_end: Optional[datetime] = None


@dataclass
class WinAnalysis:
    """
    Analysis of winning trades.

    Identifies conditions that lead to profitable trades
    to enable replication.
    """
    total_wins: int
    total_win_amount: float
    avg_win: float

    # Common features in winning trades
    common_features: Dict[str, Any] = field(default_factory=dict)

    # Best conditions
    best_hours: List[int] = field(default_factory=list)
    best_days: List[int] = field(default_factory=list)
    best_sessions: List[str] = field(default_factory=list)

    # Market conditions during wins
    market_conditions: Dict[str, Any] = field(default_factory=dict)

    # Strategy breakdown
    wins_by_strategy: Dict[str, int] = field(default_factory=dict)
    win_amount_by_strategy: Dict[str, float] = field(default_factory=dict)

    # Win characteristics
    avg_confidence_on_wins: float = 0.0
    avg_duration_minutes: float = 0.0
    hit_target_rate: float = 0.0

    # Time range
    analysis_start: Optional[datetime] = None
    analysis_end: Optional[datetime] = None


@dataclass
class Adjustment:
    """
    Suggested parameter adjustment.

    Represents a recommended change to trading parameters
    based on performance analysis.
    """
    strategy: Optional[str]
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    expected_impact: str
    confidence: float

    # Context
    asset: Optional[str] = None
    session: Optional[str] = None
    condition: Optional[str] = None

    # Priority (1=highest)
    priority: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "strategy": self.strategy,
            "parameter": self.parameter,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "asset": self.asset,
            "session": self.session,
            "condition": self.condition,
            "priority": self.priority,
        }


@dataclass
class PerformanceSnapshot:
    """
    Point-in-time performance metrics.

    Captures overall trading performance at a specific moment
    for tracking improvement over time.
    """
    timestamp: datetime

    # Win rates
    win_rate_7d: Optional[float] = None
    win_rate_30d: Optional[float] = None
    win_rate_all: Optional[float] = None

    # PnL
    total_pnl: float = 0.0
    total_pnl_7d: float = 0.0
    total_pnl_30d: float = 0.0

    # Risk metrics
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: float = 0.0
    max_drawdown_duration_hours: float = 0.0
    current_drawdown: float = 0.0

    # Trade quality
    profit_factor: Optional[float] = None
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0

    # Strategy performance
    best_strategy: Optional[str] = None
    worst_strategy: Optional[str] = None
    strategy_performance: Dict[str, Dict] = field(default_factory=dict)

    # Trade counts
    total_trades: int = 0
    trades_7d: int = 0
    trades_30d: int = 0

    # Actions
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "win_rate_7d": self.win_rate_7d,
            "win_rate_30d": self.win_rate_30d,
            "total_pnl": self.total_pnl,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "best_strategy": self.best_strategy,
            "worst_strategy": self.worst_strategy,
            "total_trades": self.total_trades,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class ImprovementReport:
    """
    Weekly/periodic improvement report.

    Summarizes what worked, what didn't, and what changed
    over the reporting period.
    """
    report_start: datetime
    report_end: datetime
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # Summary metrics
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0

    # What worked
    successful_patterns: List[Dict[str, Any]] = field(default_factory=list)
    best_performing_strategies: List[Dict[str, Any]] = field(default_factory=list)
    optimal_conditions: Dict[str, Any] = field(default_factory=dict)

    # What didn't work
    failure_patterns: List[FailurePattern] = field(default_factory=list)
    worst_performing_strategies: List[Dict[str, Any]] = field(default_factory=list)
    conditions_to_avoid: Dict[str, Any] = field(default_factory=dict)

    # Changes made
    parameter_adjustments: List[Adjustment] = field(default_factory=list)
    disabled_strategies: List[str] = field(default_factory=list)
    threshold_changes: Dict[str, Any] = field(default_factory=dict)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    # Comparison to previous period
    pnl_change: float = 0.0
    win_rate_change: float = 0.0
    improvement_score: float = 0.0

    def to_markdown(self) -> str:
        """Generate markdown report"""
        lines = [
            f"# Trading Improvement Report",
            f"**Period:** {self.report_start.strftime('%Y-%m-%d')} to {self.report_end.strftime('%Y-%m-%d')}",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M')} UTC",
            "",
            "## Summary",
            f"- **Total Trades:** {self.total_trades}",
            f"- **Win Rate:** {self.win_rate:.1f}%",
            f"- **Total PnL:** ${self.total_pnl:,.2f}",
            f"- **Improvement Score:** {self.improvement_score:+.1f}%",
            "",
            "## What Worked",
        ]

        if self.best_performing_strategies:
            lines.append("### Best Performing Strategies")
            for strat in self.best_performing_strategies:
                lines.append(f"- **{strat.get('name', 'Unknown')}**: "
                           f"{strat.get('win_rate', 0):.1f}% win rate, "
                           f"${strat.get('pnl', 0):,.2f} PnL")

        lines.append("")
        lines.append("## What Didn't Work")

        if self.failure_patterns:
            lines.append("### Detected Failure Patterns")
            for pattern in self.failure_patterns:
                lines.append(f"- **{pattern.pattern_type.value}**: {pattern.description}")

        lines.append("")
        lines.append("## Changes Made")

        if self.parameter_adjustments:
            lines.append("### Parameter Adjustments")
            for adj in self.parameter_adjustments:
                lines.append(f"- {adj.parameter}: {adj.current_value} -> {adj.suggested_value} ({adj.reason})")

        if self.disabled_strategies:
            lines.append("### Disabled Strategies")
            for strat in self.disabled_strategies:
                lines.append(f"- {strat}")

        lines.append("")
        lines.append("## Recommendations")
        for rec in self.recommendations:
            lines.append(f"- {rec}")

        return "\n".join(lines)


# =============================================================================
# Database Setup Helper
# =============================================================================


def create_database_engine(database_url: str, echo: bool = False):
    """
    Create SQLAlchemy engine and tables.

    Args:
        database_url: PostgreSQL connection URL
        echo: Whether to echo SQL statements

    Returns:
        Tuple of (engine, Session class)
    """
    engine = create_engine(database_url, echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
