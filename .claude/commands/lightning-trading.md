# Lightning Trading Session

You are resuming work on the Lightning Trading forex bot. Read CLAUDE.md for full project context.

## Quick Status Check
1. Check backend health: `curl -s https://forex-bot-ten.vercel.app/health`
2. Check frontend: `curl -sI https://mobile-liart-psi.vercel.app | head -3`
3. Check git status: `git status`

## Project URLs
- **Frontend**: https://mobile-liart-psi.vercel.app
- **Backend**: https://forex-bot-ten.vercel.app
- **GitHub**: https://github.com/PheonixOfTesla/forex-bot

## Key Directories
- Backend: `/Users/moderndavinci/hermes/forex-bot/`
- Frontend: `/Users/moderndavinci/hermes/forex-bot/mobile/`
- API Client: `mobile/src/services/api.ts`
- React Hooks: `mobile/src/hooks/useApi.ts`
- Screens: `mobile/src/screens/`

## Common Tasks
- **Deploy**: `git add . && git commit -m "msg" && git push origin main`
- **Build frontend**: `cd mobile && EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web`
- **Manual deploy frontend**: `cd mobile/dist && vercel --prod --project mobile`
- **Manual deploy backend**: `vercel --prod --project forex-bot`

## What to do
Ask the user what they want to work on. Common requests:
- Fix bugs in specific tabs
- Add new features
- Deploy changes
- Check system status
- Add new API endpoints
- Improve UI/UX

Start by running the quick status checks above, then ask what they need.
