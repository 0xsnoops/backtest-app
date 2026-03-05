from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SimulationCreate(BaseModel):
    market: str = "crypto"
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    session_filter: Optional[str] = None
    session_start: Optional[str] = None
    session_end: Optional[str] = None
    num_rounds: int = 10
    starting_capital: float = 10000.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    seed: Optional[int] = None


class SimulationResponse(BaseModel):
    id: UUID
    user_id: UUID
    market: str
    symbol: str
    timeframe: str
    session_filter: Optional[str]
    session_start: Optional[str]
    session_end: Optional[str]
    num_rounds: int
    starting_capital: float
    fee_bps: float
    slippage_bps: float
    seed: Optional[int]
    created_at: datetime


class RoundResponse(BaseModel):
    id: UUID
    simulation_id: UUID
    round_number: int
    status: str
    current_index: int
    total_candles: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class OrderCreate(BaseModel):
    side: str
    type: str = "market"
    qty: float
    limit_price: Optional[float] = None


class OrderResponse(BaseModel):
    id: UUID
    round_id: UUID
    ts_index: int
    side: str
    type: str
    qty: float
    limit_price: Optional[float]
    status: str
    created_at: datetime


class FillResponse(BaseModel):
    id: UUID
    order_id: UUID
    round_id: UUID
    ts_index: int
    fill_price: float
    qty: float
    fee: float
    side: Optional[str] = None


class SnapshotResponse(BaseModel):
    ts_index: int
    equity: float
    cash: float
    position_qty: float
    avg_price: float
    unrealized_pnl: float
    realized_pnl: float


class CandleData(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class RoundMetrics(BaseModel):
    round_number: int
    pnl_dollar: float
    pnl_pct: float
    max_drawdown: float
    win_rate: float
    avg_win: float
    avg_loss: float
    num_trades: int
    profit_factor: float
    sharpe: float
    equity_curve: list[float]


class SimulationMetrics(BaseModel):
    total_pnl_dollar: float
    total_pnl_pct: float
    max_drawdown: float
    overall_win_rate: float
    avg_win: float
    avg_loss: float
    total_trades: int
    profit_factor: float
    sharpe: float
    rounds: list[RoundMetrics]
