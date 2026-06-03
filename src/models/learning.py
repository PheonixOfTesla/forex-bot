from __future__ import annotations

"""
Learning Models for Lightning Trading Bot

Data models for tracking prediction outcomes, learning metrics,
and indicator performance weights.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class TradeOutcome(str, Enum):
    """Outcome of a completed trade."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class Direction(str, Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


# =============================================================================
# Core Learning Models
# =============================================================================


class PredictionOutcome(BaseModel):
    """
    Records the outcome of a trading prediction/signal.

    This is the fundamental unit of learning - each time a paper trade
    closes, we record whether our prediction was correct.
    """
    signal_id: str = Field(..., description="Original signal ID that generated this prediction")
    pair: str = Field(..., description="Trading pair (e.g., EUR/USD)")
    direction: Direction = Field(..., description="Predicted direction (buy/sell)")
    confidence: float = Field(..., ge=0, le=100, description="Original confidence score")
    entry_price: float = Field(..., description="Entry price of the trade")
    exit_price: float = Field(..., description="Exit price of the trade")
    outcome: TradeOutcome = Field(..., description="Trade outcome (win/loss/breakeven)")
    profit_pips: float = Field(..., description="Profit/loss in pips")
    profit_percent: float = Field(0.0, description="Profit/loss as percentage")

    # What indicators were used for this signal
    indicators_used: List[str] = Field(
        default_factory=list,
        description="List of indicators that contributed to the signal"
    )
    indicator_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Actual indicator values at signal time"
    )

    # Strategy and timeframe context
    strategy: Optional[str] = Field(None, description="Strategy that generated the signal")
    timeframe: str = Field("1H", description="Timeframe of the analysis")

    # Timestamps
    entry_timestamp: datetime = Field(..., description="When the trade was entered")
    exit_timestamp: datetime = Field(..., description="When the trade was closed")
    recorded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this outcome was recorded"
    )

    # Additional context
    market_conditions: Optional[str] = Field(
        None,
        description="Market conditions at time of trade (trending/ranging/volatile)"
    )
    session: Optional[str] = Field(
        None,
        description="Trading session (london/newyork/tokyo/sydney)"
    )


class IndicatorWeight(BaseModel):
    """
    Tracks the performance weight of an indicator.

    Weights are adjusted based on how well the indicator's signals
    correlate with successful trades.
    """
    indicator_name: str = Field(..., description="Name of the indicator")
    weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Performance weight (0.0-2.0, 1.0 = neutral)"
    )

    # Performance tracking
    total_signals: int = Field(0, description="Total signals where this indicator was used")
    winning_signals: int = Field(0, description="Signals that resulted in wins")
    losing_signals: int = Field(0, description="Signals that resulted in losses")
    win_rate: float = Field(0.0, ge=0, le=100, description="Win rate for this indicator")

    # Average contribution
    avg_confidence_when_used: float = Field(
        0.0,
        description="Average signal confidence when this indicator was prominent"
    )
    avg_profit_when_used: float = Field(
        0.0,
        description="Average profit/loss when this indicator was used"
    )

    # Timestamps
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IndicatorCombination(BaseModel):
    """
    Tracks performance of specific indicator combinations.

    Some indicator combinations work better together - this tracks
    which combinations produce the best results.
    """
    combination_id: str = Field(..., description="Unique ID for this combination")
    indicators: List[str] = Field(..., description="List of indicators in this combination")

    # Performance metrics
    total_trades: int = Field(0, description="Total trades using this combination")
    wins: int = Field(0, description="Number of winning trades")
    losses: int = Field(0, description="Number of losing trades")
    breakeven: int = Field(0, description="Number of breakeven trades")
    win_rate: float = Field(0.0, ge=0, le=100, description="Win rate percentage")

    # Profit metrics
    total_profit_pips: float = Field(0.0, description="Total profit in pips")
    avg_profit_pips: float = Field(0.0, description="Average profit per trade in pips")
    best_trade_pips: float = Field(0.0, description="Best single trade in pips")
    worst_trade_pips: float = Field(0.0, description="Worst single trade in pips")

    # Context
    best_pairs: List[str] = Field(
        default_factory=list,
        description="Pairs where this combination performs best"
    )
    best_timeframes: List[str] = Field(
        default_factory=list,
        description="Timeframes where this combination performs best"
    )

    last_updated: datetime = Field(default_factory=datetime.utcnow)


class PairPerformance(BaseModel):
    """Performance metrics for a specific trading pair."""
    pair: str = Field(..., description="Trading pair")
    total_trades: int = Field(0)
    wins: int = Field(0)
    losses: int = Field(0)
    breakeven: int = Field(0)
    win_rate: float = Field(0.0)
    total_profit_pips: float = Field(0.0)
    avg_profit_pips: float = Field(0.0)
    best_performing_indicators: List[str] = Field(default_factory=list)
    worst_performing_indicators: List[str] = Field(default_factory=list)
    last_trade: Optional[datetime] = None


class TimeframePerformance(BaseModel):
    """Performance metrics for a specific timeframe."""
    timeframe: str = Field(..., description="Timeframe (e.g., 1H, 4H, D)")
    total_trades: int = Field(0)
    wins: int = Field(0)
    losses: int = Field(0)
    win_rate: float = Field(0.0)
    avg_profit_pips: float = Field(0.0)
    best_pairs: List[str] = Field(default_factory=list)


class SetupPerformance(BaseModel):
    """Performance of a specific trading setup."""
    setup_id: str = Field(..., description="Unique identifier for this setup")
    description: str = Field(..., description="Human-readable description")
    indicators: List[str] = Field(..., description="Indicators involved")
    pair: Optional[str] = Field(None, description="Specific pair if applicable")
    timeframe: Optional[str] = Field(None, description="Specific timeframe if applicable")
    direction: Optional[Direction] = Field(None, description="Specific direction if applicable")

    # Performance
    total_trades: int = Field(0)
    win_rate: float = Field(0.0)
    avg_profit_pips: float = Field(0.0)
    profit_factor: Optional[float] = Field(None, description="Total wins / Total losses")

    # Scoring
    performance_score: float = Field(
        0.0,
        description="Composite performance score (0-100)"
    )

    last_used: Optional[datetime] = None


# =============================================================================
# Learning Metrics Aggregate
# =============================================================================


class LearningMetrics(BaseModel):
    """
    Aggregate learning metrics from all recorded outcomes.

    This provides a high-level view of what the system has learned
    about trading performance.
    """
    # Overall stats
    total_predictions: int = Field(0, description="Total predictions recorded")
    total_wins: int = Field(0, description="Total winning predictions")
    total_losses: int = Field(0, description="Total losing predictions")
    total_breakeven: int = Field(0, description="Total breakeven predictions")
    overall_win_rate: float = Field(0.0, description="Overall win rate percentage")
    overall_profit_pips: float = Field(0.0, description="Total profit in pips")

    # Accuracy breakdowns
    accuracy_by_pair: Dict[str, PairPerformance] = Field(
        default_factory=dict,
        description="Performance broken down by trading pair"
    )
    accuracy_by_timeframe: Dict[str, TimeframePerformance] = Field(
        default_factory=dict,
        description="Performance broken down by timeframe"
    )
    accuracy_by_indicator: Dict[str, IndicatorWeight] = Field(
        default_factory=dict,
        description="Performance broken down by indicator"
    )

    # Best/worst setups
    best_performing_setups: List[SetupPerformance] = Field(
        default_factory=list,
        description="Top performing trading setups"
    )
    worst_performing_setups: List[SetupPerformance] = Field(
        default_factory=list,
        description="Worst performing trading setups"
    )

    # Indicator combinations
    best_indicator_combinations: List[IndicatorCombination] = Field(
        default_factory=list,
        description="Best performing indicator combinations"
    )
    worst_indicator_combinations: List[IndicatorCombination] = Field(
        default_factory=list,
        description="Worst performing indicator combinations"
    )

    # Learning progress
    learning_started_at: Optional[datetime] = Field(
        None,
        description="When we started collecting learning data"
    )
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Confidence adjustments
    suggested_confidence_adjustments: Dict[str, float] = Field(
        default_factory=dict,
        description="Suggested confidence adjustments per indicator"
    )


