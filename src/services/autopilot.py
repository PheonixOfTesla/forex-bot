from __future__ import annotations

"""
Autopilot Engine - Autonomous Self-Testing & Self-Configuration

Continuously tests the system's own signal generation by paper trading it:

1. Generate signals on an interval (live OANDA data when configured,
   simulated market data otherwise).
2. Auto-execute qualifying signals as paper trades.
3. Monitor open trades against current prices; close at stop loss,
   take profit, or max age.
4. Record every outcome to the LearningEngine, which feeds adjusted
   indicator weights and confidence back into signal generation.
5. Skip setups the learning data has identified as low-effect
   (pairs with a proven losing record).

Over time the system converges on the configuration with the highest
measured effect: winning indicator weights, winning pairs, winning setups.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from ..models.paper_trade import ExecuteTradeRequest, PaperTrade, TradeDirection
from .learning_engine import get_learning_engine
from .paper_trading import get_paper_trading_engine
from .signal_generator import TradingSignal, get_signal_generator

logger = logging.getLogger(__name__)


def _is_oanda_configured() -> bool:
    """Check if OANDA credentials are available via environment."""
    api_key = os.getenv("OANDA_API_KEY") or os.getenv("OANDA_ACCESS_TOKEN")
    account_id = os.getenv("OANDA_ACCOUNT_ID")
    return bool(api_key and account_id)


# =============================================================================
# Price Simulator (used when OANDA is not configured)
# =============================================================================


class PriceSimulator:
    """
    Random-walk market simulator with drifting trends.

    Produces OHLCV candles per pair so the full signal pipeline
    (indicators -> confluence -> learning) can be exercised end-to-end
    without live market data.
    """

    BASE_PRICES = {
        "EUR_USD": 1.0800,
        "GBP_USD": 1.2650,
        "USD_JPY": 149.50,
        "AUD_USD": 0.6550,
        "USD_CAD": 1.3600,
        "EUR_GBP": 0.8550,
    }

    VOLATILITY = 0.0012  # per-candle relative volatility
    HISTORY_LEN = 120

    def __init__(self, pairs: List[str]):
        self.pairs = pairs
        self._history: Dict[str, List[dict]] = {}
        self._drift: Dict[str, float] = {}

        for pair in pairs:
            self._drift[pair] = 0.0
            self._history[pair] = []
            price = self.BASE_PRICES.get(pair, 1.0)
            # Pre-fill history so indicators have enough lookback
            for _ in range(self.HISTORY_LEN):
                candle, price = self._next_candle(pair, price)
                self._history[pair].append(candle)

    def _next_candle(self, pair: str, prev_close: float) -> tuple[dict, float]:
        """Generate one candle continuing from the previous close."""
        # Slowly wandering drift creates realistic trends
        self._drift[pair] += random.gauss(0, 0.00008)
        self._drift[pair] = max(-0.0006, min(0.0006, self._drift[pair]))

        ret = random.gauss(self._drift[pair], self.VOLATILITY)
        open_price = prev_close
        close = prev_close * (1 + ret)
        wick = abs(random.gauss(0, self.VOLATILITY / 2))
        high = max(open_price, close) * (1 + wick)
        low = min(open_price, close) * (1 - wick)
        volume = random.randint(700, 1600)

        candle = {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        return candle, close

    def step(self) -> None:
        """Advance the market by one candle for every pair."""
        for pair in self.pairs:
            prev_close = self._history[pair][-1]["close"]
            candle, _ = self._next_candle(pair, prev_close)
            self._history[pair].append(candle)
            self._history[pair] = self._history[pair][-self.HISTORY_LEN:]

    def dataframe(self, pair: str) -> pd.DataFrame:
        """Get candle history as a DataFrame for indicator calculation."""
        df = pd.DataFrame(self._history[pair])
        df.index = pd.date_range(
            end=datetime.utcnow(), periods=len(df), freq="h"
        )
        return df

    def price(self, pair: str) -> float:
        """Get the current (last close) price for a pair."""
        return self._history[pair][-1]["close"]


# =============================================================================
# Autopilot Engine
# =============================================================================


class AutopilotEngine:
    """
    Background engine that autonomously paper trades and self-configures.
    """

    def __init__(self):
        self.enabled = os.getenv("AUTOPILOT_ENABLED", "true").lower() in (
            "1", "true", "yes", "on",
        )
        self.cycle_seconds = float(os.getenv("AUTOPILOT_CYCLE_SECONDS", "60"))
        self.scan_every_cycles = int(os.getenv("AUTOPILOT_SCAN_CYCLES", "5"))

        # Trade qualification
        self.min_confidence = float(os.getenv("AUTOPILOT_MIN_CONFIDENCE", "62"))
        self.max_open_positions = int(os.getenv("AUTOPILOT_MAX_POSITIONS", "6"))
        self.max_trade_age_hours = float(os.getenv("AUTOPILOT_MAX_TRADE_AGE_HOURS", "24"))

        # Learning-based pair filter: skip pairs proven to lose
        self.pair_filter_min_trades = 10
        self.pair_filter_win_rate_cutoff = 40.0

        self.mode = "live" if _is_oanda_configured() else "simulation"

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._cycle_count = 0
        self._trades_opened = 0
        self._trades_closed = 0
        self._skipped_by_learning = 0
        self._last_cycle_at: Optional[datetime] = None
        self._last_error: Optional[str] = None

        # Signal metadata per open trade id, for learning attribution
        self._signal_meta: Dict[str, dict] = {}

        self._simulator = PriceSimulator(get_signal_generator().pairs)

        logger.info(
            f"AutopilotEngine initialized (mode={self.mode}, enabled={self.enabled})"
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> bool:
        """Start the autopilot background loop."""
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Autopilot started")
        return True

    async def stop(self) -> bool:
        """Stop the autopilot background loop."""
        if not self._running:
            return False
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Autopilot stopped")
        return True

    async def _run_loop(self) -> None:
        """Main background loop."""
        while self._running:
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"Autopilot cycle error: {e}", exc_info=True)
            await asyncio.sleep(self.cycle_seconds)

    # =========================================================================
    # Core Cycle
    # =========================================================================

    async def run_cycle(self) -> None:
        """
        Run one autopilot cycle: advance market, manage positions,
        and periodically scan for new trades.
        """
        self._cycle_count += 1
        self._last_cycle_at = datetime.utcnow()

        if self.mode == "simulation":
            self._simulator.step()

        await self._monitor_positions()

        if (self._cycle_count - 1) % self.scan_every_cycles == 0:
            await self._scan_and_execute()

    async def _current_price(self, display_pair: str) -> Optional[float]:
        """Get current price for a pair like 'EUR/USD'."""
        instrument = display_pair.upper().replace("/", "_")
        if self.mode == "simulation":
            if instrument not in self._simulator._history:
                return None
            return self._simulator.price(instrument)
        try:
            generator = get_signal_generator()
            client = await generator._get_client()
            update = await client.get_current_price(instrument)
            return update.mid
        except Exception as e:
            logger.warning(f"Failed to get price for {display_pair}: {e}")
            return None

    async def _monitor_positions(self) -> None:
        """Close open paper trades that hit SL/TP or exceed max age."""
        engine = get_paper_trading_engine()
        now = datetime.utcnow()

        for trade in list(engine.open_positions):
            price = await self._current_price(trade.pair)
            if price is None:
                continue

            is_long = trade.direction in (TradeDirection.BUY, TradeDirection.LONG)
            reason = None

            if is_long:
                if trade.stop_loss and price <= trade.stop_loss:
                    reason = "stop_loss"
                elif trade.take_profit and price >= trade.take_profit:
                    reason = "take_profit"
            else:
                if trade.stop_loss and price >= trade.stop_loss:
                    reason = "stop_loss"
                elif trade.take_profit and price <= trade.take_profit:
                    reason = "take_profit"

            if reason is None and trade.opened_at:
                age = now - trade.opened_at
                if age > timedelta(hours=self.max_trade_age_hours):
                    reason = "max_age"

            if reason:
                success, _, closed = engine.close_trade(
                    trade.id, price, notes=f"autopilot_close:{reason}"
                )
                if success and closed:
                    self._trades_closed += 1
                    self._record_to_learning(closed)
                    logger.info(
                        f"Autopilot closed {closed.pair} ({reason}) "
                        f"P&L ${closed.pnl:,.2f}"
                    )

    async def _generate_signals(self) -> List[TradingSignal]:
        """Generate signals from live data or the simulator."""
        generator = get_signal_generator()

        if self.mode == "live":
            return await generator.generate_signals()

        signals = []
        for pair in generator.pairs:
            df = self._simulator.dataframe(pair)
            signal = generator.analyze_dataframe(
                pair, df, entry_price=self._simulator.price(pair)
            )
            if signal is not None:
                signals.append(signal)
        return signals

    async def _scan_and_execute(self) -> None:
        """Generate signals and auto-execute the qualifying ones."""
        engine = get_paper_trading_engine()
        learning = get_learning_engine()

        signals = await self._generate_signals()
        if not signals:
            return

        open_pairs = {t.pair for t in engine.open_positions}

        for signal in sorted(signals, key=lambda s: s.confidence, reverse=True):
            if len(engine.open_positions) >= self.max_open_positions:
                break
            if signal.pair in open_pairs:
                continue
            if signal.status != "active":
                continue
            if signal.confidence < self.min_confidence:
                continue

            # Learning-based filter: skip pairs with a proven losing record
            stats = learning.get_pair_stats(signal.pair)
            if (
                stats
                and stats.total_trades >= self.pair_filter_min_trades
                and stats.win_rate < self.pair_filter_win_rate_cutoff
            ):
                self._skipped_by_learning += 1
                logger.info(
                    f"Autopilot skipping {signal.pair}: learned win rate "
                    f"{stats.win_rate:.1f}% over {stats.total_trades} trades"
                )
                continue

            meta = {
                "confidence": signal.confidence,
                "indicators_used": [
                    k for k, v in signal.feature_importance.items() if v > 0
                ],
                "indicator_values": {
                    k: v for k, v in signal.indicators.items()
                    if isinstance(v, (int, float))
                },
                "strategy": signal.strategy,
                "timeframe": "1H",
            }

            success, message, trade = engine.execute_trade(
                ExecuteTradeRequest(
                    signal_id=signal.id,
                    pair=signal.pair,
                    direction=TradeDirection.BUY if signal.direction == "buy" else TradeDirection.SELL,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    notes="autopilot:" + json.dumps(meta),
                )
            )

            if success and trade:
                self._trades_opened += 1
                self._signal_meta[trade.id] = meta
                open_pairs.add(signal.pair)
                logger.info(
                    f"Autopilot executed {signal.pair} {signal.direction} "
                    f"@ {signal.entry_price} (confidence {signal.confidence}%)"
                )
            else:
                logger.warning(f"Autopilot execution failed: {message}")

    # =========================================================================
    # Learning Feedback
    # =========================================================================

    def _get_trade_meta(self, trade: PaperTrade) -> dict:
        """Recover signal metadata for a trade (memory first, then notes)."""
        meta = self._signal_meta.pop(trade.id, None)
        if meta:
            return meta
        if trade.notes and trade.notes.startswith("autopilot:"):
            try:
                json_part = trade.notes.split("\n")[0][len("autopilot:"):]
                return json.loads(json_part)
            except (json.JSONDecodeError, IndexError):
                pass
        return {}

    def _record_to_learning(self, trade: PaperTrade) -> None:
        """Record a closed trade's outcome to the learning engine."""
        try:
            if trade.pnl is None or trade.exit_price is None:
                return

            if trade.pnl > 0:
                outcome = "win"
            elif trade.pnl < 0:
                outcome = "loss"
            else:
                outcome = "breakeven"

            meta = self._get_trade_meta(trade)

            get_learning_engine().track_prediction(
                signal_id=trade.signal_id or trade.id,
                predicted_direction=trade.direction.value,
                predicted_confidence=meta.get("confidence", 60.0),
                actual_outcome=outcome,
                pair=trade.pair,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                entry_timestamp=trade.opened_at,
                exit_timestamp=trade.closed_at or datetime.utcnow(),
                indicators_used=meta.get("indicators_used", []),
                indicator_values=meta.get("indicator_values", {}),
                strategy=meta.get("strategy", "autopilot"),
                timeframe=meta.get("timeframe", "1H"),
            )
        except Exception as e:
            logger.error(f"Failed to record trade to learning: {e}")

    # =========================================================================
    # Status & Config
    # =========================================================================

    def get_status(self) -> dict:
        """Get autopilot status including the learned configuration."""
        paper = get_paper_trading_engine()
        summary = paper.get_summary()

        return {
            "running": self._running,
            "enabled": self.enabled,
            "mode": self.mode,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at,
            "last_error": self._last_error,
            "trades_opened": self._trades_opened,
            "trades_closed": self._trades_closed,
            "skipped_by_learning": self._skipped_by_learning,
            "config": {
                "cycle_seconds": self.cycle_seconds,
                "scan_every_cycles": self.scan_every_cycles,
                "min_confidence": self.min_confidence,
                "max_open_positions": self.max_open_positions,
                "max_trade_age_hours": self.max_trade_age_hours,
                "pair_filter_min_trades": self.pair_filter_min_trades,
                "pair_filter_win_rate_cutoff": self.pair_filter_win_rate_cutoff,
            },
            "paper_account": summary,
            "learned_config": get_learning_engine().get_learned_config(),
        }

    def update_config(self, **kwargs) -> dict:
        """Update runtime configuration. Returns the new config."""
        allowed = {
            "cycle_seconds": float,
            "scan_every_cycles": int,
            "min_confidence": float,
            "max_open_positions": int,
            "max_trade_age_hours": float,
            "pair_filter_min_trades": int,
            "pair_filter_win_rate_cutoff": float,
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(self, key, allowed[key](value))
        return self.get_status()["config"]


# =============================================================================
# Singleton Instance
# =============================================================================

_autopilot: Optional[AutopilotEngine] = None


def get_autopilot() -> AutopilotEngine:
    """Get the singleton autopilot engine."""
    global _autopilot
    if _autopilot is None:
        _autopilot = AutopilotEngine()
    return _autopilot
