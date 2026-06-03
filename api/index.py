"""
Lightning Bot API - Vercel Serverless Function

Lightweight API for Vercel's serverless environment with paper trading support.
"""
from datetime import datetime
from typing import Dict, List, Optional
import random
import uuid

from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Lightning Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# In-Memory State (for serverless - resets between cold starts)
# =============================================================================

class PaperTradingState:
    """In-memory paper trading state."""
    def __init__(self):
        self.initial_balance: float = 10000.0
        self.balance: float = 10000.0
        self.open_trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.created_at: str = datetime.utcnow().isoformat()
        self.last_updated: str = datetime.utcnow().isoformat()

paper_state = PaperTradingState()


# Mock signals store
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


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {"name": "Lightning Bot API", "version": "1.0.0", "status": "operational"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/health")
async def health_v1():
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
        "balance": paper_state.balance,
        "equity": paper_state.balance,
        "today_pnl": 48.41,
        "today_pnl_pct": 0.46,
        "win_rate": 74.9,
        "total_trades": len(paper_state.closed_trades),
        "open_positions_count": len(paper_state.open_trades),
        "ml_signals": MOCK_SIGNALS[:2],
        "open_positions": paper_state.open_trades,
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
    """Get summary statistics for signals."""
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
    return {
        "mode": "paper",
        "balance": paper_state.balance,
        "paper_balance": paper_state.balance,
        "live_balance": 0.0,
        "total_pnl": paper_state.balance - paper_state.initial_balance,
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
    return paper_state.closed_trades


@app.get("/api/v1/performance")
async def performance():
    total_pnl = sum(t.get("pnl", 0) for t in paper_state.closed_trades)
    wins = len([t for t in paper_state.closed_trades if t.get("pnl", 0) > 0])
    total = len(paper_state.closed_trades)
    win_rate = (wins / total * 100) if total > 0 else 0
    return {
        "period_days": 30,
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
    }


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


# =============================================================================
# Paper Trading Endpoints
# =============================================================================

@app.get("/api/v1/paper/balance")
async def paper_balance():
    """Get paper trading balance and metrics."""
    wins = len([t for t in paper_state.closed_trades if t.get("pnl", 0) > 0])
    total = len(paper_state.closed_trades)
    win_rate = (wins / total * 100) if total > 0 else 0
    total_pnl = sum(t.get("pnl", 0) for t in paper_state.closed_trades)

    return {
        "initial_balance": paper_state.initial_balance,
        "balance": paper_state.balance,
        "equity": paper_state.balance,
        "unrealized_pnl": 0.0,
        "open_positions_count": len(paper_state.open_trades),
        "open_positions_value": sum(t.get("entry_price", 0) * t.get("quantity", 0) for t in paper_state.open_trades),
        "metrics": {
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "trades_count": total,
            "winning_trades": wins,
            "losing_trades": total - wins,
        },
        "peak_balance": max(paper_state.balance, paper_state.initial_balance),
        "created_at": paper_state.created_at,
        "last_updated": paper_state.last_updated,
    }


@app.get("/api/v1/paper/metrics")
async def paper_metrics():
    """Get trading performance metrics."""
    wins = len([t for t in paper_state.closed_trades if t.get("pnl", 0) > 0])
    total = len(paper_state.closed_trades)
    return {
        "win_rate": (wins / total * 100) if total > 0 else 0,
        "total_pnl": sum(t.get("pnl", 0) for t in paper_state.closed_trades),
        "trades_count": total,
    }


@app.get("/api/v1/paper/summary")
async def paper_summary():
    """Get paper trading summary."""
    total_pnl = sum(t.get("pnl", 0) for t in paper_state.closed_trades)
    wins = len([t for t in paper_state.closed_trades if t.get("pnl", 0) > 0])
    total = len(paper_state.closed_trades)

    return {
        "balance": paper_state.balance,
        "equity": paper_state.balance,
        "unrealized_pnl": 0.0,
        "open_positions": len(paper_state.open_trades),
        "closed_trades": len(paper_state.closed_trades),
        "total_pnl": round(total_pnl, 2),
        "win_rate": (wins / total * 100) if total > 0 else 0,
    }


@app.get("/api/v1/paper/positions")
async def paper_positions():
    """Get open paper positions."""
    positions = []
    for trade in paper_state.open_trades:
        # Simulate current price slightly different from entry
        current_price = trade["entry_price"] * 1.001
        pnl = (current_price - trade["entry_price"]) * trade["quantity"]
        if trade["direction"] in ["sell", "short"]:
            pnl = -pnl

        positions.append({
            "trade_id": trade["id"],
            "pair": trade["pair"],
            "direction": trade["direction"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "quantity": trade["quantity"],
            "unrealized_pnl": round(pnl, 2),
            "unrealized_pnl_pct": round(pnl / (trade["entry_price"] * trade["quantity"]) * 100, 2),
            "opened_at": trade["opened_at"],
            "stop_loss": trade.get("stop_loss"),
            "take_profit": trade.get("take_profit"),
        })

    return {
        "positions": positions,
        "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in positions),
        "positions_count": len(positions),
    }


@app.get("/api/v1/paper/positions/{trade_id}")
async def paper_position(trade_id: str = Path(...)):
    """Get a specific open position."""
    for trade in paper_state.open_trades:
        if trade["id"] == trade_id:
            current_price = trade["entry_price"] * 1.001
            pnl = (current_price - trade["entry_price"]) * trade["quantity"]
            if trade["direction"] in ["sell", "short"]:
                pnl = -pnl
            return {
                "trade_id": trade["id"],
                "pair": trade["pair"],
                "direction": trade["direction"],
                "entry_price": trade["entry_price"],
                "current_price": current_price,
                "quantity": trade["quantity"],
                "unrealized_pnl": round(pnl, 2),
                "opened_at": trade["opened_at"],
            }
    raise HTTPException(status_code=404, detail=f"Position not found: {trade_id}")


@app.get("/api/v1/paper/history")
async def paper_history(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    pair: Optional[str] = Query(default=None),
):
    """Get paper trade history."""
    trades = paper_state.closed_trades
    if pair:
        trades = [t for t in trades if t["pair"].upper() == pair.upper()]

    # Sort by closed_at descending
    trades = sorted(trades, key=lambda t: t.get("closed_at", ""), reverse=True)

    # Apply pagination
    paginated = trades[offset:offset + limit]

    total_pnl = sum(t.get("pnl", 0) for t in trades)
    wins = len([t for t in trades if t.get("pnl", 0) > 0])
    losses = len([t for t in trades if t.get("pnl", 0) < 0])

    return {
        "trades": paginated,
        "total_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "winning_trades": wins,
        "losing_trades": losses,
    }


@app.get("/api/v1/paper/history/{trade_id}")
async def paper_trade(trade_id: str = Path(...)):
    """Get a specific trade from history."""
    # Check open trades
    for trade in paper_state.open_trades:
        if trade["id"] == trade_id:
            return trade
    # Check closed trades
    for trade in paper_state.closed_trades:
        if trade["id"] == trade_id:
            return trade
    raise HTTPException(status_code=404, detail=f"Trade not found: {trade_id}")


@app.post("/api/v1/paper/execute")
async def execute_paper_trade(request: ExecuteTradeRequest):
    """Execute a paper trade."""
    # Calculate quantity if not provided
    quantity = request.quantity
    if quantity is None:
        # Use 2% of balance
        position_value = paper_state.balance * 0.02
        quantity = position_value / request.entry_price

    # Calculate position value
    position_value = request.entry_price * quantity

    # Check balance
    if position_value > paper_state.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance: need ${position_value:.2f}, have ${paper_state.balance:.2f}",
        )

    # Create trade
    trade_id = f"pt_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    trade = {
        "id": trade_id,
        "signal_id": request.signal_id,
        "pair": request.pair,
        "direction": request.direction,
        "entry_price": request.entry_price,
        "quantity": quantity,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "notes": request.notes,
        "status": "open",
        "opened_at": now,
    }

    # Deduct from balance
    paper_state.balance -= position_value
    paper_state.open_trades.append(trade)
    paper_state.last_updated = now

    return {
        "success": True,
        "trade_id": trade_id,
        "message": f"Trade executed: {request.direction} {quantity:.4f} {request.pair} @ ${request.entry_price:.4f}",
        "trade": trade,
        "new_balance": paper_state.balance,
    }


@app.post("/api/v1/paper/execute-signal/{signal_id}")
async def execute_signal_paper(
    signal_id: str = Path(...),
    quantity: Optional[float] = Query(default=None),
):
    """Execute a trading signal in paper mode."""
    # Find the signal
    signal = None
    for s in MOCK_SIGNALS:
        if s["id"] == signal_id:
            signal = s
            break

    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal not found: {signal_id}")

    # Calculate quantity
    qty = quantity
    if qty is None:
        position_value = paper_state.balance * 0.02
        qty = position_value / signal["entry_price"]

    position_value = signal["entry_price"] * qty

    if position_value > paper_state.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance: need ${position_value:.2f}, have ${paper_state.balance:.2f}",
        )

    # Create trade
    trade_id = f"pt_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    trade = {
        "id": trade_id,
        "signal_id": signal_id,
        "pair": signal["pair"],
        "direction": signal["direction"],
        "entry_price": signal["entry_price"],
        "quantity": qty,
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "notes": f"From signal: {signal_id} ({signal['strategy']})",
        "status": "open",
        "opened_at": now,
    }

    paper_state.balance -= position_value
    paper_state.open_trades.append(trade)
    paper_state.last_updated = now

    return {
        "success": True,
        "message": f"Trade executed from signal {signal_id}",
        "signal_id": signal_id,
        "trade_id": trade_id,
        "trade": trade,
        "new_balance": paper_state.balance,
    }


