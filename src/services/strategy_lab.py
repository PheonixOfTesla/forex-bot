from __future__ import annotations

"""
Strategy Lab - Mass Strategy Testing & Evolution

Tests thousands of candidate strategy configurations per batch against
candle data, keeps a leaderboard of the best performers, breeds mutations
of the winners, and promotes a champion configuration into the live
signal engine.

A "strategy variant" is a full parameterization of the signal engine:
- Per-indicator weights (rsi, macd, bollinger, moving_averages, momentum, volume)
- Minimum confidence threshold to enter a trade
- Stop-loss / take-profit ATR multipliers
- Maximum hold time in candles

Each variant is backtested by replaying the same candle history and
simulating every trade it would have taken. Indicator sub-signals are
precomputed once per batch, so each additional variant costs only
vectorized scoring plus trade simulation - thousands of variants run
in seconds.
"""

import json
import logging
import math
import random
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
LAB_STATE_FILE = DATA_DIR / "strategy_lab.json"

INDICATORS = ["rsi", "macd", "bollinger", "moving_averages", "momentum", "volume"]
DIRECTIONAL = ["rsi", "macd", "bollinger", "moving_averages", "momentum"]

# Minimum backtested trades before a variant can qualify as champion
CHAMPION_MIN_TRADES = 30
CHAMPION_MIN_WIN_RATE = 55.0


# =============================================================================
# Variant generation
# =============================================================================


def random_variant() -> Dict:
    """Generate a random strategy variant."""
    return {
        "id": f"strat_{uuid.uuid4().hex[:10]}",
        "weights": {name: round(random.uniform(0.0, 2.0), 2) for name in INDICATORS},
        "min_confidence": round(random.uniform(50, 78), 1),
        "sl_atr": round(random.uniform(1.0, 3.0), 2),
        "tp_atr": round(random.uniform(1.5, 6.0), 2),
        "max_hold": random.randint(12, 48),
    }


def mutate_variant(parent: Dict) -> Dict:
    """Create a jittered copy of a successful variant."""
    child = {
        "id": f"strat_{uuid.uuid4().hex[:10]}",
        "weights": {
            name: round(
                min(2.0, max(0.0, parent["weights"].get(name, 1.0) + random.gauss(0, 0.15))),
                2,
            )
            for name in INDICATORS
        },
        "min_confidence": round(
            min(78, max(50, parent["min_confidence"] + random.gauss(0, 2))), 1
        ),
        "sl_atr": round(min(3.0, max(1.0, parent["sl_atr"] + random.gauss(0, 0.2))), 2),
        "tp_atr": round(min(6.0, max(1.5, parent["tp_atr"] + random.gauss(0, 0.3))), 2),
        "max_hold": min(48, max(12, parent["max_hold"] + random.randint(-4, 4))),
    }
    return child


# =============================================================================
# Strategy Lab
# =============================================================================


class StrategyLab:
    """
    Batch strategy tester with an evolutionary leaderboard.
    """

    LEADERBOARD_SIZE = 20
    MUTATION_FRACTION = 0.3  # portion of each batch bred from the leaderboard

    def __init__(self):
        self._lock = Lock()
        self.total_variants_tested = 0
        self.total_batches = 0
        self.last_run_at: Optional[datetime] = None
        self.last_batch_seconds: Optional[float] = None
        self.leaderboard: List[Dict] = []
        self.champion: Optional[Dict] = None
        self.champion_applied = False

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()

        logger.info(
            f"StrategyLab initialized: {self.total_variants_tested} variants "
            f"tested across {self.total_batches} batches"
        )

    # =========================================================================
    # Precomputation
    # =========================================================================

    def _precompute_pair(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Precompute per-candle indicator sub-signals for one pair.

        Returns arrays used by every variant's scoring, so the per-variant
        cost is only a weighted sum.
        """
        from ..features.indicators import IndicatorEngine
        from .signal_generator import SignalGenerator

        if df is None or len(df) < 60:
            return None

        engine = IndicatorEngine(lookback_period=100)
        df = engine.calculate_all(df)
        gen = SignalGenerator.__new__(SignalGenerator)  # borrow scoring methods

        T = len(df)
        n = len(DIRECTIONAL)
        dir_mat = np.zeros((n, T))
        str_mat = np.zeros((n, T))
        vol_mod = np.ones(T)

        closes = df["close"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        atrs = df.get("atr_14", pd.Series(np.zeros(T))).fillna(0).to_numpy(dtype=float)

        prev_hist = 0.0
        for t in range(T):
            row = df.iloc[t]

            def val(col, default=0.0):
                v = row.get(col, default)
                return default if pd.isna(v) else v

            subs = [
                gen._calculate_rsi_signal(val("rsi_14", 50)),
                gen._calculate_macd_signal(
                    val("macd"), val("macd_signal"), val("macd_histogram"), prev_hist
                ),
                gen._calculate_bb_signal(
                    val("bb_position", 0.5), val("close"),
                    val("bb_upper", val("close")), val("bb_lower", val("close")),
                ),
                gen._calculate_ma_signal(
                    val("close"), val("ema_20", val("close")), val("ema_50", val("close")),
                    val("sma_20", val("close")), val("sma_50", val("close")),
                ),
                gen._calculate_momentum_signal(val("momentum_10")),
            ]
            prev_hist = val("macd_histogram")

            for i, (direction, strength) in enumerate(subs):
                if direction == "buy":
                    dir_mat[i, t] = 1.0
                elif direction == "sell":
                    dir_mat[i, t] = -1.0
                str_mat[i, t] = strength

            _, vol_mod[t] = gen._calculate_volume_signal(val("volume_ratio", 1.0))

        return {
            "dir": dir_mat,
            "str": str_mat,
            "vol_mod": vol_mod,
            "close": closes,
            "high": highs,
            "low": lows,
            "atr": atrs,
        }

    # =========================================================================
    # Backtesting
    # =========================================================================

    @staticmethod
    def _backtest_variant(variant: Dict, precomputed: Dict[str, Dict]) -> Dict:
        """Backtest one variant across all pairs. Returns aggregate stats."""
        raw_weights = np.array(
            [max(0.001, variant["weights"].get(name, 1.0)) for name in INDICATORS]
        )
        weights = raw_weights / raw_weights.sum()
        w_dir = weights[: len(DIRECTIONAL)]

        min_conf = variant["min_confidence"]
        sl_mult = variant["sl_atr"]
        tp_mult = variant["tp_atr"]
        max_hold = variant["max_hold"]

        wins = losses = 0
        total_pips = 0.0

        for pair, data in precomputed.items():
            dir_mat, str_mat = data["dir"], data["str"]
            vol_mod = data["vol_mod"]
            close, high, low, atr = data["close"], data["high"], data["low"], data["atr"]
            T = len(close)

            contrib = w_dir[:, None] * str_mat
            buy_score = (contrib * (dir_mat > 0)).sum(axis=0) * vol_mod
            sell_score = (contrib * (dir_mat < 0)).sum(axis=0) * vol_mod

            diff = buy_score - sell_score
            conf_buy = np.clip(buy_score * 100 + np.minimum(15, diff * 20), 0, 95)
            conf_sell = np.clip(sell_score * 100 + np.minimum(15, -diff * 20), 0, 95)

            is_buy = (diff > 0) & (buy_score > 0.15) & (conf_buy >= min_conf)
            is_sell = (diff < 0) & (sell_score > 0.15) & (conf_sell >= min_conf)

            pip = 0.01 if "JPY" in pair else 0.0001

            t = 55  # warmup for indicators
            while t < T - 1:
                if not (is_buy[t] or is_sell[t]) or atr[t] <= 0:
                    t += 1
                    continue

                long_trade = bool(is_buy[t])
                entry = close[t]
                sl = entry - atr[t] * sl_mult if long_trade else entry + atr[t] * sl_mult
                tp = entry + atr[t] * tp_mult if long_trade else entry - atr[t] * tp_mult

                exit_price = None
                end = min(T, t + 1 + max_hold)
                for k in range(t + 1, end):
                    if long_trade:
                        if low[k] <= sl:
                            exit_price = sl
                            break
                        if high[k] >= tp:
                            exit_price = tp
                            break
                    else:
                        if high[k] >= sl:
                            exit_price = sl
                            break
                        if low[k] <= tp:
                            exit_price = tp
                            break
                else:
                    k = end - 1
                if exit_price is None:
                    exit_price = close[k]

                pips = (
                    (exit_price - entry) / pip
                    if long_trade
                    else (entry - exit_price) / pip
                )
                total_pips += pips
                if pips > 0:
                    wins += 1
                else:
                    losses += 1

                t = k + 1  # continue after the exit candle

        trades = wins + losses
        win_rate = (wins / trades * 100) if trades else 0.0
        avg_pips = (total_pips / trades) if trades else 0.0
        # Expectancy scaled by evidence: favors profitable AND well-tested variants
        fitness = avg_pips * math.sqrt(trades) if trades else -1e9

        return {
            **variant,
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pips": round(total_pips, 1),
            "avg_pips": round(avg_pips, 2),
            "fitness": round(fitness, 2),
        }

    # =========================================================================
    # Batch Runner
    # =========================================================================

    def run_batch(
        self,
        candle_data: Dict[str, pd.DataFrame],
        batch_size: int = 1000,
    ) -> Dict:
        """
        Test a batch of strategy variants against the given candle data.

        Args:
            candle_data: pair -> OHLCV DataFrame
            batch_size: number of variants to test

        Returns:
            Batch summary with the best variant found.
        """
        started = datetime.utcnow()

        precomputed = {}
        for pair, df in candle_data.items():
            data = self._precompute_pair(df)
            if data is not None:
                precomputed[pair] = data

        if not precomputed:
            logger.warning("StrategyLab: no usable candle data, skipping batch")
            return {"tested": 0, "error": "no usable candle data"}

        # Breed part of the batch from the current leaderboard
        with self._lock:
            parents = list(self.leaderboard)
        n_mutations = int(batch_size * self.MUTATION_FRACTION) if parents else 0

        variants = [random_variant() for _ in range(batch_size - n_mutations)]
        for _ in range(n_mutations):
            variants.append(mutate_variant(random.choice(parents)))

        results = [self._backtest_variant(v, precomputed) for v in variants]

        elapsed = (datetime.utcnow() - started).total_seconds()

        with self._lock:
            self.total_variants_tested += len(results)
            self.total_batches += 1
            self.last_run_at = started
            self.last_batch_seconds = round(elapsed, 2)

            # Merge into leaderboard (dedupe by id, keep best by fitness)
            merged = {e["id"]: e for e in self.leaderboard}
            for r in results:
                if r["trades"] >= 10:
                    merged[r["id"]] = r
            ranked = sorted(merged.values(), key=lambda e: e["fitness"], reverse=True)
            self.leaderboard = ranked[: self.LEADERBOARD_SIZE]

            # Champion: best qualifying leaderboard entry
            for entry in self.leaderboard:
                if (
                    entry["trades"] >= CHAMPION_MIN_TRADES
                    and entry["win_rate"] >= CHAMPION_MIN_WIN_RATE
                ):
                    if self.champion is None or entry["fitness"] > self.champion["fitness"]:
                        self.champion = entry
                        self.champion_applied = False
                        logger.info(
                            f"StrategyLab new champion {entry['id']}: "
                            f"{entry['win_rate']}% win rate, "
                            f"{entry['avg_pips']:+.1f} avg pips over {entry['trades']} trades"
                        )
                    break

            self._save_state()

        best = max(results, key=lambda r: r["fitness"]) if results else None
        logger.info(
            f"StrategyLab batch complete: {len(results)} variants in {elapsed:.1f}s "
            f"(best fitness {best['fitness'] if best else 'n/a'})"
        )

        return {
            "tested": len(results),
            "seconds": round(elapsed, 2),
            "variants_per_second": round(len(results) / elapsed, 1) if elapsed else None,
            "best_this_batch": best,
            "champion": self.champion,
        }

    # =========================================================================
    # Champion application
    # =========================================================================

    def apply_champion(self) -> bool:
        """
        Apply the champion configuration to the live signal generator.

        Returns True if a champion was applied.
        """
        with self._lock:
            champion = self.champion
        if champion is None:
            return False

        from .signal_generator import get_signal_generator

        generator = get_signal_generator()
        generator.weight_overrides = dict(champion["weights"])
        generator.sl_atr_multiplier = champion["sl_atr"]
        generator.tp_atr_multiplier = champion["tp_atr"]
        generator.MIN_CONFIDENCE_THRESHOLD = champion["min_confidence"]

        with self._lock:
            self.champion_applied = True
            self._save_state()

        logger.info(
            f"Champion {champion['id']} applied to signal generator "
            f"(weights={champion['weights']}, sl={champion['sl_atr']}, "
            f"tp={champion['tp_atr']}, min_conf={champion['min_confidence']})"
        )
        return True

    # =========================================================================
    # Status & Persistence
    # =========================================================================

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "total_variants_tested": self.total_variants_tested,
                "total_batches": self.total_batches,
                "last_run_at": self.last_run_at,
                "last_batch_seconds": self.last_batch_seconds,
                "champion": self.champion,
                "champion_applied": self.champion_applied,
                "leaderboard": list(self.leaderboard),
            }

    def _save_state(self) -> None:
        try:
            data = {
                "total_variants_tested": self.total_variants_tested,
                "total_batches": self.total_batches,
                "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
                "leaderboard": self.leaderboard,
                "champion": self.champion,
                "champion_applied": self.champion_applied,
            }
            with open(LAB_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save strategy lab state: {e}")

    def _load_state(self) -> None:
        if not LAB_STATE_FILE.exists():
            return
        try:
            with open(LAB_STATE_FILE, "r") as f:
                data = json.load(f)
            self.total_variants_tested = data.get("total_variants_tested", 0)
            self.total_batches = data.get("total_batches", 0)
            self.leaderboard = data.get("leaderboard", [])
            self.champion = data.get("champion")
            self.champion_applied = data.get("champion_applied", False)
            if data.get("last_run_at"):
                try:
                    self.last_run_at = datetime.fromisoformat(data["last_run_at"])
                except ValueError:
                    pass
        except Exception as e:
            logger.error(f"Failed to load strategy lab state: {e}")


# =============================================================================
# Singleton
# =============================================================================

_strategy_lab: Optional[StrategyLab] = None


def get_strategy_lab() -> StrategyLab:
    """Get the singleton strategy lab."""
    global _strategy_lab
    if _strategy_lab is None:
        _strategy_lab = StrategyLab()
    return _strategy_lab
