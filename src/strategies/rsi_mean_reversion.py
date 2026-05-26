from __future__ import annotations

"""
RSI Mean Reversion Strategy

Entry Criteria:
- Pairs: EUR/CHF, EUR/GBP (ranging pairs)
- Entry LONG: RSI(14) < 30 AND price touches lower Bollinger Band
- Entry SHORT: RSI(14) > 70 AND price touches upper Bollinger Band
- Exit: RSI crosses back to 50
- Stop: 1x ATR from entry
- Win rate target: 68-75%

This strategy capitalizes on mean reversion in range-bound pairs,
entering when prices reach extreme levels indicated by both RSI
and Bollinger Bands.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from .base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    SignalStrength,
    TradeSetup,
)


class RSIMeanReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy for ranging pairs.

    Combines RSI oversold/overbought conditions with Bollinger Band
    touches to identify high-probability mean reversion trades.

    Attributes:
        name: Strategy identifier
        assets: Ranging forex pairs to trade
        rsi_oversold: RSI level for oversold condition
        rsi_overbought: RSI level for overbought condition
        rsi_exit: RSI level for exit (mean)
        bb_touch_threshold: How close to BB for a "touch" (0-1)
        atr_stop_multiplier: ATR multiplier for stop loss
    """

    name: str = "rsi_mean_reversion"
    assets = ["EUR/CHF", "EUR/GBP"]

    # RSI parameters
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    RSI_EXIT = 50

    # Bollinger Band touch threshold (0.05 = within 5% of band)
    BB_TOUCH_THRESHOLD = 0.05

    # Stop loss multiplier
    ATR_STOP_MULTIPLIER = 1.0

    def __init__(
        self,
        assets: Optional[list] = None,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        rsi_exit: float = 50,
        bb_touch_threshold: float = 0.05,
        atr_stop_multiplier: float = 1.0,
        min_confidence: float = 0.70
    ):
        """
        Initialize RSI Mean Reversion strategy.

        Args:
            assets: List of forex pairs to trade
            rsi_oversold: RSI level for oversold condition
            rsi_overbought: RSI level for overbought condition
            rsi_exit: RSI level for exit
            bb_touch_threshold: Threshold for BB touch detection
            atr_stop_multiplier: ATR multiplier for stops
            min_confidence: Minimum confidence threshold
        """
        super().__init__(
            name="rsi_mean_reversion",
            assets=assets or self.assets,
            min_confidence=min_confidence
        )
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.rsi_exit = rsi_exit
        self.bb_touch_threshold = bb_touch_threshold
        self.atr_stop_multiplier = atr_stop_multiplier

    def _check_bb_touch(
        self,
        close: float,
        bb_upper: float,
        bb_lower: float,
        band: str = "lower"
    ) -> bool:
        """
        Check if price is touching or near a Bollinger Band.

        Args:
            close: Current close price
            bb_upper: Upper Bollinger Band
            bb_lower: Lower Bollinger Band
            band: Which band to check ("lower" or "upper")

        Returns:
            True if price is touching the specified band
        """
        bb_range = bb_upper - bb_lower
        threshold_distance = bb_range * self.bb_touch_threshold

        if band == "lower":
            return close <= bb_lower + threshold_distance
        else:  # upper
            return close >= bb_upper - threshold_distance

    def _is_ranging_market(self, df: pd.DataFrame) -> bool:
        """
        Check if the market is ranging (suitable for mean reversion).

        Uses ADX or simple range analysis.

        Args:
            df: DataFrame with price data

        Returns:
            True if market appears to be ranging
        """
        if len(df) < 20:
            return True  # Not enough data, assume ranging

        # Check if price is within recent range
        recent = df.iloc[-20:]
        price_range = recent['high'].max() - recent['low'].min()
        avg_price = recent['close'].mean()
        range_percent = (price_range / avg_price) * 100

        # If range is less than 2%, consider it ranging
        # Also check if there's no strong trend (EMAs close together)
        is_ranging = range_percent < 2.0

        if 'ema_20' in df.columns and 'ema_50' in df.columns:
            ema_spread = abs(df['ema_20'].iloc[-1] - df['ema_50'].iloc[-1])
            ema_spread_percent = (ema_spread / avg_price) * 100
            is_ranging = is_ranging or ema_spread_percent < 0.3

        return is_ranging

    def generate_signal(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Generate a mean reversion signal.

        LONG conditions:
        1. RSI(14) < 30 (oversold)
        2. Price touching/below lower Bollinger Band
        3. Market is ranging (not trending)

        SHORT conditions:
        1. RSI(14) > 70 (overbought)
        2. Price touching/above upper Bollinger Band
        3. Market is ranging

        Args:
            df: DataFrame with OHLCV data and indicators
            features: Dictionary with additional features

        Returns:
            Signal if conditions met, None otherwise
        """
        if df.empty or len(df) < 20:
            return None

        current = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else current

        # Get required indicators
        rsi = current.get('rsi_14', features.get('rsi', 50))
        close = current['close']

        # Get Bollinger Bands
        bb_upper = current.get('bb_upper', features.get('bb_upper'))
        bb_lower = current.get('bb_lower', features.get('bb_lower'))
        bb_middle = current.get('bb_middle', features.get('bb_middle'))

        if pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(rsi):
            return None

        asset = features.get('asset', self.assets[0])

        # Check if market is ranging
        if not self._is_ranging_market(df):
            return None

        signal = None
        confidence = 0.0

        # LONG signal: Oversold + lower BB touch
        if rsi < self.rsi_oversold:
            if self._check_bb_touch(close, bb_upper, bb_lower, "lower"):
                # Calculate confidence
                rsi_strength = (self.rsi_oversold - rsi) / self.rsi_oversold
                bb_position = (close - bb_lower) / (bb_upper - bb_lower)

                # Higher confidence when RSI is more extreme and price is at band
                confidence = min(0.95, 0.70 + rsi_strength * 0.15 + (1 - bb_position) * 0.10)

                signal = Signal(
                    direction=SignalDirection.LONG,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"Mean reversion LONG: RSI {rsi:.1f} oversold, "
                           f"price at lower BB (position: {bb_position:.2f})",
                    metadata={
                        'rsi': rsi,
                        'bb_upper': bb_upper,
                        'bb_lower': bb_lower,
                        'bb_middle': bb_middle,
                        'bb_position': bb_position,
                        'exit_rsi': self.rsi_exit,
                        'signal_type': 'mean_reversion'
                    }
                )

        # SHORT signal: Overbought + upper BB touch
        elif rsi > self.rsi_overbought:
            if self._check_bb_touch(close, bb_upper, bb_lower, "upper"):
                rsi_strength = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
                bb_position = (close - bb_lower) / (bb_upper - bb_lower)

                confidence = min(0.95, 0.70 + rsi_strength * 0.15 + bb_position * 0.10)

                signal = Signal(
                    direction=SignalDirection.SHORT,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"Mean reversion SHORT: RSI {rsi:.1f} overbought, "
                           f"price at upper BB (position: {bb_position:.2f})",
                    metadata={
                        'rsi': rsi,
                        'bb_upper': bb_upper,
                        'bb_lower': bb_lower,
                        'bb_middle': bb_middle,
                        'bb_position': bb_position,
                        'exit_rsi': self.rsi_exit,
                        'signal_type': 'mean_reversion'
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
        Calculate entry, stop loss, and take profit for mean reversion.

        For LONG:
        - Entry: Current price
        - Stop: Entry - (1x ATR)
        - Target: BB middle (mean reversion target)

        For SHORT:
        - Entry: Current price
        - Stop: Entry + (1x ATR)
        - Target: BB middle

        Args:
            signal: The mean reversion signal
            current_price: Current market price
            atr: Average True Range value

        Returns:
            TradeSetup with all parameters
        """
        metadata = signal.metadata
        bb_middle = metadata.get('bb_middle', current_price)

        stop_distance = atr * self.atr_stop_multiplier

        if signal.direction == SignalDirection.LONG:
            entry_price = current_price
            stop_loss = entry_price - stop_distance

            # Target is BB middle (mean reversion)
            take_profit = bb_middle

            # Ensure minimum 2:1 R:R
            risk = entry_price - stop_loss
            min_target = entry_price + (risk * 2)

            if take_profit < min_target:
                take_profit = min_target

        else:  # SHORT
            entry_price = current_price
            stop_loss = entry_price + stop_distance

            take_profit = bb_middle

            risk = stop_loss - entry_price
            min_target = entry_price - (risk * 2)

            if take_profit > min_target:
                take_profit = min_target

        # Mean reversion trades typically have shorter validity
        valid_until = datetime.utcnow() + timedelta(hours=4)

        return TradeSetup(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_spread_pips=2.5,
            valid_until=valid_until
        )

    def check_exit_condition(self, df: pd.DataFrame) -> bool:
        """
        Check if RSI has crossed back to exit level.

        Args:
            df: DataFrame with RSI indicator

        Returns:
            True if exit condition is met
        """
        if len(df) < 2:
            return False

        current_rsi = df.iloc[-1].get('rsi_14', 50)
        prev_rsi = df.iloc[-2].get('rsi_14', 50)

        # Exit when RSI crosses 50
        if prev_rsi < self.rsi_exit <= current_rsi:
            return True  # Was below 50, now crossed above
        if prev_rsi > self.rsi_exit >= current_rsi:
            return True  # Was above 50, now crossed below

        return False

    def _classify_strength(self, confidence: float) -> SignalStrength:
        """Classify signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.75:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
