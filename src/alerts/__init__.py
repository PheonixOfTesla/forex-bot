"""
Alerts Module

This module handles notification and alerting:

Telegram Integration:
- Trade entry/exit alerts
- Daily performance summaries
- Risk warning notifications
- System status updates
- Error alerts

Alert Types:
- TRADE_ENTRY: New position opened
- TRADE_EXIT: Position closed
- STOP_LOSS_HIT: Stop loss triggered
- TAKE_PROFIT_HIT: Take profit reached
- RISK_WARNING: Risk limit approaching
- SYSTEM_ERROR: Critical system error
- DAILY_SUMMARY: End of day report

Usage:
    from src.alerts import TelegramAlerts, AlertScheduler, MessageFormatter

    # Initialize
    alerts = TelegramAlerts(bot_token="...", chat_id="...")

    # Send alerts
    await alerts.send_trade_executed(trade, balance=127.42, total_return=27.4)
    await alerts.send_daily_summary(summary)

    # Schedule automated alerts
    scheduler = AlertScheduler(alerts)
    await scheduler.schedule_daily_summary("23:59")
    await scheduler.start()
"""

from .telegram import TelegramAlerts
from .formatter import (
    MessageFormatter,
    DailySummary,
    Signal,
    EngineStatus,
)
from .scheduler import AlertScheduler, DayOfWeek

__all__ = [
    # Main classes
    "TelegramAlerts",
    "AlertScheduler",
    "MessageFormatter",
    # Data classes
    "DailySummary",
    "Signal",
    "EngineStatus",
    # Enums
    "DayOfWeek",
]
