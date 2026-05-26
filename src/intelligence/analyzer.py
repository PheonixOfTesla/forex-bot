from __future__ import annotations

"""
Pattern Analyzer for Trade Performance

Analyzes winning and losing trades to identify patterns,
correlations, and conditions that affect trading outcomes.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .models import (
    ActionType,
    FailurePattern,
    FailurePatternDB,
    LossAnalysis,
    PatternType,
    TradeRecord,
    WinAnalysis,
)
from .tracker import TradeTracker

logger = logging.getLogger(__name__)


class TradeAnalyzer:
    """
    Pattern Analyzer for Trade Performance

    Identifies patterns in winning and losing trades to enable
    learning and improvement.
    """

    # Thresholds for pattern detection
    MIN_PATTERN_FREQUENCY = 0.6  # 60% occurrence to be a pattern
    MIN_PATTERN_CONFIDENCE = 0.7  # 70% confidence threshold
    MIN_SAMPLE_SIZE = 10  # Minimum trades to analyze
    CORRELATION_THRESHOLD = 0.3  # Minimum correlation to report

    def __init__(self, tracker: TradeTracker, session_factory=None):
        """
        Initialize the analyzer.

        Args:
            tracker: TradeTracker instance for data access
            session_factory: Optional SQLAlchemy session factory for persistence
        """
        self.tracker = tracker
        self.session_factory = session_factory

    # =========================================================================
    # Loss Analysis
    # =========================================================================

    def analyze_losses(
        self,
        trades: Optional[List[TradeRecord]] = None,
        days: int = 30,
    ) -> LossAnalysis:
        """
        Analyze losing trades to identify common factors.

        Args:
            trades: Optional list of trades to analyze (defaults to recent)
            days: Days to look back if trades not provided

        Returns:
            LossAnalysis with identified patterns and metrics
        """
        if trades is None:
            trades = self.tracker.get_trade_history(days=days)

        losses = [t for t in trades if t.is_closed and not t.is_win]

        if not losses:
            return LossAnalysis(
                total_losses=0,
                total_loss_amount=0,
                avg_loss=0,
                analysis_start=datetime.utcnow() - timedelta(days=days),
                analysis_end=datetime.utcnow(),
            )

        # Basic metrics
        total_loss_amount = sum(abs(t.pnl or 0) for t in losses)
        avg_loss = total_loss_amount / len(losses)

        # Time patterns
        loss_hours = [t.timestamp.hour for t in losses]
        loss_days = [t.timestamp.weekday() for t in losses]
        loss_sessions = [t.session for t in losses if t.session]

        worst_hours = self._find_overrepresented(loss_hours, losses, trades)
        worst_days = self._find_overrepresented(loss_days, losses, trades)
        worst_sessions = self._find_overrepresented(loss_sessions, losses, trades)

        # Strategy breakdown
        losses_by_strategy = Counter(t.strategy for t in losses)
        loss_amount_by_strategy = defaultdict(float)
        for t in losses:
            loss_amount_by_strategy[t.strategy] += abs(t.pnl or 0)

        # Common features in losing trades
        common_features = self._analyze_common_features(losses)

        # Market conditions during losses
        market_conditions = self._analyze_market_conditions(losses)

        # Identify patterns
        patterns = self._detect_loss_patterns(losses, trades)

        return LossAnalysis(
            total_losses=len(losses),
            total_loss_amount=total_loss_amount,
            avg_loss=avg_loss,
            common_features=common_features,
            worst_hours=worst_hours,
            worst_days=worst_days,
            worst_sessions=worst_sessions,
            market_conditions=market_conditions,
            losses_by_strategy=dict(losses_by_strategy),
            loss_amount_by_strategy=dict(loss_amount_by_strategy),
            patterns=patterns,
            analysis_start=min(t.timestamp for t in losses) if losses else None,
            analysis_end=max(t.timestamp for t in losses) if losses else None,
        )

    def _find_overrepresented(
        self,
        values: List[Any],
        subset: List[TradeRecord],
        full_set: List[TradeRecord],
        min_ratio: float = 1.5,
    ) -> List[Any]:
        """
        Find values that are overrepresented in subset vs full set.

        A value is overrepresented if it occurs 1.5x more frequently
        in the subset than in the full set.
        """
        if not values or len(full_set) < 10:
            return []

        subset_counts = Counter(values)
        subset_total = len(values)

        # Get same values from full set
        all_values = []
        for attr in ["timestamp", "session"]:
            if hasattr(full_set[0], attr):
                if attr == "timestamp":
                    if isinstance(values[0], int) and max(values) <= 23:  # Hours
                        all_values = [t.timestamp.hour for t in full_set]
                    elif isinstance(values[0], int) and max(values) <= 6:  # Weekdays
                        all_values = [t.timestamp.weekday() for t in full_set]
                else:
                    all_values = [getattr(t, attr) for t in full_set if getattr(t, attr)]
                break

        if not all_values:
            return []

        full_counts = Counter(all_values)
        full_total = len(all_values)

        overrepresented = []
        for value, count in subset_counts.items():
            subset_ratio = count / subset_total
            full_ratio = full_counts.get(value, 0) / full_total if full_total > 0 else 0

            if full_ratio > 0 and subset_ratio / full_ratio >= min_ratio:
                overrepresented.append(value)

        return overrepresented

    def _analyze_common_features(
        self,
        trades: List[TradeRecord],
    ) -> Dict[str, Any]:
        """Analyze common features in a set of trades."""
        if not trades:
            return {}

        # Collect feature values
        feature_values = defaultdict(list)

        for trade in trades:
            for key, value in trade.features_snapshot.items():
                if isinstance(value, (int, float)) and not np.isnan(value):
                    feature_values[key].append(value)

        # Calculate statistics
        common = {}
        for feature, values in feature_values.items():
            if len(values) >= 5:
                common[feature] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "median": np.median(values),
                }

        return common

    def _analyze_market_conditions(
        self,
        trades: List[TradeRecord],
    ) -> Dict[str, Any]:
        """Analyze market conditions during trades."""
        if not trades:
            return {}

        conditions = defaultdict(list)

        for trade in trades:
            for key, value in trade.market_conditions.items():
                if isinstance(value, (int, float)) and not np.isnan(value):
                    conditions[key].append(value)
                elif isinstance(value, str):
                    conditions[f"{key}_mode"].append(value)

        result = {}

        # Numeric conditions
        for key, values in conditions.items():
            if "_mode" not in key and values:
                result[key] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                }

        # Categorical conditions
        for key, values in conditions.items():
            if "_mode" in key and values:
                mode_counts = Counter(values)
                result[key] = dict(mode_counts.most_common(3))

        return result

    def _detect_loss_patterns(
        self,
        losses: List[TradeRecord],
        all_trades: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect patterns in losing trades."""
        patterns = []

        if len(losses) < self.MIN_SAMPLE_SIZE:
            return patterns

        loss_rate = len(losses) / len(all_trades) if all_trades else 0

        # Pattern 1: Session-based losses
        session_patterns = self._detect_session_patterns(losses, all_trades)
        patterns.extend(session_patterns)

        # Pattern 2: Time-based losses
        time_patterns = self._detect_time_patterns(losses, all_trades)
        patterns.extend(time_patterns)

        # Pattern 3: Strategy degradation
        strategy_patterns = self._detect_strategy_issues(losses, all_trades)
        patterns.extend(strategy_patterns)

        # Pattern 4: Volatility-related losses
        volatility_patterns = self._detect_volatility_patterns(losses)
        patterns.extend(volatility_patterns)

        # Pattern 5: Confidence threshold issues
        confidence_patterns = self._detect_confidence_issues(losses, all_trades)
        patterns.extend(confidence_patterns)

        return patterns

    def _detect_session_patterns(
        self,
        losses: List[TradeRecord],
        all_trades: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect session-specific loss patterns."""
        patterns = []

        sessions = ["london", "new_york", "asia", "overlap"]
        for session in sessions:
            session_losses = [t for t in losses if t.session == session]
            session_all = [t for t in all_trades if t.session == session]

            if len(session_all) >= 5:
                session_loss_rate = len(session_losses) / len(session_all)
                overall_loss_rate = len(losses) / len(all_trades) if all_trades else 0

                # If loss rate in this session is significantly higher
                if session_loss_rate > overall_loss_rate * 1.5 and session_loss_rate > 0.6:
                    patterns.append(
                        FailurePattern(
                            pattern_type=PatternType.SESSION,
                            description=f"Loss rate of {session_loss_rate:.1%} during {session} session "
                                      f"is {session_loss_rate/overall_loss_rate:.1f}x higher than average",
                            frequency=session_loss_rate,
                            affected_trades_count=len(session_losses),
                            suggested_action=ActionType.AVOID_SESSION,
                            confidence_score=min(0.9, len(session_all) / 20),
                            affected_trade_ids=[t.id for t in session_losses],
                            additional_data={"session": session},
                        )
                    )

        return patterns

    def _detect_time_patterns(
        self,
        losses: List[TradeRecord],
        all_trades: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect time-based loss patterns."""
        patterns = []

        # Analyze by hour
        hour_losses = Counter(t.timestamp.hour for t in losses)
        hour_all = Counter(t.timestamp.hour for t in all_trades)

        for hour, loss_count in hour_losses.items():
            total = hour_all.get(hour, 0)
            if total >= 5:
                loss_rate = loss_count / total
                if loss_rate > 0.7:  # More than 70% losses in this hour
                    patterns.append(
                        FailurePattern(
                            pattern_type=PatternType.TIME_BASED,
                            description=f"Loses {loss_rate:.0%} of trades at {hour:02d}:00 UTC",
                            frequency=loss_rate,
                            affected_trades_count=loss_count,
                            suggested_action=ActionType.ADJUST_PARAMETERS,
                            confidence_score=min(0.85, total / 15),
                            additional_data={"hour": hour, "loss_count": loss_count},
                        )
                    )

        # Analyze by day of week
        day_losses = Counter(t.timestamp.weekday() for t in losses)
        day_all = Counter(t.timestamp.weekday() for t in all_trades)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day, loss_count in day_losses.items():
            total = day_all.get(day, 0)
            if total >= 5:
                loss_rate = loss_count / total
                if loss_rate > 0.7:
                    patterns.append(
                        FailurePattern(
                            pattern_type=PatternType.TIME_BASED,
                            description=f"Loses {loss_rate:.0%} of trades on {day_names[day]}s",
                            frequency=loss_rate,
                            affected_trades_count=loss_count,
                            suggested_action=ActionType.ADJUST_PARAMETERS,
                            confidence_score=min(0.85, total / 15),
                            additional_data={"weekday": day, "day_name": day_names[day]},
                        )
                    )

        return patterns

    def _detect_strategy_issues(
        self,
        losses: List[TradeRecord],
        all_trades: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect strategy-specific issues."""
        patterns = []

        strategies = set(t.strategy for t in all_trades)

        for strategy in strategies:
            strategy_losses = [t for t in losses if t.strategy == strategy]
            strategy_all = [t for t in all_trades if t.strategy == strategy]

            if len(strategy_all) >= 10:
                loss_rate = len(strategy_losses) / len(strategy_all)

                # Check if strategy is significantly underperforming
                if loss_rate > 0.6:  # More than 60% losses
                    patterns.append(
                        FailurePattern(
                            pattern_type=PatternType.STRATEGY_SPECIFIC,
                            description=f"Strategy '{strategy}' has {loss_rate:.0%} loss rate over last {len(strategy_all)} trades",
                            frequency=loss_rate,
                            affected_trades_count=len(strategy_losses),
                            suggested_action=ActionType.DISABLE_STRATEGY if loss_rate > 0.7 else ActionType.ADJUST_PARAMETERS,
                            confidence_score=min(0.9, len(strategy_all) / 20),
                            affected_trade_ids=[t.id for t in strategy_losses],
                            additional_data={"strategy": strategy},
                        )
                    )

        return patterns

    def _detect_volatility_patterns(
        self,
        losses: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect volatility-related loss patterns."""
        patterns = []

        # Extract ATR from features if available
        atr_values = []
        for trade in losses:
            atr = trade.features_snapshot.get("atr_14") or trade.market_conditions.get("atr")
            if atr:
                atr_values.append(atr)

        if len(atr_values) >= 10:
            mean_atr = np.mean(atr_values)
            # High volatility losses
            high_vol_losses = [v for v in atr_values if v > mean_atr * 1.5]

            if len(high_vol_losses) > len(atr_values) * 0.4:  # 40%+ losses in high volatility
                patterns.append(
                    FailurePattern(
                        pattern_type=PatternType.VOLATILITY,
                        description=f"40%+ of losses occur during high volatility (ATR > {mean_atr*1.5:.5f})",
                        frequency=len(high_vol_losses) / len(atr_values),
                        affected_trades_count=len(high_vol_losses),
                        suggested_action=ActionType.REDUCE_POSITION_SIZE,
                        confidence_score=0.75,
                        additional_data={"mean_atr": mean_atr, "threshold": mean_atr * 1.5},
                    )
                )

        return patterns

    def _detect_confidence_issues(
        self,
        losses: List[TradeRecord],
        all_trades: List[TradeRecord],
    ) -> List[FailurePattern]:
        """Detect issues with confidence threshold."""
        patterns = []

        if len(losses) < 10:
            return patterns

        # Analyze losses by confidence band
        confidence_bands = [
            (60, 70),
            (70, 80),
            (80, 90),
            (90, 100),
        ]

        for low, high in confidence_bands:
            band_losses = [t for t in losses if low <= t.confidence < high]
            band_all = [t for t in all_trades if low <= t.confidence < high]

            if len(band_all) >= 5:
                band_loss_rate = len(band_losses) / len(band_all)

                # Low confidence trades losing more than expected
                if low < 75 and band_loss_rate > 0.6:
                    patterns.append(
                        FailurePattern(
                            pattern_type=PatternType.STRATEGY_SPECIFIC,
                            description=f"Trades with {low}-{high}% confidence have {band_loss_rate:.0%} loss rate - "
                                      f"consider raising minimum confidence threshold",
                            frequency=band_loss_rate,
                            affected_trades_count=len(band_losses),
                            suggested_action=ActionType.INCREASE_CONFIDENCE_THRESHOLD,
                            confidence_score=0.8,
                            additional_data={
                                "confidence_band": f"{low}-{high}",
                                "suggested_min_confidence": high,
                            },
                        )
                    )

        return patterns

    # =========================================================================
    # Win Analysis
    # =========================================================================

    def analyze_wins(
        self,
        trades: Optional[List[TradeRecord]] = None,
        days: int = 30,
    ) -> WinAnalysis:
        """
        Analyze winning trades to identify success factors.

        Args:
            trades: Optional list of trades to analyze
            days: Days to look back if trades not provided

        Returns:
            WinAnalysis with identified success patterns
        """
        if trades is None:
            trades = self.tracker.get_trade_history(days=days)

        wins = [t for t in trades if t.is_closed and t.is_win]

        if not wins:
            return WinAnalysis(
                total_wins=0,
                total_win_amount=0,
                avg_win=0,
                analysis_start=datetime.utcnow() - timedelta(days=days),
                analysis_end=datetime.utcnow(),
            )

        # Basic metrics
        total_win_amount = sum(t.pnl or 0 for t in wins)
        avg_win = total_win_amount / len(wins)

        # Time patterns
        win_hours = [t.timestamp.hour for t in wins]
        win_days = [t.timestamp.weekday() for t in wins]
        win_sessions = [t.session for t in wins if t.session]

        best_hours = self._find_overrepresented(win_hours, wins, trades)
        best_days = self._find_overrepresented(win_days, wins, trades)
        best_sessions = self._find_overrepresented(win_sessions, wins, trades)

        # Strategy breakdown
        wins_by_strategy = Counter(t.strategy for t in wins)
        win_amount_by_strategy = defaultdict(float)
        for t in wins:
            win_amount_by_strategy[t.strategy] += t.pnl or 0

        # Common features
        common_features = self._analyze_common_features(wins)

        # Market conditions
        market_conditions = self._analyze_market_conditions(wins)

        # Win characteristics
        avg_confidence = sum(t.confidence for t in wins) / len(wins)
        durations = [t.duration_minutes for t in wins if t.duration_minutes]
        avg_duration = sum(durations) / len(durations) if durations else 0
        hit_target_rate = sum(1 for t in wins if t.hit_target) / len(wins)

        return WinAnalysis(
            total_wins=len(wins),
            total_win_amount=total_win_amount,
            avg_win=avg_win,
            common_features=common_features,
            best_hours=best_hours,
            best_days=best_days,
            best_sessions=best_sessions,
            market_conditions=market_conditions,
            wins_by_strategy=dict(wins_by_strategy),
            win_amount_by_strategy=dict(win_amount_by_strategy),
            avg_confidence_on_wins=avg_confidence,
            avg_duration_minutes=avg_duration,
            hit_target_rate=hit_target_rate,
            analysis_start=min(t.timestamp for t in wins) if wins else None,
            analysis_end=max(t.timestamp for t in wins) if wins else None,
        )

    # =========================================================================
    # Failure Pattern Detection
    # =========================================================================

    def find_failure_patterns(
        self,
        days: int = 30,
        min_confidence: float = 0.6,
    ) -> List[FailurePattern]:
        """
        Find all significant failure patterns in recent trading.

        Args:
            days: Days to analyze
            min_confidence: Minimum confidence score to include pattern

        Returns:
            List of FailurePattern objects sorted by confidence
        """
        trades = self.tracker.get_trade_history(days=days)
        losses = [t for t in trades if t.is_closed and not t.is_win]

        if len(trades) < self.MIN_SAMPLE_SIZE:
            return []

        # Detect all pattern types
        all_patterns = self._detect_loss_patterns(losses, trades)

        # Filter by confidence and sort
        patterns = [p for p in all_patterns if p.confidence_score >= min_confidence]
        patterns.sort(key=lambda p: p.confidence_score, reverse=True)

        # Persist patterns
        if self.session_factory:
            self._save_patterns(patterns)

        return patterns

    def _save_patterns(self, patterns: List[FailurePattern]) -> None:
        """Save detected patterns to database."""
        if not self.session_factory:
            return

        with self.session_factory() as session:
            for pattern in patterns:
                db_pattern = FailurePatternDB(
                    detected_at=pattern.detected_at,
                    pattern_type=pattern.pattern_type,
                    description=pattern.description,
                    frequency=pattern.frequency,
                    affected_trades_count=pattern.affected_trades_count,
                    affected_trade_ids=pattern.affected_trade_ids,
                    suggested_action=pattern.suggested_action,
                    confidence_score=pattern.confidence_score,
                    additional_data=pattern.additional_data,
                    is_active=True,
                )
                session.add(db_pattern)

            session.commit()

    # =========================================================================
    # Strategy Decay Detection
    # =========================================================================

    def calculate_strategy_decay(
        self,
        strategy: str,
        window: int = 50,
    ) -> float:
        """
        Detect if a strategy is degrading over time.

        Uses a sliding window to compare recent performance
        to historical performance.

        Args:
            strategy: Strategy name to analyze
            window: Number of trades to consider

        Returns:
            Decay score: negative = improving, 0 = stable, positive = degrading
            Scale: -1 to 1 (1 = completely degraded)
        """
        trades = self.tracker.get_trade_history(days=90, strategy=strategy)

        if len(trades) < window * 2:
            return 0.0

        # Sort by timestamp (oldest first)
        trades.sort(key=lambda t: t.timestamp)

        # Split into historical and recent
        mid = len(trades) // 2
        historical = trades[:mid]
        recent = trades[mid:]

        # Calculate win rates
        historical_wins = sum(1 for t in historical if t.is_win)
        historical_wr = historical_wins / len(historical) if historical else 0

        recent_wins = sum(1 for t in recent if t.is_win)
        recent_wr = recent_wins / len(recent) if recent else 0

        # Calculate PnL
        historical_pnl = sum(t.pnl_percent or 0 for t in historical)
        recent_pnl = sum(t.pnl_percent or 0 for t in recent)

        # Combine metrics
        wr_decay = historical_wr - recent_wr  # Positive = degrading
        pnl_decay = 0.0

        if historical_pnl != 0:
            pnl_decay = (historical_pnl - recent_pnl) / abs(historical_pnl)
            pnl_decay = max(-1, min(1, pnl_decay))  # Clamp to [-1, 1]

        # Combined decay score (weighted average)
        decay_score = (wr_decay * 0.6) + (pnl_decay * 0.4)

        logger.info(
            f"Strategy decay for {strategy}: WR {historical_wr:.1%} -> {recent_wr:.1%}, "
            f"decay score: {decay_score:.2f}"
        )

        return decay_score

    # =========================================================================
    # Correlation Analysis
    # =========================================================================

    def correlation_analysis(
        self,
        days: int = 30,
    ) -> Dict[str, float]:
        """
        Analyze which features correlate most with wins/losses.

        Returns:
            Dict mapping feature names to correlation with PnL
        """
        trades = self.tracker.get_trade_history(days=days)

        if len(trades) < 20:
            return {}

        # Extract features and outcomes
        features_data = defaultdict(list)
        pnl_data = []

        for trade in trades:
            if trade.pnl_percent is not None:
                pnl_data.append(trade.pnl_percent)

                # Add trade-level features
                features_data["confidence"].append(trade.confidence)
                features_data["duration_minutes"].append(trade.duration_minutes or 0)

                # Add technical features
                for key, value in trade.features_snapshot.items():
                    if isinstance(value, (int, float)) and not np.isnan(value):
                        features_data[key].append(value)

        if not pnl_data:
            return {}

        # Calculate correlations
        correlations = {}

        for feature, values in features_data.items():
            if len(values) == len(pnl_data) and len(set(values)) > 1:
                try:
                    corr, p_value = stats.pearsonr(values, pnl_data)

                    if abs(corr) >= self.CORRELATION_THRESHOLD and p_value < 0.05:
                        correlations[feature] = round(corr, 3)
                except (ValueError, TypeError):
                    continue

        # Sort by absolute correlation
        correlations = dict(
            sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        )

        logger.info(f"Feature correlations with PnL: {correlations}")

        return correlations

    def get_feature_importance_trend(
        self,
        feature: str,
        days: int = 90,
        window: int = 7,
    ) -> List[Tuple[datetime, float]]:
        """
        Track how a feature's predictive power changes over time.

        Args:
            feature: Feature name to track
            days: Total days to analyze
            window: Rolling window size in days

        Returns:
            List of (date, correlation) tuples
        """
        trades = self.tracker.get_trade_history(days=days)

        if len(trades) < 30:
            return []

        # Sort by date
        trades.sort(key=lambda t: t.timestamp)

        # Group by day
        daily_trades = defaultdict(list)
        for trade in trades:
            day = trade.timestamp.date()
            daily_trades[day].append(trade)

        # Calculate rolling correlations
        results = []
        dates = sorted(daily_trades.keys())

        for i in range(window, len(dates)):
            window_dates = dates[i - window:i]
            window_trades = []
            for d in window_dates:
                window_trades.extend(daily_trades[d])

            if len(window_trades) >= 10:
                # Extract feature and PnL
                features = []
                pnls = []

                for t in window_trades:
                    val = t.features_snapshot.get(feature)
                    if val is not None and t.pnl_percent is not None:
                        features.append(val)
                        pnls.append(t.pnl_percent)

                if len(features) >= 5 and len(set(features)) > 1:
                    try:
                        corr, _ = stats.pearsonr(features, pnls)
                        results.append((
                            datetime.combine(dates[i], datetime.min.time()),
                            round(corr, 3),
                        ))
                    except (ValueError, TypeError):
                        pass

        return results

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_active_patterns(self) -> List[FailurePattern]:
        """Get all currently active failure patterns from the database."""
        if not self.session_factory:
            return []

        with self.session_factory() as session:
            db_patterns = (
                session.query(FailurePatternDB)
                .filter(FailurePatternDB.is_active == True)
                .order_by(FailurePatternDB.confidence_score.desc())
                .all()
            )

            return [
                FailurePattern(
                    pattern_type=p.pattern_type,
                    description=p.description,
                    frequency=p.frequency,
                    affected_trades_count=p.affected_trades_count,
                    suggested_action=p.suggested_action,
                    confidence_score=p.confidence_score,
                    affected_trade_ids=p.affected_trade_ids or [],
                    additional_data=p.additional_data or {},
                    detected_at=p.detected_at,
                    is_active=p.is_active,
                )
                for p in db_patterns
            ]

    def mark_pattern_resolved(self, pattern_id: int) -> None:
        """Mark a failure pattern as resolved."""
        if not self.session_factory:
            return

        with self.session_factory() as session:
            pattern = session.query(FailurePatternDB).filter_by(id=pattern_id).first()
            if pattern:
                pattern.is_active = False
                pattern.resolved_at = datetime.utcnow()
                session.commit()
