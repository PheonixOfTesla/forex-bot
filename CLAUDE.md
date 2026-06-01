# Lightning Trading - Forex Bot

## Project Overview
AI-powered forex trading system with real-time signals, predictions, and portfolio management.

## Architecture

### Backend (Python/FastAPI)
- **Location**: `/` (root)
- **Entry**: `main.py`
- **Deployed**: https://forex-bot-ten.vercel.app
- **Key Services**:
  - `services/oanda_client.py` - OANDA broker integration
  - `services/ai_engine.py` - AI prediction engine
  - `services/signal_generator.py` - Trading signal generation
  - `routes/` - API endpoints (signals, predictions, intelligence, wallet)

### Frontend (React Native/Expo PWA)
- **Location**: `/mobile`
- **Deployed**: https://mobile-liart-psi.vercel.app
- **Key Files**:
  - `src/services/api.ts` - API client (connects to backend)
  - `src/hooks/useApi.ts` - React hooks for data fetching
  - `src/screens/` - Tab screens (Dashboard, Signals, Predict, Intel, Wallet)
  - `app/(tabs)/` - Expo Router tab navigation

## Tabs/Features
1. **Dashboard** - Overview, balance, recent activity
2. **Signals** - Real-time trading signals with confidence scores
3. **Predict** - AI predictions for currency pairs with timeframes
4. **Intel** - Market sentiment, technical indicators, AI insights, patterns
5. **Wallet** - Portfolio management, transactions, demo/live mode toggle

## API Endpoints
- `GET /api/v1/signals` - Trading signals
- `GET /api/v1/predictions` - AI predictions
- `GET /api/v1/predictions/accuracy` - Prediction accuracy stats
- `GET /api/v1/intelligence/sentiment` - Fear/greed index
- `GET /api/v1/intelligence/indicators` - Technical indicators
- `GET /api/v1/intelligence/insights` - AI market insights
- `GET /api/v1/intelligence/patterns` - Detected chart patterns
- `GET /api/v1/wallet/balance` - Current balance
- `POST /api/v1/wallet/mode` - Toggle demo/live

## Deployment Workflow
```bash
# Commit and push (auto-deploys both)
git add . && git commit -m "message" && git push origin main

# Manual deploy
vercel --prod --project forex-bot          # backend
cd mobile && npx expo export --platform web && cd dist && vercel --prod --project mobile
```

## Environment Variables
### Backend (Vercel)
- `OANDA_ACCOUNT_ID` - OANDA account ID
- `OANDA_ACCESS_TOKEN` - OANDA API token
- `OANDA_ENVIRONMENT` - practice or live

### Frontend (mobile/.env)
- `EXPO_PUBLIC_API_URL` - Backend URL (https://forex-bot-ten.vercel.app)

## Git Repository
- **Repo**: https://github.com/PheonixOfTesla/forex-bot
- **Branch**: main
- Both frontend and backend connected to Vercel via Git

## Recent Session Summary
- Fixed Predict and Intel tabs (missing hooks)
- Updated API fallback URL from Railway to Vercel
- Connected both projects to Git in Vercel
- Deleted redundant `dist` project
- Created WORKFLOW.md documentation