@app.post("/api/v1/paper/positions/{trade_id}/close")
async def close_paper_position(
    trade_id: str = Path(...),
    request: CloseTradeRequest = None,
):
    """Close an open paper position."""
    if request is None:
        raise HTTPException(status_code=400, detail="Exit price is required")

    # Find the trade
    trade = None
    trade_index = None
    for i, t in enumerate(paper_state.open_trades):
        if t["id"] == trade_id:
            trade = t
            trade_index = i
            break

    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade not found: {trade_id}")

    # Calculate P&L
    entry_value = trade["entry_price"] * trade["quantity"]
    exit_value = request.exit_price * trade["quantity"]

    if trade["direction"] in ["buy", "long"]:
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
    if request.notes:
        trade["notes"] = (trade.get("notes") or "") + f"\n{request.notes}"

    # Return position value + P&L to balance
    paper_state.balance += entry_value + pnl

    # Move to closed trades
    paper_state.open_trades.pop(trade_index)
    paper_state.closed_trades.append(trade)
    paper_state.last_updated = now

    return {
        "success": True,
        "trade_id": trade_id,
        "message": f"Trade closed: {trade['pair']} @ ${request.exit_price:.4f}, P&L: ${pnl:.2f} ({pnl_pct:.2f}%)",
        "trade": trade,
        "new_balance": paper_state.balance,
    }


