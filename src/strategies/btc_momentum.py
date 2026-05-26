"""
BTC Trend Breakout / Momentum Strategy

Entry Criteria:
- Price > EMA(20) AND EMA(20) > EMA(50) (bullish trend structure)
- Volume > 1.5x average (momentum confirmation)
- RSI > 50 AND RSI < 70 (momentum without overbought)
- ATR expanding (volatility increasing)

Exit:
- Take profit: 2x ATR
- Stop loss: 1x ATR

Win rate target: 65%

This strategy captures momentum breakouts in Bitcoin by confirming
trend direction with multiple indicators and volume.
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


class BTCMomentumStrategy(BaseStrategy):
    """
    Bitcoin Momentum / Trend Breakout Strategy.

    Identifies strong trend conditions with volume confirmation
    and enters in the direction of momentum.

    Attributes:
        name: Strategy identifier
        assets: Crypto assets to trade
        volume_threshold: Minimum volume ratio
        rsi_min: Minimum RSI for momentum
        rsi_max: Maximum RSI (avoid overbought)
        atr_expansion_threshold: ATR expansion required
        atr_tp_multiplier: ATR multiplier for take profit
        atr_sl_multiplier: ATR multiplier for stop loss
    """

    name: str = "btc_momentum"
    assets = ["BTC/USD", "BTC/USDT", "BTCUSD"]

    # Entry parameters
    VOLUME_THRESHOLD = 1.5
    RSI_MIN = 50
    RSI_MAX = 70
    ATR_EXPANSION_THRESHOLD = 1.1  # ATR should be 10% higher than previous

    # Exit parameters
    ATR_TP_MULTIPLIER = 2.0
    ATR_SL_MULTIPLIER = 1.0

    def __init__(
        self,
        assets: Optional[list] = None,
        volume_threshold: float = 1.5,
        rsi_min: float = 50,
        rsi_max: float = 70,
        atr_expansion_threshold: float = 1.1,
        atr_tp_multiplier: float = 2.0,
        atr_sl_multiplier: float = 1.0,
        min_confidence: float = 0.70
    ):
        """
        Initialize BTC Momentum strategy.

        Args:
            assets: List of crypto pairs to trade
            volume_threshold: Minimum volume ratio
            rsi_min: Minimum RSI for momentum entry
            rsi_max: Maximum RSI to avoid overbought
            atr_expansion_threshold: ATR expansion multiplier
            atr_tp_multiplier: ATR multiplier for take profit
            atr_sl_multiplier: ATR multiplier for stop loss
            min_confidence: Minimum confidence threshold
        """
        super().__init__(
            name="btc_momentum",
            assets=assets or self.assets,
            min_confidence=min_confidence
        )
        self.volume_threshold = volume_threshold
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.atr_expansion_threshold = atr_expansion_threshold
        self.atr_tp_multiplier = atr_tp_multiplier
        self.atr_sl_multiplier = atr_sl_multiplier

    def _check_trend_structure(
        self,
        close: float,
        ema_20: float,
        ema_50: float
    ) -> tuple:
        """
        Check if trend structure is valid.

        Bullish: price > EMA20 > EMA50
        Bearish: price < EMA20 < EMA50

        Args:
            close: Current close price
            ema_20: 20-period EMA
            ema_50: 50-period EMA

        Returns:
            Tuple of (is_bullish, is_bearish, trend_strength)
        """
        is_bullish = close > ema_20 > ema_50
        is_bearish = close < ema_20 < ema_50

        # Calculate trend strength (how separated are the EMAs)
        if ema_50 > 0:
            trend_strength = abs(ema_20 - ema_50) / ema_50
        else:
            trend_strength = 0

        return is_bullish, is_bearish, trend_strength

    def _check_atr_expansion(
        self,
        df: pd.DataFrame,
        lookback: int = 5
    ) -> tuple:
        """
        Check if ATR is expanding (volatility increasing).

        Args:
            df: DataFrame with ATR indicator
            lookback: Number of periods to compare

        Returns:
            Tuple of (is_expanding, expansion_ratio)
        """
        if 'atr_14' not in df.columns or len(df) < lookback:
            return False, 1.0

        current_atr = df['atr_14'].iloc[-1]
        prev_atr = df['atr_14'].iloc[-lookback:-1].mean()

        if prev_atr > 0:
            expansion_ratio = current_atr / prev_atr
        else:
            expansion_ratio = 1.0

        is_expanding = expansion_ratio >= self.atr_expansion_threshold

        return is_expanding, expansion_ratio

    def generate_signal(
        self,
        df: pd.DataFrame,
        features: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Generate a BTC momentum signal.

        LONG conditions:
        1. Price > EMA(20) > EMA(50) (bullish structure)
        2. Volume > 1.5x average
        3. RSI > 50 AND RSI < 70
        4. ATR expanding

        SHORT conditions:
        1. Price < EMA(20) < EMA(50) (bearish structure)
        2. Volume > 1.5x average
        3. RSI < 50 AND RSI > 30
        4. ATR expanding

        Args:
            df: DataFrame with OHLCV data and indicators
            features: Dictionary with additional features

        Returns:
            Signal if conditions met, None otherwise
        """
        if df.empty or len(df) < 50:
            return None

        current = df.iloc[-1]
        close = current['close']

        # Get indicators
        ema_20 = current.get('ema_20', features.get('ema_20'))
        ema_50 = current.get('ema_50', features.get('ema_50'))
        rsi = current.get('rsi_14', features.get('rsi', 50))
        volume_ratio = current.get('volume_ratio', features.get('volume_ratio', 1.0))
        atr = current.get('atr_14', features.get('atr'))

        if pd.isna(ema_20) or pd.isna(ema_50) or pd.isna(rsi):
            return None

        asset = features.get('asset', self.assets[0])

        # Check trend structure
        is_bullish, is_bearish, trend_strength = self._check_trend_structure(
            close, ema_20, ema_50
        )

        # Check ATR expansion
        atr_expanding, expansion_ratio = self._check_atr_expansion(df)

        signal = None
        confidence = 0.0

        # LONG signal
        if is_bullish:
            if (volume_ratio >= self.volume_threshold and
                self.rsi_min < rsi < self.rsi_max and
                atr_expanding):

                # Calculate confidence
                volume_score = min((volume_ratio - 1.0) / 1.0, 0.5)  # Max 0.5
                rsi_score = (rsi - 50) / 40 * 0.15  # Max 0.15 at RSI 70
                trend_score = min(trend_strength * 100, 0.15)  # Max 0.15
                atr_score = min((expansion_ratio - 1.0) * 0.2, 0.15)  # Max 0.15

                confidence = min(0.95, 0.70 + volume_score * 0.1 + rsi_score + trend_score + atr_score)

                signal = Signal(
                    direction=SignalDirection.LONG,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"BTC momentum LONG: Bullish structure (EMA20 > EMA50), "
                           f"RSI {rsi:.1f}, volume {volume_ratio:.2f}x, "
                           f"ATR expansion {expansion_ratio:.2f}x",
                    metadata={
                        'ema_20': ema_20,
                        'ema_50': ema_50,
                        'rsi': rsi,
                        'volume_ratio': volume_ratio,
                        'atr': atr,
                        'atr_expansion': expansion_ratio,
                        'trend_strength': trend_strength,
                        'signal_type': 'momentum_breakout'
                    }
                )

        # SHORT signal
        elif is_bearish:
            if (volume_ratio >= self.volume_threshold and
                30 < rsi < self.rsi_min and  # RSI below 50 but not oversold
                atr_expanding):

                volume_score = min((volume_ratio - 1.0) / 1.0, 0.5)
                rsi_score = (50 - rsi) / 40 * 0.15
                trend_score = min(trend_strength * 100, 0.15)
                atr_score = min((expansion_ratio - 1.0) * 0.2, 0.15)

                confidence = min(0.95, 0.70 + volume_score * 0.1 + rsi_score + trend_score + atr_score)

                signal = Signal(
                    direction=SignalDirection.SHORT,
                    confidence=confidence,
                    asset=asset,
                    strategy_name=self.name,
                    strength=self._classify_strength(confidence),
                    reason=f"BTC momentum SHORT: Bearish structure (EMA20 < EMA50), "
                           f"RSI {rsi:.1f}, volume {volume_ratio:.2f}x, "
                           f"ATR expansion {expansion_ratio:.2f}x",
                    metadata={
                        'ema_20': ema_20,
                        'ema_50': ema_50,
                        'rsi': rsi,
                        'volume_ratio': volume_ratio,
                        'atr': atr,
                        'atr_expansion': expansion_ratio,
                        'trend_strength': trend_strength,
                        'signal_type': 'momentum_breakout'
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
        Calculate entry, stop loss, and take profit for BTC momentum.

        For LONG:
        - Entry: Current price
        - Stop: Entry - (1x ATR)
        - Target: Entry + (2x ATR)

        For SHORT:
        - Entry: Current price
        - Stop: Entry + (1x ATR)
        - Target: Entry - (2x ATR)

        Args:
            signal: The momentum signal
            current_price: Current market price
            atr: Average True Range value

        Returns:
            TradeSetup with all parameters
        """
        # Use ATR from signal metadata if available
        if signal.metadata.get('atr'):
            atr = signal.metadata['atr']

        stop_distance = atr * self.atr_sl_multiplier
        target_distance = atr * self.atr_tp_multiplier

        if signal.direction == SignalDirection.LONG:
            entry_price = current_price
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + target_distance

        else:  # SHORT
            entry_price = current_price
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - target_distance

        # Crypto trades can have longer validity
        valid_until = datetime.utcnow() + timedelta(hours=12)

        return TradeSetup(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_spread_pips=50,  # Crypto has wider spreads (in price units)
            valid_until=valid_until
        )

    def _classify_strength(self, confidence: float) -> SignalStrength:
        """Classify signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.75:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
