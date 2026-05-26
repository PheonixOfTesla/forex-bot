from __future__ import annotations

"""
Strategy Manager

Coordinates multiple trading strategies, aggregates signals,
and manages strategy lifecycle.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Type
import logging
from dataclasses import dataclass, field
import pandas as pd

from .base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    TradeSetup,
    StrategyStats,
)


logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy."""
    name: str
    signals_generated: int = 0
    signals_executed: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_pips: float = 0.0
    total_loss_pips: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    largest_win_pips: float = 0.0
    largest_loss_pips: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def update_metrics(self):
        """Recalculate derived metrics."""
        total_trades = self.winning_trades + self.losing_trades

        if total_trades > 0:
            self.win_rate = self.winning_trades / total_trades

        if self.total_loss_pips > 0:
            self.profit_factor = self.total_profit_pips / self.total_loss_pips

        if self.winning_trades > 0:
            self.avg_win_pips = self.total_profit_pips / self.winning_trades

        if self.losing_trades > 0:
            self.avg_loss_pips = self.total_loss_pips / self.losing_trades

        self.last_updated = datetime.utcnow()


class StrategyManager:
    """
    Manages multiple trading strategies.

    Responsibilities:
    - Register and unregister strategies
    - Collect signals from all active strategies
    - Rank signals by confidence
    - Track strategy performance
    - Enable/disable strategies based on performance

    Attributes:
        strategies: Dictionary of registered strategies
        performance: Performance tracking for each strategy
        max_signals_per_cycle: Maximum signals to return per cycle
        auto_disable_threshold: Win rate below which to auto-disable
    """

    def __init__(
        self,
        max_signals_per_cycle: int = 5,
        auto_disable_threshold: float = 0.40,
        min_trades_for_disable: int = 20
    ):
        """
        Initialize the Strategy Manager.

        Args:
            max_signals_per_cycle: Maximum signals to return per cycle
            auto_disable_threshold: Win rate threshold for auto-disable
            min_trades_for_disable: Minimum trades before auto-disable logic
        """
        self.strategies: Dict[str, BaseStrategy] = {}
        self.performance: Dict[str, StrategyPerformance] = {}
        self.max_signals_per_cycle = max_signals_per_cycle
        self.auto_disable_threshold = auto_disable_threshold
        self.min_trades_for_disable = min_trades_for_disable

        self._disabled_strategies: Dict[str, str] = {}  # name -> reason

    def register_strategy(
        self,
        strategy: BaseStrategy,
        auto_enable: bool = True
    ):
        """
        Register a strategy with the manager.

        Args:
            strategy: Strategy instance to register
            auto_enable: Whether to enable the strategy immediately
        """
        name = strategy.name

        if name in self.strategies:
            logger.warning(f"Strategy '{name}' already registered, replacing")

        self.strategies[name] = strategy
        self.performance[name] = StrategyPerformance(name=name)

        if auto_enable:
            strategy.enable()

        logger.info(f"Registered strategy: {name} (assets: {strategy.assets})")

    def unregister_strategy(self, name: str) -> bool:
        """
        Unregister a strategy.

        Args:
            name: Strategy name to unregister

        Returns:
            True if strategy was found and removed
        """
        if name in self.strategies:
            del self.strategies[name]
            if name in self.performance:
                del self.performance[name]
            if name in self._disabled_strategies:
                del self._disabled_strategies[name]
            logger.info(f"Unregistered strategy: {name}")
            return True
        return False

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """
        Get a strategy by name.

        Args:
            name: Strategy name

        Returns:
            Strategy instance or None
        """
        return self.strategies.get(name)

    def get_all_signals(
        self,
        market_data: Dict[str, pd.DataFrame],
        features: Dict[str, Dict[str, Any]] = None
    ) -> List[Signal]:
        """
        Get signals from all active strategies.

        Args:
            market_data: Dictionary of asset -> DataFrame with OHLCV + indicators
            features: Dictionary of asset -> additional features

        Returns:
            List of all generated signals
        """
        signals = []
        features = features or {}

        for name, strategy in self.strategies.items():
            if not strategy.is_enabled:
                continue

            for asset, df in market_data.items():
                if not strategy.can_trade_asset(asset):
                    continue

                try:
                    # Get features for this asset
                    asset_features = features.get(asset, {})
                    asset_features['asset'] = asset

                    signal = strategy.generate_signal(df, asset_features)

                    if signal:
                        signals.append(signal)
                        self.performance[name].signals_generated += 1
                        logger.debug(
                            f"Signal from {name}: {signal.direction.value} "
                            f"{asset} (confidence: {signal.confidence:.2f})"
                        )

                except Exception as e:
                    logger.error(f"Error generating signal from {name} for {asset}: {e}")

        return signals

    def rank_signals_by_confidence(
        self,
        signals: List[Signal],
        min_confidence: Optional[float] = None
    ) -> List[Signal]:
        """
        Rank signals by confidence score.

        Args:
            signals: List of signals to rank
            min_confidence: Optional minimum confidence filter

        Returns:
            Sorted list of signals (highest confidence first)
        """
        if min_confidence is not None:
            signals = [s for s in signals if s.confidence >= min_confidence]

        # Sort by confidence descending
        ranked = sorted(signals, key=lambda s: s.confidence, reverse=True)

        # Limit to max signals per cycle
        return ranked[:self.max_signals_per_cycle]

    def get_top_signals(
        self,
        market_data: Dict[str, pd.DataFrame],
        features: Dict[str, Dict[str, Any]] = None,
        min_confidence: float = 0.70
    ) -> List[Signal]:
        """
        Get top-ranked signals from all strategies.

        Convenience method that combines get_all_signals and rank_signals.

        Args:
            market_data: Dictionary of asset -> DataFrame
            features: Optional additional features
            min_confidence: Minimum confidence threshold

        Returns:
            List of top-ranked signals
        """
        all_signals = self.get_all_signals(market_data, features)
        return self.rank_signals_by_confidence(all_signals, min_confidence)

    def disable_strategy(self, name: str, reason: str):
        """
        Disable a strategy.

        Args:
            name: Strategy name to disable
            reason: Reason for disabling
        """
        if name in self.strategies:
            self.strategies[name].disable(reason)
            self._disabled_strategies[name] = reason
            logger.warning(f"Disabled strategy '{name}': {reason}")

    def enable_strategy(self, name: str):
        """
        Enable a previously disabled strategy.

        Args:
            name: Strategy name to enable
        """
        if name in self.strategies:
            self.strategies[name].enable()
            if name in self._disabled_strategies:
                del self._disabled_strategies[name]
            logger.info(f"Enabled strategy: {name}")

    def record_trade_result(
        self,
        strategy_name: str,
        profit_pips: float
    ):
        """
        Record a trade result for a strategy.

        Args:
            strategy_name: Name of the strategy
            profit_pips: Profit/loss in pips (negative for loss)
        """
        if strategy_name not in self.performance:
            logger.warning(f"Unknown strategy: {strategy_name}")
            return

        perf = self.performance[strategy_name]

        if profit_pips > 0:
            perf.winning_trades += 1
            perf.total_profit_pips += profit_pips
            perf.consecutive_wins += 1
            perf.consecutive_losses = 0

            if profit_pips > perf.largest_win_pips:
                perf.largest_win_pips = profit_pips
            if perf.consecutive_wins > perf.max_consecutive_wins:
                perf.max_consecutive_wins = perf.consecutive_wins
        else:
            perf.losing_trades += 1
            perf.total_loss_pips += abs(profit_pips)
            perf.consecutive_losses += 1
            perf.consecutive_wins = 0

            if abs(profit_pips) > perf.largest_loss_pips:
                perf.largest_loss_pips = abs(profit_pips)
            if perf.consecutive_losses > perf.max_consecutive_losses:
                perf.max_consecutive_losses = perf.consecutive_losses

        perf.signals_executed += 1
        perf.update_metrics()

        # Update strategy's internal stats
        if strategy_name in self.strategies:
            self.strategies[strategy_name].record_trade_result(profit_pips)

        # Check for auto-disable
        self._check_auto_disable(strategy_name)

    def _check_auto_disable(self, strategy_name: str):
        """
        Check if a strategy should be auto-disabled due to poor performance.

        Args:
            strategy_name: Strategy to check
        """
        perf = self.performance.get(strategy_name)

        if not perf:
            return

        total_trades = perf.winning_trades + perf.losing_trades

        if total_trades < self.min_trades_for_disable:
            return

        if perf.win_rate < self.auto_disable_threshold:
            reason = (
                f"Win rate {perf.win_rate:.1%} below threshold "
                f"{self.auto_disable_threshold:.1%} after {total_trades} trades"
            )
            self.disable_strategy(strategy_name, reason)

    def get_strategy_stats(self) -> Dict[str, StrategyStats]:
        """
        Get statistics for all strategies.

        Returns:
            Dictionary of strategy name -> StrategyStats
        """
        stats = {}

        for name, strategy in self.strategies.items():
            stats[name] = strategy.stats

        return stats

    def get_strategy_performance(self) -> Dict[str, StrategyPerformance]:
        """
        Get detailed performance metrics for all strategies.

        Returns:
            Dictionary of strategy name -> StrategyPerformance
        """
        return self.performance.copy()

    def get_enabled_strategies(self) -> List[str]:
        """
        Get list of enabled strategy names.

        Returns:
            List of enabled strategy names
        """
        return [
            name for name, strategy in self.strategies.items()
            if strategy.is_enabled
        ]

    def get_disabled_strategies(self) -> Dict[str, str]:
        """
        Get disabled strategies and their reasons.

        Returns:
            Dictionary of strategy name -> disable reason
        """
        return self._disabled_strategies.copy()

    def get_strategies_for_asset(self, asset: str) -> List[BaseStrategy]:
        """
        Get all strategies that can trade a given asset.

        Args:
            asset: Asset symbol

        Returns:
            List of strategies that trade this asset
        """
        return [
            strategy for strategy in self.strategies.values()
            if strategy.can_trade_asset(asset) and strategy.is_enabled
        ]

    def reset_performance(self, strategy_name: Optional[str] = None):
        """
        Reset performance metrics.

        Args:
            strategy_name: Strategy to reset, or None for all
        """
        if strategy_name:
            if strategy_name in self.performance:
                self.performance[strategy_name] = StrategyPerformance(
                    name=strategy_name
                )
        else:
            for name in self.performance:
                self.performance[name] = StrategyPerformance(name=name)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the strategy manager state.

        Returns:
            Dictionary with manager state summary
        """
        total_signals = sum(
            p.signals_generated for p in self.performance.values()
        )
        total_trades = sum(
            p.winning_trades + p.losing_trades
            for p in self.performance.values()
        )
        total_wins = sum(p.winning_trades for p in self.performance.values())

        return {
            'total_strategies': len(self.strategies),
            'enabled_strategies': len(self.get_enabled_strategies()),
            'disabled_strategies': len(self._disabled_strategies),
            'total_signals_generated': total_signals,
            'total_trades_executed': total_trades,
            'overall_win_rate': total_wins / total_trades if total_trades > 0 else 0,
            'strategies': list(self.strategies.keys()),
            'disabled': self._disabled_strategies
        }

    def __repr__(self) -> str:
        return (
            f"StrategyManager(strategies={len(self.strategies)}, "
            f"enabled={len(self.get_enabled_strategies())})"
        )
