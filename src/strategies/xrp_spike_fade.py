"""
XRP Volatility Spike Fade Strategy

Entry Criteria (SHORT - fading the spike):
- Price change 1h > 8% (spike detection)
- Volume > 3x average (volume spike)
- RSI > 75 (overbought)

Exit:
- Take profit: 5% retracement from entry
- Stop loss: 2.5% above entry
- R:R: 2:1

This strategy fades extreme volatility spikes in XRP, which is known
for sharp but often unsustainable price movements.
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


class XRPSpikeFadeStrategy(BaseStrategy):
    """
    XRP Volatility Spike Fade Strategy.

    Identifies extreme price spikes in XRP and enters short positions
    to capture the subsequent retracement.

    Attributes:
        name: Strategy identifier
        assets: XRP pairs to trade
        spike_threshold_percent: Minimum 1h price change for spike
        volume_spike_threshold: Volume ratio for spike confirmation
        rsi_overbought: RSI level for overbought confirmation
        rsi_oversold: RSI level for oversold (long fade)
        take_profit_percent: Target retracement percentage
        stop_loss_percent: Stop loss percentage
    """

    name: str = "xrp_spike_fade"
    assets = ["XRP/USD", "XRP/USDT", "XRPUSD"]

    # Spike detection parameters
    SPIKE_THRESHOLD_PERCENT = 8.0  # 8% move in 1 hour
    VOLUME_SPIKE_THRESHOLD = 3.0  # 3x average volume
    RSI_OVERBOUGHT = 75
    RSI_OVERSOLD = 25

    # Exit parameters
    TAKE_PROFIT_PERCENT = 5.0
    STOP_LOSS_PERCENT = 2.5

    def __init__(
        self,
        assets: Optional[list] = None,
        spike_threshold_percent: float = 8.0,
        volume_spike_threshold: float = 3.0,
        rsi_overbought: float = 75,
        rsi_oversold: float = 25,
        take_profit_percent: float = 5.0,
        stop_loss_percent: float = 2.5,
        min_confidence: float = 0.70
    ):
        """
        Initialize XRP Spike Fade strategy.

        Args:
            assets: List of XRP pairs to trade
            spike_threshold_percent: Minimum 1h move for spike
            volume_spike_threshold: Volume ratio for confirmation
            rsi_overbought: RSI level for overbought
            rsi_oversold: RSI level for oversold
            take_profit_percent: Target retracement
            stop_loss_percent: Stop loss percentage
            min_confidence: Minimum confidence threshold
        """
        super().__init__(
            name="xrp_spike_fade",
            assets=assets or self.assets,
            min_confidence=min_confidence
        )
        self.spike_threshold_percent = spike_threshold_percent
        self.volume_spike_threshold = volume_spike_threshold
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.take_profit_percent = take_profit_percent
        self.stop_loss_percent = stop_loss_percent

    def _calculate_price_change(
        self,
        df: pd.DataFrame,
        periods: int = 12  # 12 x 5min = 1 hour
    ) -> float:
        """
        Calculate price change over specified periods.

        Args:
            df: DataFrame with price data
            periods: Number of periods to look back

        Returns:
            Percentage price change
        """
        if len(df) < periods:
            return 0.0

        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-periods]

        if past_price > 0:
            return ((current_price - past_price) / past_price) * 100
        return 0.0

    def _detect_spike(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> tuple:
        """
        Detect if a price spike has occurred.

        Args:
            df: DataFrame with price and volume data
            features: Additional features

        Returns:
            Tuple of (spike_detected, direction, spike_magnitude, volume_ratio)
        """
        # Calculate 1h price change
        price_change = self._calculate_price_change(df, periods=12)

        # Get volume ratio
        current = df.iloc[-1]
        volume_ratio = current.get('volume_ratio', features.get('volume_ratio', 1.0))

        # Check for upward spike
        if price_change >= self.spike_threshold_percent:
            if volume_ratio >= self.volume_spike_threshold:
                return True, "up", price_change, volume_ratio

        # Check for downward spike
        if price_change <= -self.spike_threshold_percent:
            if volume_ratio >= self.volume_spike_threshold:
                return True, "down", abs(price_change), volume_ratio

        return False, None, 0.0, volume_ratio

    def generate_signal(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Generate an XRP spike fade signal.

        SHORT conditions (fade upward spike):
        1. Price change 1h > +8%
        2. Volume > 3x average
        3. RSI > 75 (overbought)

        LONG conditions (fade downward spike):
        1. Price change 1h < -8%
        2. Volume > 3x average
        3. RSI < 25 (oversold)

        Args:
            df: DataFrame with OHLCV data and indicators
            features: Dictionary with additional features

        Returns:
            Signal if conditions met, None otherwise
        """
        if df.empty or len(df) < 15:
            return None

        current = df.iloc[-1]
        close = current['close']
        rsi = current.get('rsi_14', features.get('rsi', 50))

        asset = features.get('asset', self.assets[0])

        # Detect spike
        spike_detected, direction, magnitude, volume_ratio = self._detect_spike(df, features)

        if not spike_detected:
            return None

        signal = None
        confidence = 0.0

        # Fade upward spike (SHORT)
        if direction == "up" and rsi >= self.rsi_overbought:
            # Calculate confidence based on spike extremity
            magnitude_score = min((magnitude - self.spike_threshold_percent) / 10, 0.15)
            volume_score = min((volume_ratio - self.volume_spike_threshold) / 3, 0.1)
            rsi_score = min((rsi - self.rsi_overbought) / 25, 0.1)

            confidence = min(0.95, 0.70 + magnitude_score + volume_score + rsi_score)

            signal = Signal(
                direction=SignalDirection.SHORT,
                confidence=confidence,
                asset=asset,
                strategy_name=self.name,
                strength=self._classify_strength(confidence),
                reason=f"XRP spike fade SHORT: +{magnitude:.1f}% spike, "
                       f"volume {volume_ratio:.1f}x, RSI {rsi:.1f} overbought",
                metadata={
                    'spike_direction': 'up',
                    'spike_magnitude': magnitude,
                    'volume_ratio': volume_ratio,
                    'rsi': rsi,
                    'entry_price': close,
                    'target_percent': self.take_profit_percent,
                    'stop_percent': self.stop_loss_percent,
                    'signal_type': 'spike_fade'
                }
            )

        # Fade downward spike (LONG)
        elif direction == "down" and rsi <= self.rsi_oversold:
            magnitude_score = min((magnitude - self.spike_threshold_percent) / 10, 0.15)
            volume_score = min((volume_ratio - self.volume_spike_threshold) / 3, 0.1)
            rsi_score = min((self.rsi_oversold - rsi) / 25, 0.1)

            confidence = min(0.95, 0.70 + magnitude_score + volume_score + rsi_score)

            signal = Signal(
                direction=SignalDirection.LONG,
                confidence=confidence,
                asset=asset,
                strategy_name=self.name,
                strength=self._classify_strength(confidence),
                reason=f"XRP spike fade LONG: -{magnitude:.1f}% spike, "
                       f"volume {volume_ratio:.1f}x, RSI {rsi:.1f} oversold",
                metadata={
                    'spike_direction': 'down',
                    'spike_magnitude': magnitude,
                    'volume_ratio': volume_ratio,
                    'rsi': rsi,
                    'entry_price': close,
                    'target_percent': self.take_profit_percent,
                    'stop_percent': self.stop_loss_percent,
                    'signal_type': 'spike_fade'
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
        Calculate entry, stop loss, and take profit for spike fade.

        For SHORT (fading up spike):
        - Entry: Current price
        - Stop: Entry + 2.5%
        - Target: Entry - 5%

        For LONG (fading down spike):
        - Entry: Current price
        - Stop: Entry - 2.5%
        - Target: Entry + 5%

        Args:
            signal: The spike fade signal
            current_price: Current market price
            atr: Average True Range value (used as fallback)

        Returns:
            TradeSetup with all parameters
        """
        tp_percent = self.take_profit_percent / 100
        sl_percent = self.stop_loss_percent / 100

        if signal.direction == SignalDirection.SHORT:
            entry_price = current_price
            stop_loss = entry_price * (1 + sl_percent)
            take_profit = entry_price * (1 - tp_percent)

        else:  # LONG
            entry_price = current_price
            stop_loss = entry_price * (1 - sl_percent)
            take_profit = entry_price * (1 + tp_percent)

        # Spike fades should resolve quickly
        valid_until = datetime.utcnow() + timedelta(hours=4)

        return TradeSetup(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_spread_pips=30,  # Crypto spreads
            valid_until=valid_until
        )

    def _classify_strength(self, confidence: float) -> SignalStrength:
        """Classify signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.75:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
