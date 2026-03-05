import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum


def gen_uuid():
    return uuid.uuid4()


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class RoundStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    simulations = relationship("Simulation", back_populates="user")


class Simulation(Base):
    __tablename__ = "simulations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    market = Column(String(20), nullable=False)
    symbol = Column(String(30), nullable=False)
    timeframe = Column(String(10), nullable=False, default="1m")
    session_filter = Column(String(50), nullable=True)
    session_start = Column(String(10), nullable=True)
    session_end = Column(String(10), nullable=True)
    num_rounds = Column(Integer, nullable=False, default=10)
    starting_capital = Column(Float, nullable=False, default=10000.0)
    fee_bps = Column(Float, nullable=False, default=10.0)
    slippage_bps = Column(Float, nullable=False, default=5.0)
    seed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="simulations")
    rounds = relationship("Round", back_populates="simulation", order_by="Round.round_number")


class Round(Base):
    __tablename__ = "rounds"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    simulation_id = Column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    hidden_date = Column(String(20), nullable=False)
    status = Column(SAEnum(RoundStatus), default=RoundStatus.PENDING)
    current_index = Column(Integer, default=0)
    total_candles = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    simulation = relationship("Simulation", back_populates="rounds")
    orders = relationship("Order", back_populates="round")
    fills = relationship("Fill", back_populates="round")
    snapshots = relationship("Snapshot", back_populates="round", order_by="Snapshot.ts_index")


class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.id"), nullable=False)
    ts_index = Column(Integer, nullable=False)
    side = Column(SAEnum(OrderSide), nullable=False)
    type = Column(SAEnum(OrderType), nullable=False, default=OrderType.MARKET)
    qty = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=True)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    round = relationship("Round", back_populates="orders")
    fills = relationship("Fill", back_populates="order")


class Fill(Base):
    __tablename__ = "fills"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.id"), nullable=False)
    ts_index = Column(Integer, nullable=False)
    fill_price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    order = relationship("Order", back_populates="fills")
    round = relationship("Round", back_populates="fills")


class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.id"), nullable=False)
    ts_index = Column(Integer, nullable=False)
    equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    position_qty = Column(Float, nullable=False, default=0.0)
    avg_price = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    round = relationship("Round", back_populates="snapshots")
