<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/fastapi-async-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/broker-OANDA-orange" alt="OANDA">
</p>

<h1 align="center">📈 Forex Bot</h1>

<p align="center">
  <strong>FastAPI trading dashboard with OANDA integration, technical indicators, and paper trading simulation.</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api">API</a> •
  <a href="#indicators">Indicators</a>
</p>

---

## Features

### 📊 Live Market Data
- **OANDA REST API**: Real-time forex prices
- **Multiple Pairs**: EUR/USD, GBP/USD, USD/JPY, etc.
- **Candlestick Data**: M1 to Monthly timeframes

### 📉 Technical Indicators
| Indicator | Description |
|-----------|-------------|
| RSI | Relative Strength Index (overbought/oversold) |
| MACD | Moving Average Convergence Divergence |
| ATR | Average True Range (volatility) |
| Bollinger Bands | Price channels with standard deviation |

### 💰 Paper Trading
- **Simulated Orders**: Test strategies without real money
- **Position Tracking**: Open/close positions
- **P&L Calculation**: Track performance

### ⚡ FastAPI Backend
- **Async Architecture**: Non-blocking I/O
- **MongoDB**: Serverless-optimized connection pooling
- **Railway Deployment**: Production-ready

---

## Quick Start

```bash
# Clone
git clone https://github.com/PheonixOfTesla/forex-bot.git
cd forex-bot

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add OANDA API key, MongoDB URI

# Run
uvicorn src.main:app --reload
```

### Environment Variables

```env
OANDA_API_KEY=your-api-key
OANDA_ACCOUNT_ID=your-account-id
MONGODB_URI=mongodb://localhost:27017/forex
```

---

## API Endpoints

### Get Market Price
```bash
curl /api/v1/price/EUR_USD
```

### Get Indicators
```bash
curl /api/v1/indicators/EUR_USD?timeframe=H1
```

### Paper Trade
```bash
curl -X POST /api/v1/trade \
  -d '{"pair": "EUR_USD", "side": "buy", "units": 1000}'
```

---

## Tech Stack

- **Runtime**: Python 3.10+
- **Framework**: FastAPI
- **Database**: MongoDB
- **Broker**: OANDA REST API
- **Hosting**: Railway / Vercel

---

## License

MIT License
