"""
Real Signal Generation Service

Fetches live market data from OANDA, calculates technical indicators,
and generates trading signals with confidence scores based on indicator confluence.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

import numpy as np
import pandas as pd

from ..brokers.oanda import OandaClient, Granularity, create_oanda_client
from ..features.indicators import IndicatorEngine

logger = logging.getLogger(__name__)


# =============================================================================
# Signal Data Classes
# =============================================================================


@dataclass
class TradingSignal:
    """Represents a trading signal with all relevant data."""

    id: str
    pair: str
    direction: str  # "buy" or "sell"
    confidence: float  # 0-100
    status: str  # "active", "executed", "skipped", "expired"
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    strategy: str
    created_at: datetime
    expires_at: datetime
    indicators: Dict
    model_version: str = "v3.0.0-live"
    feature_importance: Dict = field(default_factory=dict)
    similar_historical_trades: int = 0
    historical_win_rate: float = 0.0

    def to_dict(self) -> Dict:
        """Convert signal to dictionary format for API response."""
        return {
            "id": self.id,
            "pair": self.pair,
            "direction": self.direction,
            "confidence": self.confidence,
            "status": self.status,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "strategy": self.strategy,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "features": self.indicators,
            "model_version": self.model_version,
            "feature_importance": self.feature_importance,
            "similar_historical_trades": self.similar_historical_trades,
            "historical_win_rate": self.historical_win_rate,
        }


# =============================================================================
# Signal Generator
# =============================================================================


class SignalGenerator:
    """
    Real signal generation engine using OANDA market data.

    Analyzes multiple technical indicators to identify high-probability
    trading opportunities with confluence-based confidence scoring.
    """

    # Default forex pairs to analyze
    DEFAULT_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "EUR_GBP"]

    # Timeframe for analysis
    ANALYSIS_TIMEFRAME = Granularity.H1
    CANDLE_COUNT = 100

    # Signal expiry time in minutes
    SIGNAL_EXPIRY_MINUTES = 60

    # Minimum confidence threshold for generating signals
    MIN_CONFIDENCE_THRESHOLD = 55.0

    # ATR multipliers for stop loss and take profit
    SL_ATR_MULTIPLIER = 1.5
    TP_ATR_MULTIPLIER = 3.0  # 2:1 R:R ratio

    def __init__(
        self,
        oanda_client: Optional[OandaClient] = None,
        pairs: Optional[List[str]] = None,
    ):
        """
        Initialize the signal generator.

        Args:
            oanda_client: OANDA client instance (optional, will create if not provided)
            pairs: List of currency pairs to analyze (optional, uses defaults)
        """
        self._oanda_client = oanda_client
        self._owns_client = oanda_client is None
        self.pairs = pairs or self.DEFAULT_PAIRS
        self.indicator_engine = IndicatorEngine(lookback_period=100)

        # Cache for recent signals to avoid duplicates
        self._signal_cache: Dict[str, TradingSignal] = {}
        self._cache_expiry: Dict[str, datetime] = {}

        # Track signal status changes
        self._signal_status_store: Dict[str, str] = {}

        logger.info(f"SignalGenerator initialized for pairs: {self.pairs}")

    async def _get_client(self) -> OandaClient:
        """Get or create OANDA client."""
        if self._oanda_client is None:
            self._oanda_client = create_oanda_client()
            await self._oanda_client.connect()
        return self._oanda_client

    async def close(self) -> None:
        """Close the OANDA client if we own it."""
        if self._owns_client and self._oanda_client is not None:
            await self._oanda_client.disconnect()
            self._oanda_client = None

    def _generate_signal_id(self, pair: str, direction: str, timestamp: datetime) -> str:
        """Generate a unique signal ID."""
        # Create hash from pair, direction, and timestamp (rounded to hour)
        hour_timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
        hash_input = f"{pair}_{direction}_{hour_timestamp.isoformat()}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"sig_{int(timestamp.timestamp())}_{pair.replace('_', '')}_{hash_suffix}"

    def _calculate_rsi_signal(self, rsi: float) -> Tuple[str, float]:
        """
        Calculate signal from RSI.

        Returns:
            Tuple of (direction, weight) where direction is 'buy', 'sell', or 'neutral'
        """
        if rsi < 30:
            # Oversold - potential buy
            return "buy", min(1.0, (30 - rsi) / 15)
        elif rsi > 70:
            # Overbought - potential sell
            return "sell", min(1.0, (rsi - 70) / 15)
        elif rsi < 40:
            return "buy", 0.3
        elif rsi > 60:
            return "sell", 0.3
        return "neutral", 0.0

    def _calculate_macd_signal(
        self,
        macd: float,
        macd_signal: float,
        macd_histogram: float,
        prev_histogram: float
    ) -> Tuple[str, float]:
        """
        Calculate signal from MACD.

        Returns:
            Tuple of (direction, weight)
        """
        # Check for crossover
        bullish_crossover = prev_histogram <= 0 and macd_histogram > 0
        bearish_crossover = prev_histogram >= 0 and macd_histogram < 0

        if bullish_crossover:
            return "buy", 1.0
        elif bearish_crossover:
            return "sell", 1.0
        elif macd > macd_signal:
            # Bullish momentum
            weight = min(0.6, abs(macd - macd_signal) * 100)
            return "buy", weight
        elif macd < macd_signal:
            # Bearish momentum
            weight = min(0.6, abs(macd - macd_signal) * 100)
            return "sell", weight

        return "neutral", 0.0

    def _calculate_bb_signal(self, bb_position: float, close: float, bb_upper: float, bb_lower: float) -> Tuple[str, float]:
        """
        Calculate signal from Bollinger Bands.

        Returns:
            Tuple of (direction, weight)
        """
        if bb_position < 0.1:
            # Price near lower band - potential buy
            return "buy", min(1.0, (0.2 - bb_position) * 5)
        elif bb_position > 0.9:
            # Price near upper band - potential sell
            return "sell", min(1.0, (bb_position - 0.8) * 5)
        elif bb_position < 0.3:
            return "buy", 0.4
        elif bb_position > 0.7:
            return "sell", 0.4

        return "neutral", 0.0

    def _calculate_ma_signal(
        self,
        close: float,
        ema_20: float,
        ema_50: float,
        sma_20: float,
        sma_50: float
    ) -> Tuple[str, float]:
        """
        Calculate signal from Moving Averages.

        Returns:
            Tuple of (direction, weight)
        """
        bullish_signals = 0
        bearish_signals = 0

        # Price vs EMAs
        if close > ema_20:
            bullish_signals += 1
        else:
            bearish_signals += 1

        if close > ema_50:
            bullish_signals += 1
        else:
            bearish_signals += 1

        # EMA alignment (trend)
        if ema_20 > ema_50:
            bullish_signals += 1
        else:
            bearish_signals += 1

        # SMA alignment
        if sma_20 > sma_50:
            bullish_signals += 1
        else:
            bearish_signals += 1

        total = bullish_signals + bearish_signals
        if bullish_signals > bearish_signals:
            return "buy", bullish_signals / total
        elif bearish_signals > bullish_signals:
            return "sell", bearish_signals / total

        return "neutral", 0.0

    def _calculate_momentum_signal(self, momentum: float) -> Tuple[str, float]:
        """
        Calculate signal from price momentum.

        Returns:
            Tuple of (direction, weight)
        """
        if momentum > 0.5:
            return "buy", min(1.0, momentum / 2)
        elif momentum < -0.5:
            return "sell", min(1.0, abs(momentum) / 2)
        elif momentum > 0.1:
            return "buy", 0.3
        elif momentum < -0.1:
            return "sell", 0.3

        return "neutral", 0.0

    def _calculate_volume_signal(self, volume_ratio: float) -> Tuple[str, float]:
        """
        Calculate volume confirmation signal.

        Volume doesn't give direction but confirms strength.
        Returns weight modifier (1.0 = no change, >1.0 = confirmation, <1.0 = weak)
        """
        if volume_ratio > 1.5:
            return "confirm", 1.3  # Strong volume confirmation
        elif volume_ratio > 1.2:
            return "confirm", 1.15
        elif volume_ratio < 0.5:
            return "weak", 0.7  # Low volume - reduce confidence
        elif volume_ratio < 0.8:
            return "weak", 0.85

        return "neutral", 1.0

    def _calculate_confluence_score(
        self,
        indicators: Dict,
        df: pd.DataFrame
    ) -> Tuple[str, float, Dict]:
        """
        Calculate overall signal direction and confidence from indicator confluence.

        Returns:
            Tuple of (direction, confidence, feature_importance)
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

        # Weights for each indicator
        weights = {
            "rsi": 0.20,
            "macd": 0.25,
            "bollinger": 0.15,
            "moving_averages": 0.25,
            "momentum": 0.10,
            "volume": 0.05,
        }

        signals = {}
        signal_weights = {}

        # RSI Signal
        rsi_dir, rsi_strength = self._calculate_rsi_signal(indicators["rsi"])
        signals["rsi"] = (rsi_dir, rsi_strength * weights["rsi"])
        signal_weights["rsi"] = weights["rsi"] * rsi_strength

        # MACD Signal
        macd_dir, macd_strength = self._calculate_macd_signal(
            indicators["macd"],
            indicators["macd_signal"],
            latest.get("macd_histogram", 0),
            prev.get("macd_histogram", 0)
        )
        signals["macd"] = (macd_dir, macd_strength * weights["macd"])
        signal_weights["macd"] = weights["macd"] * macd_strength

        # Bollinger Bands Signal
        bb_dir, bb_strength = self._calculate_bb_signal(
            indicators["bb_position"],
            latest["close"],
            latest.get("bb_upper", latest["close"]),
            latest.get("bb_lower", latest["close"])
        )
        signals["bollinger"] = (bb_dir, bb_strength * weights["bollinger"])
        signal_weights["bollinger"] = weights["bollinger"] * bb_strength

        # Moving Averages Signal
        ma_dir, ma_strength = self._calculate_ma_signal(
            latest["close"],
            latest.get("ema_20", latest["close"]),
            latest.get("ema_50", latest["close"]),
            latest.get("sma_20", latest["close"]),
            latest.get("sma_50", latest["close"])
        )
        signals["moving_averages"] = (ma_dir, ma_strength * weights["moving_averages"])
        signal_weights["moving_averages"] = weights["moving_averages"] * ma_strength

        # Momentum Signal
        mom_dir, mom_strength = self._calculate_momentum_signal(
            latest.get("momentum_10", 0)
        )
        signals["momentum"] = (mom_dir, mom_strength * weights["momentum"])
        signal_weights["momentum"] = weights["momentum"] * mom_strength

        # Volume Signal (modifier)
        vol_type, vol_modifier = self._calculate_volume_signal(
            indicators.get("volume_ratio", 1.0)
        )
        signal_weights["volume"] = weights["volume"]

        # Aggregate signals
        buy_score = 0.0
        sell_score = 0.0

        for indicator, (direction, weighted_strength) in signals.items():
            if direction == "buy":
                buy_score += weighted_strength
            elif direction == "sell":
                sell_score += weighted_strength

        # Apply volume modifier
        buy_score *= vol_modifier
        sell_score *= vol_modifier

        # Determine overall direction and confidence
        total_potential = sum(weights.values())

        if buy_score > sell_score and buy_score > 0.15:
            direction = "buy"
            # Confidence is the buy score normalized to 0-100
            raw_confidence = (buy_score / total_potential) * 100
            # Also factor in how much stronger buy is than sell
            confluence_bonus = min(15, (buy_score - sell_score) * 20)
            confidence = min(95, raw_confidence + confluence_bonus)
        elif sell_score > buy_score and sell_score > 0.15:
            direction = "sell"
            raw_confidence = (sell_score / total_potential) * 100
            confluence_bonus = min(15, (sell_score - buy_score) * 20)
            confidence = min(95, raw_confidence + confluence_bonus)
        else:
            direction = "neutral"
            confidence = 0.0

        # Normalize feature importance
        total_weight = sum(signal_weights.values()) or 1.0
        feature_importance = {k: round(v / total_weight, 2) for k, v in signal_weights.items()}

        return direction, round(confidence, 1), feature_importance

    def _calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        pair: str
    ) -> float:
        """Calculate stop loss price based on ATR."""
        sl_distance = atr * self.SL_ATR_MULTIPLIER

        if direction == "buy":
            stop_loss = entry_price - sl_distance
        else:
            stop_loss = entry_price + sl_distance

        # Round to appropriate decimal places
        if "JPY" in pair:
            return round(stop_loss, 3)
        return round(stop_loss, 5)

    def _calculate_take_profit(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        pair: str
    ) -> float:
        """Calculate take profit price based on ATR and risk/reward."""
        tp_distance = atr * self.TP_ATR_MULTIPLIER

        if direction == "buy":
            take_profit = entry_price + tp_distance
        else:
            take_profit = entry_price - tp_distance

        # Round to appropriate decimal places
        if "JPY" in pair:
            return round(take_profit, 3)
        return round(take_profit, 5)

    def _determine_strategy(self, indicators: Dict, direction: str) -> str:
        """Determine the strategy type based on indicator signals."""
        rsi = indicators.get("rsi", 50)
        bb_position = indicators.get("bb_position", 0.5)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        trend_strength = indicators.get("trend_strength", 50)

        # Mean Reversion
        if (rsi < 35 and direction == "buy") or (rsi > 65 and direction == "sell"):
            if bb_position < 0.2 or bb_position > 0.8:
                return "mean_reversion"

        # Trend Following
        if trend_strength > 60:
            if (direction == "buy" and macd > macd_signal) or \
               (direction == "sell" and macd < macd_signal):
                return "trend_following"

        # Momentum Breakout
        if abs(macd - macd_signal) > 0.0005:
            return "momentum_breakout"

        # Default
        return "multi_indicator_confluence"

    async def _analyze_pair(self, pair: str) -> Optional[TradingSignal]:
        """
        Analyze a single currency pair and generate signal if conditions are met.

        Args:
            pair: Currency pair to analyze (e.g., "EUR_USD")

        Returns:
            TradingSignal if conditions are met, None otherwise
        """
        try:
            client = await self._get_client()

            # Fetch candle data
            df = await client.get_candles(
                instrument=pair,
                granularity=self.ANALYSIS_TIMEFRAME,
                count=self.CANDLE_COUNT
            )

            if df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {pair}: {len(df)} candles")
                return None

            # Calculate all technical indicators
            df = self.indicator_engine.calculate_all(df)

            # Get latest indicator values
            latest = df.iloc[-1]

            indicators = {
                "rsi": round(latest.get("rsi_14", 50), 1),
                "macd": round(latest.get("macd", 0), 6),
                "macd_signal": round(latest.get("macd_signal", 0), 6),
                "bb_position": round(latest.get("bb_position", 0.5), 2),
                "atr": round(latest.get("atr_14", 0), 5),
                "volume_ratio": round(latest.get("volume_ratio", 1.0), 2),
                "trend_strength": round(abs(latest.get("momentum_10", 0)) * 10 + 50, 1),
                "support_level": round(latest.get("bb_lower", latest["close"]), 5),
                "resistance_level": round(latest.get("bb_upper", latest["close"]), 5),
            }

            # Adjust for JPY pairs
            if "JPY" in pair:
                indicators["atr"] = round(latest.get("atr_14", 0), 3)
                indicators["support_level"] = round(latest.get("bb_lower", latest["close"]), 3)
                indicators["resistance_level"] = round(latest.get("bb_upper", latest["close"]), 3)

            # Calculate confluence score
            direction, confidence, feature_importance = self._calculate_confluence_score(
                indicators, df
            )

            # Skip if confidence too low or neutral
            if direction == "neutral" or confidence < self.MIN_CONFIDENCE_THRESHOLD:
                logger.debug(f"{pair}: No signal (direction={direction}, confidence={confidence})")
                return None

            # Get current price for entry
            price_update = await client.get_current_price(pair)
            entry_price = price_update.mid

            # Round entry price appropriately
            if "JPY" in pair:
                entry_price = round(entry_price, 3)
            else:
                entry_price = round(entry_price, 5)

            # Calculate stop loss and take profit
            atr = indicators["atr"]
            stop_loss = self._calculate_stop_loss(entry_price, direction, atr, pair)
            take_profit = self._calculate_take_profit(entry_price, direction, atr, pair)

            # Calculate risk/reward ratio
            sl_distance = abs(entry_price - stop_loss)
            tp_distance = abs(take_profit - entry_price)
            risk_reward = round(tp_distance / sl_distance, 2) if sl_distance > 0 else 2.0

            # Determine strategy
            strategy = self._determine_strategy(indicators, direction)

            # Generate signal
            now = datetime.utcnow()
            signal_id = self._generate_signal_id(pair, direction, now)

            # Check if we already have a recent signal for this pair
            cache_key = f"{pair}_{direction}"
            if cache_key in self._signal_cache:
                cached = self._signal_cache[cache_key]
                if cached.expires_at > now:
                    # Return cached signal with updated status
                    cached.status = self._signal_status_store.get(cached.id, "active")
                    return cached

            signal = TradingSignal(
                id=signal_id,
                pair=pair.replace("_", "/"),
                direction=direction,
                confidence=confidence,
                status="active",
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=risk_reward,
                strategy=strategy,
                created_at=now,
                expires_at=now + timedelta(minutes=self.SIGNAL_EXPIRY_MINUTES),
                indicators=indicators,
                feature_importance=feature_importance,
                similar_historical_trades=int(confidence / 2),  # Estimated
                historical_win_rate=round(50 + confidence / 4, 1),  # Estimated
            )

            # Cache the signal
            self._signal_cache[cache_key] = signal
            self._cache_expiry[cache_key] = signal.expires_at

            logger.info(
                f"Signal generated: {pair} {direction.upper()} @ {entry_price} "
                f"(confidence: {confidence}%, strategy: {strategy})"
            )

            return signal

        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            return None

    async def generate_signals(self, pairs: Optional[List[str]] = None) -> List[TradingSignal]:
        """
        Generate signals for all configured pairs.

        Args:
            pairs: Optional list of pairs to analyze (defaults to configured pairs)

        Returns:
            List of TradingSignal objects
        """
        pairs_to_analyze = pairs or self.pairs
        signals = []

        try:
            # Analyze all pairs concurrently
            tasks = [self._analyze_pair(pair) for pair in pairs_to_analyze]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error analyzing {pairs_to_analyze[i]}: {result}")
                elif result is not None:
                    signals.append(result)

            # Clean up expired signals from cache
            now = datetime.utcnow()
            expired_keys = [k for k, v in self._cache_expiry.items() if v < now]
            for key in expired_keys:
                self._signal_cache.pop(key, None)
                self._cache_expiry.pop(key, None)

            return signals

        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []

    def get_all_signals(self) -> List[TradingSignal]:
        """Get all cached signals (both active and recent)."""
        now = datetime.utcnow()
        signals = []

        for signal in self._signal_cache.values():
            # Update status from store
            stored_status = self._signal_status_store.get(signal.id)
            if stored_status:
                signal.status = stored_status
            elif signal.expires_at < now:
                signal.status = "expired"

            signals.append(signal)

        return signals

    def get_signal_by_id(self, signal_id: str) -> Optional[TradingSignal]:
        """Get a specific signal by ID."""
        for signal in self._signal_cache.values():
            if signal.id == signal_id:
                # Update status from store
                stored_status = self._signal_status_store.get(signal.id)
                if stored_status:
                    signal.status = stored_status
                elif signal.expires_at < datetime.utcnow():
                    signal.status = "expired"
                return signal
        return None

    def update_signal_status(self, signal_id: str, status: str) -> bool:
        """Update the status of a signal."""
        signal = self.get_signal_by_id(signal_id)
        if signal:
            self._signal_status_store[signal_id] = status
            signal.status = status
            return True
        return False


# =============================================================================
# Singleton Instance
# =============================================================================

_signal_generator_instance: Optional[SignalGenerator] = None


def get_signal_generator() -> SignalGenerator:
    """Get or create the signal generator singleton."""
    global _signal_generator_instance

    if _signal_generator_instance is None:
        _signal_generator_instance = SignalGenerator()

    return _signal_generator_instance


async def shutdown_signal_generator() -> None:
    """Shutdown the signal generator and cleanup resources."""
    global _signal_generator_instance

    if _signal_generator_instance is not None:
        await _signal_generator_instance.close()
        _signal_generator_instance = None
