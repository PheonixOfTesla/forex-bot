from __future__ import annotations

"""
Forex Bot - Automated Trading System

A comprehensive algorithmic trading system supporting forex (via OANDA)
and cryptocurrency (via Binance) markets with ML-powered strategies.

Features:
- Multiple broker integrations (OANDA, Binance)
- ML-powered trading strategies (XGBoost, optional TensorFlow)
- Risk management with Kelly Criterion
- Real-time alerts via Telegram
- FastAPI dashboard for monitoring
- PostgreSQL for trade history and analytics
"""

__version__ = "0.1.0"
__author__ = "ModernDavinci"
__email__ = "dev@moderndavinci.com"

# Lazy imports to avoid import errors when running src.api.main directly
def get_settings():
    from config.settings import get_settings as _get_settings
    return _get_settings()

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "get_settings",
]
