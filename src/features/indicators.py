"""
Technical Indicator Engine for Forex Trading Bot

Provides vectorized calculations for technical indicators,
session detection, and ML feature preparation.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Literal
from datetime import datetime, time


SessionType = Literal["london", "new_york", "asia", "overlap"]


class IndicatorEngine:
    """
    Complete technical indicator calculator optimized for forex trading.

    Attributes:
        lookback_period: Number of periods to maintain for calculations
    """

    # Session times in UTC
    LONDON_OPEN = time(7, 0)
    LONDON_CLOSE = time(16, 0)
    NY_OPEN = time(12, 0)
    NY_CLOSE = time(21, 0)
    ASIA_OPEN = time(23, 0)
    ASIA_CLOSE = time(8, 0)

    def __init__(self, lookback_period: int = 100):
        """
        Initialize the indicator engine.

        Args:
            lookback_period: Number of periods to use for calculations
        """
        self.lookback_period = lookback_period

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators and add them to the DataFrame.

        Args:
            df: DataFrame with columns [open, high, low, close, volume]

        Returns:
            DataFrame with all indicators added as new columns
        """
        result = df.copy()

        # Ensure we have the required columns
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in result.columns:
                raise ValueError(f"Missing required column: {col}")

        # RSI
        result['rsi_14'] = self.rsi(result['close'], period=14)

        # MACD
        macd_line, signal_line, histogram = self.macd(result['close'])
        result['macd'] = macd_line
        result['macd_signal'] = signal_line
        result['macd_histogram'] = histogram

        # Moving Averages
        result['ema_12'] = self.ema(result['close'], period=12)
        result['ema_20'] = self.ema(result['close'], period=20)
        result['ema_50'] = self.ema(result['close'], period=50)
        result['sma_20'] = self.sma(result['close'], period=20)
        result['sma_50'] = self.sma(result['close'], period=50)

        # ATR
        result['atr_14'] = self.atr(result['high'], result['low'], result['close'], period=14)

        # Bollinger Bands
        upper, middle, lower = self.bollinger_bands(result['close'])
        result['bb_upper'] = upper
        result['bb_middle'] = middle
        result['bb_lower'] = lower
        result['bb_position'] = (result['close'] - lower) / (upper - lower)

        # Volume indicators (if volume is present)
        if 'volume' in result.columns:
            result['volume_sma_20'] = self.volume_sma(result['volume'], period=20)
            result['volume_ratio'] = result['volume'] / result['volume_sma_20']

        # Price momentum
        result['momentum_10'] = self.price_momentum(result['close'], period=10)

        # Session detection (if index is datetime)
        if isinstance(result.index, pd.DatetimeIndex):
            result['session'] = result.index.to_series().apply(self.detect_session)
            result['is_london_open'] = result.index.to_series().apply(self.is_london_open)
            result['hour'] = result.index.hour
            result['weekday'] = result.index.weekday

        return result

    # -------------------------------------------------------------------------
    # Individual Indicator Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.

        Args:
            close: Series of closing prices
            period: RSI period (default 14)

        Returns:
            Series with RSI values (0-100)
        """
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Use exponential moving average for smoothing
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def macd(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            close: Series of closing prices
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def ema(close: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average.

        Args:
            close: Series of prices
            period: EMA period

        Returns:
            Series with EMA values
        """
        return close.ewm(span=period, adjust=False).mean()

    @staticmethod
    def sma(close: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average.

        Args:
            close: Series of prices
            period: SMA period

        Returns:
            Series with SMA values
        """
        return close.rolling(window=period).mean()

    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range.

        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of closing prices
            period: ATR period (default 14)

        Returns:
            Series with ATR values
        """
        prev_close = close.shift(1)

        # True Range is the greatest of:
        # 1. Current High - Current Low
        # 2. |Current High - Previous Close|
        # 3. |Current Low - Previous Close|
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR is the smoothed average of True Range
        atr = true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        return atr

    @staticmethod
    def bollinger_bands(
        close: pd.Series,
        period: int = 20,
        std: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.

        Args:
            close: Series of closing prices
            period: Moving average period (default 20)
            std: Standard deviation multiplier (default 2)

        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        middle = close.rolling(window=period).mean()
        rolling_std = close.rolling(window=period).std()

        upper = middle + (rolling_std * std)
        lower = middle - (rolling_std * std)

        return upper, middle, lower

    @staticmethod
    def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Calculate Simple Moving Average of volume.

        Args:
            volume: Series of volume data
            period: SMA period (default 20)

        Returns:
            Series with volume SMA values
        """
        return volume.rolling(window=period).mean()

    @staticmethod
    def price_momentum(close: pd.Series, period: int = 10) -> pd.Series:
        """
        Calculate price momentum (rate of change).

        Args:
            close: Series of closing prices
            period: Momentum period (default 10)

        Returns:
            Series with momentum values (percentage change)
        """
        return (close - close.shift(period)) / close.shift(period) * 100

    # -------------------------------------------------------------------------
    # Session Detection
    # -------------------------------------------------------------------------

    def detect_session(self, timestamp: datetime) -> SessionType:
        """
        Detect which forex trading session is active.

        Args:
            timestamp: Datetime to check (should be in UTC)

        Returns:
            Session type: "london", "new_york", "asia", or "overlap"
        """
        t = timestamp.time() if hasattr(timestamp, 'time') else timestamp

        london_open = self.LONDON_OPEN <= t < self.LONDON_CLOSE
        ny_open = self.NY_OPEN <= t < self.NY_CLOSE

        # Asia session spans midnight
        asia_open = t >= self.ASIA_OPEN or t < self.ASIA_CLOSE

        # Check for overlaps first
        if london_open and ny_open:
            return "overlap"
        elif london_open:
            return "london"
        elif ny_open:
            return "new_york"
        elif asia_open:
            return "asia"
        else:
            # Default to the nearest session
            return "asia"

    def is_london_open(self, timestamp: datetime) -> bool:
        """
        Check if London session is currently open.

        Args:
            timestamp: Datetime to check (should be in UTC)

        Returns:
            True if London session is open
        """
        t = timestamp.time() if hasattr(timestamp, 'time') else timestamp
        return self.LONDON_OPEN <= t < self.LONDON_CLOSE

    def get_overnight_range(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Get the overnight range for London breakout strategy.

        Calculates high and low from Asian session (23:00 - 07:00 UTC).

        Args:
            df: DataFrame with DatetimeIndex and 'high', 'low' columns

        Returns:
            Tuple of (overnight_high, overnight_low)
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")

        # Filter for Asian session (overnight for London)
        hours = df.index.hour
        overnight_mask = (hours >= 23) | (hours < 7)
        overnight_data = df[overnight_mask]

        if overnight_data.empty:
            return np.nan, np.nan

        overnight_high = overnight_data['high'].max()
        overnight_low = overnight_data['low'].min()

        return overnight_high, overnight_low

    # -------------------------------------------------------------------------
    # ML Feature Preparation
    # -------------------------------------------------------------------------

    def prepare_ml_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for machine learning models.

        Creates a standardized feature set optimized for forex prediction.

        Args:
            df: DataFrame with OHLCV data and DatetimeIndex

        Returns:
            DataFrame with ML-ready features:
            [open, high, low, close, volume, rsi_14, macd_signal, atr_14,
             hour, weekday, spread, ema_20, ema_50, bb_position, volume_ratio]
        """
        # Start with calculated indicators
        result = self.calculate_all(df)

        # Calculate spread if we have ask/bid, otherwise estimate from high-low
        if 'spread' not in result.columns:
            result['spread'] = (result['high'] - result['low']) / result['close'] * 10000  # In pips

        # Ensure hour and weekday exist
        if isinstance(result.index, pd.DatetimeIndex):
            if 'hour' not in result.columns:
                result['hour'] = result.index.hour
            if 'weekday' not in result.columns:
                result['weekday'] = result.index.weekday
        else:
            # Default values if no datetime index
            result['hour'] = 0
            result['weekday'] = 0

        # Ensure volume_ratio exists
        if 'volume_ratio' not in result.columns:
            if 'volume' in result.columns:
                vol_sma = self.volume_sma(result['volume'], period=20)
                result['volume_ratio'] = result['volume'] / vol_sma
            else:
                result['volume_ratio'] = 1.0

        # Select and order the ML feature columns
        ml_columns = [
            'open', 'high', 'low', 'close', 'volume',
            'rsi_14', 'macd_signal', 'atr_14',
            'hour', 'weekday', 'spread',
            'ema_20', 'ema_50', 'bb_position', 'volume_ratio'
        ]

        # Only include columns that exist
        available_columns = [col for col in ml_columns if col in result.columns]

        # Add volume column with default if missing
        if 'volume' not in result.columns:
            result['volume'] = 0

        ml_features = result[available_columns].copy()

        # Fill NaN values for ML readiness
        # Forward fill first, then backward fill remaining
        ml_features = ml_features.ffill().bfill()

        return ml_features

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_latest_signals(self, df: pd.DataFrame) -> dict:
        """
        Extract latest trading signals from calculated indicators.

        Args:
            df: DataFrame with indicators already calculated

        Returns:
            Dictionary with signal information
        """
        if df.empty:
            return {}

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        signals = {
            'rsi': latest.get('rsi_14', np.nan),
            'rsi_oversold': latest.get('rsi_14', 50) < 30,
            'rsi_overbought': latest.get('rsi_14', 50) > 70,
            'macd_bullish': latest.get('macd', 0) > latest.get('macd_signal', 0),
            'macd_crossover': (
                latest.get('macd', 0) > latest.get('macd_signal', 0) and
                prev.get('macd', 0) <= prev.get('macd_signal', 0)
            ),
            'macd_crossunder': (
                latest.get('macd', 0) < latest.get('macd_signal', 0) and
                prev.get('macd', 0) >= prev.get('macd_signal', 0)
            ),
            'above_ema_20': latest.get('close', 0) > latest.get('ema_20', 0),
            'above_ema_50': latest.get('close', 0) > latest.get('ema_50', 0),
            'bb_position': latest.get('bb_position', 0.5),
            'bb_squeeze': (
                latest.get('bb_upper', 1) - latest.get('bb_lower', 0)
            ) / latest.get('bb_middle', 1) if latest.get('bb_middle', 1) != 0 else 0,
            'atr': latest.get('atr_14', np.nan),
            'momentum': latest.get('momentum_10', 0),
            'session': latest.get('session', 'unknown'),
            'volume_ratio': latest.get('volume_ratio', 1.0),
        }

        return signals


# Convenience function for quick indicator calculation
def calculate_indicators(
    df: pd.DataFrame,
    lookback: int = 100
) -> pd.DataFrame:
    """
    Convenience function to calculate all indicators on a DataFrame.

    Args:
        df: DataFrame with OHLCV data
        lookback: Lookback period for the engine

    Returns:
        DataFrame with all indicators added
    """
    engine = IndicatorEngine(lookback_period=lookback)
    return engine.calculate_all(df)


def prepare_features(
    df: pd.DataFrame,
    lookback: int = 100
) -> pd.DataFrame:
    """
    Convenience function to prepare ML features from a DataFrame.

    Args:
        df: DataFrame with OHLCV data
        lookback: Lookback period for the engine

    Returns:
        DataFrame with ML-ready features
    """
    engine = IndicatorEngine(lookback_period=lookback)
    return engine.prepare_ml_features(df)
