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

| Project | Type | URL |
|---------|------|-----|
| `forex-bot` | Backend API | forex-bot-ten.vercel.app |
| `mobile` | Frontend PWA | mobile-liart-psi.vercel.app |

---

## Git: Push / Commit

```bash
# Stage all changes
git add .

# Commit
git commit -m "Your message"

# Push to main (triggers auto-deploy)
git push origin main
```

---

## Vercel: Test Deployments

### Backend API
```bash
cd /Users/moderndavinci/hermes/forex-bot
vercel --prod --project forex-bot
```

### Frontend PWA
```bash
cd /Users/moderndavinci/hermes/forex-bot/mobile
EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1 npx expo export --platform web
vercel dist --prod --project mobile
```

---

## Vercel: Check Status

```bash
# List deployments
vercel ls --project forex-bot
vercel ls --project mobile

# Check logs
vercel logs forex-bot-ten.vercel.app
vercel logs mobile-liart-psi.vercel.app
```

---

## URLs

- **Frontend**: https://mobile-liart-psi.vercel.app
- **Backend**: https://forex-bot-ten.vercel.app
