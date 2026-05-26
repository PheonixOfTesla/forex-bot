"""
XRP Range Mean Reversion Strategy

Entry Criteria:
- Detect support/resistance from 20-period lookback
- Buy at support level + RSI < 35
- Sell at resistance level + RSI > 65
- Target: Range midpoint

This strategy identifies consolidation ranges in XRP and trades
bounces from the range boundaries.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from .base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    SignalStrength,
    TradeSetup,
)


class XRPRangeStrategy(BaseStrategy):
    """
    XRP Range Mean Reversion Strategy.

    Identifies support and resistance levels from recent price action
    and trades mean reversion when price reaches range boundaries.

    Attributes:
        name: Strategy identifier
        assets: XRP pairs to trade
        lookback_period: Periods for S/R detection
        rsi_oversold: RSI level for long entries
        rsi_overbought: RSI level for short entries
        sr_tolerance: Tolerance for S/R level touch
        min_range_percent: Minimum range size to trade
    """

    name: str = "xrp_range"
    assets = ["XRP/USD", "XRP/USDT", "XRPUSD"]

    # Range detection parameters
    LOOKBACK_PERIOD = 20
    SR_TOLERANCE = 0.005  # 0.5% tolerance for S/R touch
    MIN_RANGE_PERCENT = 3.0  # Minimum 3% range to trade

    # RSI parameters
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 65

    def __init__(
        self,
        assets: Optional[list] = None,
        lookback_period: int = 20,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65,
        sr_tolerance: float = 0.005,
        min_range_percent: float = 3.0,
        min_confidence: float = 0.70
    ):
        """
        Initialize XRP Range strategy.

        Args:
            assets: List of XRP pairs to trade
            lookback_period: Periods for S/R detection
            rsi_oversold: RSI level for long entries
            rsi_overbought: RSI level for short entries
            sr_tolerance: Tolerance for S/R level touch
            min_range_percent: Minimum range size
            min_confidence: Minimum confidence threshold
        """
        super().__init__(
            name="xrp_range",
            assets=assets or self.assets,
            min_confidence=min_confidence
        )
        self.lookback_period = lookback_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.sr_tolerance = sr_tolerance
        self.min_range_percent = min_range_percent

    def _detect_support_resistance(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """
        Detect support and resistance levels from recent price action.

        Uses the high/low of the lookback period with some refinement
        based on price clusters.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Tuple of (support, resistance, midpoint)
        """
        if len(df) < self.lookback_period:
            return np.nan, np.nan, np.nan

        recent = df.iloc[-self.lookback_period:]

        # Simple approach: use recent highs and lows
        resistance = recent['high'].max()
        support = recent['low'].min()

        # Refine by looking at where price tends to cluster
        # Find the most touched high levels
        high_levels = recent['high'].values
        low_levels = recent['low'].values

        # Use percentile for more robust S/R
        resistance_refined = np.percentile(high_levels, 95)
        support_refined = np.percentile(low_levels, 5)

        # Average with simple min/max for stability
        resistance = (resistance + resistance_refined) / 2
        support = (support + support_refined) / 2

        midpoint = (support + resistance) / 2

        return support, resistance, midpoint

    def _is_at_support(
        self,
        price: float,
        support: float
    ) -> Tuple[bool, float]:
        """
        Check if price is at support level.

        Args:
            price: Current price
            support: Support level

        Returns:
            Tuple of (at_support, distance_percent)
        """
        distance_percent = abs(price - support) / support
        at_support = distance_percent <= self.sr_tolerance

        return at_support, distance_percent * 100

    def _is_at_resistance(
        self,
        price: float,
        resistance: float
    ) -> Tuple[bool, float]:
        """
        Check if price is at resistance level.

        Args:
            price: Current price
            resistance: Resistance level

        Returns:
            Tuple of (at_resistance, distance_percent)
        """
        distance_percent = abs(price - resistance) / resistance
        at_resistance = distance_percent <= self.sr_tolerance

        return at_resistance, distance_percent * 100

    def _calculate_range_percent(
        self,
        support: float,
        resistance: float
    ) -> float:
        """
        Calculate range size as percentage.

        Args:
            support: Support level
            resistance: Resistance level

        Returns:
            Range size as percentage
        """
        if support > 0:
            return ((resistance - support) / support) * 100
        return 0.0

    def generate_signal(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Generate an XRP range trading signal.

        LONG conditions:
        1. Price at support level (within tolerance)
        2. RSI < 35 (oversold)
        3. Range is wide enough to trade

        SHORT conditions:
        1. Price at resistance level (within tolerance)
        2. RSI > 65 (overbought)
        3. Range is wide enough to trade

        Args:
            df: DataFrame with OHLCV data and indicators
            features: Dictionary with additional features

        Returns:
            Signal if conditions met, None otherwise
        """
        if df.empty or len(df) < self.lookback_period:
            return None

        current = df.iloc[-1]
        close = current['close']
        rsi = current.get('rsi_14', features.get('rsi', 50))

        asset = features.get('asset', self.assets[0])

        # Detect support and resistance
        support, resistance, midpoint = self._detect_support_resistance(df)

        if pd.isna(support) or pd.isna(resistance):
            return None

        # Check if range is wide enough
        range_percent = self._calculate_range_percent(support, resistance)

        if range_percent < self.min_range_percent:
            return None

        signal = None
        confidence = 0.0

        # Check for LONG at support
        at_support, support_distance = self._is_at_support(close, support)

        if at_support and rsi < self.rsi_oversold:
            # Calculate confidence
            rsi_score = (self.rsi_oversold - rsi) / self.rsi_oversold * 0.15
            proximity_score = (self.sr_tolerance * 100 - support_distance) / (self.sr_tolerance * 100) * 0.1
            range_score = min(range_percent / 10, 0.1)

            confidence = min(0.95, 0.70 + rsi_score + proximity_score + range_score)

            signal = Signal(
                direction=SignalDirection.LONG,
                confidence=confidence,
                asset=asset,
                strategy_name=self.name,
                strength=self._classify_strength(confidence),
                reason=f"XRP range LONG: At support {support:.4f} "
                       f"(distance: {support_distance:.2f}%), RSI {rsi:.1f}",
                metadata={
                    'support': support,
                    'resistance': resistance,
                    'midpoint': midpoint,
                    'range_percent': range_percent,
                    'rsi': rsi,
                    'distance_to_level': support_distance,
                    'signal_type': 'range_mean_reversion'
                }
            )

        # Check for SHORT at resistance
        at_resistance, resistance_distance = self._is_at_resistance(close, resistance)

        if at_resistance and rsi > self.rsi_overbought:
            rsi_score = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought) * 0.15
            proximity_score = (self.sr_tolerance * 100 - resistance_distance) / (self.sr_tolerance * 100) * 0.1
            range_score = min(range_percent / 10, 0.1)

            confidence = min(0.95, 0.70 + rsi_score + proximity_score + range_score)

            signal = Signal(
                direction=SignalDirection.SHORT,
                confidence=confidence,
                asset=asset,
                strategy_name=self.name,
                strength=self._classify_strength(confidence),
                reason=f"XRP range SHORT: At resistance {resistance:.4f} "
                       f"(distance: {resistance_distance:.2f}%), RSI {rsi:.1f}",
                metadata={
                    'support': support,
                    'resistance': resistance,
                    'midpoint': midpoint,
                    'range_percent': range_percent,
                    'rsi': rsi,
                    'distance_to_level': resistance_distance,
                    'signal_type': 'range_mean_reversion'
                }
            )

        if signal and confidence >= self.min_confidence:
            self.record_signal(signal)
            return signal

        return None

    def calculate_entry_exit(
        self,
        signal: Signal,
        current_price: float,
        atr: float
    ) -> TradeSetup:
        """
        Calculate entry, stop loss, and take profit for range trade.

        For LONG:
        - Entry: Current price (at support)
        - Stop: Support - (ATR or 1% of price)
        - Target: Range midpoint

        For SHORT:
        - Entry: Current price (at resistance)
        - Stop: Resistance + (ATR or 1% of price)
        - Target: Range midpoint

        Args:
            signal: The range trading signal
            current_price: Current market price
            atr: Average True Range value

        Returns:
            TradeSetup with all parameters
        """
        metadata = signal.metadata
        support = metadata.get('support', current_price * 0.97)
        resistance = metadata.get('resistance', current_price * 1.03)
        midpoint = metadata.get('midpoint', (support + resistance) / 2)

        # Use ATR or 1% of price for stop buffer, whichever is larger
        stop_buffer = max(atr, current_price * 0.01)

        if signal.direction == SignalDirection.LONG:
            entry_price = current_price
            stop_loss = support - stop_buffer
            take_profit = midpoint

            # Ensure minimum 2:1 R:R
            risk = entry_price - stop_loss
            min_target = entry_price + (risk * 2)

            if take_profit < min_target:
                take_profit = min_target

        else:  # SHORT
            entry_price = current_price
            stop_loss = resistance + stop_buffer
            take_profit = midpoint

            risk = stop_loss - entry_price
            min_target = entry_price - (risk * 2)

            if take_profit > min_target:
                take_profit = min_target

        # Range trades have moderate validity
        valid_until = datetime.utcnow() + timedelta(hours=8)

        return TradeSetup(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_spread_pips=20,
            valid_until=valid_until
        )

    def get_current_range(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Get current detected range levels.

        Useful for external analysis and visualization.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dictionary with support, resistance, midpoint, range_percent
        """
        support, resistance, midpoint = self._detect_support_resistance(df)
        range_percent = self._calculate_range_percent(support, resistance)

        return {
            'support': support,
            'resistance': resistance,
            'midpoint': midpoint,
            'range_percent': range_percent
        }

    def _classify_strength(self, confidence: float) -> SignalStrength:
        """Classify signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.75:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
