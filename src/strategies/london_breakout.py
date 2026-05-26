"""
London Session Breakout Strategy

Entry Criteria:
- Session: First 30 minutes of London open (3am EST / 8am UTC)
- Entry: price > overnight_high + 2pip buffer AND volume > 1.5x avg
- Stop: overnight_high - 5 pips
- Target: entry + 15 pips (2:1 R:R minimum)
- Win rate target: 65-72%

This strategy capitalizes on the increased volatility and momentum
that typically occurs at the London session open.
"""

from datetime import datetime, time, timedelta
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


class LondonBreakoutStrategy(BaseStrategy):
    """
    London Session Breakout Strategy.

    Trades the breakout of overnight range during the first 30 minutes
    of the London session.

    Attributes:
        name: Strategy identifier
        assets: Major forex pairs to trade
        pip_buffer: Buffer above overnight high for entry (in pips)
        stop_buffer_pips: Buffer below overnight high for stop (in pips)
        target_pips: Target profit in pips
        volume_threshold: Minimum volume ratio for confirmation
        london_open_hour: London open hour in UTC
        entry_window_minutes: Minutes after open to look for entries
    """

    name: str = "london_breakout"
    assets = ["EUR/USD", "GBP/USD", "USD/JPY", "EUR/GBP", "GBP/JPY"]

    # London open times (UTC)
    LONDON_OPEN_HOUR = 8  # 8:00 UTC = 3:00 EST
    ENTRY_WINDOW_MINUTES = 30

    # Trade parameters
    PIP_BUFFER = 2  # Pips above overnight high for entry
    STOP_BUFFER_PIPS = 5  # Pips below overnight high for stop
    TARGET_PIPS = 15  # Default target (adjusted for 2:1 R:R)
    VOLUME_THRESHOLD = 1.5  # Minimum volume ratio

    def __init__(
        self,
        assets: Optional[list] = None,
        pip_buffer: float = 2,
        stop_buffer_pips: float = 5,
        target_pips: float = 15,
        volume_threshold: float = 1.5,
        min_confidence: float = 0.70
    ):
        """
        Initialize London Breakout strategy.

        Args:
            assets: List of forex pairs to trade
            pip_buffer: Pips above overnight high for entry
            stop_buffer_pips: Pips below overnight high for stop
            target_pips: Target profit in pips
            volume_threshold: Minimum volume ratio for entry
            min_confidence: Minimum confidence threshold
        """
        super().__init__(
            name="london_breakout",
            assets=assets or self.assets,
            min_confidence=min_confidence
        )
        self.pip_buffer = pip_buffer
        self.stop_buffer_pips = stop_buffer_pips
        self.target_pips = target_pips
        self.volume_threshold = volume_threshold

    def _is_london_entry_window(self, timestamp: datetime) -> bool:
        """
        Check if we're in the London entry window.

        Args:
            timestamp: Current timestamp (UTC)

        Returns:
            True if within first 30 minutes of London open
        """
        current_time = timestamp.time() if hasattr(timestamp, 'time') else timestamp

        # London open time
        london_open = time(self.LONDON_OPEN_HOUR, 0)
        london_entry_close = time(self.LONDON_OPEN_HOUR, self.ENTRY_WINDOW_MINUTES)

        return london_open <= current_time < london_entry_close

    def _calculate_overnight_range(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, float]:
        """
        Calculate the overnight range (Asian session high/low).

        Asian session: 23:00 - 07:00 UTC

        Args:
            df: DataFrame with DatetimeIndex and OHLC data

        Returns:
            Tuple of (overnight_high, overnight_low)
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            # Try to find overnight range from recent data
            return df['high'].iloc[-20:].max(), df['low'].iloc[-20:].min()

        # Get today's date
        today = df.index[-1].date()

        # Filter for overnight period (23:00 yesterday to 07:00 today)
        overnight_mask = (
            ((df.index.date == today - timedelta(days=1)) & (df.index.hour >= 23)) |
            ((df.index.date == today) & (df.index.hour < 7))
        )

        overnight_data = df[overnight_mask]

        if overnight_data.empty:
            # Fallback: use last 8 hours of data
            overnight_data = df.iloc[-8*12:]  # Assuming 5-minute candles

        overnight_high = overnight_data['high'].max()
        overnight_low = overnight_data['low'].min()

        return overnight_high, overnight_low

    def _pips_to_price(self, pips: float, pair: str = "EUR/USD") -> float:
        """
        Convert pips to price movement.

        Args:
            pips: Number of pips
            pair: Currency pair (for pip size determination)

        Returns:
            Price movement equivalent
        """
        # JPY pairs have 2 decimal places, others have 4
        if "JPY" in pair.upper():
            return pips * 0.01
        return pips * 0.0001

    def generate_signal(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Generate a London breakout signal.

        Conditions for LONG signal:
        1. Within London entry window (first 30 minutes)
        2. Price breaks above overnight_high + pip_buffer
        3. Volume > 1.5x average

        Conditions for SHORT signal:
        1. Within London entry window
        2. Price breaks below overnight_low - pip_buffer
        3. Volume > 1.5x average

        Args:
            df: DataFrame with OHLCV data and indicators
            features: Dictionary with additional features

        Returns:
            Signal if conditions met, None otherwise
        """
        if df.empty or len(df) < 20:
            return None

        # Get current data
        current = df.iloc[-1]
        current_price = current['close']
        asset = features.get('asset', self.assets[0])

        # Check if we're in the London entry window
        if isinstance(df.index, pd.DatetimeIndex):
            current_time = df.index[-1]
            if not self._is_london_entry_window(current_time):
                return None
        else:
            # If no datetime index, check from features
            current_time = features.get('timestamp')
            if current_time and not self._is_london_entry_window(current_time):
                return None

        # Calculate overnight range
        overnight_high, overnight_low = self._calculate_overnight_range(df)

        if pd.isna(overnight_high) or pd.isna(overnight_low):
            return None

        # Calculate pip buffer in price terms
        pip_buffer_price = self._pips_to_price(self.pip_buffer, asset)

        # Get volume ratio
        volume_ratio = features.get('volume_ratio', 1.0)
        if 'volume_ratio' in df.columns:
            volume_ratio = current.get('volume_ratio', 1.0)

        # Check for breakout conditions
        signal = None
        confidence = 0.0

        # LONG breakout: price above overnight high + buffer
        if current_price > overnight_high + pip_buffer_price:
            if volume_ratio >= self.volume_threshold:
                # Calculate confidence based on breakout strength and volume
                breakout_strength = (current_price - overnight_high) / overnight_high
                confidence = min(0.95, 0.70 + (breakout_strength * 100) + (volume_ratio - 1.5) * 0.1)

                signal = Signal(
                    direction=SignalDirection.LONG,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"London breakout LONG: Price {current_price:.5f} broke overnight high "
                           f"{overnight_high:.5f} with volume ratio {volume_ratio:.2f}x",
                    metadata={
                        'overnight_high': overnight_high,
                        'overnight_low': overnight_low,
                        'breakout_price': overnight_high + pip_buffer_price,
                        'volume_ratio': volume_ratio,
                        'breakout_type': 'london_open'
                    }
                )

        # SHORT breakout: price below overnight low - buffer
        elif current_price < overnight_low - pip_buffer_price:
            if volume_ratio >= self.volume_threshold:
                breakout_strength = (overnight_low - current_price) / overnight_low
                confidence = min(0.95, 0.70 + (breakout_strength * 100) + (volume_ratio - 1.5) * 0.1)

                signal = Signal(
                    direction=SignalDirection.SHORT,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"London breakout SHORT: Price {current_price:.5f} broke overnight low "
                           f"{overnight_low:.5f} with volume ratio {volume_ratio:.2f}x",
                    metadata={
                        'overnight_high': overnight_high,
                        'overnight_low': overnight_low,
                        'breakout_price': overnight_low - pip_buffer_price,
                        'volume_ratio': volume_ratio,
                        'breakout_type': 'london_open'
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
        Calculate entry, stop loss, and take profit for London breakout.

        For LONG:
        - Entry: current price (breakout already confirmed)
        - Stop: overnight_high - stop_buffer_pips
        - Target: Minimum 2:1 R:R, at least target_pips

        For SHORT:
        - Entry: current price
        - Stop: overnight_low + stop_buffer_pips
        - Target: Minimum 2:1 R:R, at least target_pips

        Args:
            signal: The breakout signal
            current_price: Current market price
            atr: Average True Range value

        Returns:
            TradeSetup with all parameters
        """
        asset = signal.asset
        metadata = signal.metadata

        overnight_high = metadata.get('overnight_high', current_price + atr)
        overnight_low = metadata.get('overnight_low', current_price - atr)

        stop_buffer = self._pips_to_price(self.stop_buffer_pips, asset)
        target_pips_price = self._pips_to_price(self.target_pips, asset)

        if signal.direction == SignalDirection.LONG:
            entry_price = current_price
            stop_loss = overnight_high - stop_buffer

            # Calculate risk
            risk = entry_price - stop_loss

            # Ensure minimum 2:1 R:R
            min_target = entry_price + (risk * 2)
            target_from_pips = entry_price + target_pips_price

            take_profit = max(min_target, target_from_pips)

        else:  # SHORT
            entry_price = current_price
            stop_loss = overnight_low + stop_buffer

            risk = stop_loss - entry_price

            min_target = entry_price - (risk * 2)
            target_from_pips = entry_price - target_pips_price

            take_profit = min(min_target, target_from_pips)

        # Set validity window (30 minutes from now)
        valid_until = datetime.utcnow() + timedelta(minutes=30)

        return TradeSetup(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_spread_pips=2.0,  # Tight spread required for breakout
            valid_until=valid_until
        )

    def _classify_strength(self, confidence: float) -> SignalStrength:
        """Classify signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.75:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
