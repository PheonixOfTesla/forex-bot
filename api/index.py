"""
Lightning Bot API - Vercel Serverless Function

API for Vercel's serverless environment with MongoDB persistence and OANDA live trading.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random

from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import get_db, check_connection, init_db
from .models import (
    TradeCreate, TradeUpdate, TradeStatus, TradeDirection,
    AccountCreate, AccountUpdate, AccountMode,
    PositionCreate, PositionUpdate,
    TradeDocument, AccountDocument,
)
from .repository import (
    TradeRepository, AccountRepository, PositionRepository,
)
from .broker import get_oanda_client, get_oanda_client_with_db, OandaError, reset_oanda_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lightning Bot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        if os.environ.get("MONGODB_URI"):
            await init_db()
            logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")


# =============================================================================
# Request/Response Models
# =============================================================================

class ExecuteTradeRequest(BaseModel):
    signal_id: Optional[str] = None
    pair: str
    direction: str  # buy, sell, long, short
    entry_price: float
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


class CloseTradeRequest(BaseModel):
    exit_price: float
    notes: Optional[str] = None


class SetModeRequest(BaseModel):
    mode: str  # "paper" or "live"


# =============================================================================
# Helper Functions
# =============================================================================

def normalize_direction(direction: str) -> TradeDirection:
    """Normalize direction to TradeDirection enum."""
    if direction.lower() in ["buy", "long"]:
        return TradeDirection.LONG
    return TradeDirection.SHORT


def format_trade_response(trade: dict) -> dict:
    """Format trade document for API response."""
    return {
        "id": trade.get("_id") or trade.get("id"),
        "signal_id": trade.get("signal_id"),
        "pair": trade["pair"],
        "direction": trade["direction"],
        "entry_price": trade["entry_price"],
        "exit_price": trade.get("exit_price"),
        "size": trade["quantity"],
        "pnl": trade.get("pnl"),
        "pnl_pct": trade.get("pnl_pct"),
        "stop_loss": trade.get("stop_loss"),
        "take_profit": trade.get("take_profit"),
        "opened_at": trade["opened_at"].isoformat() if isinstance(trade["opened_at"], datetime) else trade["opened_at"],
        "closed_at": trade["closed_at"].isoformat() if trade.get("closed_at") and isinstance(trade["closed_at"], datetime) else trade.get("closed_at"),
        "status": trade.get("status", "open"),
        "broker": trade.get("broker", "paper"),
    }


def format_position_response(trade: dict, current_price: Optional[float] = None) -> dict:
    """Format open trade as position response."""
    entry_price = trade["entry_price"]
    quantity = trade["quantity"]
    cp = current_price or entry_price * 1.001  # Simulate slight movement if no price

    if trade["direction"] == "long":
        pnl = (cp - entry_price) * quantity
    else:
        pnl = (entry_price - cp) * quantity

    entry_value = entry_price * quantity
    pnl_pct = (pnl / entry_value * 100) if entry_value > 0 else 0

    return {
        "id": trade.get("_id") or trade.get("id"),
        "signal_id": trade.get("signal_id"),
        "pair": trade["pair"],
        "direction": trade["direction"],
        "entry_price": entry_price,
        "current_price": cp,
        "size": quantity,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "stop_loss": trade.get("stop_loss"),
        "take_profit": trade.get("take_profit"),
        "opened_at": trade["opened_at"].isoformat() if isinstance(trade["opened_at"], datetime) else trade["opened_at"],
        "status": "open",
        "broker": trade.get("broker", "paper"),
    }


async def get_current_price(pair: str) -> Optional[float]:
    """Get current price from OANDA or return None."""
    try:
        oanda = get_oanda_client()
        if oanda.is_configured():
            price = await oanda.get_price(pair)
            if price:
                return price["mid"]
    except Exception as e:
        logger.warning(f"Failed to get price for {pair}: {e}")
    return None


def use_database() -> bool:
    """Check if database is configured."""
    return bool(os.environ.get("MONGODB_URI"))


# =============================================================================
# Fallback In-Memory State (when no database configured)
# =============================================================================

class FallbackState:
    """Fallback in-memory state when database is not configured."""
    def __init__(self):
        self.initial_balance: float = 10000.0
        self.balance: float = 10000.0
        self.open_trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.mode: str = "paper"

_fallback = FallbackState()


# =============================================================================
# Mock Signals (for demo purposes)
# =============================================================================

MOCK_SIGNALS = [
    {
        "id": "sig_001",
        "pair": "EUR/USD",
        "direction": "buy",
        "confidence": 88.0,
        "entry_price": 1.0845,
        "stop_loss": 1.0795,
        "take_profit": 1.0945,
        "strategy": "momentum_breakout",
        "status": "active",
    },
    {
        "id": "sig_002",
        "pair": "GBP/USD",
        "direction": "sell",
        "confidence": 74.8,
        "entry_price": 1.2650,
        "stop_loss": 1.2720,
        "take_profit": 1.2510,
        "strategy": "mean_reversion",
        "status": "active",
    },
    {
        "id": "sig_003",
        "pair": "USD/JPY",
        "direction": "buy",
        "confidence": 81.3,
        "entry_price": 148.559,
        "stop_loss": 147.668,
        "take_profit": 150.342,
        "strategy": "trend_following",
        "status": "active",
    },
]


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {"name": "Lightning Bot API", "version": "2.0.0", "status": "operational"}


@app.get("/health")
async def health():
    db_status = "not_configured"
    oanda_status = "not_configured"

    if use_database():
        db_status = "connected" if await check_connection() else "disconnected"

    oanda = get_oanda_client()
    if oanda.is_configured():
        try:
            await oanda.get_account()
            oanda_status = "connected"
        except Exception:
            oanda_status = "error"

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "oanda": oanda_status,
    }


@app.get("/api/v1/health")
async def health_v1():
    return await health()


@app.get("/ping")
async def ping():
    return {"pong": True}


# =============================================================================
# Account Mode
# =============================================================================

@app.get("/api/v1/account/mode")
async def get_account_mode():
    """Get current trading mode."""
    if use_database():
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        return {"mode": account.mode.value if hasattr(account.mode, 'value') else account.mode}
    return {"mode": _fallback.mode}


@app.post("/api/v1/account/mode")
async def set_account_mode(request: SetModeRequest):
    """Set trading mode (paper or live)."""
    mode = AccountMode.LIVE if request.mode == "live" else AccountMode.PAPER

    if mode == AccountMode.LIVE:
        oanda = get_oanda_client()
        if not oanda.is_configured():
            raise HTTPException(
                status_code=400,
                detail="OANDA credentials not configured. Set OANDA_ACCOUNT_ID and OANDA_ACCESS_TOKEN."
            )

    if use_database():
        # Get or create both accounts
        await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        await AccountRepository.get_or_create_account("default", AccountMode.LIVE)

        # Update mode on paper account (we use paper account doc to track mode)
        db = await get_db()
        await db.accounts.update_one(
            {"user_id": "default", "mode": AccountMode.PAPER.value},
            {"$set": {"current_mode": mode.value}}
        )

        return {"success": True, "mode": mode.value}

    _fallback.mode = mode.value
    return {"success": True, "mode": mode.value}


# =============================================================================
# Dashboard
# =============================================================================

@app.get("/api/v1/dashboard")
async def dashboard():
    if use_database():
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        open_trades = await TradeRepository.get_open_trades("default")
        stats = await TradeRepository.get_trade_stats("default")

        # Calculate unrealized P&L
        total_unrealized = 0.0
        positions = []
        for trade in open_trades:
            pos = format_position_response(trade.__dict__ if hasattr(trade, '__dict__') else trade)
            total_unrealized += pos["pnl"]
            positions.append(pos)

        balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)
        initial = account.initial_balance if hasattr(account, 'initial_balance') else account.get("initial_balance", 10000)

        return {
            "balance": balance,
            "equity": balance + total_unrealized,
            "today_pnl": round(total_unrealized, 2),
            "today_pnl_pct": round((total_unrealized / initial) * 100, 2) if initial > 0 else 0,
            "win_rate": stats.get("win_rate", 0),
            "total_trades": stats.get("total_trades", 0),
            "open_positions_count": len(open_trades),
            "ml_signals": MOCK_SIGNALS[:2],
            "open_positions": positions,
            "last_updated": datetime.utcnow().isoformat(),
        }

    # Fallback in-memory
    positions = []
    total_unrealized = 0.0
    for trade in _fallback.open_trades:
        pos = format_position_response(trade)
        total_unrealized += pos["pnl"]
        positions.append(pos)

    wins = len([t for t in _fallback.closed_trades if t.get("pnl", 0) > 0])
    total = len(_fallback.closed_trades)

    return {
        "balance": _fallback.balance,
        "equity": _fallback.balance + total_unrealized,
        "today_pnl": round(total_unrealized, 2),
        "today_pnl_pct": round((total_unrealized / _fallback.initial_balance) * 100, 2) if _fallback.initial_balance > 0 else 0,
        "win_rate": (wins / total * 100) if total > 0 else 0,
        "total_trades": total,
        "open_positions_count": len(_fallback.open_trades),
        "ml_signals": MOCK_SIGNALS[:2],
        "open_positions": positions,
        "last_updated": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Signals
# =============================================================================

@app.get("/api/v1/signals")
async def signals():
    return MOCK_SIGNALS


@app.get("/api/v1/signals/summary")
async def signals_summary():
    return {
        "total": len(MOCK_SIGNALS),
        "active": len([s for s in MOCK_SIGNALS if s["status"] == "active"]),
        "data_source": "mock",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/signals/{signal_id}")
async def get_signal(signal_id: str = Path(...)):
    for signal in MOCK_SIGNALS:
        if signal["id"] == signal_id:
            return signal
    raise HTTPException(status_code=404, detail=f"Signal not found: {signal_id}")


# =============================================================================
# Engine
# =============================================================================

@app.get("/api/v1/engine/status")
async def engine_status():
    return {
        "status": "running",
        "uptime_seconds": 3600,
        "components": {
            "websocket_feed": "running",
            "ml_classifier": "running",
            "risk_manager": "running",
        }
    }


# =============================================================================
# Wallet
# =============================================================================

@app.get("/api/v1/wallet")
async def wallet():
    if use_database():
        paper = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        live = await AccountRepository.get_or_create_account("default", AccountMode.LIVE)

        paper_bal = paper.balance if hasattr(paper, 'balance') else paper.get("balance", 10000)
        paper_init = paper.initial_balance if hasattr(paper, 'initial_balance') else paper.get("initial_balance", 10000)
        live_bal = live.balance if hasattr(live, 'balance') else live.get("balance", 0)

        # Sync live balance from OANDA if configured
        oanda = get_oanda_client()
        if oanda.is_configured():
            try:
                live_bal = await oanda.get_account_balance()
            except Exception as e:
                logger.warning(f"Failed to sync OANDA balance: {e}")

        return {
            "mode": "paper",  # Default mode
            "balance": paper_bal,
            "paper_balance": paper_bal,
            "live_balance": live_bal,
            "total_pnl": paper_bal - paper_init,
        }

    return {
        "mode": _fallback.mode,
        "balance": _fallback.balance,
        "paper_balance": _fallback.balance,
        "live_balance": 0.0,
        "total_pnl": _fallback.balance - _fallback.initial_balance,
    }


@app.get("/api/v1/wallet/balance-history")
async def wallet_balance_history(days: int = Query(default=30, ge=1, le=365)):
    """Get balance history for chart display."""
    if use_database():
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)
        initial = account.initial_balance if hasattr(account, 'initial_balance') else account.get("initial_balance", 10000)
    else:
        balance = _fallback.balance
        initial = _fallback.initial_balance

    # Generate mock balance history
    history = []
    base_balance = initial
    for i in range(days):
        day_offset = days - i
        timestamp = datetime.utcnow() - timedelta(days=day_offset)
        daily_change = random.uniform(-50, 100)
        base_balance += daily_change
        base_balance = max(base_balance, initial * 0.9)
        history.append({
            "timestamp": timestamp.isoformat(),
            "balance": round(base_balance, 2),
        })

    if history:
        history[-1]["balance"] = balance

    return history


# =============================================================================
# Predictions
# =============================================================================

@app.get("/api/v1/predictions")
async def predictions():
    base_prices = {
        "EUR/USD": 1.0845,
        "GBP/USD": 1.2650,
        "USD/JPY": 148.55,
        "BTC/USD": 67500.00,
        "ETH/USD": 3450.00,
    }

    key_factors_pool = [
        "Strong momentum indicators",
        "RSI showing oversold conditions",
        "MACD bullish crossover",
        "Support level holding",
        "Resistance level approaching",
        "Volume increasing",
        "Moving average convergence",
        "Fibonacci retracement at 61.8%",
        "Bollinger bands squeeze",
        "ADX trending strength",
    ]

    preds = []
    now = datetime.utcnow()

    for pair in base_prices.keys():
        current_price = base_prices[pair]
        direction = random.choice(["UP", "DOWN"])
        confidence = round(random.uniform(65, 92), 1)

        if direction == "UP":
            predicted_low = current_price * 0.998
            predicted_high = current_price * 1.008
        else:
            predicted_low = current_price * 0.992
            predicted_high = current_price * 1.002

        preds.append({
            "pair": pair,
            "timeframe": "1h",
            "direction": direction,
            "confidence": confidence,
            "current_price": current_price,
            "predicted_low": round(predicted_low, 5 if "JPY" not in pair and "BTC" not in pair and "ETH" not in pair else 2),
            "predicted_high": round(predicted_high, 5 if "JPY" not in pair and "BTC" not in pair and "ETH" not in pair else 2),
            "key_factors": random.sample(key_factors_pool, 3),
            "generated_at": now.isoformat(),
            "valid_until": (now + timedelta(hours=1)).isoformat(),
        })

    return {"predictions": preds, "total": len(preds)}


@app.get("/api/v1/predictions/accuracy")
async def predictions_accuracy():
    return {
        "overall_accuracy": {"1h": 72.5, "4h": 68.3, "24h": 61.2},
        "by_pair": {},
    }


# =============================================================================
# Intelligence
# =============================================================================

@app.get("/api/v1/intelligence/sentiment")
async def sentiment():
    return {
        "fear_greed_index": 58.5,
        "fear_greed_label": "Greed",
        "market_mood": "bullish",
        "pair_sentiments": {
            "EUR/USD": {"bullish": 55, "bearish": 30, "neutral": 15, "overall": "bullish"},
            "GBP/USD": {"bullish": 40, "bearish": 45, "neutral": 15, "overall": "bearish"},
            "USD/JPY": {"bullish": 60, "bearish": 25, "neutral": 15, "overall": "bullish"},
            "BTC/USD": {"bullish": 70, "bearish": 20, "neutral": 10, "overall": "bullish"},
            "ETH/USD": {"bullish": 45, "bearish": 40, "neutral": 15, "overall": "neutral"},
        },
    }


@app.get("/api/v1/intelligence/indicators")
async def indicators():
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD", "ETH/USD"]
    indicators_data = []

    for pair in pairs:
        rsi_value = round(random.uniform(25, 75), 1)
        rsi_signal = "oversold" if rsi_value < 30 else ("overbought" if rsi_value > 70 else "neutral")

        adx_value = round(random.uniform(15, 45), 1)
        adx_strength = "strong" if adx_value > 25 else "weak"

        macd_trend = random.choice(["bullish", "bearish"])
        ma_trend = random.choice(["bullish", "bearish"])

        overall = "bullish" if (macd_trend == "bullish" and ma_trend == "bullish") else (
            "bearish" if (macd_trend == "bearish" and ma_trend == "bearish") else "neutral"
        )

        indicators_data.append({
            "pair": pair,
            "rsi": {"value": rsi_value, "signal": rsi_signal},
            "macd": {"value": round(random.uniform(-0.5, 0.5), 4), "histogram": round(random.uniform(-0.2, 0.2), 4), "trend": macd_trend},
            "moving_averages": {"trend": ma_trend},
            "bollinger_bands": {"position": round(random.uniform(0, 100), 1), "squeeze": random.choice([True, False])},
            "adx": {"value": adx_value, "trend_strength": adx_strength},
            "overall_bias": overall,
        })

    return {"indicators": indicators_data, "updated_at": datetime.utcnow().isoformat()}


@app.get("/api/v1/intelligence/insights")
async def insights():
    now = datetime.utcnow()
    insights_data = [
        {
            "id": "ins_001",
            "title": "USD Strengthening Trend",
            "content": "The US Dollar is showing signs of strength against major pairs.",
            "category": "market_analysis",
            "priority": "high",
            "pairs_affected": ["EUR/USD", "GBP/USD"],
            "generated_at": now.isoformat(),
        },
        {
            "id": "ins_002",
            "title": "BTC Volatility Alert",
            "content": "Bitcoin volatility is expected to increase ahead of upcoming announcements.",
            "category": "risk_alert",
            "priority": "medium",
            "pairs_affected": ["BTC/USD", "ETH/USD"],
            "generated_at": now.isoformat(),
        },
    ]
    return {"insights": insights_data, "total": len(insights_data)}


@app.get("/api/v1/intelligence/patterns")
async def patterns():
    patterns_data = [
        {
            "id": "pat_001",
            "pair": "EUR/USD",
            "pattern_name": "Double Bottom",
            "pattern_type": "reversal",
            "direction": "bullish",
            "timeframe": "4h",
            "completion_percentage": 85,
            "reliability_score": 72,
        },
        {
            "id": "pat_002",
            "pair": "GBP/USD",
            "pattern_name": "Descending Triangle",
            "pattern_type": "continuation",
            "direction": "bearish",
            "timeframe": "1h",
            "completion_percentage": 92,
            "reliability_score": 68,
        },
    ]
    return {"patterns": patterns_data, "total": len(patterns_data)}


# =============================================================================
# Trades & History
# =============================================================================

@app.get("/api/v1/trades")
async def trades():
    if use_database():
        closed = await TradeRepository.get_closed_trades("default")
        return [format_trade_response(t.__dict__ if hasattr(t, '__dict__') else t) for t in closed]
    return _fallback.closed_trades


@app.get("/api/v1/performance")
async def performance():
    if use_database():
        stats = await TradeRepository.get_trade_stats("default")
        return {
            "period_days": 30,
            "total_trades": stats.get("total_trades", 0),
            "win_rate": round(stats.get("win_rate", 0), 1),
            "total_pnl": round(stats.get("total_pnl", 0), 2),
        }

    total_pnl = sum(t.get("pnl", 0) for t in _fallback.closed_trades)
    wins = len([t for t in _fallback.closed_trades if t.get("pnl", 0) > 0])
    total = len(_fallback.closed_trades)
    return {
        "period_days": 30,
        "total_trades": total,
        "win_rate": round((wins / total * 100) if total > 0 else 0, 1),
        "total_pnl": round(total_pnl, 2),
    }


# =============================================================================
# Settings
# =============================================================================

class SaveSettingsRequest(BaseModel):
    """Request to save settings."""
    oanda_account_id: Optional[str] = None
    oanda_access_token: Optional[str] = None
    oanda_environment: Optional[str] = None
    trading_mode: Optional[str] = None
    risk_per_trade: Optional[float] = None
    max_daily_trades: Optional[int] = None
    max_daily_loss: Optional[float] = None
    ml_confidence_threshold: Optional[float] = None


@app.get("/api/v1/settings")
async def get_settings():
    """Get current settings."""
    if use_database():
        from .repository import SettingsRepository
        settings = await SettingsRepository.get_or_create_settings("default")

        # Mask the access token for security
        oanda_configured = bool(settings.get("oanda_account_id") and settings.get("oanda_access_token"))
        masked_account_id = None
        if settings.get("oanda_account_id"):
            aid = settings["oanda_account_id"]
            masked_account_id = f"{aid[:8]}...{aid[-4:]}" if len(aid) > 12 else aid

        return {
            "trading_mode": settings.get("trading_mode", "paper"),
            "oanda_configured": oanda_configured,
            "oanda_account_id": masked_account_id,
            "oanda_environment": settings.get("oanda_environment", "practice"),
            "risk_per_trade": settings.get("risk_per_trade", 0.02),
            "max_daily_trades": settings.get("max_daily_trades", 10),
            "max_daily_loss": settings.get("max_daily_loss", 0.06),
            "ml_confidence_threshold": settings.get("ml_confidence_threshold", 0.70),
        }

    # Fallback when no database
    return {
        "trading_mode": "paper",
        "oanda_configured": False,
        "oanda_account_id": None,
        "oanda_environment": "practice",
        "risk_per_trade": 0.02,
        "max_daily_trades": 10,
        "max_daily_loss": 0.06,
        "ml_confidence_threshold": 0.70,
    }


@app.post("/api/v1/settings")
async def save_settings(request: SaveSettingsRequest):
    """Save settings including OANDA credentials."""
    if not use_database():
        raise HTTPException(
            status_code=400,
            detail="Database not configured. Cannot save settings."
        )

    from .repository import SettingsRepository
    from .broker import reset_oanda_client

    # Build updates dict with only provided fields
    updates = {}
    if request.oanda_account_id is not None:
        updates["oanda_account_id"] = request.oanda_account_id
    if request.oanda_access_token is not None:
        updates["oanda_access_token"] = request.oanda_access_token
    if request.oanda_environment is not None:
        updates["oanda_environment"] = request.oanda_environment
    if request.trading_mode is not None:
        updates["trading_mode"] = request.trading_mode
    if request.risk_per_trade is not None:
        updates["risk_per_trade"] = request.risk_per_trade
    if request.max_daily_trades is not None:
        updates["max_daily_trades"] = request.max_daily_trades
    if request.max_daily_loss is not None:
        updates["max_daily_loss"] = request.max_daily_loss
    if request.ml_confidence_threshold is not None:
        updates["ml_confidence_threshold"] = request.ml_confidence_threshold

    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update")

    # Save to database
    await SettingsRepository.update_settings("default", updates)

    # Reset OANDA client to pick up new credentials
    reset_oanda_client()

    # Verify OANDA connection if credentials were updated
    oanda_status = None
    if request.oanda_account_id and request.oanda_access_token:
        from .broker import get_oanda_client_with_db
        try:
            client = await get_oanda_client_with_db("default")
            if client.is_configured():
                account = await client.get_account()
                oanda_status = {
                    "connected": True,
                    "balance": float(account.get("balance", 0)),
                    "currency": account.get("currency", "USD"),
                }
        except Exception as e:
            oanda_status = {
                "connected": False,
                "error": str(e),
            }

    return {
        "success": True,
        "message": "Settings saved successfully",
        "oanda_status": oanda_status,
    }


@app.post("/api/v1/settings/test-oanda")
async def test_oanda_connection():
    """Test OANDA connection with saved credentials."""
    if not use_database():
        raise HTTPException(status_code=400, detail="Database not configured")

    from .broker import get_oanda_client_with_db

    try:
        client = await get_oanda_client_with_db("default")

        if not client.is_configured():
            return {
                "success": False,
                "error": "OANDA credentials not configured",
            }

        account = await client.get_account()

        return {
            "success": True,
            "account": {
                "id": account.get("id"),
                "balance": float(account.get("balance", 0)),
                "currency": account.get("currency", "USD"),
                "nav": float(account.get("NAV", 0)),
                "unrealized_pnl": float(account.get("unrealizedPL", 0)),
                "open_trades": int(account.get("openTradeCount", 0)),
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Paper Trading Endpoints
# =============================================================================

@app.get("/api/v1/paper/balance")
async def paper_balance():
    """Get paper trading balance and metrics."""
    if use_database():
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        open_trades = await TradeRepository.get_open_trades("default")
        stats = await TradeRepository.get_trade_stats("default")

        balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)
        initial = account.initial_balance if hasattr(account, 'initial_balance') else account.get("initial_balance", 10000)

        unrealized_pnl = 0.0
        used_margin = 0.0
        for trade in open_trades:
            t = trade.__dict__ if hasattr(trade, '__dict__') else trade
            pos = format_position_response(t)
            unrealized_pnl += pos["pnl"]
            used_margin += t["entry_price"] * t["quantity"]

        realized_pnl = stats.get("total_pnl", 0)

        return {
            "balance": balance,
            "equity": balance + unrealized_pnl,
            "available_margin": balance,
            "used_margin": round(used_margin, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "total_pnl": round(realized_pnl + unrealized_pnl, 2),
            "initial_balance": initial,
            "pnl_percentage": round(((balance - initial) / initial * 100), 2) if initial > 0 else 0,
        }

    # Fallback
    wins = len([t for t in _fallback.closed_trades if t.get("pnl", 0) > 0])
    realized_pnl = sum(t.get("pnl", 0) for t in _fallback.closed_trades)
    unrealized_pnl = sum(
        (t["entry_price"] * 0.001 * t["quantity"]) if t["direction"] == "long" else -(t["entry_price"] * 0.001 * t["quantity"])
        for t in _fallback.open_trades
    )
    used_margin = sum(t["entry_price"] * t["quantity"] for t in _fallback.open_trades)

    return {
        "balance": _fallback.balance,
        "equity": _fallback.balance + unrealized_pnl,
        "available_margin": _fallback.balance,
        "used_margin": round(used_margin, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(realized_pnl + unrealized_pnl, 2),
        "initial_balance": _fallback.initial_balance,
        "pnl_percentage": round(((_fallback.balance - _fallback.initial_balance) / _fallback.initial_balance * 100), 2),
    }


@app.get("/api/v1/paper/positions")
async def paper_positions():
    """Get open paper positions."""
    if use_database():
        open_trades = await TradeRepository.get_open_trades("default")
        return [format_position_response(t.__dict__ if hasattr(t, '__dict__') else t) for t in open_trades]

    return [format_position_response(t) for t in _fallback.open_trades]


@app.get("/api/v1/paper/history")
async def paper_history(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    pair: Optional[str] = Query(default=None),
):
    """Get paper trade history."""
    if use_database():
        closed = await TradeRepository.get_closed_trades("default", limit=limit, offset=offset)
        stats = await TradeRepository.get_trade_stats("default")

        trades = []
        for trade in closed:
            t = trade.__dict__ if hasattr(trade, '__dict__') else trade
            result = "win" if t.get("pnl", 0) > 0 else ("loss" if t.get("pnl", 0) < 0 else "breakeven")
            resp = format_trade_response(t)
            resp["result"] = result
            trades.append(resp)

        return {
            "trades": trades,
            "total_count": stats.get("total_trades", 0),
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "win_rate": round(stats.get("win_rate", 0), 2),
        }

    # Fallback
    all_trades = _fallback.closed_trades
    if pair:
        all_trades = [t for t in all_trades if t["pair"].upper() == pair.upper()]

    all_trades = sorted(all_trades, key=lambda t: t.get("closed_at", ""), reverse=True)
    paginated = all_trades[offset:offset + limit]

    formatted = []
    for t in paginated:
        result = "win" if t.get("pnl", 0) > 0 else ("loss" if t.get("pnl", 0) < 0 else "breakeven")
        formatted.append({**format_trade_response(t), "result": result})

    wins = len([t for t in all_trades if t.get("pnl", 0) > 0])
    losses = len([t for t in all_trades if t.get("pnl", 0) < 0])
    total = len(all_trades)

    return {
        "trades": formatted,
        "total_count": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total * 100) if total > 0 else 0, 2),
    }


@app.post("/api/v1/paper/execute")
async def execute_paper_trade(request: ExecuteTradeRequest):
    """Execute a paper trade."""
    direction = normalize_direction(request.direction)

    if use_database():
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)

        # Calculate quantity
        quantity = request.quantity
        if quantity is None:
            position_value = balance * 0.02
            quantity = position_value / request.entry_price

        position_value = request.entry_price * quantity

        if position_value > balance:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance: need ${position_value:.2f}, have ${balance:.2f}",
            )

        # Create trade in DB
        trade_data = TradeCreate(
            user_id="default",
            pair=request.pair,
            direction=direction,
            entry_price=request.entry_price,
            quantity=quantity,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            signal_id=request.signal_id,
        )
        trade = await TradeRepository.create_trade(trade_data)

        # Update account balance
        new_balance = balance - position_value
        await AccountRepository.update_account(
            "default",
            AccountMode.PAPER,
            AccountUpdate(balance=new_balance)
        )

        trade_dict = trade.__dict__ if hasattr(trade, '__dict__') else trade
        return {
            "success": True,
            "trade_id": trade_dict.get("_id") or trade_dict.get("id"),
            "message": f"Trade executed: {direction.value} {quantity:.4f} {request.pair} @ ${request.entry_price:.4f}",
            "trade": format_trade_response(trade_dict),
            "new_balance": new_balance,
        }

    # Fallback
    quantity = request.quantity or (_fallback.balance * 0.02 / request.entry_price)
    position_value = request.entry_price * quantity

    if position_value > _fallback.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance: need ${position_value:.2f}, have ${_fallback.balance:.2f}",
        )

    import uuid
    trade_id = f"pt_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    trade = {
        "id": trade_id,
        "_id": trade_id,
        "signal_id": request.signal_id,
        "pair": request.pair,
        "direction": direction.value,
        "entry_price": request.entry_price,
        "quantity": quantity,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "status": "open",
        "opened_at": now,
        "broker": "paper",
    }

    _fallback.balance -= position_value
    _fallback.open_trades.append(trade)

    return {
        "success": True,
        "trade_id": trade_id,
        "message": f"Trade executed: {direction.value} {quantity:.4f} {request.pair} @ ${request.entry_price:.4f}",
        "trade": format_trade_response(trade),
        "new_balance": _fallback.balance,
    }


@app.post("/api/v1/paper/positions/{trade_id}/close")
async def close_paper_position(
    trade_id: str = Path(...),
    request: CloseTradeRequest = None,
):
    """Close an open paper position."""
    if request is None:
        raise HTTPException(status_code=400, detail="Exit price is required")

    if use_database():
        trade = await TradeRepository.get_trade(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail=f"Trade not found: {trade_id}")

        trade_dict = trade.__dict__ if hasattr(trade, '__dict__') else trade

        # Close trade
        closed = await TradeRepository.close_trade(trade_id, request.exit_price, request.notes)
        if not closed:
            raise HTTPException(status_code=400, detail="Failed to close trade")

        closed_dict = closed.__dict__ if hasattr(closed, '__dict__') else closed
        pnl = closed_dict.get("pnl", 0)

        # Update account balance
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)

        # Return position value + P&L
        entry_value = trade_dict["entry_price"] * trade_dict["quantity"]
        new_balance = balance + entry_value + pnl

        trade_result = "win" if pnl > 0 else ("loss" if pnl < 0 else None)
        await AccountRepository.update_account_balance(
            "default", AccountMode.PAPER, pnl,
            is_realized_pnl=True, trade_result=trade_result
        )
        await AccountRepository.update_account(
            "default", AccountMode.PAPER, AccountUpdate(balance=new_balance)
        )

        return {
            "success": True,
            "trade_id": trade_id,
            "message": f"Trade closed: {trade_dict['pair']} @ ${request.exit_price:.4f}, P&L: ${pnl:.2f}",
            "trade": format_trade_response(closed_dict),
            "new_balance": new_balance,
        }

    # Fallback
    trade = None
    trade_index = None
    for i, t in enumerate(_fallback.open_trades):
        if t["id"] == trade_id or t.get("_id") == trade_id:
            trade = t
            trade_index = i
            break

    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade not found: {trade_id}")

    # Calculate P&L
    entry_value = trade["entry_price"] * trade["quantity"]
    exit_value = request.exit_price * trade["quantity"]

    if trade["direction"] == "long":
        pnl = exit_value - entry_value
    else:
        pnl = entry_value - exit_value

    pnl_pct = (pnl / entry_value) * 100

    # Close the trade
    now = datetime.utcnow().isoformat()
    trade["exit_price"] = request.exit_price
    trade["pnl"] = round(pnl, 2)
    trade["pnl_pct"] = round(pnl_pct, 2)
    trade["status"] = "closed"
    trade["closed_at"] = now

    _fallback.balance += entry_value + pnl
    _fallback.open_trades.pop(trade_index)
    _fallback.closed_trades.append(trade)

    return {
        "success": True,
        "trade_id": trade_id,
        "message": f"Trade closed: {trade['pair']} @ ${request.exit_price:.4f}, P&L: ${pnl:.2f} ({pnl_pct:.2f}%)",
        "trade": format_trade_response(trade),
        "new_balance": _fallback.balance,
    }


@app.post("/api/v1/paper/reset")
async def reset_paper_account(new_balance: Optional[float] = Query(default=None, gt=0)):
    """Reset the paper trading account."""
    balance = new_balance or 10000.0

    if use_database():
        # Get previous stats
        account = await AccountRepository.get_or_create_account("default", AccountMode.PAPER)
        prev_balance = account.balance if hasattr(account, 'balance') else account.get("balance", 10000)
        stats = await TradeRepository.get_trade_stats("default")

        # Reset account
        await AccountRepository.reset_account("default", AccountMode.PAPER, balance)

        # Delete all trades
        db = await get_db()
        await db.trades.delete_many({"user_id": "default"})

        return {
            "success": True,
            "message": f"Account reset to ${balance:,.2f}",
            "new_balance": balance,
            "previous_balance": prev_balance,
            "previous_total_pnl": stats.get("total_pnl", 0),
        }

    # Fallback
    prev_balance = _fallback.balance
    prev_pnl = sum(t.get("pnl", 0) for t in _fallback.closed_trades)

    _fallback.initial_balance = balance
    _fallback.balance = balance
    _fallback.open_trades.clear()
    _fallback.closed_trades.clear()

    return {
        "success": True,
        "message": f"Account reset to ${balance:,.2f}",
        "new_balance": balance,
        "previous_balance": prev_balance,
        "previous_total_pnl": prev_pnl,
    }


# =============================================================================
# Live Trading Endpoints (OANDA)
# =============================================================================

@app.get("/api/v1/live/balance")
async def live_balance():
    """Get live trading balance from OANDA."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    try:
        account = await oanda.get_account()
        return {
            "balance": float(account.get("balance", 0)),
            "equity": float(account.get("NAV", 0)),
            "unrealized_pnl": float(account.get("unrealizedPL", 0)),
            "margin_used": float(account.get("marginUsed", 0)),
            "margin_available": float(account.get("marginAvailable", 0)),
            "open_trade_count": int(account.get("openTradeCount", 0)),
            "currency": account.get("currency", "USD"),
        }
    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/live/positions")
