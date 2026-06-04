# Lightning Trading - Forex Bot

## Quick Start
```bash
cd /Users/moderndavinci/hermes/forex-bot
```

## Live URLs
- **Frontend**: https://mobile-liart-psi.vercel.app (Vercel)
- **Backend**: https://web-production-7d1c.up.railway.app (Railway)
- **GitHub**: https://github.com/PheonixOfTesla/forex-bot

## What This Is
AI-powered forex trading PWA with real-time signals, AI predictions, market intelligence, paper trading, and **live OANDA trading**. Built with Python/FastAPI backend (Railway) and React Native/Expo frontend (Vercel PWA).

## Architecture

### Backend (Python/FastAPI) - Railway
- **Location**: `src/api/`
- **Entry**: `src/api/main.py`
- **Key Modules**:
  - `src/api/broker.py` - OANDA REST API client
  - `src/api/database.py` - MongoDB connection (Motor async)
  - `src/api/repository.py` - Data access layer
- **Routes**: `src/api/routes/` - API endpoints

### Frontend (React Native/Expo PWA) - Vercel
- **Location**: `/mobile`
- **Key Files**:
  - `src/services/api.ts` - API client (points to Railway)
  - `src/hooks/useApi.ts` - React hooks for data fetching
  - `src/screens/` - Tab screens
  - `app/(tabs)/` - Expo Router navigation

## The 5 Tabs
1. **Dashboard** - Overview, balance, recent activity
2. **Signals** - Real-time trading signals with confidence scores
3. **Predict** - AI predictions for currency pairs with timeframes
4. **Intel** - Market sentiment, technical indicators, AI insights, chart patterns
5. **Wallet** - Portfolio management, paper/live mode toggle

## API Endpoints

### Core
```
GET  /health                         - Health check
GET  /api/v1/dashboard               - Dashboard data
GET  /api/v1/signals                 - Trading signals
GET  /api/v1/predictions             - AI predictions
```

### Settings & OANDA
```
GET  /api/v1/settings                - Get all settings
POST /api/v1/settings/oanda          - Save OANDA credentials
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
GET  /api/v1/live/positions          - Live positions
POST /api/v1/live/execute            - Execute live trade
POST /api/v1/live/close/{trade_id}   - Close live trade
GET  /api/v1/live/price/{instrument} - Get live price
```

## Environment Variables

### Railway Backend
- `MONGODB_URI` - MongoDB Atlas connection string
- `OANDA_ACCOUNT_ID` - OANDA account ID (or use Settings UI)
- `OANDA_ACCESS_TOKEN` - OANDA API token (or use Settings UI)
- `OANDA_ENVIRONMENT` - "practice" or "live"

### Vercel Frontend
- `EXPO_PUBLIC_API_URL=https://web-production-7d1c.up.railway.app`

## Deploy Commands
```bash
# Push to Git (auto-deploys Railway, manually deploy frontend)
git add . && git commit -m "message" && git push origin main

# Frontend deploy (Vercel)
cd mobile && npx expo export --platform web
cd dist && vercel --prod --project mobile

# Check Railway backend
curl -s https://web-production-7d1c.up.railway.app/health

# Check Vercel frontend
curl -sI https://mobile-liart-psi.vercel.app | head -3
```

## Database
- **MongoDB Atlas**: `lightning_trading` database
- **Collections**: settings, trades, positions, accounts
- **Connection**: Set `MONGODB_URI` in Railway

## OANDA Integration
- **Practice Account**: 101-001-39423274-001
- **Environment**: practice (demo $100k)
- **Credentials**: Saved via Settings UI or env vars
- Live trading ready when switched to "live" mode

## Recent Work Done
- Added MongoDB persistence (Motor async driver)
- Added OANDA broker client (httpx)
- Settings saved to DB via frontend UI
- Live trading endpoints for OANDA
- Paper trading with position tracking
- Separated Railway (backend) and Vercel (frontend)

## Common Tasks
- **Update frontend API URL**: `mobile/src/services/api.ts`
- **Add API endpoint**: Add to `src/api/routes/`, register in `main.py`
- **Debug backend**: Check Railway logs
- **Test OANDA**: POST /api/v1/settings/oanda/test
