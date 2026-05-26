"""
Feature Engineering

This module handles technical indicator calculations and feature
engineering for ML models:

Technical Indicators:
- Moving Averages (SMA, EMA, WMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- Stochastic Oscillator
- ADX (Average Directional Index)
- Volume indicators

Feature Engineering:
- Price action features (candlestick patterns)
- Volatility features
- Trend features
- Market microstructure features
- Lagged features
- Rolling statistics
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .indicators import TechnicalIndicators
    from .feature_engineer import FeatureEngineer

__all__ = [
    "TechnicalIndicators",
    "FeatureEngineer",
]
