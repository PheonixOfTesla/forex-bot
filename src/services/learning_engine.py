from __future__ import annotations

"""
Learning Engine for Lightning Trading Bot

The brain that learns from paper trading results. Tracks signal accuracy,
identifies what indicator combinations work best, and provides feedback
to adjust future signal confidence.
"""

import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models.learning import (
    AccuracyResponse,
    Direction,
    IndicatorCombination,
    IndicatorPerformanceResponse,
    IndicatorWeight,
    InsightsResponse,
    LearningInsight,
    LearningMetrics,
    PairPerformance,
    PredictionOutcome,
    RecordOutcomeRequest,
    SetupPerformance,
    TimeframePerformance,
    TradeOutcome,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Storage Path
# =============================================================================

DATA_DIR = Path(__file__).parent.parent.parent / "data"
LEARNING_HISTORY_FILE = DATA_DIR / "learning_history.json"


# =============================================================================
# Learning Engine Class
# =============================================================================


class LearningEngine:
    """
    The learning engine tracks prediction outcomes and learns what works.

    Key responsibilities:
    1. Record prediction outcomes (wins/losses) when paper trades close
    2. Calculate accuracy per pair, timeframe, and indicator combination
    3. Track which indicator combinations lead to wins vs losses
    4. Provide confidence adjustments based on learned patterns
    5. Generate insights about trading performance
    """

    def __init__(self):
        """Initialize the learning engine."""
        self._outcomes: List[PredictionOutcome] = []
        self._indicator_weights: Dict[str, IndicatorWeight] = {}
        self._indicator_combinations: Dict[str, IndicatorCombination] = {}
        self._pair_performance: Dict[str, PairPerformance] = {}
        self._timeframe_performance: Dict[str, TimeframePerformance] = {}
        self._metrics: Optional[LearningMetrics] = None

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load_history()

        logger.info(
            f"LearningEngine initialized with {len(self._outcomes)} historical outcomes"
        )

    # =========================================================================
    # Core Tracking Methods
    # =========================================================================

    def track_prediction(
        self,
        signal_id: str,
        predicted_direction: str,
        predicted_confidence: float,
        actual_outcome: str,
        pair: str,
        entry_price: float,
        exit_price: float,
        entry_timestamp: datetime,
        exit_timestamp: datetime,
        indicators_used: List[str] = None,
        indicator_values: Dict[str, float] = None,
        strategy: str = None,
        timeframe: str = "1H",
        market_conditions: str = None,
        session: str = None,
    ) -> PredictionOutcome:
        """
        Track a prediction outcome when a paper trade closes.

        This is the main entry point for learning. Every time a paper trade
        completes, call this method to record whether the prediction was correct.

        Args:
            signal_id: The original signal ID
            predicted_direction: The predicted direction (buy/sell)
            predicted_confidence: The confidence score (0-100)
            actual_outcome: The actual outcome (win/loss/breakeven)
            pair: Trading pair
            entry_price: Entry price
            exit_price: Exit price
            entry_timestamp: When trade was entered
            exit_timestamp: When trade was closed
            indicators_used: List of indicator names used
            indicator_values: Dict of indicator name -> value
            strategy: Strategy name
            timeframe: Analysis timeframe
            market_conditions: Market conditions at time
            session: Trading session

        Returns:
            The recorded PredictionOutcome
        """
        indicators_used = indicators_used or []
        indicator_values = indicator_values or {}

        # Calculate profit in pips
        profit_pips = self._calculate_pips(pair, entry_price, exit_price, predicted_direction)

        # Normalize direction
        direction = Direction(predicted_direction.lower())

        # Normalize outcome
        outcome = TradeOutcome(actual_outcome.lower())

        # Calculate profit percent
        if entry_price > 0:
            if direction in [Direction.BUY, Direction.LONG]:
                profit_percent = ((exit_price - entry_price) / entry_price) * 100
            else:
                profit_percent = ((entry_price - exit_price) / entry_price) * 100
        else:
            profit_percent = 0.0

        # Create outcome record
        prediction_outcome = PredictionOutcome(
            signal_id=signal_id,
            pair=pair,
            direction=direction,
            confidence=predicted_confidence,
            entry_price=entry_price,
            exit_price=exit_price,
            outcome=outcome,
            profit_pips=profit_pips,
            profit_percent=profit_percent,
            indicators_used=indicators_used,
            indicator_values=indicator_values,
            strategy=strategy,
            timeframe=timeframe,
            entry_timestamp=entry_timestamp,
            exit_timestamp=exit_timestamp,
            market_conditions=market_conditions,
            session=session,
        )

        # Store the outcome
        self._outcomes.append(prediction_outcome)

        # Update statistics
        self._update_indicator_weights(prediction_outcome)
        self._update_indicator_combinations(prediction_outcome)
        self._update_pair_performance(prediction_outcome)
        self._update_timeframe_performance(prediction_outcome)

        # Persist to disk
        self._save_history()

        logger.info(
            f"Tracked prediction: {signal_id} {pair} {direction.value} -> {outcome.value} "
            f"({profit_pips:+.1f} pips)"
        )

        return prediction_outcome

    def record_outcome(self, request: RecordOutcomeRequest) -> PredictionOutcome:
        """
        Record an outcome from API request.

        Convenience method that takes a request object.
        """
        # Determine outcome based on entry/exit prices and direction
        if request.direction in [Direction.BUY, Direction.LONG]:
            profit = request.exit_price - request.entry_price
        else:
            profit = request.entry_price - request.exit_price

        # Determine outcome
        pip_value = self._get_pip_value(request.pair)
        profit_pips = profit / pip_value

        if profit_pips > 2:  # More than 2 pips profit = win
            outcome = "win"
        elif profit_pips < -2:  # More than 2 pips loss = loss
            outcome = "loss"
        else:
            outcome = "breakeven"

        return self.track_prediction(
            signal_id=request.signal_id,
            predicted_direction=request.direction.value,
            predicted_confidence=request.confidence,
            actual_outcome=outcome,
            pair=request.pair,
            entry_price=request.entry_price,
            exit_price=request.exit_price,
            entry_timestamp=request.entry_timestamp,
            exit_timestamp=request.exit_timestamp,
            indicators_used=request.indicators_used,
            indicator_values=request.indicator_values,
            strategy=request.strategy,
            timeframe=request.timeframe,
            market_conditions=request.market_conditions,
            session=request.session,
        )

    # =========================================================================
    # Accuracy Calculation Methods
    # =========================================================================

    def get_accuracy_stats(self) -> AccuracyResponse:
        """
        Get overall and per-pair accuracy statistics.

        Returns comprehensive accuracy breakdown.
        """
        if not self._outcomes:
            return AccuracyResponse(
                overall_accuracy=0.0,
                total_predictions=0,
                by_pair={},
                by_timeframe={},
                by_direction={},
            )

        # Overall accuracy
        wins = sum(1 for o in self._outcomes if o.outcome == TradeOutcome.WIN)
        total = len(self._outcomes)
        overall_accuracy = (wins / total) * 100 if total > 0 else 0.0

        # By pair
        by_pair = {}
        for pair, perf in self._pair_performance.items():
            by_pair[pair] = {
                "accuracy": perf.win_rate,
                "total": perf.total_trades,
                "wins": perf.wins,
                "losses": perf.losses,
                "avg_profit_pips": perf.avg_profit_pips,
            }

        # By timeframe
        by_timeframe = {}
        for tf, perf in self._timeframe_performance.items():
            by_timeframe[tf] = {
                "accuracy": perf.win_rate,
                "total": perf.total_trades,
                "wins": perf.wins,
                "losses": perf.losses,
                "avg_profit_pips": perf.avg_profit_pips,
            }

        # By direction
        buy_outcomes = [o for o in self._outcomes if o.direction in [Direction.BUY, Direction.LONG]]
        sell_outcomes = [o for o in self._outcomes if o.direction in [Direction.SELL, Direction.SHORT]]

        buy_wins = sum(1 for o in buy_outcomes if o.outcome == TradeOutcome.WIN)
        sell_wins = sum(1 for o in sell_outcomes if o.outcome == TradeOutcome.WIN)

        by_direction = {
            "buy": {
                "accuracy": (buy_wins / len(buy_outcomes) * 100) if buy_outcomes else 0.0,
                "total": len(buy_outcomes),
                "wins": buy_wins,
            },
            "sell": {
                "accuracy": (sell_wins / len(sell_outcomes) * 100) if sell_outcomes else 0.0,
                "total": len(sell_outcomes),
                "wins": sell_wins,
            },
        }

        # Calculate trends
        accuracy_trend_7d = self._calculate_accuracy_trend(days=7)
        accuracy_trend_30d = self._calculate_accuracy_trend(days=30)

        return AccuracyResponse(
            overall_accuracy=round(overall_accuracy, 2),
            total_predictions=total,
            by_pair=by_pair,
            by_timeframe=by_timeframe,
            by_direction=by_direction,
            accuracy_trend_7d=accuracy_trend_7d,
            accuracy_trend_30d=accuracy_trend_30d,
        )

    def get_indicator_performance(self) -> IndicatorPerformanceResponse:
        """
        Get indicator performance statistics.

        Returns which indicators are performing best.
        """
        indicators = list(self._indicator_weights.values())
        indicators.sort(key=lambda x: x.win_rate, reverse=True)

        # Get best and worst combinations
        combinations = list(self._indicator_combinations.values())
        combinations.sort(key=lambda x: x.win_rate, reverse=True)

        best_combinations = combinations[:5] if len(combinations) >= 5 else combinations
        worst_combinations = combinations[-5:][::-1] if len(combinations) >= 5 else []

        # Calculate recommended weights
        recommended_weights = {}
        for ind in indicators:
            if ind.total_signals >= 5:  # Only recommend if enough data
                # Weight based on relative performance
                # Win rate above 50% gets boost, below gets penalty
                base_weight = 1.0
                if ind.win_rate > 50:
                    boost = (ind.win_rate - 50) / 50  # 0-1 range
                    base_weight += boost * 0.5  # Max 1.5
                else:
                    penalty = (50 - ind.win_rate) / 50  # 0-1 range
                    base_weight -= penalty * 0.5  # Min 0.5

                recommended_weights[ind.indicator_name] = round(
                    max(0.5, min(1.5, base_weight)), 2
                )

        return IndicatorPerformanceResponse(
            indicators=indicators,
            best_combinations=best_combinations,
            worst_combinations=worst_combinations,
            recommended_weights=recommended_weights,
        )

    def get_confidence_adjustment(
        self,
        pair: str,
        indicators_used: List[str],
        timeframe: str = "1H",
    ) -> float:
        """
        Get confidence adjustment factor based on learned patterns.

        This is the key feedback mechanism - it adjusts signal confidence
        based on what we've learned about similar setups.

        Args:
            pair: The trading pair
            indicators_used: List of indicators in the signal
            timeframe: The timeframe

        Returns:
            Adjustment factor (0.5 to 1.5) to multiply confidence by
        """
        adjustments = []

        # Pair adjustment
        if pair in self._pair_performance:
            pair_perf = self._pair_performance[pair]
            if pair_perf.total_trades >= 5:
                # Win rate relative to 50%
                pair_adj = 1.0 + (pair_perf.win_rate - 50) / 100
                adjustments.append(pair_adj)

        # Timeframe adjustment
        if timeframe in self._timeframe_performance:
            tf_perf = self._timeframe_performance[timeframe]
            if tf_perf.total_trades >= 5:
                tf_adj = 1.0 + (tf_perf.win_rate - 50) / 100
                adjustments.append(tf_adj)

        # Indicator adjustment
        for indicator in indicators_used:
            if indicator in self._indicator_weights:
                ind_weight = self._indicator_weights[indicator]
                if ind_weight.total_signals >= 5:
                    adjustments.append(ind_weight.weight)

        # Combination adjustment
        combo_id = self._get_combination_id(indicators_used)
        if combo_id in self._indicator_combinations:
            combo = self._indicator_combinations[combo_id]
            if combo.total_trades >= 3:
                combo_adj = 1.0 + (combo.win_rate - 50) / 100
                adjustments.append(combo_adj)

        # Calculate final adjustment
        if not adjustments:
            return 1.0

        # Weighted average of adjustments
        avg_adjustment = sum(adjustments) / len(adjustments)

        # Clamp to reasonable range
        return round(max(0.5, min(1.5, avg_adjustment)), 3)

    def adjust_signal_confidence(
        self,
        original_confidence: float,
        pair: str,
        indicators_used: List[str],
        timeframe: str = "1H",
    ) -> Tuple[float, str]:
        """
        Adjust a signal's confidence based on learning.

        Args:
            original_confidence: The original confidence score (0-100)
            pair: Trading pair
            indicators_used: Indicators used in the signal
            timeframe: Analysis timeframe

        Returns:
            Tuple of (adjusted_confidence, explanation)
        """
        adjustment = self.get_confidence_adjustment(pair, indicators_used, timeframe)
        adjusted = original_confidence * adjustment

        # Clamp to 0-100
        adjusted = max(0, min(100, adjusted))

        # Generate explanation
        if adjustment > 1.05:
            explanation = (
                f"Confidence boosted by {(adjustment - 1) * 100:.1f}% based on "
                f"strong historical performance for this setup"
            )
        elif adjustment < 0.95:
            explanation = (
                f"Confidence reduced by {(1 - adjustment) * 100:.1f}% due to "
                f"weaker historical performance for this setup"
            )
        else:
            explanation = "Confidence unchanged - neutral historical performance"

        return round(adjusted, 1), explanation

    # =========================================================================
    # Insights Generation
    # =========================================================================

    def generate_insights(self, limit: int = 10) -> InsightsResponse:
        """
        Generate AI insights about trading performance.

        Analyzes the learning data to produce actionable insights.
        """
        insights = []

        if len(self._outcomes) < 5:
            insights.append(
                LearningInsight(
                    id="insight_bootstrap",
                    title="More Data Needed",
                    content="Continue paper trading to build up enough data for meaningful insights. "
                    f"Currently have {len(self._outcomes)} recorded outcomes.",
                    category="performance",
                    priority="low",
                    recommendation="Complete at least 20-30 paper trades to enable pattern detection.",
                )
            )
            return InsightsResponse(
                insights=insights,
                total_insights=1,
                data_points=len(self._outcomes),
            )

        # Overall performance insight
        accuracy = self.get_accuracy_stats()
        insights.append(self._generate_overall_performance_insight(accuracy))

        # Best performing pair
        best_pair_insight = self._generate_best_pair_insight()
        if best_pair_insight:
            insights.append(best_pair_insight)

        # Worst performing pair
        worst_pair_insight = self._generate_worst_pair_insight()
        if worst_pair_insight:
            insights.append(worst_pair_insight)

        # Best indicator combinations
        combo_insight = self._generate_combination_insight()
        if combo_insight:
            insights.append(combo_insight)

        # Indicator performance insight
        ind_insight = self._generate_indicator_insight()
        if ind_insight:
            insights.append(ind_insight)

        # Timeframe insight
        tf_insight = self._generate_timeframe_insight()
        if tf_insight:
            insights.append(tf_insight)

        # Recent trend insight
        trend_insight = self._generate_trend_insight()
        if trend_insight:
            insights.append(trend_insight)

        # Filter and limit
        insights = [i for i in insights if i is not None]
        insights.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.priority, 1))

        return InsightsResponse(
            insights=insights[:limit],
            total_insights=len(insights),
            data_points=len(self._outcomes),
            analysis_period_days=30,
        )

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _calculate_pips(
        self, pair: str, entry: float, exit: float, direction: str
    ) -> float:
        """Calculate profit/loss in pips."""
        pip_value = self._get_pip_value(pair)

        if direction.lower() in ["buy", "long"]:
            pips = (exit - entry) / pip_value
        else:
            pips = (entry - exit) / pip_value

        return round(pips, 1)

    def _get_pip_value(self, pair: str) -> float:
        """Get pip value for a pair."""
        pair_upper = pair.upper().replace("-", "/")

        # JPY pairs have different pip value
        if "JPY" in pair_upper:
            return 0.01

        # Crypto pairs
        if any(c in pair_upper for c in ["BTC", "ETH", "XRP"]):
            return 1.0

        # Standard forex
        return 0.0001

    def _get_combination_id(self, indicators: List[str]) -> str:
        """Generate a unique ID for an indicator combination."""
        sorted_indicators = sorted([i.lower() for i in indicators])
        combo_str = "|".join(sorted_indicators)
        return hashlib.md5(combo_str.encode()).hexdigest()[:12]

    def _update_indicator_weights(self, outcome: PredictionOutcome) -> None:
        """Update indicator weights based on outcome."""
        for indicator in outcome.indicators_used:
            if indicator not in self._indicator_weights:
                self._indicator_weights[indicator] = IndicatorWeight(
                    indicator_name=indicator
                )

            weight = self._indicator_weights[indicator]
            weight.total_signals += 1

            if outcome.outcome == TradeOutcome.WIN:
                weight.winning_signals += 1
            elif outcome.outcome == TradeOutcome.LOSS:
                weight.losing_signals += 1

            # Recalculate win rate
            if weight.total_signals > 0:
                weight.win_rate = (weight.winning_signals / weight.total_signals) * 100

            # Update weight based on performance (decaying average)
            alpha = 0.1  # Learning rate
            target_weight = 1.0 + (weight.win_rate - 50) / 100
            weight.weight = weight.weight * (1 - alpha) + target_weight * alpha
            weight.weight = round(max(0.5, min(1.5, weight.weight)), 3)

            # Update averages
            n = weight.total_signals
            weight.avg_confidence_when_used = (
                weight.avg_confidence_when_used * (n - 1) + outcome.confidence
            ) / n
            weight.avg_profit_when_used = (
                weight.avg_profit_when_used * (n - 1) + outcome.profit_pips
            ) / n

            weight.last_updated = datetime.utcnow()

    def _update_indicator_combinations(self, outcome: PredictionOutcome) -> None:
        """Update indicator combination performance."""
        if len(outcome.indicators_used) < 2:
            return

        combo_id = self._get_combination_id(outcome.indicators_used)

        if combo_id not in self._indicator_combinations:
            self._indicator_combinations[combo_id] = IndicatorCombination(
                combination_id=combo_id,
                indicators=sorted(outcome.indicators_used),
            )

        combo = self._indicator_combinations[combo_id]
        combo.total_trades += 1

        if outcome.outcome == TradeOutcome.WIN:
            combo.wins += 1
        elif outcome.outcome == TradeOutcome.LOSS:
            combo.losses += 1
        else:
            combo.breakeven += 1

        # Update metrics
        combo.win_rate = (combo.wins / combo.total_trades) * 100 if combo.total_trades > 0 else 0
        combo.total_profit_pips += outcome.profit_pips
        combo.avg_profit_pips = combo.total_profit_pips / combo.total_trades

        if outcome.profit_pips > combo.best_trade_pips:
            combo.best_trade_pips = outcome.profit_pips
        if outcome.profit_pips < combo.worst_trade_pips:
            combo.worst_trade_pips = outcome.profit_pips

        # Track best pairs for this combo
        if outcome.outcome == TradeOutcome.WIN:
            if outcome.pair not in combo.best_pairs:
                combo.best_pairs.append(outcome.pair)
                combo.best_pairs = combo.best_pairs[:5]  # Keep top 5

        if outcome.timeframe not in combo.best_timeframes:
            combo.best_timeframes.append(outcome.timeframe)

        combo.last_updated = datetime.utcnow()

    def _update_pair_performance(self, outcome: PredictionOutcome) -> None:
        """Update pair performance metrics."""
        pair = outcome.pair

        if pair not in self._pair_performance:
            self._pair_performance[pair] = PairPerformance(pair=pair)

        perf = self._pair_performance[pair]
        perf.total_trades += 1

        if outcome.outcome == TradeOutcome.WIN:
            perf.wins += 1
        elif outcome.outcome == TradeOutcome.LOSS:
            perf.losses += 1
        else:
            perf.breakeven += 1

        perf.win_rate = (perf.wins / perf.total_trades) * 100 if perf.total_trades > 0 else 0
        perf.total_profit_pips += outcome.profit_pips
        perf.avg_profit_pips = perf.total_profit_pips / perf.total_trades
        perf.last_trade = outcome.exit_timestamp

    def _update_timeframe_performance(self, outcome: PredictionOutcome) -> None:
        """Update timeframe performance metrics."""
        tf = outcome.timeframe

        if tf not in self._timeframe_performance:
            self._timeframe_performance[tf] = TimeframePerformance(timeframe=tf)

        perf = self._timeframe_performance[tf]
        perf.total_trades += 1

        if outcome.outcome == TradeOutcome.WIN:
            perf.wins += 1
        elif outcome.outcome == TradeOutcome.LOSS:
            perf.losses += 1

        perf.win_rate = (perf.wins / perf.total_trades) * 100 if perf.total_trades > 0 else 0
        perf.avg_profit_pips = (
            sum(o.profit_pips for o in self._outcomes if o.timeframe == tf)
            / perf.total_trades
        )

    def _calculate_accuracy_trend(self, days: int) -> Optional[float]:
        """Calculate accuracy trend over specified days."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        recent = [o for o in self._outcomes if o.exit_timestamp >= cutoff]
        older = [o for o in self._outcomes if o.exit_timestamp < cutoff]

        if len(recent) < 3 or len(older) < 3:
            return None

        recent_win_rate = sum(1 for o in recent if o.outcome == TradeOutcome.WIN) / len(recent) * 100
        older_win_rate = sum(1 for o in older if o.outcome == TradeOutcome.WIN) / len(older) * 100

        return round(recent_win_rate - older_win_rate, 1)

    # =========================================================================
    # Insight Generation Helpers
    # =========================================================================

    def _generate_overall_performance_insight(self, accuracy: AccuracyResponse) -> LearningInsight:
        """Generate overall performance insight."""
        if accuracy.overall_accuracy >= 65:
            title = "Strong Overall Performance"
            content = (
                f"Your prediction accuracy is {accuracy.overall_accuracy:.1f}% across "
                f"{accuracy.total_predictions} trades. This is above the profitable threshold."
            )
            priority = "medium"
            recommendation = "Consider increasing position sizes on high-confidence signals."
        elif accuracy.overall_accuracy >= 50:
            title = "Moderate Performance - Room for Improvement"
            content = (
                f"Your prediction accuracy is {accuracy.overall_accuracy:.1f}% across "
                f"{accuracy.total_predictions} trades. This is near breakeven territory."
            )
            priority = "high"
            recommendation = "Focus on signals with 80%+ confidence and favorable risk/reward."
        else:
            title = "Performance Below Profitability Threshold"
            content = (
                f"Your prediction accuracy is {accuracy.overall_accuracy:.1f}% across "
                f"{accuracy.total_predictions} trades. This needs improvement."
            )
            priority = "high"
            recommendation = "Review losing trades, consider filtering by pair or indicator."

        return LearningInsight(
            id="insight_overall",
            title=title,
            content=content,
            category="performance",
            priority=priority,
            recommendation=recommendation,
        )

    def _generate_best_pair_insight(self) -> Optional[LearningInsight]:
        """Generate insight about best performing pair."""
        if not self._pair_performance:
            return None

        # Find best pair with enough trades
        valid_pairs = [p for p in self._pair_performance.values() if p.total_trades >= 3]
        if not valid_pairs:
            return None

        best = max(valid_pairs, key=lambda x: x.win_rate)

        if best.win_rate < 55:
            return None

        return LearningInsight(
            id="insight_best_pair",
            title=f"Strong Performance on {best.pair}",
            content=(
                f"{best.pair} is your best performing pair with {best.win_rate:.1f}% win rate "
                f"across {best.total_trades} trades, averaging {best.avg_profit_pips:+.1f} pips."
            ),
            category="pair",
            priority="medium",
            affected_pairs=[best.pair],
            recommendation=f"Consider focusing more signals on {best.pair}.",
            confidence_impact=0.1,
        )

    def _generate_worst_pair_insight(self) -> Optional[LearningInsight]:
        """Generate insight about worst performing pair."""
        if not self._pair_performance:
            return None

        valid_pairs = [p for p in self._pair_performance.values() if p.total_trades >= 3]
        if not valid_pairs:
            return None

        worst = min(valid_pairs, key=lambda x: x.win_rate)

        if worst.win_rate > 45:
            return None

        return LearningInsight(
            id="insight_worst_pair",
            title=f"Weak Performance on {worst.pair}",
            content=(
                f"{worst.pair} is struggling with {worst.win_rate:.1f}% win rate "
                f"across {worst.total_trades} trades, averaging {worst.avg_profit_pips:+.1f} pips."
            ),
            category="pair",
            priority="high",
            affected_pairs=[worst.pair],
            recommendation=f"Consider reducing or avoiding signals on {worst.pair}.",
            confidence_impact=-0.15,
        )

    def _generate_combination_insight(self) -> Optional[LearningInsight]:
        """Generate insight about indicator combinations."""
        if not self._indicator_combinations:
            return None

        valid_combos = [c for c in self._indicator_combinations.values() if c.total_trades >= 3]
        if not valid_combos:
            return None

        best = max(valid_combos, key=lambda x: x.win_rate)

        if best.win_rate < 60:
            return None

        indicators_str = ", ".join(best.indicators)

        return LearningInsight(
            id="insight_combo",
            title="High-Performance Indicator Combination",
            content=(
                f"The combination of {indicators_str} has a {best.win_rate:.1f}% win rate "
                f"with {best.avg_profit_pips:+.1f} pips average profit over {best.total_trades} trades."
            ),
            category="indicator",
            priority="medium",
            affected_indicators=best.indicators,
            recommendation="Prioritize signals that use this indicator combination.",
            confidence_impact=0.1,
        )

    def _generate_indicator_insight(self) -> Optional[LearningInsight]:
        """Generate insight about indicator performance."""
        if not self._indicator_weights:
            return None

        valid_inds = [i for i in self._indicator_weights.values() if i.total_signals >= 5]
        if not valid_inds:
            return None

        best = max(valid_inds, key=lambda x: x.win_rate)
        worst = min(valid_inds, key=lambda x: x.win_rate)

        if best.win_rate < 55 or worst.win_rate > 45:
            return None

        return LearningInsight(
            id="insight_indicator",
            title="Indicator Performance Variance",
            content=(
                f"{best.indicator_name} is your most reliable indicator ({best.win_rate:.1f}% win rate), "
                f"while {worst.indicator_name} underperforms ({worst.win_rate:.1f}% win rate)."
            ),
            category="indicator",
            priority="medium",
            affected_indicators=[best.indicator_name, worst.indicator_name],
            recommendation=(
                f"Weight {best.indicator_name} more heavily in confluence decisions. "
                f"Be cautious with signals primarily based on {worst.indicator_name}."
            ),
        )

    def _generate_timeframe_insight(self) -> Optional[LearningInsight]:
        """Generate insight about timeframe performance."""
        if not self._timeframe_performance:
            return None

        valid_tfs = [t for t in self._timeframe_performance.values() if t.total_trades >= 5]
        if not valid_tfs:
            return None

        best = max(valid_tfs, key=lambda x: x.win_rate)

        if best.win_rate < 55:
            return None

        return LearningInsight(
            id="insight_timeframe",
            title=f"Best Performing Timeframe: {best.timeframe}",
            content=(
                f"The {best.timeframe} timeframe shows {best.win_rate:.1f}% win rate "
                f"across {best.total_trades} trades."
            ),
            category="strategy",
            priority="low",
            recommendation=f"Consider focusing analysis on {best.timeframe} timeframe.",
        )

    def _generate_trend_insight(self) -> Optional[LearningInsight]:
        """Generate insight about recent performance trend."""
        trend_7d = self._calculate_accuracy_trend(days=7)

        if trend_7d is None:
            return None

        if trend_7d > 5:
            return LearningInsight(
                id="insight_trend",
                title="Performance Improving",
                content=(
                    f"Your win rate has improved by {trend_7d:+.1f}% over the last 7 days. "
                    "Keep doing what's working!"
                ),
                category="performance",
                priority="low",
            )
        elif trend_7d < -5:
            return LearningInsight(
                id="insight_trend",
                title="Performance Declining",
                content=(
                    f"Your win rate has declined by {abs(trend_7d):.1f}% over the last 7 days. "
                    "Consider reviewing recent losing trades."
                ),
                category="performance",
                priority="high",
                recommendation="Take a break or reduce position sizes until the trend reverses.",
            )

        return None

    # =========================================================================
    # Persistence Methods
    # =========================================================================

    def _save_history(self) -> None:
        """Save learning history to disk."""
        try:
            data = {
                "outcomes": [o.model_dump(mode="json") for o in self._outcomes],
                "indicator_weights": {
                    k: v.model_dump(mode="json") for k, v in self._indicator_weights.items()
                },
                "indicator_combinations": {
                    k: v.model_dump(mode="json") for k, v in self._indicator_combinations.items()
                },
                "pair_performance": {
                    k: v.model_dump(mode="json") for k, v in self._pair_performance.items()
                },
                "timeframe_performance": {
                    k: v.model_dump(mode="json") for k, v in self._timeframe_performance.items()
                },
                "last_updated": datetime.utcnow().isoformat(),
            }

            with open(LEARNING_HISTORY_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Saved learning history: {len(self._outcomes)} outcomes")

        except Exception as e:
            logger.error(f"Failed to save learning history: {e}")

    def _load_history(self) -> None:
        """Load learning history from disk."""
        if not LEARNING_HISTORY_FILE.exists():
            logger.info("No learning history found, starting fresh")
            return

        try:
            with open(LEARNING_HISTORY_FILE, "r") as f:
                data = json.load(f)

            # Load outcomes
            self._outcomes = [
                PredictionOutcome(**self._parse_dates(o))
                for o in data.get("outcomes", [])
            ]

            # Load indicator weights
            self._indicator_weights = {
                k: IndicatorWeight(**self._parse_dates(v))
                for k, v in data.get("indicator_weights", {}).items()
            }

            # Load indicator combinations
            self._indicator_combinations = {
                k: IndicatorCombination(**self._parse_dates(v))
                for k, v in data.get("indicator_combinations", {}).items()
            }

            # Load pair performance
            self._pair_performance = {
                k: PairPerformance(**self._parse_dates(v))
                for k, v in data.get("pair_performance", {}).items()
            }

            # Load timeframe performance
            self._timeframe_performance = {
                k: TimeframePerformance(**v)
                for k, v in data.get("timeframe_performance", {}).items()
            }

            logger.info(f"Loaded learning history: {len(self._outcomes)} outcomes")

        except Exception as e:
            logger.error(f"Failed to load learning history: {e}")
            # Start fresh on error
            self._outcomes = []

    def _parse_dates(self, data: dict) -> dict:
        """Parse date strings back to datetime objects."""
        date_fields = [
            "entry_timestamp", "exit_timestamp", "recorded_at", "last_updated",
            "created_at", "last_trade", "generated_at", "valid_until", "last_used"
        ]

        for field in date_fields:
            if field in data and data[field] is not None:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field].replace("Z", "+00:00"))
                    except ValueError:
                        pass

        return data

    # =========================================================================
    # Public Methods for External Use
    # =========================================================================

    def get_metrics(self) -> LearningMetrics:
        """Get comprehensive learning metrics."""
        accuracy = self.get_accuracy_stats()

        return LearningMetrics(
            total_predictions=accuracy.total_predictions,
            total_wins=sum(1 for o in self._outcomes if o.outcome == TradeOutcome.WIN),
            total_losses=sum(1 for o in self._outcomes if o.outcome == TradeOutcome.LOSS),
            total_breakeven=sum(1 for o in self._outcomes if o.outcome == TradeOutcome.BREAKEVEN),
            overall_win_rate=accuracy.overall_accuracy,
            overall_profit_pips=sum(o.profit_pips for o in self._outcomes),
            accuracy_by_pair={k: v for k, v in self._pair_performance.items()},
            accuracy_by_timeframe={k: v for k, v in self._timeframe_performance.items()},
            accuracy_by_indicator={k: v for k, v in self._indicator_weights.items()},
            learning_started_at=min(o.recorded_at for o in self._outcomes) if self._outcomes else None,
            suggested_confidence_adjustments={
                k: v.weight for k, v in self._indicator_weights.items()
            },
        )

    def clear_history(self) -> None:
        """Clear all learning history (use with caution)."""
        self._outcomes = []
        self._indicator_weights = {}
        self._indicator_combinations = {}
        self._pair_performance = {}
        self._timeframe_performance = {}
        self._metrics = None

        if LEARNING_HISTORY_FILE.exists():
            LEARNING_HISTORY_FILE.unlink()

        logger.info("Learning history cleared")


# =============================================================================
# Singleton Instance
# =============================================================================


_learning_engine: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    """Get the singleton learning engine instance."""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine()
    return _learning_engine
