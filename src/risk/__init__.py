from __future__ import annotations

"""
Risk Management System
Provides comprehensive risk controls for forex trading.

Key Components:
- RiskManager: Core risk management orchestration
- KellyCalculator: Optimal position sizing using Kelly Criterion
- CircuitBreaker: Emergency trading controls
- Models: Data structures for risk configuration and assessment

Hardcoded Spec Values:
- MAX_RISK_PER_TRADE = 0.02 (2%)
- MAX_DAILY_LOSS = 0.06 (6%)
- MAX_LEVERAGE_USED = 10
- MIN_ML_CONFIDENCE = 0.70
- MIN_REWARD_RISK = 2.0
- MAX_OPEN_TRADES = 3
- SPREAD_MAX_PIPS = 2.0
- TRAILING_STOP = True
"""

from .circuit_breaker import CircuitBreaker
from .kelly import KellyCalculator
from .manager import RiskManager
from .models import (
    CircuitBreakerState,
    CircuitBreakerStatus,
    DailyStats,
    Position,
    RiskAssessment,
    RiskConfig,
    Signal,
    TradeDirection,
)

__all__ = [
    # Core components
    "RiskManager",
    "KellyCalculator",
    "CircuitBreaker",
    # Models
    "RiskConfig",
    "RiskAssessment",
    "Position",
    "Signal",
    "DailyStats",
    "CircuitBreakerStatus",
    "CircuitBreakerState",
    "TradeDirection",
]
