# Deployment Workflow

## Project Structure

```
forex-bot/
├── api/                 # Backend API (Vercel Serverless)
├── mobile/              # Frontend PWA (Expo Web)
├── src/                 # Core trading engine
└── vercel.json          # Backend config
```

## Vercel Projects

| Project | Type | URL | Root Directory |
|---------|------|-----|----------------|
| forex-bot | Backend API | forex-bot-ten.vercel.app | `/` (root) |
| mobile | Frontend PWA | mobile-liart-psi.vercel.app | `/mobile` |

## Git → Vercel Connection

Both projects connect to: `github.com/PheonixOfTesla/forex-bot`

### Backend (forex-bot)
- **Root Directory**: `/`
- **Build Command**: (none - uses api/index.py)
- **Output**: Serverless Functions

### Frontend (mobile)
- **Root Directory**: `mobile`
- **Build Command**: `EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web`
- **Output Directory**: `dist`

## Deployment Workflow

### 1. Make Changes
```bash
# Edit files in /mobile for frontend
# Edit files in /api or /src for backend
```

### 2. Commit & Push
```bash
git add .
git commit -m "Your commit message"
git push origin main
```

### 3. Auto-Deploy
Vercel automatically deploys both projects when you push to `main`:
- Backend API rebuilds from `/api/index.py`
- Frontend PWA rebuilds from `/mobile`

## Environment Variables

### Backend (.env in root)
```
# Add any API keys here
```

### Frontend (mobile/.env)
```
EXPO_PUBLIC_API_URL=https://forex-bot-ten.vercel.app
EXPO_PUBLIC_WS_URL=wss://forex-bot-ten.vercel.app/ws
```

## Manual Deploy (if needed)

```bash
# Backend
cd /Users/moderndavinci/hermes/forex-bot
vercel --prod

# Frontend
cd /Users/moderndavinci/hermes/forex-bot/mobile
EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web
cd dist && vercel --prod
```

## Vercel Dashboard Setup

### Connect Mobile Project to Git:
1. Go to vercel.com → mobile project → Settings → Git
2. Connect to `PheonixOfTesla/forex-bot`
3. Set Root Directory: `mobile`
4. Build Command: `EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web`
5. Output Directory: `dist`

## URLs

- **Frontend**: https://mobile-liart-psi.vercel.app
- **Backend**: https://forex-bot-ten.vercel.app
- **API Docs**: https://forex-bot-ten.vercel.app/docs
