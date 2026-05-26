"""
Configuration Module

Provides centralized configuration management for the forex bot.

Usage:
    from config import settings

    # Access OANDA settings
    account_id = settings.oanda.account_id

    # Access risk parameters
    max_risk = settings.risk.risk_per_trade_pct

    # Check if Telegram is configured
    if settings.telegram.is_configured:
        send_alert(...)
"""

from .settings import Settings, get_settings, settings

__all__ = [
    "Settings",
    "get_settings",
    "settings",
]
