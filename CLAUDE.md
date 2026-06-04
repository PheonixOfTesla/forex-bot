# Lightning Trading - Forex Bot

## Quick Start
```bash
cd /Users/moderndavinci/hermes/forex-bot
```

## Live URLs
- **Frontend**: https://mobile-liart-psi.vercel.app (Vercel)
- **Backend**: https://web-production-7d1c.up.railway.app (Railway)
- **GitHub**: https://github.com/PheonixOfTesla/forex-bot

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                     │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FRONTEND (Vercel)                           │    │
│  │         mobile-liart-psi.vercel.app                     │    │
│  │                                                          │    │
│  │  React Native/Expo PWA                                  │    │
│  │  - Settings UI saves OANDA credentials                  │    │
│  │  - Paper/Live trading toggle                            │    │
│  │  - Dashboard, Signals, Predict, Intel, Wallet tabs      │    │
│  └─────────────────────┬───────────────────────────────────┘    │
│                        │ API calls                               │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              BACKEND (Railway)                           │    │
│  │       web-production-7d1c.up.railway.app                │    │
│  │                                                          │    │
│  │  FastAPI + Python                                       │    │
│  │  - src/api/main.py (entry point)                        │    │
│  │  - src/api/routes/ (all endpoints)                      │    │
│  │  - src/api/broker.py (OANDA client)                     │    │
│  │  - src/api/database.py (MongoDB connection)             │    │
│  └─────────────┬──────────────────────┬────────────────────┘    │
│                │                      │                          │
│                ▼                      ▼                          │
│  ┌─────────────────────┐    ┌─────────────────────────────┐     │
│  │    MongoDB Atlas    │    │         OANDA API           │     │
│  │                     │    │                             │     │
│  │  Collections:       │    │  Practice/Live Trading      │     │
│  │  - settings         │    │  - Account balance          │     │
│  │  - trades           │    │  - Place orders             │     │
│  │  - positions        │    │  - Get positions            │     │
│  │  - accounts         │    │  - Real-time prices         │     │
│  └─────────────────────┘    └─────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### OANDA Credentials
1. User enters credentials in Settings UI (frontend)
2. Frontend POSTs to `/api/v1/settings/oanda`
3. Backend saves to MongoDB `settings` collection
4. Credentials persist across Railway restarts
5. Live trading endpoints read from MongoDB

### Trade Execution (Live)
1. User clicks Execute on a signal
2. Frontend POSTs to `/api/v1/live/execute`
3. Backend loads OANDA credentials from MongoDB
4. Backend calls OANDA REST API to place order
5. Trade result returned to frontend

## Environment Variables

### Railway (Backend)
| Variable | Value | Purpose |
|----------|-------|---------|
| `MONGODB_URI` | `mongodb+srv://Admin:...@cluster0.0gnxplz.mongodb.net/lightning_trading` | Database connection |

OANDA credentials are stored in MongoDB, not env vars (for UI-based configuration).

### Vercel (Frontend)
| Variable | Value | Purpose |
|----------|-------|---------|
| `EXPO_PUBLIC_API_URL` | `https://web-production-7d1c.up.railway.app` | Backend API URL |

## API Endpoints

### Health & Status
```
GET  /health                         - Backend health check
GET  /api/v1/dashboard               - Dashboard data with positions
```

### Settings & OANDA Configuration
```
GET  /api/v1/settings                - All settings
GET  /api/v1/settings/oanda          - OANDA config (masked)
POST /api/v1/settings/oanda          - Save OANDA credentials → MongoDB
POST /api/v1/settings/oanda/test     - Test OANDA connection
```

### Paper Trading
```
GET  /api/v1/paper/balance           - Paper account balance
GET  /api/v1/paper/positions         - Open paper positions
POST /api/v1/paper/execute           - Execute paper trade
POST /api/v1/paper/positions/{id}/close - Close paper position
```

### Live Trading (OANDA)
```
GET  /api/v1/live/balance            - Live OANDA balance
GET  /api/v1/live/positions          - Live positions from OANDA
POST /api/v1/live/execute            - Execute live trade on OANDA
POST /api/v1/live/close/{trade_id}   - Close live trade
GET  /api/v1/live/price/{instrument} - Get live price
```

## MongoDB Collections

### `settings` Collection
```json
{
  "_id": "oanda_credentials",
  "account_id": "101-001-39423274-001",
  "access_token": "f9560a7c...",
  "environment": "practice",
  "updated_at": "2026-06-04T..."
}
```

### `trades` Collection
```json
{
  "_id": "tr_abc123",
  "user_id": "default",
  "pair": "EUR/USD",
  "direction": "long",
  "entry_price": 1.0845,
  "quantity": 1000,
  "status": "open",
  "broker": "paper|oanda"
}
```

## OANDA Integration

| Property | Value |
|----------|-------|
| Practice Account | `101-001-39423274-001` |
| Environment | `practice` (demo $100k) |
| API Endpoint | `api-fxpractice.oanda.com` |

Credentials are saved to MongoDB when user clicks "SAVE API KEYS" in Settings UI.

## Deploy Commands

```bash
# Push code (auto-deploys to Railway)
git add . && git commit -m "message" && git push origin main

# Check Railway backend
curl -s https://web-production-7d1c.up.railway.app/health

# Test OANDA connection
curl -X POST https://web-production-7d1c.up.railway.app/api/v1/settings/oanda/test

# Frontend deploy (manual, Vercel)
cd mobile && npx expo export --platform web
# Then deploy via Vercel dashboard or CLI
```

## File Structure

```
forex-bot/
├── src/api/                    # Railway Backend
│   ├── main.py                 # FastAPI app entry
│   ├── broker.py               # OANDA REST client
│   ├── database.py             # MongoDB connection
│   ├── repository.py           # Data access layer
│   └── routes/
│       ├── settings.py         # Settings + OANDA save
│       ├── live_trading.py     # Live OANDA trading
│       ├── paper_trading.py    # Paper trading
│       └── ...
├── mobile/                     # Vercel Frontend
│   ├── src/services/api.ts     # API client → Railway
│   └── src/screens/            # UI screens
└── api/                        # (Vercel serverless - legacy)
```

## Troubleshooting

### OANDA not connecting
1. Check credentials saved: `GET /api/v1/settings/oanda`
2. Test connection: `POST /api/v1/settings/oanda/test`
3. Check Railway logs for errors

### Data not persisting
1. Verify `MONGODB_URI` in Railway variables
2. Check MongoDB Atlas IP whitelist (0.0.0.0/0)
3. Check MongoDB Atlas cluster status

### Frontend not loading
1. Check API URL in `mobile/src/services/api.ts`
2. Verify Railway backend is running
3. Check browser console for CORS errors
