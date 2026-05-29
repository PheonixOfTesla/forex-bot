"""
Minimal Vercel Serverless API
Lightweight endpoint for Vercel's 500MB Lambda limit
"""
from datetime import datetime, timedelta
from typing import List, Optional
import random

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Lightning Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {"name": "Lightning Bot API", "version": "1.0.0", "status": "operational"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/ping")
async def ping():
    return {"pong": True}

# =============================================================================
# Dashboard
# =============================================================================

@app.get("/api/v1/dashboard")
async def dashboard():
    return {
        "balance": 10484.61,
        "equity": 10540.01,
        "today_pnl": 48.41,
        "today_pnl_pct": 0.46,
        "win_rate": 74.9,
        "total_trades": 10,
        "open_positions_count": 2,
        "ml_signals": [
            {"pair": "EUR/USD", "direction": "buy", "confidence": 89.9, "entry_price": 1.0845},
            {"pair": "GBP/USD", "direction": "sell", "confidence": 74.1, "entry_price": 1.265},
        ],
        "open_positions": [
            {"id": "pos_001", "pair": "EUR/USD", "direction": "buy", "entry_price": 1.0825, "unrealized_pnl": 29.1},
            {"id": "pos_002", "pair": "USD/JPY", "direction": "sell", "entry_price": 149.5, "unrealized_pnl": 26.3},
        ],
        "last_updated": datetime.utcnow().isoformat(),
    }

# =============================================================================
# Signals
# =============================================================================

@app.get("/api/v1/signals")
async def signals():
    return [
        {"id": "sig_001", "pair": "EUR/USD", "direction": "buy", "confidence": 88.0, "status": "active"},
        {"id": "sig_002", "pair": "GBP/USD", "direction": "sell", "confidence": 74.8, "status": "active"},
        {"id": "sig_003", "pair": "USD/JPY", "direction": "buy", "confidence": 81.3, "status": "active"},
    ]

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
    return {
        "mode": "paper",
        "balance": 10485.32,
        "paper_balance": 10485.32,
        "live_balance": 0.0,
        "total_pnl": 485.32,
    }

# =============================================================================
# Predictions
# =============================================================================

@app.get("/api/v1/predictions")
async def predictions():
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD", "ETH/USD"]
    preds = []
    for pair in pairs:
        preds.append({
            "pair": pair,
            "timeframe": "1h",
            "direction": random.choice(["UP", "DOWN"]),
            "confidence": round(random.uniform(65, 92), 1),
            "generated_at": datetime.utcnow().isoformat(),
        })
    return {"predictions": preds, "total": len(preds)}

# =============================================================================
# Intelligence
# =============================================================================

@app.get("/api/v1/intelligence/sentiment")
async def sentiment():
    return {
        "fear_greed_index": 58.5,
        "fear_greed_label": "Greed",
        "market_mood": "bullish",
    }

@app.get("/api/v1/intelligence/indicators")
async def indicators():
    return {"indicators": [], "updated_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/intelligence/insights")
async def insights():
    return {"insights": [], "total": 0}

@app.get("/api/v1/intelligence/patterns")
async def patterns():
    return {"patterns": [], "total": 0}

# =============================================================================
# Trades & History
# =============================================================================

@app.get("/api/v1/trades")
async def trades():
    return []

@app.get("/api/v1/performance")
async def performance():
    return {"period_days": 30, "total_trades": 10, "win_rate": 74.9, "total_pnl": 485.32}

# =============================================================================
# Settings
# =============================================================================

@app.get("/api/v1/settings")
async def settings():
    return {
        "trading_mode": "paper",
        "risk_per_trade": 0.02,
        "max_daily_loss": 0.06,
        "ml_confidence_threshold": 0.70,
    }
