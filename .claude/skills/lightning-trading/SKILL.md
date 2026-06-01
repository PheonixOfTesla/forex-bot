---
description: Resume Lightning Trading forex bot session - checks status and loads full project context
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Lightning Trading Session

Read CLAUDE.md first for full project context, then run these status checks:

```bash
curl -s https://forex-bot-ten.vercel.app/health
curl -sI https://mobile-liart-psi.vercel.app | head -3
git status
```

## Project URLs
- **Frontend**: https://mobile-liart-psi.vercel.app
- **Backend**: https://forex-bot-ten.vercel.app
- **GitHub**: https://github.com/PheonixOfTesla/forex-bot

## Architecture
- **Backend**: Python/FastAPI at root `/`
- **Frontend**: React Native/Expo PWA at `/mobile`
- **API Client**: `mobile/src/services/api.ts`
- **Hooks**: `mobile/src/hooks/useApi.ts`
- **Screens**: `mobile/src/screens/`

## Deploy Commands
```bash
# Auto-deploy (push to git)
git add . && git commit -m "message" && git push origin main

# Manual frontend
cd mobile && EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web
cd dist && vercel --prod --project mobile

# Manual backend
vercel --prod --project forex-bot
```

## Tabs
1. Dashboard - Overview, balance
2. Signals - Real-time trading signals
3. Predict - AI predictions
4. Intel - Market sentiment, indicators, patterns
5. Wallet - Portfolio, demo/live toggle

After running status checks, ask the user what they want to work on.