# =============================================================================
# Insight Models
# =============================================================================


class LearningInsight(BaseModel):
    """
    AI-generated insight from learning data.
    """
    id: str = Field(..., description="Unique insight ID")
    title: str = Field(..., description="Insight title")
    content: str = Field(..., description="Detailed insight content")
    category: str = Field(
        ...,
        description="Category (performance/indicator/pair/strategy/risk)"
    )
    priority: str = Field("medium", description="Priority level (high/medium/low)")

    # Supporting data
    affected_pairs: List[str] = Field(default_factory=list)
    affected_indicators: List[str] = Field(default_factory=list)

    # Actionable recommendation
    recommendation: Optional[str] = Field(
        None,
        description="Actionable recommendation based on insight"
    )
    confidence_impact: Optional[float] = Field(
        None,
        description="Suggested impact on future confidence scores"
    )

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = Field(
        None,
        description="When this insight should be re-evaluated"
    )


# =============================================================================
# Request/Response Models for API
# =============================================================================


class RecordOutcomeRequest(BaseModel):
    """Request to record a trade outcome."""
    signal_id: str = Field(..., description="The signal ID that generated the trade")
    pair: str = Field(..., description="Trading pair")
    direction: Direction = Field(..., description="Trade direction")
    confidence: float = Field(..., ge=0, le=100, description="Original confidence")
    entry_price: float = Field(..., description="Entry price")
    exit_price: float = Field(..., description="Exit price")
    entry_timestamp: datetime = Field(..., description="Entry time")
    exit_timestamp: datetime = Field(..., description="Exit time")

    # Optional context
    indicators_used: List[str] = Field(default_factory=list)
    indicator_values: Dict[str, float] = Field(default_factory=dict)
    strategy: Optional[str] = None
    timeframe: str = "1H"
    market_conditions: Optional[str] = None
    session: Optional[str] = None


class AccuracyResponse(BaseModel):
    """Response for accuracy stats endpoint."""
    overall_accuracy: float = Field(..., description="Overall prediction accuracy %")
    total_predictions: int = Field(..., description="Total predictions tracked")

    # Breakdown
    by_pair: Dict[str, dict] = Field(default_factory=dict)
    by_timeframe: Dict[str, dict] = Field(default_factory=dict)
    by_direction: Dict[str, dict] = Field(default_factory=dict)

    # Trends
    accuracy_trend_7d: Optional[float] = Field(
        None,
        description="Accuracy change over last 7 days"
    )
    accuracy_trend_30d: Optional[float] = Field(
        None,
        description="Accuracy change over last 30 days"
    )

    last_updated: datetime = Field(default_factory=datetime.utcnow)


class IndicatorPerformanceResponse(BaseModel):
    """Response for indicator performance endpoint."""
    indicators: List[IndicatorWeight] = Field(default_factory=list)
    best_combinations: List[IndicatorCombination] = Field(default_factory=list)
    worst_combinations: List[IndicatorCombination] = Field(default_factory=list)

    # Recommendations
    recommended_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Recommended indicator weights based on performance"
    )

    last_updated: datetime = Field(default_factory=datetime.utcnow)


class InsightsResponse(BaseModel):
    """Response for AI insights endpoint."""
    insights: List[LearningInsight] = Field(default_factory=list)
    total_insights: int = Field(0)

    # Summary stats used for insights
    data_points: int = Field(0, description="Number of outcomes analyzed")
    analysis_period_days: int = Field(30)

    generated_at: datetime = Field(default_factory=datetime.utcnow)