@app.post("/api/v1/paper/close-all")
async def close_all_paper_positions(exit_prices: Optional[Dict[str, float]] = None):
    """Close all open paper positions."""
    if not paper_state.open_trades:
        return {
            "success": True,
            "message": "No open positions to close",
            "closed_count": 0,
            "new_balance": paper_state.balance,
        }

    prices = exit_prices or {}
    closed_trades = []
    now = datetime.utcnow().isoformat()

    for trade in list(paper_state.open_trades):
        exit_price = prices.get(trade["pair"], trade["entry_price"] * 1.001)

        entry_value = trade["entry_price"] * trade["quantity"]
        exit_value = exit_price * trade["quantity"]

        if trade["direction"] in ["buy", "long"]:
            pnl = exit_value - entry_value
        else:
            pnl = entry_value - exit_value

        trade["exit_price"] = exit_price
        trade["pnl"] = round(pnl, 2)
        trade["pnl_pct"] = round((pnl / entry_value) * 100, 2)
        trade["status"] = "closed"
        trade["closed_at"] = now

        paper_state.balance += entry_value + pnl
        paper_state.closed_trades.append(trade)
        closed_trades.append(trade["id"])

    paper_state.open_trades.clear()
    paper_state.last_updated = now

    total_pnl = sum(t.get("pnl", 0) for t in paper_state.closed_trades[-len(closed_trades):])

    return {
        "success": True,
        "message": f"Closed {len(closed_trades)} positions",
        "closed_count": len(closed_trades),
        "total_pnl": round(total_pnl, 2),
        "new_balance": paper_state.balance,
        "closed_trades": closed_trades,
    }


@app.post("/api/v1/paper/reset")
async def reset_paper_account(
    new_balance: Optional[float] = Query(default=None, gt=0),
):
    """Reset the paper trading account."""
    previous_balance = paper_state.balance
    previous_pnl = sum(t.get("pnl", 0) for t in paper_state.closed_trades)

    balance = new_balance or 10000.0

    paper_state.initial_balance = balance
    paper_state.balance = balance
    paper_state.open_trades.clear()
    paper_state.closed_trades.clear()
    paper_state.created_at = datetime.utcnow().isoformat()
    paper_state.last_updated = datetime.utcnow().isoformat()

    return {
        "success": True,
        "message": f"Account reset to ${balance:,.2f}",
        "new_balance": balance,
        "previous_balance": previous_balance,
        "previous_total_pnl": previous_pnl,
    }


# =============================================================================
# Learning Endpoints (Mock)
# =============================================================================

@app.get("/api/v1/learning/accuracy")
async def learning_accuracy():
    """Get learning engine accuracy metrics."""
    return {
        "overall_accuracy": 72.5,
        "total_signals": len(paper_state.closed_trades),
        "correct_predictions": int(len(paper_state.closed_trades) * 0.725),
        "by_pair": {},
        "by_direction": {
            "long": {"accuracy": 74.0, "total": 10, "correct": 7},
            "short": {"accuracy": 68.0, "total": 5, "correct": 3},
        },
        "by_timeframe": {},
    }


@app.get("/api/v1/learning/insights")
async def learning_insights():
    """Get learning engine insights."""
    return {
        "insights": [],
        "total": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }
