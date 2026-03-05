# Market Replay Backtester

An interactive market replay backtesting platform where users practice and evaluate trading strategies in a realistic, candle-by-candle replay environment — with hidden dates to prevent hindsight bias.

## Features

- **Market Replay**: Candle-by-candle playback of historical market data at configurable speeds
- **Hidden Dates**: Each round uses a randomly selected historical day — the date is never revealed
- **Trading**: Place market and limit orders mid-replay with realistic fill simulation
- **Fees & Slippage**: Configurable fee (bps) and slippage (bps) models
- **Session Filters**: Filter candles by session (premarket, regular, afterhours, custom time window)
- **Metrics**: PnL, max drawdown, win rate, avg win/loss, profit factor, Sharpe ratio, equity curves
- **Multiple Rounds**: Run N rounds per simulation, each with a different random day
- **No Lookahead**: Server-controlled candle delivery ensures no future data leaks to client

## Architecture

```
├── server/          # FastAPI backend (Python)
│   ├── app/
│   │   ├── api/       # REST endpoints (auth, simulations)
│   │   ├── engine/    # Simulation engine (fills, fees, metrics)
│   │   ├── models/    # SQLAlchemy models
│   │   ├── providers/ # Market data providers (Binance)
│   │   ├── schemas/   # Pydantic schemas
│   │   └── ws/        # WebSocket handler
│   └── tests/         # Engine unit tests
├── web/             # Next.js frontend (TypeScript)
│   └── src/
│       ├── app/       # Pages (landing, dashboard, simulation, results)
│       ├── components/ # Chart, OrderTicket, PlaybackControls, etc.
│       └── lib/       # API client, Zustand store
└── docker-compose.yml
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Run with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **Postgres** on port 5432
- **FastAPI server** on port 8000 (with auto-migration)
- **Next.js frontend** on port 3000

Open http://localhost:3000 in your browser.

### Run Locally (without Docker)

#### 1. Start Postgres

```bash
docker run -d --name backtest-db \
  -e POSTGRES_USER=backtest \
  -e POSTGRES_PASSWORD=backtest \
  -e POSTGRES_DB=backtest \
  -p 5432:5432 \
  postgres:15-alpine
```

#### 2. Backend

```bash
cd server
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### 3. Frontend

```bash
cd web
npm install
npm run dev
```

### Environment Variables

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://backtest:backtest@localhost:5432/backtest` | Postgres connection |
| `JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | WebSocket URL |

## Usage

1. **Register/Login** at the landing page
2. **Create Simulation**: pick symbol (e.g. BTCUSDT), rounds, capital, fees, session filter
3. **Play Rounds**: start each round, candles stream one-by-one. Use play/pause/step/speed controls
4. **Trade**: place buy/sell orders via the order ticket. Positions and P&L update live
5. **View Results**: after completing rounds, see per-round and combined metrics with equity curves

## Data Provider

The MVP uses **Binance public klines API** for crypto data (BTCUSDT, ETHUSDT, etc.). Data is cached locally to reduce API calls.

The provider layer is pluggable — implement the `MarketDataProvider` interface to add stocks, forex, etc.

## Simulation Engine

- **Market orders** fill at current candle's close price (+ slippage)
- **Limit orders** fill if price crosses during the candle (conservative: uses OHLC)
- **Fees**: configurable basis points per trade
- **Slippage**: configurable basis points added/subtracted from fill price
- **No lookahead**: fill logic only uses the current candle

## Running Tests

```bash
cd server
pytest tests/ -v
```

Tests cover:
- Market order fills (buy/sell with slippage)
- Limit order fills (touch/no-touch scenarios)
- Fee calculation
- Slippage direction (buy vs sell)
- No-lookahead invariants
- Position tracking (round-trip P&L)
- Metrics computation
- Edge cases (finished engine, empty state)
