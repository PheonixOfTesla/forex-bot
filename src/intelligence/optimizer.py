from __future__ import annotations

"""
Strategy Optimizer

Self-optimizing component that suggests parameter adjustments,
dynamic position sizing, and strategy management based on
performance analysis.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import (
    ActionType,
    Adjustment,
    FailurePattern,
    ImprovementReport,
    LossAnalysis,
    PerformanceSnapshot,
    WinAnalysis,
)
from .analyzer import TradeAnalyzer
from .tracker import TradeTracker

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """
    Self-Optimizing Strategy Manager

    Suggests parameter adjustments, manages position sizing,
    and generates improvement reports based on performance data.
    """

    # Default thresholds
    MIN_WIN_RATE_THRESHOLD = 0.40  # 40% minimum win rate
    DISABLE_WIN_RATE_THRESHOLD = 0.35  # Disable if below 35%
    MIN_TRADES_FOR_DECISION = 10  # Minimum trades to make decisions

    # Kelly Criterion settings
    MAX_KELLY_FRACTION = 0.25  # Max 25% of Kelly
    MIN_KELLY_FRACTION = 0.05  # Min 5% of Kelly
    KELLY_DECAY_FACTOR = 0.1  # Reduce Kelly during drawdowns

    # Confidence adjustment settings
    BASE_CONFIDENCE_THRESHOLD = 70.0
    MAX_CONFIDENCE_ADJUSTMENT = 15.0  # Max adjustment amount

    def __init__(
        self,
        tracker: TradeTracker,
        analyzer: TradeAnalyzer,
        session_factory=None,
    ):
        """
        Initialize the optimizer.

        Args:
            tracker: TradeTracker instance
            analyzer: TradeAnalyzer instance
            session_factory: SQLAlchemy session factory for persistence
        """
        self.tracker = tracker
        self.analyzer = analyzer
        self.session_factory = session_factory

        # Track applied adjustments
        self._applied_adjustments: List[Adjustment] = []
        self._disabled_strategies: List[str] = []

    # =========================================================================
    # Parameter Adjustments
    # =========================================================================

    def suggest_parameter_adjustments(
        self,
        analysis: Optional[LossAnalysis] = None,
        days: int = 30,
    ) -> List[Adjustment]:
        """
        Suggest parameter adjustments based on loss analysis.

        Examples:
        - "Increase min confidence to 75% for XRP during Asia session"
        - "Reduce position size during high volatility"
        - "Disable momentum strategy for EUR_USD"

        Args:
            analysis: Optional LossAnalysis (will generate if not provided)
            days: Days to analyze if generating analysis

        Returns:
            List of suggested Adjustment objects
        """
        if analysis is None:
            analysis = self.analyzer.analyze_losses(days=days)

        adjustments = []

        # 1. Confidence threshold adjustments
        confidence_adjustments = self._suggest_confidence_adjustments(analysis)
        adjustments.extend(confidence_adjustments)

        # 2. Session-specific adjustments
        session_adjustments = self._suggest_session_adjustments(analysis)
        adjustments.extend(session_adjustments)

        # 3. Strategy-specific adjustments
        strategy_adjustments = self._suggest_strategy_adjustments(analysis)
        adjustments.extend(strategy_adjustments)

        # 4. Position size adjustments
        position_adjustments = self._suggest_position_adjustments(analysis)
        adjustments.extend(position_adjustments)

        # Sort by priority
        adjustments.sort(key=lambda a: a.priority)

        logger.info(f"Generated {len(adjustments)} parameter adjustment suggestions")

        return adjustments

    def _suggest_confidence_adjustments(
        self,
        analysis: LossAnalysis,
    ) -> List[Adjustment]:
        """Suggest confidence threshold adjustments."""
        adjustments = []

        # Check for confidence-related patterns
        for pattern in analysis.patterns:
            if (
                pattern.suggested_action == ActionType.INCREASE_CONFIDENCE_THRESHOLD
                and pattern.confidence_score > 0.7
            ):
                suggested_threshold = pattern.additional_data.get(
                    "suggested_min_confidence", 75
                )

                adjustments.append(
                    Adjustment(
                        strategy=None,  # Global adjustment
                        parameter="min_confidence_threshold",
                        current_value=self.BASE_CONFIDENCE_THRESHOLD,
                        suggested_value=suggested_threshold,
                        reason=pattern.description,
                        expected_impact=f"Could reduce losses by filtering {pattern.affected_trades_count} low-confidence trades",
                        confidence=pattern.confidence_score,
                        priority=1,
                    )
                )

        return adjustments

    def _suggest_session_adjustments(
        self,
        analysis: LossAnalysis,
    ) -> List[Adjustment]:
        """Suggest session-specific adjustments."""
        adjustments = []

        for pattern in analysis.patterns:
            if pattern.pattern_type.value == "session":
                session = pattern.additional_data.get("session", "unknown")

                # Option 1: Raise confidence for this session
                adjustments.append(
                    Adjustment(
                        strategy=None,
                        parameter="session_confidence_boost",
                        current_value=0,
                        suggested_value=10,  # +10% confidence requirement
                        reason=f"High loss rate during {session} session",
                        expected_impact=f"Fewer trades during {session}, better quality",
                        confidence=pattern.confidence_score,
                        session=session,
                        priority=2,
                    )
                )

                # Option 2: Reduce position size for this session
                if pattern.frequency > 0.7:  # Very high loss rate
                    adjustments.append(
                        Adjustment(
                            strategy=None,
                            parameter="session_position_multiplier",
                            current_value=1.0,
                            suggested_value=0.5,  # 50% position size
                            reason=f"Very high loss rate ({pattern.frequency:.0%}) during {session} session",
                            expected_impact="Reduced risk exposure during problematic session",
                            confidence=pattern.confidence_score,
                            session=session,
                            priority=1,
                        )
                    )

        return adjustments

    def _suggest_strategy_adjustments(
        self,
        analysis: LossAnalysis,
    ) -> List[Adjustment]:
        """Suggest strategy-specific adjustments."""
        adjustments = []

        # Analyze each strategy's performance
        for strategy, loss_count in analysis.losses_by_strategy.items():
            loss_amount = analysis.loss_amount_by_strategy.get(strategy, 0)

            # Get win rate for this strategy
            win_rate = self.tracker.get_win_rate(strategy=strategy, days=30)

            # Strategy needs attention
            if win_rate < 50:
                # Check for decay
                decay = self.analyzer.calculate_strategy_decay(strategy)

                if decay > 0.3:  # Significant decay
                    adjustments.append(
                        Adjustment(
                            strategy=strategy,
                            parameter="strategy_enabled",
                            current_value=True,
                            suggested_value=False,
                            reason=f"Strategy decay score {decay:.2f}, win rate dropped to {win_rate:.1f}%",
                            expected_impact="Stop losses from degrading strategy",
                            confidence=min(0.9, 0.5 + decay),
                            priority=1 if decay > 0.5 else 2,
                        )
                    )
                elif win_rate < 45:
                    # Suggest reducing exposure
                    adjustments.append(
                        Adjustment(
                            strategy=strategy,
                            parameter="strategy_position_multiplier",
                            current_value=1.0,
                            suggested_value=0.5,
                            reason=f"Strategy win rate at {win_rate:.1f}%",
                            expected_impact="Reduced exposure while strategy recovers",
                            confidence=0.75,
                            priority=2,
                        )
                    )

        return adjustments

    def _suggest_position_adjustments(
        self,
        analysis: LossAnalysis,
    ) -> List[Adjustment]:
        """Suggest position size adjustments."""
        adjustments = []

        # Check for volatility patterns
        for pattern in analysis.patterns:
            if pattern.pattern_type.value == "volatility":
                adjustments.append(
                    Adjustment(
                        strategy=None,
                        parameter="high_volatility_position_reduction",
                        current_value=1.0,
                        suggested_value=0.7,  # 30% reduction
                        reason=pattern.description,
                        expected_impact="Smaller losses during volatile periods",
                        confidence=pattern.confidence_score,
                        condition="high_volatility",
                        priority=2,
                    )
                )

        return adjustments

    # =========================================================================
    # Strategy Management
    # =========================================================================

    def should_disable_strategy(
        self,
        strategy: str,
        recent_performance: Optional[Dict[str, Any]] = None,
        min_trades: int = 10,
    ) -> bool:
        """
        Determine if a strategy should be automatically disabled.

        Criteria:
        - Win rate below threshold
        - Consistent losses over multiple trades
        - Significant strategy decay

        Args:
            strategy: Strategy name to evaluate
            recent_performance: Optional performance dict (will calculate if not provided)
            min_trades: Minimum trades required for decision

        Returns:
            True if strategy should be disabled
        """
        if recent_performance is None:
            recent_performance = self.tracker.get_strategy_performance(days=14).get(
                strategy, {}
            )

        total_trades = recent_performance.get("total_trades", 0)

        # Not enough data
        if total_trades < min_trades:
            logger.info(
                f"Strategy {strategy}: insufficient trades ({total_trades}) for disable decision"
            )
            return False

        win_rate = recent_performance.get("win_rate", 0) / 100  # Convert to decimal
        total_pnl = recent_performance.get("total_pnl", 0)

        # Check win rate threshold
        if win_rate < self.DISABLE_WIN_RATE_THRESHOLD:
            logger.warning(
                f"Strategy {strategy} below disable threshold: "
                f"{win_rate:.1%} win rate < {self.DISABLE_WIN_RATE_THRESHOLD:.1%}"
            )
            return True

        # Check for consistent losses
        recent_trades = self.tracker.get_trade_history(days=7, strategy=strategy)
        if len(recent_trades) >= 5:
            recent_losses = sum(1 for t in recent_trades if not t.is_win)
            if recent_losses / len(recent_trades) > 0.8:  # 80%+ losses in last 5+ trades
                logger.warning(
                    f"Strategy {strategy} has {recent_losses}/{len(recent_trades)} "
                    f"recent losses, recommending disable"
                )
                return True

        # Check strategy decay
        decay = self.analyzer.calculate_strategy_decay(strategy)
        if decay > 0.5:  # Severe decay
            logger.warning(
                f"Strategy {strategy} has severe decay score: {decay:.2f}"
            )
            return True

        return False

    def get_disabled_strategies(self) -> List[str]:
        """Get list of currently disabled strategies."""
        return self._disabled_strategies.copy()

    def disable_strategy(self, strategy: str, reason: str) -> None:
        """
        Disable a strategy.

        Args:
            strategy: Strategy name
            reason: Reason for disabling
        """
        if strategy not in self._disabled_strategies:
            self._disabled_strategies.append(strategy)
            logger.warning(f"Disabled strategy '{strategy}': {reason}")

    def enable_strategy(self, strategy: str) -> None:
        """
        Re-enable a previously disabled strategy.

        Args:
            strategy: Strategy name
        """
        if strategy in self._disabled_strategies:
            self._disabled_strategies.remove(strategy)
            logger.info(f"Re-enabled strategy '{strategy}'")

    # =========================================================================
    # Position Sizing
    # =========================================================================

    def calculate_optimal_position_size(
        self,
        recent_volatility: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        current_drawdown: float = 0.0,
        base_position: float = 1.0,
    ) -> float:
        """
        Calculate optimal position size using dynamic Kelly adjustment.

        Uses Kelly Criterion with adjustments for:
        - Recent volatility
        - Current drawdown
        - Recent performance

        Args:
            recent_volatility: Recent ATR or similar volatility measure
            win_rate: Recent win rate (0-1), will calculate if not provided
            avg_win: Average win amount
            avg_loss: Average loss amount
            current_drawdown: Current drawdown percentage (0-100)
            base_position: Base position size (default 1.0 = 100%)

        Returns:
            Optimal position size as multiplier (e.g., 0.5 = 50% of base)
        """
        # Get historical data if not provided
        if win_rate is None or avg_win is None or avg_loss is None:
            trades = self.tracker.get_trade_history(days=30)
            wins = [t for t in trades if t.is_win]
            losses = [t for t in trades if not t.is_win]

            if len(trades) < 10:
                return base_position * 0.5  # Conservative default

            win_rate = len(wins) / len(trades) if trades else 0.5
            avg_win = sum(t.pnl or 0 for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t.pnl or 0 for t in losses) / len(losses)) if losses else 0

        # Calculate Kelly fraction
        kelly_fraction = self._calculate_kelly(win_rate, avg_win, avg_loss)

        # Adjust for current drawdown
        if current_drawdown > 5:  # More than 5% drawdown
            drawdown_factor = 1 - (current_drawdown / 100) * self.KELLY_DECAY_FACTOR
            kelly_fraction *= max(0.5, drawdown_factor)

        # Adjust for volatility
        # Assuming recent_volatility is normalized (1.0 = normal)
        if recent_volatility > 1.5:  # High volatility
            volatility_factor = 1.0 / (recent_volatility ** 0.5)
            kelly_fraction *= volatility_factor

        # Apply limits
        kelly_fraction = max(
            self.MIN_KELLY_FRACTION,
            min(self.MAX_KELLY_FRACTION, kelly_fraction),
        )

        optimal_size = base_position * kelly_fraction

        logger.debug(
            f"Position sizing: win_rate={win_rate:.1%}, kelly={kelly_fraction:.2f}, "
            f"optimal_size={optimal_size:.2f}"
        )

        return optimal_size

    def _calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Calculate Kelly Criterion fraction.

        Formula: f* = (bp - q) / b
        where:
        - b = avg_win / avg_loss (odds)
        - p = win_rate
        - q = 1 - win_rate
        """
        if avg_loss == 0 or win_rate == 0:
            return self.MIN_KELLY_FRACTION

        b = abs(avg_win / avg_loss) if avg_loss != 0 else 1
        p = win_rate
        q = 1 - win_rate

        kelly = (b * p - q) / b

        # Kelly can be negative if edge is negative
        if kelly <= 0:
            return self.MIN_KELLY_FRACTION

        return kelly

    def get_session_position_multiplier(
        self,
        session: str,
    ) -> float:
        """
        Get position size multiplier for a specific session.

        Based on historical performance in that session.

        Args:
            session: Trading session name

        Returns:
            Position multiplier (1.0 = normal, 0.5 = half size, etc.)
        """
        # Check active adjustments
        for adj in self._applied_adjustments:
            if (
                adj.parameter == "session_position_multiplier"
                and adj.session == session
            ):
                return adj.suggested_value

        # Calculate from historical data
        trades = self.tracker.get_trade_history(days=30)
        session_trades = [t for t in trades if t.session == session]

        if len(session_trades) < 10:
            return 1.0

        session_win_rate = sum(1 for t in session_trades if t.is_win) / len(session_trades)

        # Reduce size for poor performing sessions
        if session_win_rate < 0.4:
            return 0.5
        elif session_win_rate < 0.5:
            return 0.75
        elif session_win_rate > 0.6:
            return 1.25  # Slight increase for good sessions

        return 1.0

    # =========================================================================
    # Improvement Reports
    # =========================================================================

    def generate_improvement_report(
        self,
        period_days: int = 7,
    ) -> ImprovementReport:
        """
        Generate a comprehensive improvement report.

        Summarizes what worked, what didn't, and what changed
        over the reporting period.

        Args:
            period_days: Number of days to cover in report

        Returns:
            ImprovementReport with analysis and recommendations
        """
        now = datetime.utcnow()
        report_start = now - timedelta(days=period_days)

        # Get analyses
        trades = self.tracker.get_trade_history(days=period_days)
        win_analysis = self.analyzer.analyze_wins(trades)
        loss_analysis = self.analyzer.analyze_losses(trades)
        failure_patterns = self.analyzer.find_failure_patterns(days=period_days)

        # Get performance
        snapshot = self.tracker.create_performance_snapshot()
        strategy_perf = self.tracker.get_strategy_performance(days=period_days)

        # Previous period for comparison
        prev_trades = self.tracker.get_trade_history(days=period_days * 2)
        prev_trades = [
            t for t in prev_trades
            if t.timestamp < report_start
        ]

        # Calculate metrics
        total_trades = len(trades)
        win_rate = (win_analysis.total_wins / total_trades * 100) if total_trades else 0
        total_pnl = win_analysis.total_win_amount - loss_analysis.total_loss_amount

        # Previous period metrics
        prev_wins = sum(1 for t in prev_trades if t.is_win)
        prev_win_rate = (prev_wins / len(prev_trades) * 100) if prev_trades else 0
        prev_pnl = sum(t.pnl or 0 for t in prev_trades)

        # What worked
        successful_patterns = []
        if win_analysis.best_sessions:
            successful_patterns.append({
                "type": "session",
                "description": f"Best performance during {', '.join(win_analysis.best_sessions)} session(s)",
            })
        if win_analysis.best_hours:
            successful_patterns.append({
                "type": "timing",
                "description": f"Best trades at hours: {win_analysis.best_hours}",
            })

        # Best strategies
        best_strategies = []
        for strategy, perf in sorted(
            strategy_perf.items(),
            key=lambda x: x[1].get("total_pnl", 0),
            reverse=True,
        )[:3]:
            if perf.get("total_trades", 0) >= 5:
                best_strategies.append({
                    "name": strategy,
                    "win_rate": perf.get("win_rate", 0),
                    "pnl": perf.get("total_pnl", 0),
                    "trades": perf.get("total_trades", 0),
                })

        # Worst strategies
        worst_strategies = []
        for strategy, perf in sorted(
            strategy_perf.items(),
            key=lambda x: x[1].get("total_pnl", 0),
        )[:3]:
            if perf.get("total_trades", 0) >= 5 and perf.get("total_pnl", 0) < 0:
                worst_strategies.append({
                    "name": strategy,
                    "win_rate": perf.get("win_rate", 0),
                    "pnl": perf.get("total_pnl", 0),
                    "trades": perf.get("total_trades", 0),
                })

        # Conditions to avoid
        conditions_to_avoid = {}
        if loss_analysis.worst_sessions:
            conditions_to_avoid["sessions"] = loss_analysis.worst_sessions
        if loss_analysis.worst_hours:
            conditions_to_avoid["hours"] = loss_analysis.worst_hours

        # Generate recommendations
        recommendations = self._generate_recommendations(
            win_rate=win_rate,
            total_pnl=total_pnl,
            failure_patterns=failure_patterns,
            strategy_perf=strategy_perf,
            snapshot=snapshot,
        )

        # Calculate improvement score
        improvement_score = 0.0
        if prev_win_rate > 0:
            improvement_score += (win_rate - prev_win_rate) / prev_win_rate * 50
        if prev_pnl != 0:
            improvement_score += (total_pnl - prev_pnl) / abs(prev_pnl) * 50
        improvement_score = max(-100, min(100, improvement_score))

        report = ImprovementReport(
            report_start=report_start,
            report_end=now,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            successful_patterns=successful_patterns,
            best_performing_strategies=best_strategies,
            optimal_conditions={
                "sessions": win_analysis.best_sessions,
                "hours": win_analysis.best_hours,
                "avg_confidence": win_analysis.avg_confidence_on_wins,
            },
            failure_patterns=failure_patterns,
            worst_performing_strategies=worst_strategies,
            conditions_to_avoid=conditions_to_avoid,
            parameter_adjustments=self._applied_adjustments.copy(),
            disabled_strategies=self._disabled_strategies.copy(),
            recommendations=recommendations,
            pnl_change=total_pnl - prev_pnl,
            win_rate_change=win_rate - prev_win_rate,
            improvement_score=improvement_score,
        )

        logger.info(
            f"Generated improvement report: {report.total_trades} trades, "
            f"{report.win_rate:.1f}% win rate, ${report.total_pnl:,.2f} PnL"
        )

        return report

    def _generate_recommendations(
        self,
        win_rate: float,
        total_pnl: float,
        failure_patterns: List[FailurePattern],
        strategy_perf: Dict[str, Dict],
        snapshot: PerformanceSnapshot,
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Win rate recommendations
        if win_rate < 45:
            recommendations.append(
                "WIN RATE LOW: Consider increasing minimum confidence threshold to filter weak signals"
            )
        elif win_rate < 50:
            recommendations.append(
                "Win rate below 50%: Review entry criteria and consider tightening filters"
            )

        # PnL recommendations
        if total_pnl < 0:
            recommendations.append(
                "NEGATIVE PnL: Focus on loss reduction - consider reducing position sizes until performance improves"
            )

        # Pattern-based recommendations
        for pattern in failure_patterns[:3]:  # Top 3 patterns
            if pattern.suggested_action == ActionType.DISABLE_STRATEGY:
                recommendations.append(
                    f"Consider disabling underperforming strategy: {pattern.description}"
                )
            elif pattern.suggested_action == ActionType.AVOID_SESSION:
                session = pattern.additional_data.get("session", "unknown")
                recommendations.append(
                    f"Reduce or avoid trading during {session} session due to poor performance"
                )
            elif pattern.suggested_action == ActionType.INCREASE_CONFIDENCE_THRESHOLD:
                recommendations.append(
                    f"Raise confidence threshold: {pattern.description}"
                )

        # Strategy recommendations
        for strategy, perf in strategy_perf.items():
            if perf.get("total_trades", 0) >= 10:
                wr = perf.get("win_rate", 0)
                if wr < 35:
                    recommendations.append(
                        f"DISABLE '{strategy}': Only {wr:.0f}% win rate over {perf.get('total_trades')} trades"
                    )
                elif wr > 60 and perf.get("total_pnl", 0) > 0:
                    recommendations.append(
                        f"SCALE UP '{strategy}': {wr:.0f}% win rate performing well"
                    )

        # Drawdown recommendations
        if snapshot.max_drawdown > 10:
            recommendations.append(
                f"Max drawdown reached {snapshot.max_drawdown:.1f}%: Consider reducing overall position sizes"
            )

        # Sharpe ratio recommendations
        if snapshot.sharpe_ratio and snapshot.sharpe_ratio < 1:
            recommendations.append(
                "Risk-adjusted returns below target: Focus on consistency and reducing volatility"
            )

        return recommendations[:10]  # Limit to 10 recommendations

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def apply_adjustment(self, adjustment: Adjustment) -> None:
        """
        Record an applied adjustment.

        Args:
            adjustment: The adjustment that was applied
        """
        self._applied_adjustments.append(adjustment)
        logger.info(
            f"Applied adjustment: {adjustment.parameter} = {adjustment.suggested_value} "
            f"(was {adjustment.current_value})"
        )

    def get_applied_adjustments(
        self,
        since: Optional[datetime] = None,
    ) -> List[Adjustment]:
        """Get list of applied adjustments."""
        return self._applied_adjustments.copy()

    def reset_adjustments(self) -> None:
        """Clear all tracked adjustments."""
        self._applied_adjustments.clear()
        logger.info("Reset all tracked adjustments")

    def get_current_confidence_threshold(
        self,
        strategy: Optional[str] = None,
        session: Optional[str] = None,
        asset: Optional[str] = None,
    ) -> float:
        """
        Get the current effective confidence threshold.

        Takes into account any active adjustments.

        Args:
            strategy: Optional strategy name
            session: Optional trading session
            asset: Optional asset name

        Returns:
            Effective confidence threshold (0-100)
        """
        threshold = self.BASE_CONFIDENCE_THRESHOLD

        # Apply global adjustments
        for adj in self._applied_adjustments:
            if adj.parameter == "min_confidence_threshold" and adj.strategy is None:
                threshold = adj.suggested_value

        # Apply session-specific boosts
        if session:
            for adj in self._applied_adjustments:
                if (
                    adj.parameter == "session_confidence_boost"
                    and adj.session == session
                ):
                    threshold += adj.suggested_value

        # Apply strategy-specific adjustments
        if strategy:
            for adj in self._applied_adjustments:
                if (
                    adj.parameter == "strategy_confidence_threshold"
                    and adj.strategy == strategy
                ):
                    threshold = adj.suggested_value

        # Ensure within bounds
        return max(50, min(95, threshold))

    def should_take_trade(
        self,
        confidence: float,
        strategy: str,
        session: Optional[str] = None,
        asset: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if a trade should be taken based on current optimization state.

        Args:
            confidence: Model confidence for the trade
            strategy: Strategy generating the signal
            session: Current trading session
            asset: Asset being traded

        Returns:
            Tuple of (should_trade, reason)
        """
        # Check if strategy is disabled
        if strategy in self._disabled_strategies:
            return False, f"Strategy '{strategy}' is disabled"

        # Check confidence threshold
        threshold = self.get_current_confidence_threshold(
            strategy=strategy,
            session=session,
            asset=asset,
        )

        if confidence < threshold:
            return False, f"Confidence {confidence:.1f}% below threshold {threshold:.1f}%"

        # Check for any blocking patterns
        patterns = self.analyzer.get_active_patterns()
        for pattern in patterns:
            if pattern.suggested_action == ActionType.AVOID_SESSION:
                if pattern.additional_data.get("session") == session:
                    return False, f"Session {session} flagged for avoidance"

        return True, "Trade approved"
