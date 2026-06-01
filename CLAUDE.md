# Lightning Trading - Forex Bot

## Quick Start
```bash
cd /Users/moderndavinci/hermes/forex-bot
```

## Live URLs
- **Frontend**: https://mobile-liart-psi.vercel.app
- **Backend**: https://forex-bot-ten.vercel.app
- **GitHub**: https://github.com/PheonixOfTesla/forex-bot

## What This Is
AI-powered forex trading PWA with real-time signals, AI predictions, market intelligence, and portfolio management. Built with Python/FastAPI backend and React Native/Expo frontend deployed as a Progressive Web App.

## Architecture

### Backend (Python/FastAPI)
- **Location**: `/` (root directory)
- **Entry**: `main.py`
- **Services**:
  - `services/oanda_client.py` - OANDA broker integration
  - `services/ai_engine.py` - AI prediction engine
  - `services/signal_generator.py` - Trading signal generation
- **Routes**: `routes/` - API endpoints

### Frontend (React Native/Expo PWA)
- **Location**: `/mobile`
- **Key Files**:
  - `src/services/api.ts` - API client
  - `src/hooks/useApi.ts` - React hooks for data fetching
  - `src/screens/` - Tab screens
  - `app/(tabs)/` - Expo Router navigation

## The 5 Tabs
1. **Dashboard** - Overview, balance, recent activity
2. **Signals** - Real-time trading signals with confidence scores
3. **Predict** - AI predictions for currency pairs with timeframes
4. **Intel** - Market sentiment, technical indicators, AI insights, chart patterns
5. **Wallet** - Portfolio management, transactions, demo/live mode toggle

## API Endpoints
```
GET  /api/v1/signals              - Trading signals
GET  /api/v1/predictions          - AI predictions
GET  /api/v1/predictions/accuracy - Prediction accuracy stats
GET  /api/v1/intelligence/sentiment  - Fear/greed index
GET  /api/v1/intelligence/indicators - Technical indicators
GET  /api/v1/intelligence/insights   - AI market insights
GET  /api/v1/intelligence/patterns   - Detected chart patterns
GET  /api/v1/wallet/balance       - Current balance
POST /api/v1/wallet/mode          - Toggle demo/live
GET  /health                      - Health check
```

## Deploy Commands
```bash
# Push to Git (auto-deploys both frontend and backend)
git add . && git commit -m "message" && git push origin main

# Manual frontend deploy
cd mobile && EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web
cd dist && vercel --prod --project mobile

# Manual backend deploy
vercel --prod --project forex-bot

# Check status
curl -s https://forex-bot-ten.vercel.app/health
```

## Environment Variables
### Backend (set in Vercel dashboard)
- `OANDA_ACCOUNT_ID` - Your OANDA account ID
- `OANDA_ACCESS_TOKEN` - Your OANDA API token
- `OANDA_ENVIRONMENT` - "practice" or "live"

### Frontend (mobile/.env)
- `EXPO_PUBLIC_API_URL=https://forex-bot-ten.vercel.app`

## Recent Work Done
- Fixed Predict tab (added usePredictions, usePredictionAccuracy hooks)
- Fixed Intel tab (added useMarketSentiment, useTechnicalIndicators, useAIInsights, useDetectedPatterns hooks)
- Changed API fallback URL from Railway to Vercel
- Connected both Vercel projects to Git for auto-deploy
- Deleted redundant "dist" project
- Created /lightning-trading slash command for session pickup

## Common Tasks
- **Fix a tab**: Check `mobile/src/screens/[Tab]Screen.tsx` and `mobile/src/hooks/useApi.ts`
- **Add API endpoint**: Add to `routes/` in backend, then add method in `mobile/src/services/api.ts` and hook in `mobile/src/hooks/useApi.ts`
- **Debug**: Check browser console, run `curl` against backend endpoints
- **Deploy**: Just push to git, both auto-deploy

## Status Check Commands
```bash
curl -s https://forex-bot-ten.vercel.app/health
curl -sI https://mobile-liart-psi.vercel.app | head -3
git status
```
