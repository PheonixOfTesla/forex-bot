from __future__ import annotations

"""
Strategy Backtester

Comprehensive backtesting engine for trading strategies with ML integration.
Supports performance metrics, equity curves, and strategy comparison.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

from .models import (
    Prediction,
    Trade,
    BacktestResults,
    BacktestMetrics,
    ComparisonReport,
)
from .classifier import TradingClassifier

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def generate_signal(
        self,
        data: DataFrame,
        current_idx: int,
    ) -> Optional[Prediction]:
        """
        Generate trading signal for current bar.

        Args:
            data: Full DataFrame with features
            current_idx: Index of current bar

        Returns:
            Prediction or None if no signal
        """
        pass

    @abstractmethod
    def get_stop_loss(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate stop loss price."""
        pass

    @abstractmethod
    def get_take_profit(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate take profit price."""
        pass


class MLStrategy(BaseStrategy):
    """
    ML-based trading strategy using TradingClassifier.

    Uses the trained classifier to generate signals and applies
    ATR-based stop loss and take profit levels.
    """

    def __init__(
        self,
        classifier: TradingClassifier,
        confidence_threshold: float = 0.70,
        sl_atr_multiplier: float = 1.5,
        tp_atr_multiplier: float = 2.0,
    ):
        """
        Initialize MLStrategy.

        Args:
            classifier: Trained TradingClassifier
            confidence_threshold: Minimum confidence for trades
            sl_atr_multiplier: ATR multiplier for stop loss
            tp_atr_multiplier: ATR multiplier for take profit
        """
        self.classifier = classifier
        self.confidence_threshold = confidence_threshold
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier

    def generate_signal(
        self,
        data: DataFrame,
        current_idx: int,
    ) -> Optional[Prediction]:
        """Generate signal using ML classifier."""
        if current_idx < 0 or current_idx >= len(data):
            return None

        # Get features for current bar
        row = data.iloc[current_idx]
        features = {col: float(row[col]) for col in self.classifier.feature_columns if col in data.columns}

        # Get prediction
        prediction = self.classifier.predict_single(features)

        # Filter by confidence
        if prediction.confidence < self.confidence_threshold:
            return None

        if prediction.signal == "SKIP":
            return None

        return prediction

    def get_stop_loss(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate ATR-based stop loss."""
        sl_distance = atr * self.sl_atr_multiplier
        if direction == "BUY":
            return entry_price - sl_distance
        else:
            return entry_price + sl_distance

    def get_take_profit(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate ATR-based take profit."""
        tp_distance = atr * self.tp_atr_multiplier
        if direction == "BUY":
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance


class Backtester:
    """
    Comprehensive backtesting engine for trading strategies.

    Features:
    - Event-driven backtesting
    - Multiple position management
    - Commission and slippage modeling
    - Detailed performance metrics
    - Equity curve generation
    - Strategy comparison
    """

    def __init__(
        self,
        initial_capital: float = 25.0,
        leverage: float = 10.0,
        commission_per_lot: float = 0.0,
        slippage_pips: float = 0.5,
        max_positions: int = 1,
        pip_value: float = 0.0001,  # For major pairs
    ):
        """
        Initialize Backtester.

        Args:
            initial_capital: Starting capital in account currency
            leverage: Account leverage
            commission_per_lot: Commission per lot traded
            slippage_pips: Estimated slippage in pips
            max_positions: Maximum concurrent positions
            pip_value: Pip value (0.0001 for most pairs, 0.01 for JPY)
        """
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.commission_per_lot = commission_per_lot
        self.slippage_pips = slippage_pips
        self.max_positions = max_positions
        self.pip_value = pip_value

    def run_backtest(
        self,
        strategy: BaseStrategy,
        data: DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        lot_size: float = 0.01,
    ) -> BacktestResults:
        """
        Run backtest for a strategy.

        Args:
            strategy: Trading strategy to backtest
            data: DataFrame with OHLCV data and features
            start_date: Backtest start date
            end_date: Backtest end date
            lot_size: Position size in lots

        Returns:
            BacktestResults with performance metrics
        """
        logger.info("Starting backtest")

        # Filter data by date range
        data = self._filter_data_by_date(data, start_date, end_date)

        if len(data) == 0:
            logger.warning("No data in date range")
            return self._empty_results()

        # Initialize state
        capital = self.initial_capital
        equity_curve = [capital]
        timestamps = [data.index[0] if isinstance(data.index, pd.DatetimeIndex)
                      else data.iloc[0].get("datetime", datetime.now())]
        trades: List[Trade] = []
        open_positions: List[Trade] = []

        # Iterate through data
        for i in range(1, len(data)):
            current_bar = data.iloc[i]
            prev_bar = data.iloc[i - 1]

            # Get current timestamp
            if isinstance(data.index, pd.DatetimeIndex):
                current_time = data.index[i]
            else:
                current_time = current_bar.get("datetime", datetime.now())

            # Update open positions
            positions_to_close = []
            for pos in open_positions:
                close_signal, exit_price, exit_reason = self._check_exit(
                    pos, current_bar
                )
                if close_signal:
                    # Close position
                    pos.exit_time = current_time
                    pos.exit_price = exit_price
                    pos.exit_reason = exit_reason
                    pos.pnl = self._calculate_pnl(pos, lot_size)
                    pos.pnl_pips = self._calculate_pnl_pips(pos)
                    capital += pos.pnl
                    trades.append(pos)
                    positions_to_close.append(pos)

            # Remove closed positions
            for pos in positions_to_close:
                open_positions.remove(pos)

            # Generate new signals if we can open more positions
            if len(open_positions) < self.max_positions:
                prediction = strategy.generate_signal(data, i)

                if prediction and prediction.signal in ["BUY", "SELL"]:
                    # Get entry price with slippage
                    entry_price = current_bar["close"]
                    if prediction.signal == "BUY":
                        entry_price += self.slippage_pips * self.pip_value
                    else:
                        entry_price -= self.slippage_pips * self.pip_value

                    # Get ATR for SL/TP
                    atr = current_bar.get("atr_14", entry_price * 0.001)

                    # Create new position
                    trade = Trade(
                        entry_time=current_time,
                        exit_time=None,
                        symbol=current_bar.get("symbol", "UNKNOWN"),
                        direction=prediction.signal,
                        entry_price=entry_price,
                        lot_size=lot_size,
                        confidence=prediction.confidence,
                        features_at_entry=prediction.features_used,
                        stop_loss=strategy.get_stop_loss(entry_price, prediction.signal, atr),
                        take_profit=strategy.get_take_profit(entry_price, prediction.signal, atr),
                    )
                    open_positions.append(trade)

            # Update equity curve
            unrealized_pnl = sum(
                self._calculate_unrealized_pnl(pos, current_bar["close"], lot_size)
                for pos in open_positions
            )
            equity_curve.append(capital + unrealized_pnl)
            timestamps.append(current_time)

        # Close any remaining open positions at end
        if open_positions:
            final_bar = data.iloc[-1]
            final_time = (data.index[-1] if isinstance(data.index, pd.DatetimeIndex)
                          else final_bar.get("datetime", datetime.now()))
            for pos in open_positions:
                pos.exit_time = final_time
                pos.exit_price = final_bar["close"]
                pos.exit_reason = "backtest_end"
                pos.pnl = self._calculate_pnl(pos, lot_size)
                pos.pnl_pips = self._calculate_pnl_pips(pos)
                capital += pos.pnl
                trades.append(pos)

        # Calculate metrics
        metrics = self.calculate_metrics(trades)

        # Determine dates
        actual_start = (timestamps[0] if timestamps else start_date)
        actual_end = (timestamps[-1] if timestamps else end_date)

        results = BacktestResults(
            total_trades=len(trades),
            win_rate=metrics.win_rate,
            total_pnl=metrics.total_pnl,
            max_drawdown=metrics.max_drawdown,
            sharpe_ratio=metrics.sharpe_ratio,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            start_date=actual_start if isinstance(actual_start, datetime) else None,
            end_date=actual_end if isinstance(actual_end, datetime) else None,
            initial_capital=self.initial_capital,
            final_capital=capital,
            timestamps=timestamps,
        )

        logger.info(
            f"Backtest complete: {len(trades)} trades, "
            f"win_rate={metrics.win_rate:.2%}, "
            f"total_pnl=${metrics.total_pnl:.2f}"
        )

        return results

    def calculate_metrics(self, trades: List[Trade]) -> BacktestMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            trades: List of completed trades

        Returns:
            BacktestMetrics with all performance statistics
        """
        if not trades:
            return BacktestMetrics()

        # Basic counts
        pnls = [t.pnl for t in trades]
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]

        total_trades = len(trades)
        winning_trades = len(winners)
        losing_trades = len(losers)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # PnL metrics
        total_pnl = sum(pnls)
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = sum(t.pnl for t in losers) if losers else 0
        profit_factor = (abs(gross_profit / gross_loss)
                         if gross_loss != 0 else float('inf') if gross_profit > 0 else 0)

        # Average metrics
        avg_trade_pnl = np.mean(pnls) if pnls else 0
        avg_winner = np.mean([t.pnl for t in winners]) if winners else 0
        avg_loser = np.mean([t.pnl for t in losers]) if losers else 0
        largest_winner = max([t.pnl for t in winners]) if winners else 0
        largest_loser = min([t.pnl for t in losers]) if losers else 0

        # Duration metrics
        durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
        avg_duration = np.mean(durations) if durations else 0

        # Drawdown calculation
        cumulative_pnl = np.cumsum([self.initial_capital] + pnls)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdowns = (running_max - cumulative_pnl) / running_max
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

        # Drawdown duration
        in_drawdown = drawdowns > 0
        drawdown_periods = []
        current_dd_start = None
        for i, is_dd in enumerate(in_drawdown):
            if is_dd and current_dd_start is None:
                current_dd_start = i
            elif not is_dd and current_dd_start is not None:
                drawdown_periods.append(i - current_dd_start)
                current_dd_start = None
        if current_dd_start is not None:
            drawdown_periods.append(len(in_drawdown) - current_dd_start)
        max_dd_duration_bars = max(drawdown_periods) if drawdown_periods else 0

        # Sharpe ratio (assuming daily returns and risk-free rate of 0)
        if len(pnls) > 1:
            returns = np.array(pnls) / self.initial_capital
            sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)
                            if np.std(returns) > 0 else 0)
        else:
            sharpe_ratio = 0

        # Sortino ratio (downside deviation)
        if len(pnls) > 1:
            negative_returns = [p / self.initial_capital for p in pnls if p < 0]
            if negative_returns:
                downside_std = np.std(negative_returns)
                sortino_ratio = (np.mean(pnls) / self.initial_capital /
                                 downside_std * np.sqrt(252) if downside_std > 0 else 0)
            else:
                sortino_ratio = float('inf') if np.mean(pnls) > 0 else 0
        else:
            sortino_ratio = 0

        # Trades per day
        if trades:
            time_span = (trades[-1].exit_time - trades[0].entry_time).days if trades[-1].exit_time else 1
            trades_per_day = total_trades / max(time_span, 1)
        else:
            trades_per_day = 0

        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_duration_days=max_dd_duration_bars / 24,  # Approximate for hourly data
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_trade_pnl=avg_trade_pnl,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            avg_trade_duration_minutes=avg_duration,
            trades_per_day=trades_per_day,
        )

    def plot_equity_curve(
        self,
        results: BacktestResults,
        show_trades: bool = True,
        figsize: Tuple[int, int] = (14, 8),
    ) -> None:
        """
        Plot equity curve with optional trade markers.

        Args:
            results: BacktestResults to plot
            show_trades: Whether to show trade entry/exit points
            figsize: Figure size
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            logger.warning("matplotlib not installed, cannot plot")
            return

        fig, axes = plt.subplots(2, 1, figsize=figsize, height_ratios=[3, 1])

        # Equity curve
        ax1 = axes[0]
        timestamps = results.timestamps if results.timestamps else range(len(results.equity_curve))
        ax1.plot(timestamps, results.equity_curve, label="Equity", color="blue", linewidth=1.5)
        ax1.axhline(y=results.initial_capital, color="gray", linestyle="--", alpha=0.5)
        ax1.fill_between(timestamps, results.initial_capital, results.equity_curve,
                         where=[e >= results.initial_capital for e in results.equity_curve],
                         alpha=0.3, color="green")
        ax1.fill_between(timestamps, results.initial_capital, results.equity_curve,
                         where=[e < results.initial_capital for e in results.equity_curve],
                         alpha=0.3, color="red")

        ax1.set_title(f"Equity Curve - Total PnL: ${results.total_pnl:.2f} | "
                      f"Win Rate: {results.win_rate:.1%} | "
                      f"Sharpe: {results.sharpe_ratio:.2f}")
        ax1.set_ylabel("Equity ($)")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Trade markers
        if show_trades and results.trades:
            for trade in results.trades:
                if trade.entry_time in timestamps:
                    idx = timestamps.index(trade.entry_time)
                    marker = "^" if trade.direction == "BUY" else "v"
                    color = "green" if trade.is_winner else "red"
                    ax1.scatter(trade.entry_time, results.equity_curve[idx],
                                marker=marker, color=color, s=50, alpha=0.7)

        # Drawdown plot
        ax2 = axes[1]
        cumulative = np.array(results.equity_curve)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max * 100

        ax2.fill_between(timestamps, 0, drawdown, color="red", alpha=0.5)
        ax2.set_ylabel("Drawdown (%)")
        ax2.set_xlabel("Time")
        ax2.grid(True, alpha=0.3)
        ax2.invert_yaxis()

        if isinstance(timestamps[0], datetime):
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            plt.xticks(rotation=45)

        plt.tight_layout()
        plt.show()

    def compare_strategies(
        self,
        strategies: List[Tuple[str, BaseStrategy]],
        data: DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ComparisonReport:
        """
        Compare multiple strategies on the same data.

        Args:
            strategies: List of (name, strategy) tuples
            data: Backtest data
            start_date: Start date
            end_date: End date

        Returns:
            ComparisonReport with comparison results
        """
        logger.info(f"Comparing {len(strategies)} strategies")

        results = {}
        comparison_metrics = {}

        for name, strategy in strategies:
            logger.info(f"Running backtest for {name}")
            result = self.run_backtest(
                strategy,
                data,
                start_date,
                end_date,
            )
            results[name] = result

            comparison_metrics[name] = {
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "total_pnl": result.total_pnl,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "profit_factor": result.metrics.profit_factor if result.metrics else 0,
            }

        # Rank by Sharpe ratio
        ranking = sorted(
            comparison_metrics.keys(),
            key=lambda x: comparison_metrics[x]["sharpe_ratio"],
            reverse=True,
        )

        return ComparisonReport(
            strategy_names=[name for name, _ in strategies],
            results=results,
            best_strategy=ranking[0] if ranking else "",
            ranking=ranking,
            comparison_metrics=comparison_metrics,
        )

    def _filter_data_by_date(
        self,
        data: DataFrame,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> DataFrame:
        """Filter data by date range."""
        data = data.copy()

        if isinstance(data.index, pd.DatetimeIndex):
            if start_date:
                data = data[data.index >= start_date]
            if end_date:
                data = data[data.index <= end_date]
        elif "datetime" in data.columns:
            data["datetime"] = pd.to_datetime(data["datetime"])
            if start_date:
                data = data[data["datetime"] >= start_date]
            if end_date:
                data = data[data["datetime"] <= end_date]

        return data

    def _check_exit(
        self,
        position: Trade,
        current_bar: Series,
    ) -> Tuple[bool, float, str]:
        """Check if position should be closed."""
        high = current_bar["high"]
        low = current_bar["low"]
        close = current_bar["close"]

        if position.direction == "BUY":
            # Check stop loss
            if position.stop_loss and low <= position.stop_loss:
                return True, position.stop_loss, "sl_hit"
            # Check take profit
            if position.take_profit and high >= position.take_profit:
                return True, position.take_profit, "tp_hit"
        else:  # SELL
            # Check stop loss
            if position.stop_loss and high >= position.stop_loss:
                return True, position.stop_loss, "sl_hit"
            # Check take profit
            if position.take_profit and low <= position.take_profit:
                return True, position.take_profit, "tp_hit"

        return False, close, ""

    def _calculate_pnl(self, trade: Trade, lot_size: float) -> float:
        """Calculate PnL for a trade."""
        if trade.exit_price is None:
            return 0

        # Standard lot = 100,000 units
        units = lot_size * 100000

        if trade.direction == "BUY":
            pips = (trade.exit_price - trade.entry_price) / self.pip_value
        else:
            pips = (trade.entry_price - trade.exit_price) / self.pip_value

        # PnL in account currency (assuming USD account)
        pnl = pips * self.pip_value * units

        # Subtract commission
        pnl -= self.commission_per_lot * lot_size

        return pnl

    def _calculate_pnl_pips(self, trade: Trade) -> float:
        """Calculate PnL in pips."""
        if trade.exit_price is None:
            return 0

        if trade.direction == "BUY":
            return (trade.exit_price - trade.entry_price) / self.pip_value
        else:
            return (trade.entry_price - trade.exit_price) / self.pip_value

    def _calculate_unrealized_pnl(
        self,
        position: Trade,
        current_price: float,
        lot_size: float,
    ) -> float:
        """Calculate unrealized PnL for open position."""
        units = lot_size * 100000

        if position.direction == "BUY":
            pips = (current_price - position.entry_price) / self.pip_value
        else:
            pips = (position.entry_price - current_price) / self.pip_value

        return pips * self.pip_value * units

    def _empty_results(self) -> BacktestResults:
        """Return empty results for edge cases."""
        return BacktestResults(
            total_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            trades=[],
            equity_curve=[self.initial_capital],
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
        )
