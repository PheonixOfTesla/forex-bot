# Forex Bot

**FastAPI trading dashboard with OANDA integration, technical indicators, and paper trading simulation.**

> **Strongest proof**: `src/api/database.py:47-60` — serverless-optimized MongoDB connection pooling.

---

## What's Real

| Feature | Status | Proof |
|---------|--------|-------|
| FastAPI async architecture | Working | `src/api/main.py` |
| MongoDB connection pooling (serverless-optimized) | Working | `src/api/database.py` |
| OANDA REST API client | Working | `src/api/broker.py` |
| Technical indicators (RSI, MACD, ATR, Bollinger) | Working | `src/features/indicators.py` |
| Paper trading simulation | Working | `src/api/routes/` |
| Pydantic request validation | Working | Throughout API |

## What's Scaffolded

- **ML predictions**: `src/api/routes/predictions.py:101-151` uses `random.uniform()` with 75% bias — not real ML
- **XGBoost classifier**: imported but never used, no trained models exist
- **Autonomous bot**: `src/main.py` (819 lines) is never deployed — only the API runs
- **Binance integration**: client code exists, never called in production
- **Telegram alerts**: placeholder comments, not implemented

---

## Tech Stack

- **API**: FastAPI + Uvicorn
- **Database**: MongoDB (Motor async driver)
- **Broker**: OANDA REST API
- **Indicators**: pandas vectorized calculations
- **Hosting**: Railway (API only)

---

## Run

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

---

## Architecture

```
src/
  api/
    main.py        # FastAPI app (this is what runs)
    database.py    # MongoDB pooling
    broker.py      # OANDA client
    routes/        # API endpoints
  features/
    indicators.py  # RSI, MACD, etc.
  main.py          # Bot orchestrator (NOT DEPLOYED)
  ml/              # Classifier skeleton (NOT USED)
```

---

*Trading dashboard with real OANDA integration. The "ML predictions" are random numbers — classifier is scaffolding.*
