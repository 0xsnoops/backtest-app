from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Candle:
    timestamp: int  # ms epoch
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_candles(
        self, symbol: str, start_ms: int, end_ms: int, timeframe: str = "1m"
    ) -> list[Candle]:
        ...

    @abstractmethod
    async def get_available_dates(
        self, symbol: str, timeframe: str = "1m"
    ) -> list[str]:
        """Return list of YYYY-MM-DD date strings with data."""
        ...
