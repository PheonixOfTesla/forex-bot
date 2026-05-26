"""
Intelligence Engine for Self-Improving Trading

This module provides the brain for continuous learning and adaptation,
analyzing every trade to improve future performance.
"""

from .models import (
    TradeRecord,
    FailurePattern,
    PerformanceSnapshot,
    LossAnalysis,
    WinAnalysis,
    DrawdownEvent,
    Adjustment,
    ImprovementReport,
)
from .tracker import TradeTracker
from .analyzer import TradeAnalyzer
from .optimizer import StrategyOptimizer
from .feedback_loop import FeedbackLoop

__all__ = [
    # Models
    "TradeRecord",
    "FailurePattern",
    "PerformanceSnapshot",
    "LossAnalysis",
    "WinAnalysis",
    "DrawdownEvent",
    "Adjustment",
    "ImprovementReport",
    # Core components
    "TradeTracker",
    "TradeAnalyzer",
    "StrategyOptimizer",
    "FeedbackLoop",
]
