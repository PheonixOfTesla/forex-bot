"""
Message Formatter for Telegram Alerts

Provides static methods for formatting currency, percentages,
and structured alert messages for trading notifications.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ml.models import Trade


@dataclass
class DailySummary:
    """Daily trading summary data."""
    date: date
    trades: int
    wins: int
    losses: int
    pnl: float
    balance: float
    win_rate: float
    best_trade: float
    worst_trade: float


@dataclass
class Signal:
    """Trading signal data."""
    symbol: str
    direction: str  # "LONG" or "SHORT"
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime


@dataclass
class EngineStatus:
    """Trading engine status."""
    is_running: bool
    uptime_hours: float
    active_positions: int
    daily_trades: int
    balance: float
    daily_pnl: float
    last_trade_time: Optional[datetime] = None


class MessageFormatter:
    """
    Static methods for formatting trading alert messages.

    Formats currency, percentages, and structured messages
    following the Lightning Bot UI specification.
    """

    # Unicode symbols for visual formatting
    LIGHTNING = "\u26a1"
    CHART_UP = "\U0001F4C8"
    CHART_DOWN = "\U0001F4C9"
    MONEY_BAG = "\U0001F4B0"
    WARNING = "\u26a0\ufe0f"
    STOP = "\U0001F6D1"
    CHECK = "\u2705"
    CROSS = "\u274c"
    CLOCK = "\U0001F551"
    FIRE = "\U0001F525"
    TROPHY = "\U0001F3C6"
    ROBOT = "\U0001F916"

    @staticmethod
    def format_currency(value: float, symbol: str = '$') -> str:
        """
        Format a value as currency.

        Args:
            value: The monetary value to format
            symbol: Currency symbol (default: '$')

        Returns:
            Formatted currency string (e.g., '$1,234.56')
        """
        if abs(value) >= 1000:
            return f"{symbol}{value:,.2f}"
        return f"{symbol}{value:.2f}"

    @staticmethod
    def format_percent(value: float, include_sign: bool = True) -> str:
        """
        Format a value as percentage.

        Args:
            value: The percentage value (e.g., 27.4 for 27.4%)
            include_sign: Whether to include +/- sign

        Returns:
            Formatted percentage string (e.g., '+27.4%')
        """
        if include_sign:
            sign = '+' if value >= 0 else ''
            return f"{sign}{value:.1f}%"
        return f"{value:.1f}%"

    @staticmethod
    def format_price(value: float) -> str:
        """
        Format a price value with appropriate precision.

        Args:
            value: The price value

        Returns:
            Formatted price string
        """
        # Crypto prices (typically > $100) get 2 decimals
        # Forex pips need more precision
        if value >= 100:
            return f"${value:,.2f}"
        elif value >= 1:
            return f"${value:.4f}"
        else:
            return f"${value:.5f}"

    @staticmethod
    def format_trade_alert(
        trade: "Trade",
        balance: float,
        total_return: float,
        risk_amount: Optional[float] = None,
        risk_percent: Optional[float] = None
    ) -> str:
        """
        Format a trade execution alert message.

        Args:
            trade: The executed trade
            balance: Current account balance
            total_return: Total return percentage
            risk_amount: Dollar amount at risk (optional)
            risk_percent: Risk as percentage of balance (optional)

        Returns:
            Formatted trade alert message
        """
        direction = "LONG" if trade.direction == "BUY" else "SHORT"
        direction_emoji = MessageFormatter.CHART_UP if direction == "LONG" else MessageFormatter.CHART_DOWN

        # Calculate risk if not provided
        if risk_amount is None and trade.stop_loss is not None:
            risk_pips = abs(trade.entry_price - trade.stop_loss)
            risk_amount = risk_pips * trade.lot_size * 10  # Rough estimate

        if risk_percent is None and risk_amount is not None:
            risk_percent = (risk_amount / balance) * 100 if balance > 0 else 0

        # Build the message
        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{direction_emoji} TRADE EXECUTED",
            f"Asset:      {trade.symbol}",
            f"Direction:  {direction}",
            f"Entry:      {MessageFormatter.format_price(trade.entry_price)}",
        ]

        if trade.stop_loss is not None:
            lines.append(f"Stop:       {MessageFormatter.format_price(trade.stop_loss)}")

        if trade.take_profit is not None:
            lines.append(f"Target:     {MessageFormatter.format_price(trade.take_profit)}")

        lines.append(f"Confidence: {int(trade.confidence * 100)}%")

        if risk_amount is not None and risk_percent is not None:
            lines.append(f"Risk:       {MessageFormatter.format_currency(risk_amount)} ({risk_percent:.0f}%)")

        lines.extend([
            "",
            f"Balance: {MessageFormatter.format_currency(balance)} ({MessageFormatter.format_percent(total_return)})"
        ])

        return "\n".join(lines)

    @staticmethod
    def format_trade_closed(
        trade: "Trade",
        pnl: float,
        balance: float,
        total_return: float
    ) -> str:
        """
        Format a trade closed alert message.

        Args:
            trade: The closed trade
            pnl: Profit/loss from this trade
            balance: Current account balance
            total_return: Total return percentage

        Returns:
            Formatted trade closed message
        """
        is_winner = pnl > 0
        result_emoji = MessageFormatter.CHECK if is_winner else MessageFormatter.CROSS
        result_text = "WIN" if is_winner else "LOSS"

        direction = "LONG" if trade.direction == "BUY" else "SHORT"

        # Exit reason formatting
        exit_reasons = {
            'tp_hit': 'Take Profit Hit',
            'sl_hit': 'Stop Loss Hit',
            'signal_exit': 'Signal Exit',
            'timeout': 'Time Limit',
            'manual': 'Manual Close'
        }
        exit_reason = exit_reasons.get(trade.exit_reason, trade.exit_reason or 'Unknown')

        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{result_emoji} TRADE CLOSED - {result_text}",
            f"Asset:      {trade.symbol}",
            f"Direction:  {direction}",
            f"Entry:      {MessageFormatter.format_price(trade.entry_price)}",
            f"Exit:       {MessageFormatter.format_price(trade.exit_price)}",
            f"Reason:     {exit_reason}",
            "",
            f"P/L:        {MessageFormatter.format_currency(pnl)} ({MessageFormatter.format_percent(pnl / (balance - pnl) * 100 if balance != pnl else 0)})",
        ]

        if trade.duration_minutes is not None:
            hours = int(trade.duration_minutes // 60)
            mins = int(trade.duration_minutes % 60)
            if hours > 0:
                lines.append(f"Duration:   {hours}h {mins}m")
            else:
                lines.append(f"Duration:   {mins}m")

        lines.extend([
            "",
            f"Balance: {MessageFormatter.format_currency(balance)} ({MessageFormatter.format_percent(total_return)})"
        ])

        return "\n".join(lines)

    @staticmethod
    def format_daily_summary(
        date: date,
        trades: int,
        wins: int,
        pnl: float,
        balance: float,
        win_rate: float,
        best_trade: Optional[float] = None,
        worst_trade: Optional[float] = None
    ) -> str:
        """
        Format a daily trading summary message.

        Args:
            date: The summary date
            trades: Total number of trades
            wins: Number of winning trades
            pnl: Total P/L for the day
            balance: End of day balance
            win_rate: Win rate as percentage (0-100)
            best_trade: Best trade P/L (optional)
            worst_trade: Worst trade P/L (optional)

        Returns:
            Formatted daily summary message
        """
        losses = trades - wins
        pnl_emoji = MessageFormatter.CHART_UP if pnl >= 0 else MessageFormatter.CHART_DOWN

        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{MessageFormatter.TROPHY} DAILY SUMMARY",
            f"Date:       {date.strftime('%Y-%m-%d')}",
            "",
            f"Trades:     {trades}",
            f"Wins:       {wins} {MessageFormatter.CHECK}",
            f"Losses:     {losses} {MessageFormatter.CROSS}",
            f"Win Rate:   {win_rate:.1f}%",
            "",
            f"{pnl_emoji} P/L:       {MessageFormatter.format_currency(pnl)} ({MessageFormatter.format_percent(pnl / (balance - pnl) * 100 if balance != pnl else 0)})",
        ]

        if best_trade is not None:
            lines.append(f"Best:       {MessageFormatter.format_currency(best_trade)}")

        if worst_trade is not None:
            lines.append(f"Worst:      {MessageFormatter.format_currency(worst_trade)}")

        lines.extend([
            "",
            f"{MessageFormatter.MONEY_BAG} Balance:   {MessageFormatter.format_currency(balance)}"
        ])

        return "\n".join(lines)

    @staticmethod
    def format_signal_alert(signal: Signal) -> str:
        """
        Format a trading signal alert.

        Args:
            signal: The trading signal

        Returns:
            Formatted signal alert message
        """
        direction_emoji = MessageFormatter.CHART_UP if signal.direction == "LONG" else MessageFormatter.CHART_DOWN

        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{direction_emoji} NEW SIGNAL",
            f"Asset:      {signal.symbol}",
            f"Direction:  {signal.direction}",
            f"Entry:      {MessageFormatter.format_price(signal.entry_price)}",
            f"Stop:       {MessageFormatter.format_price(signal.stop_loss)}",
            f"Target:     {MessageFormatter.format_price(signal.take_profit)}",
            f"Confidence: {int(signal.confidence * 100)}%",
            "",
            f"{MessageFormatter.CLOCK} {signal.timestamp.strftime('%H:%M:%S UTC')}"
        ]

        return "\n".join(lines)

    @staticmethod
    def format_risk_warning(warning: str, details: Optional[str] = None) -> str:
        """
        Format a risk warning message.

        Args:
            warning: The warning message
            details: Optional additional details

        Returns:
            Formatted risk warning message
        """
        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{MessageFormatter.WARNING} RISK WARNING",
            "",
            warning
        ]

        if details:
            lines.extend(["", details])

        return "\n".join(lines)

    @staticmethod
    def format_engine_status(status: EngineStatus) -> str:
        """
        Format an engine status message.

        Args:
            status: The engine status

        Returns:
            Formatted engine status message
        """
        status_emoji = MessageFormatter.CHECK if status.is_running else MessageFormatter.STOP
        status_text = "RUNNING" if status.is_running else "STOPPED"

        pnl_emoji = MessageFormatter.CHART_UP if status.daily_pnl >= 0 else MessageFormatter.CHART_DOWN

        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{MessageFormatter.ROBOT} ENGINE STATUS",
            f"Status:     {status_emoji} {status_text}",
            f"Uptime:     {status.uptime_hours:.1f}h",
            f"Positions:  {status.active_positions}",
            f"Trades:     {status.daily_trades} today",
            "",
            f"{pnl_emoji} Daily P/L: {MessageFormatter.format_currency(status.daily_pnl)}",
            f"{MessageFormatter.MONEY_BAG} Balance:   {MessageFormatter.format_currency(status.balance)}"
        ]

        if status.last_trade_time:
            lines.append(f"{MessageFormatter.CLOCK} Last trade: {status.last_trade_time.strftime('%H:%M:%S')}")

        return "\n".join(lines)

    @staticmethod
    def format_emergency_stop(reason: str) -> str:
        """
        Format an emergency stop message.

        Args:
            reason: The reason for the emergency stop

        Returns:
            Formatted emergency stop message
        """
        lines = [
            f"{MessageFormatter.LIGHTNING} LIGHTNING BOT",
            "",
            f"{MessageFormatter.STOP} EMERGENCY STOP",
            "",
            f"{MessageFormatter.FIRE} All trading has been halted!",
            "",
            f"Reason: {reason}",
            "",
            "Manual intervention required."
        ]

        return "\n".join(lines)
