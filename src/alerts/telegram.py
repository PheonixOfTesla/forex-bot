from __future__ import annotations

"""
Telegram Bot for Trading Alerts

Provides asynchronous Telegram notifications for:
- Trade executions and closures
- Daily/weekly summaries
- Signal alerts
- Risk warnings
- Engine status updates
- Emergency stops
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from .formatter import (
    MessageFormatter,
    DailySummary,
    Signal,
    EngineStatus,
)

if TYPE_CHECKING:
    from src.ml.models import Trade

logger = logging.getLogger(__name__)


class TelegramAlerts:
    """
    Telegram Bot client for sending trading alerts.

    Handles all Telegram communications with proper error handling,
    rate limiting awareness, and message formatting.

    Example usage:
        alerts = TelegramAlerts(bot_token="...", chat_id="...")
        await alerts.send_trade_executed(trade, balance=127.42, total_return=27.4)
    """

    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize the Telegram alerts client.

        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat ID for alerts
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot: Optional[Bot] = None
        self._initialized = False

    @property
    def bot(self) -> Bot:
        """Get or create the Telegram bot instance."""
        if self._bot is None:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def _send_message(
        self,
        text: str,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False
    ) -> bool:
        """
        Send a message to the configured chat.

        Args:
            text: Message text to send
            parse_mode: Optional parse mode (HTML, Markdown, etc.)
            disable_notification: Whether to send silently

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
            logger.debug(f"Telegram message sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error sending Telegram message: {e}")
            return False

    async def send_trade_executed(
        self,
        trade: "Trade",
        balance: float,
        total_return: float,
        risk_amount: Optional[float] = None,
        risk_percent: Optional[float] = None
    ) -> bool:
        """
        Send a trade executed notification.

        Args:
            trade: The executed trade
            balance: Current account balance
            total_return: Total return percentage
            risk_amount: Dollar amount at risk
            risk_percent: Risk as percentage of balance

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_trade_alert(
            trade=trade,
            balance=balance,
            total_return=total_return,
            risk_amount=risk_amount,
            risk_percent=risk_percent
        )
        return await self._send_message(message)

    async def send_trade_closed(
        self,
        trade: "Trade",
        pnl: float,
        balance: float,
        total_return: Optional[float] = None
    ) -> bool:
        """
        Send a trade closed notification.

        Args:
            trade: The closed trade
            pnl: Profit/loss from this trade
            balance: Current account balance
            total_return: Total return percentage (optional, calculated if not provided)

        Returns:
            True if sent successfully
        """
        # Calculate total return if not provided
        if total_return is None:
            initial_balance = balance - pnl
            total_return = ((balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

        message = MessageFormatter.format_trade_closed(
            trade=trade,
            pnl=pnl,
            balance=balance,
            total_return=total_return
        )
        return await self._send_message(message)

    async def send_daily_summary(self, summary: DailySummary) -> bool:
        """
        Send a daily trading summary.

        Args:
            summary: The daily summary data

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_daily_summary(
            date=summary.date,
            trades=summary.trades,
            wins=summary.wins,
            pnl=summary.pnl,
            balance=summary.balance,
            win_rate=summary.win_rate,
            best_trade=summary.best_trade,
            worst_trade=summary.worst_trade
        )
        return await self._send_message(message)

    async def send_signal_alert(self, signal: Signal) -> bool:
        """
        Send a trading signal alert.

        Args:
            signal: The trading signal

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_signal_alert(signal)
        return await self._send_message(message)

    async def send_risk_warning(
        self,
        warning: str,
        details: Optional[str] = None
    ) -> bool:
        """
        Send a risk warning notification.

        Args:
            warning: The warning message
            details: Optional additional details

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_risk_warning(warning, details)
        return await self._send_message(message)

    async def send_engine_status(self, status: EngineStatus) -> bool:
        """
        Send an engine status update.

        Args:
            status: The engine status

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_engine_status(status)
        return await self._send_message(message)

    async def send_emergency_stop(self, reason: str) -> bool:
        """
        Send an emergency stop notification.

        This is a critical alert that requires immediate attention.

        Args:
            reason: The reason for the emergency stop

        Returns:
            True if sent successfully
        """
        message = MessageFormatter.format_emergency_stop(reason)
        # Emergency stops should never be silent
        return await self._send_message(message, disable_notification=False)

    async def send_custom_message(
        self,
        message: str,
        silent: bool = False
    ) -> bool:
        """
        Send a custom message.

        Args:
            message: The message text
            silent: Whether to send without notification

        Returns:
            True if sent successfully
        """
        return await self._send_message(message, disable_notification=silent)

    async def test_connection(self) -> bool:
        """
        Test the Telegram bot connection.

        Returns:
            True if connection is working
        """
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"Telegram bot connected: @{bot_info.username}")
            return True
        except TelegramError as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

    def format_trade_message(self, trade: "Trade") -> str:
        """
        Format a trade for display (helper method).

        Args:
            trade: The trade to format

        Returns:
            Formatted trade string
        """
        direction = "LONG" if trade.direction == "BUY" else "SHORT"
        return (
            f"{trade.symbol} {direction} @ "
            f"{MessageFormatter.format_price(trade.entry_price)}"
        )

    def format_summary_message(self, summary: DailySummary) -> str:
        """
        Format a daily summary for display (helper method).

        Args:
            summary: The summary to format

        Returns:
            Formatted summary string
        """
        return MessageFormatter.format_daily_summary(
            date=summary.date,
            trades=summary.trades,
            wins=summary.wins,
            pnl=summary.pnl,
            balance=summary.balance,
            win_rate=summary.win_rate,
            best_trade=summary.best_trade,
            worst_trade=summary.worst_trade
        )

    async def close(self) -> None:
        """Close the bot connection and cleanup resources."""
        if self._bot is not None:
            # python-telegram-bot v20+ uses application context
            # Bot itself doesn't need explicit closing, but we reset the reference
            self._bot = None
            self._initialized = False
            logger.debug("Telegram bot connection closed")
