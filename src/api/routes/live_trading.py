from __future__ import annotations

"""
Live Trading API Routes

Endpoints for live trading with OANDA broker.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class ExecuteTradeRequest(BaseModel):
    """Request to execute a live trade."""
    pair: str
    direction: str  # buy, sell, long, short
    entry_price: float
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


# =============================================================================
# Helper Functions
# =============================================================================


async def get_oanda_credentials():
    """Get OANDA credentials from MongoDB or memory."""
    # Try MongoDB first
    try:
        from ..database import get_db
        db = await get_db()
        if db:
            settings = await db.settings.find_one({"_id": "oanda_credentials"})
            if settings and settings.get("account_id") and settings.get("access_token"):
                return (
                    settings.get("account_id"),
                    settings.get("access_token"),
                    settings.get("environment", "practice"),
                )
    except Exception as e:
        logger.warning(f"Could not load OANDA from DB: {e}")

    # Fall back to in-memory settings store
    from .settings import _settings_store
    return (
        _settings_store.oanda_account_id,
        _settings_store.oanda_access_token,
        _settings_store.oanda_environment,
    )


async def get_oanda_client():
    """Get configured OANDA client."""
    from ..broker import OandaClient

    account_id, access_token, environment = await get_oanda_credentials()

    if not account_id or not access_token:
        raise HTTPException(
            status_code=400,
            detail="OANDA not configured. Save credentials in Settings."
        )

    return OandaClient(
        account_id=account_id,
        access_token=access_token,
        environment=environment,
    )


# =============================================================================
# Live Trading Endpoints
# =============================================================================


@router.get("/live/balance")
async def live_balance():
    """Get live account balance from OANDA."""
    client = await get_oanda_client()

    try:
        account = await client.get_account()
        return {
            "balance": float(account.get("balance", 0)),
            "equity": float(account.get("NAV", 0)),
            "unrealized_pnl": float(account.get("unrealizedPL", 0)),
            "margin_used": float(account.get("marginUsed", 0)),
            "margin_available": float(account.get("marginAvailable", 0)),
            "open_trade_count": int(account.get("openTradeCount", 0)),
            "currency": account.get("currency", "USD"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()


@router.get("/live/positions")
async def live_positions():
    """Get live positions from OANDA."""
    client = await get_oanda_client()

    try:
        positions = await client.get_positions()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()


@router.post("/live/execute")
async def execute_live_trade(request: ExecuteTradeRequest):
    """Execute a live trade on OANDA."""
    client = await get_oanda_client()

    # Normalize direction
    direction = request.direction.lower()
    is_long = direction in ["buy", "long"]

    # Calculate units
    quantity = request.quantity
    if quantity is None:
        balance = await client.get_account_balance()
        position_value = balance * 0.02  # 2% risk
        quantity = int(position_value / request.entry_price)

    units = int(quantity) if is_long else -int(quantity)

    try:
        result = await client.place_market_order(
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

        logger.info(f"Live trade executed: {request.pair} {units} @ {fill_price}")

        return {
            "success": True,
            "trade_id": oanda_trade_id,
            "message": f"Trade executed: {'long' if is_long else 'short'} {fill_units} {request.pair} @ {fill_price:.5f}",
            "fill_price": fill_price,
            "fill_units": fill_units,
        }

    except Exception as e:
        logger.error(f"Live trade failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()


@router.post("/live/close/{trade_id}")
async def close_live_trade(trade_id: str = Path(...)):
    """Close a live trade on OANDA."""
    client = await get_oanda_client()

    try:
        result = await client.close_trade(trade_id)

        close_txn = result.get("orderFillTransaction", {})
        pnl = float(close_txn.get("pl", 0))
        close_price = float(close_txn.get("price", 0))

        logger.info(f"Trade {trade_id} closed. P&L: {pnl}")

        return {
            "success": True,
            "trade_id": trade_id,
            "message": f"Trade closed, P&L: ${pnl:.2f}",
            "pnl": pnl,
            "close_price": close_price,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()


@router.get("/live/price/{instrument}")
async def get_live_price(instrument: str = Path(...)):
    """Get live price for an instrument."""
    client = await get_oanda_client()

    try:
        price = await client.get_price(instrument)
        if not price:
            raise HTTPException(status_code=404, detail=f"Price not found: {instrument}")

        return {
            "instrument": instrument.replace("_", "/"),
            "bid": price["bid"],
            "ask": price["ask"],
            "mid": price["mid"],
            "spread": round(price["ask"] - price["bid"], 5),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()