async def live_positions():
    """Get live positions from OANDA."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    try:
        positions = await oanda.get_positions()
        formatted = []
        for pos in positions:
            instrument = pos["instrument"].replace("_", "/")

            # Long position
            long_units = float(pos.get("long", {}).get("units", 0))
            if long_units > 0:
                formatted.append({
                    "id": f"{pos['instrument']}_long",
                    "pair": instrument,
                    "direction": "long",
                    "size": long_units,
                    "entry_price": float(pos.get("long", {}).get("averagePrice", 0)),
                    "pnl": float(pos.get("long", {}).get("unrealizedPL", 0)),
                    "broker": "oanda",
                })

            # Short position
            short_units = abs(float(pos.get("short", {}).get("units", 0)))
            if short_units > 0:
                formatted.append({
                    "id": f"{pos['instrument']}_short",
                    "pair": instrument,
                    "direction": "short",
                    "size": short_units,
                    "entry_price": float(pos.get("short", {}).get("averagePrice", 0)),
                    "pnl": float(pos.get("short", {}).get("unrealizedPL", 0)),
                    "broker": "oanda",
                })

        return formatted
    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/live/execute")
async def execute_live_trade(request: ExecuteTradeRequest):
    """Execute a live trade on OANDA."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    direction = normalize_direction(request.direction)

    # Calculate units (positive for buy, negative for sell)
    quantity = request.quantity
    if quantity is None:
        # Get account balance and use 2%
        balance = await oanda.get_account_balance()
        position_value = balance * 0.02
        quantity = int(position_value / request.entry_price)

    units = int(quantity) if direction == TradeDirection.LONG else -int(quantity)

    try:
        result = await oanda.place_market_order(
            instrument=request.pair,
            units=units,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )

        # Extract fill info
        order_fill = result.get("orderFillTransaction", {})
        trade_opened = order_fill.get("tradeOpened", {})

        oanda_trade_id = trade_opened.get("tradeID")
        fill_price = float(order_fill.get("price", request.entry_price))
        fill_units = abs(int(order_fill.get("units", units)))

        # Store in DB if configured
        if use_database():
            trade_data = TradeCreate(
                user_id="default",
                pair=request.pair,
                direction=direction,
                entry_price=fill_price,
                quantity=fill_units,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                signal_id=request.signal_id,
            )
            trade = await TradeRepository.create_trade(trade_data)
            trade_dict = trade.__dict__ if hasattr(trade, '__dict__') else trade

            # Store OANDA trade ID
            if oanda_trade_id:
                db = await get_db()
                await db.trades.update_one(
                    {"_id": trade_dict.get("_id") or trade_dict.get("id")},
                    {"$set": {"oanda_trade_id": oanda_trade_id, "broker": "oanda"}}
                )

        return {
            "success": True,
            "trade_id": oanda_trade_id,
            "message": f"Live trade executed: {direction.value} {fill_units} {request.pair} @ ${fill_price:.5f}",
            "fill_price": fill_price,
            "fill_units": fill_units,
            "oanda_response": result,
        }

    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/live/close/{trade_id}")
async def close_live_trade(trade_id: str = Path(...)):
    """Close a live trade on OANDA."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    try:
        result = await oanda.close_trade(trade_id)

        # Extract close info
        close_txn = result.get("orderFillTransaction", {})
        pnl = float(close_txn.get("pl", 0))
        close_price = float(close_txn.get("price", 0))

        return {
            "success": True,
            "trade_id": trade_id,
            "message": f"Trade closed, P&L: ${pnl:.2f}",
            "pnl": pnl,
            "close_price": close_price,
            "oanda_response": result,
        }
    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/live/close-position/{instrument}")
async def close_live_position(
    instrument: str = Path(...),
    direction: str = Query(default="all"),
):
    """Close a live position on OANDA."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    try:
        long_units = "ALL" if direction in ["all", "long"] else None
        short_units = "ALL" if direction in ["all", "short"] else None

        result = await oanda.close_position(instrument, long_units, short_units)

        return {
            "success": True,
            "instrument": instrument,
            "message": f"Position closed for {instrument}",
            "oanda_response": result,
        }
    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/live/price/{instrument}")
async def get_live_price(instrument: str = Path(...)):
    """Get live price for an instrument."""
    oanda = await get_oanda_client_with_db("default")
    if not oanda.is_configured():
        raise HTTPException(status_code=400, detail="OANDA not configured")

    try:
        price = await oanda.get_price(instrument)
        if not price:
            raise HTTPException(status_code=404, detail=f"Price not found for {instrument}")

        return {
            "instrument": instrument.replace("_", "/"),
            "bid": price["bid"],
            "ask": price["ask"],
            "mid": price["mid"],
            "spread": round(price["ask"] - price["bid"], 5),
        }
    except OandaError as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Learning Endpoints (Mock)
# =============================================================================

@app.get("/api/v1/learning/accuracy")
async def learning_accuracy():
    if use_database():
        stats = await TradeRepository.get_trade_stats("default")
        return {
            "overall_accuracy": 72.5,
            "total_signals": stats.get("total_trades", 0),
            "correct_predictions": int(stats.get("total_trades", 0) * 0.725),
            "by_pair": {},
            "by_direction": {
                "long": {"accuracy": 74.0, "total": 10, "correct": 7},
                "short": {"accuracy": 68.0, "total": 5, "correct": 3},
            },
        }

    return {
        "overall_accuracy": 72.5,
        "total_signals": len(_fallback.closed_trades),
        "correct_predictions": int(len(_fallback.closed_trades) * 0.725),
        "by_pair": {},
        "by_direction": {
            "long": {"accuracy": 74.0, "total": 10, "correct": 7},
            "short": {"accuracy": 68.0, "total": 5, "correct": 3},
        },
    }


@app.get("/api/v1/learning/insights")
async def learning_insights():
    return {
        "insights": [],
        "total": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }
