from __future__ import annotations

"""
Trading Strategies Module

Provides a collection of trading strategies and a manager to coordinate them.

Forex Strategies:
- LondonBreakoutStrategy: Captures volatility at London session open
- RSIMeanReversionStrategy: Mean reversion for ranging pairs (EUR/CHF, EUR/GBP)

Crypto Strategies:
- BTCMomentumStrategy: Trend-following momentum strategy for Bitcoin
- XRPSpikeFadeStrategy: Fades extreme volatility spikes in XRP
- XRPRangeStrategy: Range mean reversion for XRP

Each strategy implements the BaseStrategy interface with:
- generate_signal(): Produce buy/sell signals
- calculate_entry_exit(): Calculate entry, stop-loss and take-profit
- validate_setup(): Validate trade setup meets criteria
"""

from .base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    SignalStrength,
    TradeSetup,
    StrategyStats,
)

from .london_breakout import LondonBreakoutStrategy
from .rsi_mean_reversion import RSIMeanReversionStrategy
from .btc_momentum import BTCMomentumStrategy
from .xrp_spike_fade import XRPSpikeFadeStrategy
from .xrp_range import XRPRangeStrategy
from .manager import StrategyManager, StrategyPerformance


__all__ = [
    # Base classes
    'BaseStrategy',
    'Signal',
    'SignalDirection',
    'SignalStrength',
    'TradeSetup',
    'StrategyStats',

    # Strategies
    'LondonBreakoutStrategy',
    'RSIMeanReversionStrategy',
    'BTCMomentumStrategy',
    'XRPSpikeFadeStrategy',
    'XRPRangeStrategy',

    # Manager
    'StrategyManager',
    'StrategyPerformance',
]


def create_default_manager() -> StrategyManager:
    """
    Create a strategy manager with all default strategies registered.

    Returns:
        StrategyManager with all strategies registered and enabled
    """
    manager = StrategyManager()

    # Register all strategies
    manager.register_strategy(LondonBreakoutStrategy())
    manager.register_strategy(RSIMeanReversionStrategy())
    manager.register_strategy(BTCMomentumStrategy())
    manager.register_strategy(XRPSpikeFadeStrategy())
    manager.register_strategy(XRPRangeStrategy())

    return manager
