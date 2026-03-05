import httpx
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from app.providers.base import MarketDataProvider, Candle

CACHE_DIR = Path(os.getenv("CANDLE_CACHE_DIR", "/tmp/candle_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BINANCE_API = "https://api.binance.com"


class BinanceProvider(MarketDataProvider):
    """Binance public klines provider for crypto pairs."""

    INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}

    async def get_candles(
        self, symbol: str, start_ms: int, end_ms: int, timeframe: str = "1m"
    ) -> list[Candle]:
        cache_key = f"{symbol}_{timeframe}_{start_ms}_{end_ms}"
        cache_path = CACHE_DIR / f"{cache_key}.json"

        if cache_path.exists():
            with open(cache_path) as f:
                raw = json.load(f)
            return [Candle(*r) for r in raw]

        interval = self.INTERVAL_MAP.get(timeframe, "1m")
        candles: list[Candle] = []
        current = start_ms

        async with httpx.AsyncClient(timeout=30) as client:
            while current < end_ms:
                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": current,
                    "endTime": end_ms,
                    "limit": 1000,
                }
                resp = await client.get(f"{BINANCE_API}/api/v3/klines", params=params)
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                for k in data:
                    candles.append(Candle(
                        timestamp=int(k[0]),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                    ))
                current = int(data[-1][0]) + 1

        # Cache
        with open(cache_path, "w") as f:
            json.dump([(c.timestamp, c.open, c.high, c.low, c.close, c.volume) for c in candles], f)

        return candles

    async def get_available_dates(self, symbol: str, timeframe: str = "1m") -> list[str]:
        """Return dates from last ~2 years that have data. We sample daily."""
        dates = []
        end = datetime.utcnow() - timedelta(days=2)
        start = end - timedelta(days=730)
        d = start
        while d <= end:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return dates


def get_provider(market: str = "crypto") -> MarketDataProvider:
    if market == "crypto":
        return BinanceProvider()
    raise ValueError(f"Unsupported market: {market}")
