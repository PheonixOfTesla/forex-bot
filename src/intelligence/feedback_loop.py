"""
Continuous Learning Feedback Loop

Orchestrates the learning process by connecting trade outcomes
to analysis, optimization, and model retraining decisions.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .analyzer import TradeAnalyzer
from .models import (
    ActionType,
    Adjustment,
    FeatureImportanceDB,
    PerformanceSnapshot,
    TradeRecord,
)
from .optimizer import StrategyOptimizer
from .tracker import TradeTracker

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    Continuous Learning Feedback Loop

    Orchestrates the entire learning cycle:
    1. Trade closes -> update trackers
    2. Analyze performance -> detect patterns
    3. Optimize parameters -> adjust thresholds
    4. Trigger retraining -> update models

    This is the brain's central nervous system.
    """

    # Thresholds for triggering actions
    RETRAIN_WIN_RATE_DROP = 10.0  # Retrain if win rate drops 10%
    RETRAIN_MIN_TRADES = 50  # Min trades since last retrain
    CONFIDENCE_ADJUSTMENT_STEP = 2.5  # Adjust by 2.5% at a time
    PERFORMANCE_CHECK_INTERVAL = 50  # Check performance every N trades

    def __init__(
        self,
        tracker: TradeTracker,
        analyzer: TradeAnalyzer,
        optimizer: StrategyOptimizer,
        session_factory=None,
        on_retrain_needed: Optional[Callable[[], None]] = None,
        on_adjustment_needed: Optional[Callable[[Adjustment], None]] = None,
    ):
        """
        Initialize the feedback loop.

        Args:
            tracker: TradeTracker instance
            analyzer: TradeAnalyzer instance
            optimizer: StrategyOptimizer instance
            session_factory: SQLAlchemy session factory
            on_retrain_needed: Callback when model retraining is needed
            on_adjustment_needed: Callback when parameter adjustment is needed
        """
        self.tracker = tracker
        self.analyzer = analyzer
        self.optimizer = optimizer
        self.session_factory = session_factory

        # Callbacks
        self.on_retrain_needed = on_retrain_needed
        self.on_adjustment_needed = on_adjustment_needed

        # State tracking
        self._last_retrain_check: datetime = datetime.utcnow()
        self._trades_since_retrain: int = 0
        self._baseline_win_rate: Optional[float] = None
        self._baseline_confidence: float = 70.0
        self._current_confidence_threshold: float = 70.0

        # Feature importance tracking
        self._feature_importance: Dict[str, float] = {}
        self._feature_correlation_history: Dict[str, List[float]] = {}

        # Performance history for trend detection
        self._performance_history: List[PerformanceSnapshot] = []

    # =========================================================================
    # Trade Event Handling
    # =========================================================================

    def on_trade_close(self, trade: TradeRecord) -> Dict[str, Any]:
        """
        Process a closed trade through the feedback loop.

        This is the main entry point - called after every trade closes.
        Triggers the full learning cycle.

        Args:
            trade: The closed trade record

        Returns:
            Dict with any actions triggered (adjustments, retrain, etc.)
        """
        logger.info(f"Processing closed trade: {trade.id} - PnL: {trade.pnl_percent:.2f}%")

        actions_triggered = {
            "adjustments": [],
            "retrain_triggered": False,
            "strategies_disabled": [],
            "confidence_adjusted": False,
        }

        # Increment counter
        self._trades_since_retrain += 1

        # Update feature importance
        self.update_feature_importance({trade.id: trade})

        # Periodic performance check
        if self._trades_since_retrain % self.PERFORMANCE_CHECK_INTERVAL == 0:
            # Create performance snapshot
            snapshot = self.tracker.create_performance_snapshot()
            self._performance_history.append(snapshot)

            # Check if retrain needed
            if self.retrain_trigger():
                actions_triggered["retrain_triggered"] = True
                if self.on_retrain_needed:
                    self.on_retrain_needed()

            # Adjust confidence threshold
            confidence_changed = self.adjust_confidence_threshold(
                current_performance=snapshot.win_rate_30d or 50.0
            )
            if confidence_changed:
                actions_triggered["confidence_adjusted"] = True

            # Check strategies for disabling
            for strategy in self.tracker.get_unique_strategies():
                if self.optimizer.should_disable_strategy(strategy):
                    self.optimizer.disable_strategy(
                        strategy,
                        reason=f"Auto-disabled due to poor performance at trade {trade.id}",
                    )
                    actions_triggered["strategies_disabled"].append(strategy)

        # Quick analysis after every losing trade
        if not trade.is_win:
            adjustments = self._analyze_loss(trade)
            actions_triggered["adjustments"].extend(adjustments)

        # Log summary
        if any(actions_triggered.values()):
            logger.info(f"Feedback loop actions: {actions_triggered}")

        return actions_triggered

    def _analyze_loss(self, trade: TradeRecord) -> List[Adjustment]:
        """Quick analysis after a loss to detect immediate issues."""
        adjustments = []

        # Get recent trades for context
        recent = self.tracker.get_recent_trades(limit=20)
        recent_losses = [t for t in recent if not t.is_win]

        # Check if this loss is part of a streak
        loss_streak = 0
        for t in recent:
            if not t.is_win:
                loss_streak += 1
            else:
                break

        if loss_streak >= 3:
            logger.warning(f"Loss streak detected: {loss_streak} consecutive losses")

            # Suggest raising confidence
            adjustment = Adjustment(
                strategy=trade.strategy,
                parameter="min_confidence_threshold",
                current_value=self._current_confidence_threshold,
                suggested_value=min(90, self._current_confidence_threshold + 5),
                reason=f"Loss streak of {loss_streak} trades",
                expected_impact="Reduce trade frequency, improve win rate",
                confidence=0.7,
                priority=1,
            )
            adjustments.append(adjustment)

            if self.on_adjustment_needed:
                self.on_adjustment_needed(adjustment)

        # Check for pattern in this session
        session_trades = [t for t in recent if t.session == trade.session]
        session_losses = [t for t in session_trades if not t.is_win]

        if len(session_trades) >= 3 and len(session_losses) / len(session_trades) > 0.7:
            adjustment = Adjustment(
                strategy=None,
                parameter="session_position_multiplier",
                current_value=1.0,
                suggested_value=0.5,
                reason=f"High loss rate in {trade.session} session",
                expected_impact="Reduce exposure during problematic session",
                confidence=0.65,
                session=trade.session,
                priority=2,
            )
            adjustments.append(adjustment)

        return adjustments

    # =========================================================================
    # Retrain Triggering
    # =========================================================================

    def retrain_trigger(self) -> bool:
        """
        Determine if ML model should be retrained.

        Triggers retraining when:
        - Win rate drops significantly from baseline
        - Sufficient new data since last retrain
        - Strategy decay detected

        Returns:
            True if model should retrain
        """
        # Not enough trades since last check
        if self._trades_since_retrain < self.RETRAIN_MIN_TRADES:
            return False

        # Get current performance
        current_win_rate = self.tracker.get_win_rate(days=14)

        # Set baseline if not set
        if self._baseline_win_rate is None:
            self._baseline_win_rate = current_win_rate
            return False

        # Check for significant drop
        win_rate_drop = self._baseline_win_rate - current_win_rate

        if win_rate_drop >= self.RETRAIN_WIN_RATE_DROP:
            logger.warning(
                f"Retrain triggered: Win rate dropped {win_rate_drop:.1f}% "
                f"(from {self._baseline_win_rate:.1f}% to {current_win_rate:.1f}%)"
            )
            self._reset_retrain_tracking(current_win_rate)
            return True

        # Check strategy decays
        for strategy in self.tracker.get_unique_strategies():
            decay = self.analyzer.calculate_strategy_decay(strategy)
            if decay > 0.4:  # Significant decay
                logger.warning(
                    f"Retrain triggered: Strategy '{strategy}' has decay score {decay:.2f}"
                )
                self._reset_retrain_tracking(current_win_rate)
                return True

        # Check feature importance changes
        if self._detect_feature_importance_shift():
            logger.warning("Retrain triggered: Feature importance shift detected")
            self._reset_retrain_tracking(current_win_rate)
            return True

        return False

    def _reset_retrain_tracking(self, new_baseline: float) -> None:
        """Reset tracking after a retrain trigger."""
        self._trades_since_retrain = 0
        self._baseline_win_rate = new_baseline
        self._last_retrain_check = datetime.utcnow()

    def force_retrain(self, reason: str = "manual") -> None:
        """Force a model retrain."""
        logger.info(f"Forcing retrain: {reason}")
        self._reset_retrain_tracking(self.tracker.get_win_rate(days=14))
        if self.on_retrain_needed:
            self.on_retrain_needed()

    # =========================================================================
    # Feature Importance Tracking
    # =========================================================================

    def update_feature_importance(
        self,
        trade_results: Dict[str, TradeRecord],
    ) -> None:
        """
        Update feature importance tracking based on trade results.

        Args:
            trade_results: Dict mapping trade_id to TradeRecord
        """
        if not trade_results:
            return

        # Collect feature-outcome pairs
        for trade_id, trade in trade_results.items():
            if trade.pnl_percent is None:
                continue

            outcome = 1 if trade.is_win else 0

            for feature, value in trade.features_snapshot.items():
                if not isinstance(value, (int, float)) or np.isnan(value):
                    continue

                if feature not in self._feature_correlation_history:
                    self._feature_correlation_history[feature] = []

                # Store (value, outcome) pairs
                self._feature_correlation_history[feature].append((value, outcome))

                # Keep only last 200 data points per feature
                if len(self._feature_correlation_history[feature]) > 200:
                    self._feature_correlation_history[feature] = \
                        self._feature_correlation_history[feature][-200:]

        # Recalculate importance scores
        self._recalculate_feature_importance()

    def _recalculate_feature_importance(self) -> None:
        """Recalculate feature importance from correlation history."""
        from scipy import stats

        for feature, history in self._feature_correlation_history.items():
            if len(history) < 20:
                continue

            values = [h[0] for h in history]
            outcomes = [h[1] for h in history]

            try:
                # Calculate point-biserial correlation
                corr, p_value = stats.pointbiserialr(outcomes, values)

                if p_value < 0.1:  # Some significance
                    self._feature_importance[feature] = abs(corr)
                else:
                    self._feature_importance[feature] = 0.0
            except (ValueError, TypeError):
                self._feature_importance[feature] = 0.0

        # Persist if session factory available
        if self.session_factory and self._feature_importance:
            self._save_feature_importance()

    def _save_feature_importance(self) -> None:
        """Save feature importance to database."""
        with self.session_factory() as session:
            timestamp = datetime.utcnow()

            for feature, importance in self._feature_importance.items():
                db_record = FeatureImportanceDB(
                    timestamp=timestamp,
                    feature_name=feature,
                    importance_score=importance,
                    sample_size=len(self._feature_correlation_history.get(feature, [])),
                )
                session.add(db_record)

            session.commit()

    def _detect_feature_importance_shift(self) -> bool:
        """
        Detect if feature importance has shifted significantly.

        Compares current importance to historical importance.

        Returns:
            True if significant shift detected
        """
        if not self.session_factory or len(self._feature_importance) < 5:
            return False

        with self.session_factory() as session:
            # Get historical importance from 30 days ago
            cutoff = datetime.utcnow() - timedelta(days=30)

            historical = (
                session.query(FeatureImportanceDB)
                .filter(FeatureImportanceDB.timestamp < cutoff)
                .order_by(FeatureImportanceDB.timestamp.desc())
                .limit(20)
                .all()
            )

            if len(historical) < 10:
                return False

            # Compare top features
            hist_importance = {h.feature_name: h.importance_score for h in historical}

            # Calculate shift
            shifts = []
            for feature, current_imp in self._feature_importance.items():
                if feature in hist_importance:
                    hist_imp = hist_importance[feature]
                    if hist_imp > 0:
                        shift = abs(current_imp - hist_imp) / hist_imp
                        shifts.append(shift)

            if shifts and np.mean(shifts) > 0.3:  # 30% average shift
                return True

        return False

    def get_feature_importance(self) -> Dict[str, float]:
        """Get current feature importance scores."""
        return dict(
            sorted(
                self._feature_importance.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get top N most important features."""
        sorted_features = sorted(
            self._feature_importance.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_features[:n]

    # =========================================================================
    # Confidence Threshold Adjustment
    # =========================================================================

    def adjust_confidence_threshold(
        self,
        current_performance: float,
        target_win_rate: float = 55.0,
    ) -> bool:
        """
        Dynamically adjust confidence threshold based on performance.

        Rules:
        - If losing consistently, raise threshold to be more selective
        - If winning consistently, can lower slightly to capture more trades
        - Never go below baseline or above 90%

        Args:
            current_performance: Current win rate (0-100)
            target_win_rate: Target win rate to aim for

        Returns:
            True if threshold was adjusted
        """
        old_threshold = self._current_confidence_threshold

        # Performance is below target - raise threshold
        if current_performance < target_win_rate - 5:
            adjustment = self.CONFIDENCE_ADJUSTMENT_STEP
            self._current_confidence_threshold = min(
                90.0,
                self._current_confidence_threshold + adjustment,
            )

        # Performance is above target - can lower slightly
        elif current_performance > target_win_rate + 10:
            # Only lower if we've been consistently winning
            recent_snapshots = self._performance_history[-5:]
            if len(recent_snapshots) >= 3:
                recent_avg = np.mean([s.win_rate_7d or 50 for s in recent_snapshots])
                if recent_avg > target_win_rate + 5:
                    adjustment = self.CONFIDENCE_ADJUSTMENT_STEP / 2  # Smaller decrease
                    self._current_confidence_threshold = max(
                        self._baseline_confidence,
                        self._current_confidence_threshold - adjustment,
                    )

        # Log if changed
        if self._current_confidence_threshold != old_threshold:
            logger.info(
                f"Confidence threshold adjusted: {old_threshold:.1f}% -> "
                f"{self._current_confidence_threshold:.1f}% "
                f"(performance: {current_performance:.1f}%)"
            )

            # Create adjustment record
            adjustment = Adjustment(
                strategy=None,
                parameter="min_confidence_threshold",
                current_value=old_threshold,
                suggested_value=self._current_confidence_threshold,
                reason=f"Performance-based adjustment (win rate: {current_performance:.1f}%)",
                expected_impact="Optimize trade selection for target win rate",
                confidence=0.8,
                priority=2,
            )

            self.optimizer.apply_adjustment(adjustment)

            if self.on_adjustment_needed:
                self.on_adjustment_needed(adjustment)

            return True

        return False

    def get_current_confidence_threshold(self) -> float:
        """Get the current dynamic confidence threshold."""
        return self._current_confidence_threshold

    def set_baseline_confidence(self, threshold: float) -> None:
        """Set the baseline confidence threshold."""
        self._baseline_confidence = threshold
        self._current_confidence_threshold = threshold

    # =========================================================================
    # Learning Summary
    # =========================================================================

    def get_learning_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current learning state.

        Returns:
            Dict with learning metrics and status
        """
        return {
            "trades_since_retrain": self._trades_since_retrain,
            "baseline_win_rate": self._baseline_win_rate,
            "current_confidence_threshold": self._current_confidence_threshold,
            "baseline_confidence": self._baseline_confidence,
            "feature_importance": self.get_top_features(5),
            "disabled_strategies": self.optimizer.get_disabled_strategies(),
            "applied_adjustments": len(self.optimizer.get_applied_adjustments()),
            "performance_history_length": len(self._performance_history),
            "last_retrain_check": self._last_retrain_check.isoformat(),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status of the learning system.

        Returns:
            Dict with health indicators
        """
        # Get current metrics
        current_win_rate = self.tracker.get_win_rate(days=7)
        total_pnl = self.tracker.get_total_pnl(days=7)
        sharpe = self.tracker.get_sharpe_ratio(days=30)

        # Determine status
        status = "healthy"
        warnings = []

        if current_win_rate < 40:
            status = "critical"
            warnings.append(f"Win rate critically low: {current_win_rate:.1f}%")
        elif current_win_rate < 50:
            status = "warning"
            warnings.append(f"Win rate below target: {current_win_rate:.1f}%")

        if total_pnl < 0:
            if status == "healthy":
                status = "warning"
            warnings.append(f"Negative PnL this week: ${total_pnl:,.2f}")

        if sharpe and sharpe < 0.5:
            if status == "healthy":
                status = "warning"
            warnings.append(f"Low Sharpe ratio: {sharpe:.2f}")

        # Check for stale learning
        hours_since_check = (
            datetime.utcnow() - self._last_retrain_check
        ).total_seconds() / 3600

        if hours_since_check > 168:  # 1 week
            warnings.append(f"No retrain check in {hours_since_check:.0f} hours")

        return {
            "status": status,
            "warnings": warnings,
            "current_win_rate": current_win_rate,
            "weekly_pnl": total_pnl,
            "sharpe_ratio": sharpe,
            "confidence_threshold": self._current_confidence_threshold,
            "disabled_strategies": len(self.optimizer.get_disabled_strategies()),
        }

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def initialize(self, baseline_win_rate: Optional[float] = None) -> None:
        """
        Initialize the feedback loop with baseline metrics.

        Call this when starting the trading system.

        Args:
            baseline_win_rate: Optional baseline to use (will calculate if not provided)
        """
        if baseline_win_rate is not None:
            self._baseline_win_rate = baseline_win_rate
        else:
            self._baseline_win_rate = self.tracker.get_win_rate(days=30)

        # Load recent performance history
        self._performance_history = self.tracker.get_snapshot_history(days=30)

        # Load feature importance from DB
        if self.session_factory:
            self._load_feature_importance()

        logger.info(
            f"Feedback loop initialized: baseline_win_rate={self._baseline_win_rate:.1f}%, "
            f"confidence_threshold={self._current_confidence_threshold:.1f}%"
        )

    def _load_feature_importance(self) -> None:
        """Load recent feature importance from database."""
        with self.session_factory() as session:
            recent = (
                session.query(FeatureImportanceDB)
                .order_by(FeatureImportanceDB.timestamp.desc())
                .limit(50)
                .all()
            )

            for record in recent:
                if record.feature_name not in self._feature_importance:
                    self._feature_importance[record.feature_name] = record.importance_score

    def shutdown(self) -> None:
        """
        Clean shutdown of the feedback loop.

        Persists current state and generates final report.
        """
        logger.info("Shutting down feedback loop...")

        # Save final feature importance
        if self.session_factory and self._feature_importance:
            self._save_feature_importance()

        # Create final snapshot
        try:
            self.tracker.create_performance_snapshot()
        except Exception as e:
            logger.error(f"Error creating final snapshot: {e}")

        logger.info("Feedback loop shutdown complete")
