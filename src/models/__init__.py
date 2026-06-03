from __future__ import annotations

"""
Models Package

Contains Pydantic models for data structures.
"""

from .paper_trade import (
    PaperTrade,
    PaperPosition,
    TradingMetrics,
    PaperTradeStatus,
    TradeDirection,
    PaperAccountState,
    ExecuteTradeRequest,
    CloseTradeRequest,
    PaperBalanceResponse,
    PaperPositionsResponse,
    PaperHistoryResponse,
    ExecuteTradeResponse,
    ResetAccountResponse,
)

from .learning import (
    AccuracyResponse,
    Direction,
    IndicatorCombination,
    IndicatorPerformanceResponse,
    IndicatorWeight,
    InsightsResponse,
    LearningInsight,
    LearningMetrics,
    PairPerformance,
    PredictionOutcome,
    RecordOutcomeRequest,
    SetupPerformance,
    TimeframePerformance,
    TradeOutcome,
)

__all__ = [
    # Paper Trading Models
    "PaperTrade",
    "PaperPosition",
    "TradingMetrics",
    "PaperTradeStatus",
    "TradeDirection",
    "PaperAccountState",
    "ExecuteTradeRequest",
    "CloseTradeRequest",
    "PaperBalanceResponse",
    "PaperPositionsResponse",
    "PaperHistoryResponse",
    "ExecuteTradeResponse",
    "ResetAccountResponse",
    # Learning Models
    "AccuracyResponse",
    "Direction",
    "IndicatorCombination",
    "IndicatorPerformanceResponse",
    "IndicatorWeight",
    "InsightsResponse",
    "LearningInsight",
    "LearningMetrics",
    "PairPerformance",
    "PredictionOutcome",
    "RecordOutcomeRequest",
    "SetupPerformance",
    "TimeframePerformance",
    "TradeOutcome",
]
