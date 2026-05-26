"""
Kelly Criterion Calculator
Implements optimal position sizing using the Kelly formula with safety adjustments.
"""

import math
from typing import Optional, Tuple


class KellyCalculator:
    """
    Calculates optimal position sizes using the Kelly Criterion.

    The Kelly Criterion provides the mathematically optimal bet size to maximize
    long-term growth rate while avoiding ruin. This implementation uses Half Kelly
    for additional safety margin.

    Formula: Kelly % = W - (1-W) / R
    Where:
        W = Win rate (probability of winning)
        R = Win/Loss ratio (average win / average loss)
    """

    def __init__(
        self,
        max_kelly: float = 0.25,  # Never exceed 25% Kelly
        min_trades_required: int = 30,  # Minimum trades for reliable stats
        drawdown_scale_factor: float = 0.5  # How much to reduce at max drawdown
    ):
        """
        Initialize the Kelly Calculator.

        Args:
            max_kelly: Maximum Kelly fraction allowed (caps position size)
            min_trades_required: Minimum trades needed for reliable statistics
            drawdown_scale_factor: Scaling factor when in drawdown
        """
        self.max_kelly = max_kelly
        self.min_trades_required = min_trades_required
        self.drawdown_scale_factor = drawdown_scale_factor

    def calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate the full Kelly fraction.

        Kelly % = W - (1-W) / R
        Where R = avg_win / avg_loss (the win/loss ratio)

        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)

        Returns:
            Kelly fraction (0-1), or 0 if no edge exists
        """
        # Validate inputs
        if not 0 <= win_rate <= 1:
            raise ValueError(f"win_rate must be between 0 and 1, got {win_rate}")
        if avg_win <= 0:
            return 0.0
        if avg_loss <= 0:
            return 0.0

        # Calculate win/loss ratio
        win_loss_ratio = avg_win / avg_loss

        # Kelly formula: W - (1-W) / R
        kelly = win_rate - (1 - win_rate) / win_loss_ratio

        # No edge or negative edge = no bet
        if kelly <= 0:
            return 0.0

        # Cap at maximum allowed Kelly
        return min(kelly, self.max_kelly)

    def calculate_half_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Half Kelly for safer position sizing.

        Half Kelly sacrifices some growth for significantly reduced variance
        and drawdown. Studies show it produces ~75% of the growth rate with
        ~50% of the volatility.

        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)

        Returns:
            Half Kelly fraction (0-1)
        """
        full_kelly = self.calculate_kelly(win_rate, avg_win, avg_loss)
        return full_kelly / 2.0

    def calculate_quarter_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Quarter Kelly for ultra-conservative position sizing.

        Useful during uncertain market conditions or after significant drawdown.

        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)

        Returns:
            Quarter Kelly fraction (0-1)
        """
        full_kelly = self.calculate_kelly(win_rate, avg_win, avg_loss)
        return full_kelly / 4.0

    def calculate_ruin_probability(
        self,
        kelly_fraction: float,
        win_rate: float,
        num_trades: int,
        ruin_threshold: float = 0.5  # Consider ruin at 50% drawdown
    ) -> float:
        """
        Estimate probability of ruin (severe drawdown) over N trades.

        Uses a simplified model based on the relationship between
        bet size and probability of reaching the ruin threshold.

        Args:
            kelly_fraction: Fraction of capital risked per trade
            win_rate: Probability of winning
            num_trades: Number of trades to simulate
            ruin_threshold: Drawdown level considered as ruin (0-1)

        Returns:
            Estimated probability of ruin (0-1)
        """
        if kelly_fraction <= 0 or num_trades <= 0:
            return 0.0

        if win_rate <= 0 or win_rate >= 1:
            return 1.0 if win_rate <= 0 else 0.0

        # Approximate ruin probability using Gambler's Ruin formula variant
        # P(ruin) ~ ((1-p)/p)^n where n is related to starting capital
        # This is simplified; real implementation would use Monte Carlo

        # Edge factor: positive edge reduces ruin probability
        edge = win_rate - (1 - win_rate)

        if edge <= 0:
            # No edge or negative edge: high ruin probability
            return min(1.0, 0.5 + kelly_fraction * num_trades * 0.01)

        # With positive edge, ruin probability decreases with edge
        # but increases with bet size (kelly_fraction)
        base_ruin = math.exp(-2 * edge * edge * num_trades / (kelly_fraction + 0.01))

        # Adjust for ruin threshold (lower threshold = higher probability)
        threshold_factor = (1 - ruin_threshold) / 0.5

        return min(1.0, base_ruin * threshold_factor)

    def adjust_for_drawdown(
        self,
        base_kelly: float,
        current_drawdown: float,
        max_drawdown_threshold: float = 0.20  # 20% drawdown
    ) -> float:
        """
        Dynamically adjust Kelly fraction based on current drawdown.

        Reduces position size progressively as drawdown increases,
        helping to preserve capital during losing streaks.

        Args:
            base_kelly: Original Kelly fraction
            current_drawdown: Current drawdown as fraction (0-1)
            max_drawdown_threshold: Drawdown level where scaling is maximized

        Returns:
            Adjusted Kelly fraction
        """
        if current_drawdown <= 0:
            return base_kelly

        if current_drawdown >= max_drawdown_threshold:
            # At or beyond max drawdown, use minimum scaling
            return base_kelly * self.drawdown_scale_factor

        # Linear scaling between full Kelly and scaled Kelly
        scale_ratio = current_drawdown / max_drawdown_threshold
        adjusted_scale = 1 - (scale_ratio * (1 - self.drawdown_scale_factor))

        return base_kelly * adjusted_scale

    def adjust_for_confidence(
        self,
        base_kelly: float,
        ml_confidence: float,
        min_confidence: float = 0.70
    ) -> float:
        """
        Adjust Kelly fraction based on ML model confidence.

        Higher confidence signals warrant larger positions.

        Args:
            base_kelly: Original Kelly fraction
            ml_confidence: ML model confidence (0-1)
            min_confidence: Minimum confidence threshold

        Returns:
            Confidence-adjusted Kelly fraction
        """
        if ml_confidence < min_confidence:
            return 0.0

        # Scale Kelly between min_confidence and 1.0
        confidence_range = 1.0 - min_confidence
        confidence_factor = (ml_confidence - min_confidence) / confidence_range

        # Use square root for gentler scaling
        return base_kelly * math.sqrt(confidence_factor)

    def get_optimal_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        current_drawdown: float = 0.0,
        ml_confidence: float = 1.0,
        trade_count: int = 0,
        use_half_kelly: bool = True
    ) -> Tuple[float, dict]:
        """
        Calculate the optimal position fraction considering all factors.

        Args:
            win_rate: Historical win rate
            avg_win: Average winning trade
            avg_loss: Average losing trade
            current_drawdown: Current portfolio drawdown
            ml_confidence: ML model confidence for this trade
            trade_count: Number of historical trades
            use_half_kelly: Whether to use half Kelly (recommended)

        Returns:
            Tuple of (optimal_fraction, details_dict)
        """
        # Calculate base Kelly
        full_kelly = self.calculate_kelly(win_rate, avg_win, avg_loss)

        # Use half or full Kelly
        base_kelly = full_kelly / 2 if use_half_kelly else full_kelly

        # Adjust for drawdown
        drawdown_adjusted = self.adjust_for_drawdown(base_kelly, current_drawdown)

        # Adjust for confidence
        final_kelly = self.adjust_for_confidence(drawdown_adjusted, ml_confidence)

        # If not enough trades, be more conservative
        if trade_count < self.min_trades_required:
            confidence_factor = trade_count / self.min_trades_required
            final_kelly *= confidence_factor

        # Calculate ruin probability for reporting
        ruin_prob = self.calculate_ruin_probability(
            final_kelly, win_rate, 100  # Over next 100 trades
        )

        details = {
            "full_kelly": full_kelly,
            "base_kelly": base_kelly,
            "drawdown_adjusted": drawdown_adjusted,
            "final_kelly": final_kelly,
            "ruin_probability_100_trades": ruin_prob,
            "win_rate": win_rate,
            "win_loss_ratio": avg_win / avg_loss if avg_loss > 0 else 0,
            "trade_count": trade_count,
            "sufficient_data": trade_count >= self.min_trades_required
        }

        return final_kelly, details
