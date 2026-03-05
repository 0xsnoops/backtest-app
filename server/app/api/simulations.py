import random
import math
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.api.auth import get_current_user
from app.models.tables import (
    User, Simulation, Round, Order, Fill, Snapshot,
    RoundStatus, OrderSide, OrderType, OrderStatus,
)
from app.schemas.schemas import (
    SimulationCreate, SimulationResponse, RoundResponse,
    OrderCreate, OrderResponse, FillResponse, SnapshotResponse,
)
from app.providers.binance import get_provider
from app.engine.simulator import SimulationEngine, SimOrder, SimFill, EquitySnapshot
from app.engine.session_filter import filter_session as _filter_session
from app.providers.base import Candle as EngineCandle

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# In-memory engine store (round_id -> engine)
_engines: dict[str, SimulationEngine] = {}


def _get_engine(round_id: str) -> SimulationEngine | None:
    return _engines.get(round_id)


async def _verify_sim_ownership(sim_id: UUID, user: User, db: AsyncSession) -> "Simulation":
    """Verify user owns the simulation. Returns sim or raises 404."""
    result = await db.execute(
        select(Simulation).where(Simulation.id == sim_id, Simulation.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(404, "Simulation not found")
    return sim


async def _verify_round_ownership(sim_id: UUID, round_id: UUID, user: User, db: AsyncSession) -> tuple:
    """Verify user owns the simulation AND round belongs to it. Returns (sim, round)."""
    sim = await _verify_sim_ownership(sim_id, user, db)
    result = await db.execute(
        select(Round).where(Round.id == round_id, Round.simulation_id == sim_id)
    )
    rnd = result.scalar_one_or_none()
    if not rnd:
        raise HTTPException(404, "Round not found")
    return sim, rnd


def _compute_metrics_from_db(
    snapshots: list[Snapshot],
    fills: list[Fill],
    starting_capital: float,
) -> dict:
    """Compute round metrics from persisted DB data (no in-memory engine needed)."""
    if not snapshots:
        return {
            "pnl_dollar": 0, "pnl_pct": 0, "max_drawdown": 0, "win_rate": 0,
            "avg_win": 0, "avg_loss": 0, "num_trades": 0, "profit_factor": 0,
            "sharpe": 0, "equity_curve": [],
        }

    equity_curve = [s.equity for s in snapshots]
    final_equity = equity_curve[-1] if equity_curve else starting_capital
    pnl_dollar = final_equity - starting_capital
    pnl_pct = (pnl_dollar / starting_capital) * 100 if starting_capital > 0 else 0

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # Compute trade PnLs from fills
    trade_pnls = _compute_trade_pnls_from_fills(fills)
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]

    win_rate = len(wins) / len(trade_pnls) * 100 if trade_pnls else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.99 if gross_profit > 0 else 0)

    # Basic Sharpe
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            returns.append((equity_curve[i] - prev) / prev)
    if returns and len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = (sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
        sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0
    else:
        sharpe = 0

    return {
        "pnl_dollar": round(pnl_dollar, 2),
        "pnl_pct": round(pnl_pct, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "num_trades": len(trade_pnls),
        "profit_factor": round(profit_factor, 2),
        "sharpe": round(sharpe, 2),
        "equity_curve": [round(e, 2) for e in equity_curve],
    }


def _compute_trade_pnls_from_fills(fills: list[Fill]) -> list[float]:
    """Compute PnL for each round-trip trade from DB fills."""
    pnls = []
    position = 0.0
    entry_cost = 0.0
    for fill in fills:
        side = fill.side if isinstance(fill.side, str) else fill.side.value
        signed = fill.qty if side == "buy" else -fill.qty
        if position == 0 or (position > 0 and signed > 0) or (position < 0 and signed < 0):
            entry_cost += fill.fill_price * abs(signed) + fill.fee
            position += signed
        else:
            close_qty = min(abs(signed), abs(position))
            avg_entry = entry_cost / abs(position) if abs(position) > 1e-10 else 0
            if position > 0:
                pnl = (fill.fill_price - avg_entry) * close_qty - fill.fee
            else:
                pnl = (avg_entry - fill.fill_price) * close_qty - fill.fee
            pnls.append(pnl)
            remaining = abs(signed) - close_qty
            if remaining > 1e-10:
                position = remaining if signed > 0 else -remaining
                entry_cost = fill.fill_price * remaining
            else:
                position += signed
                if abs(position) < 1e-10:
                    position = 0
                    entry_cost = 0
                else:
                    entry_cost = entry_cost * (abs(position) / (abs(position) + close_qty))
    return pnls


async def _persist_fills_and_update_orders(
    db: AsyncSession,
    new_fills: list[SimFill],
    round_id,
) -> None:
    """Persist fills to DB and update order statuses to FILLED."""
    for f in new_fills:
        db.add(Fill(
            order_id=f.order_id,
            round_id=round_id,
            ts_index=f.ts_index,
            fill_price=f.fill_price,
            qty=f.qty,
            fee=f.fee,
            side=f.side,
        ))
        # Update the order status to FILLED
        result = await db.execute(select(Order).where(Order.id == f.order_id))
        order = result.scalar_one_or_none()
        if order:
            order.status = OrderStatus.FILLED.value


@router.post("", response_model=SimulationResponse)
async def create_simulation(
    data: SimulationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    seed = data.seed if data.seed is not None else random.randint(1, 999999)
    sim = Simulation(
        user_id=user.id,
        market=data.market,
        symbol=data.symbol,
        timeframe=data.timeframe,
        session_filter=data.session_filter,
        session_start=data.session_start,
        session_end=data.session_end,
        num_rounds=data.num_rounds,
        starting_capital=data.starting_capital,
        fee_bps=data.fee_bps,
        slippage_bps=data.slippage_bps,
        seed=seed,
    )
    db.add(sim)
    await db.commit()
    await db.refresh(sim)

    # Generate rounds with hidden dates
    provider = get_provider(data.market)
    available_dates = await provider.get_available_dates(data.symbol, data.timeframe)

    rng = random.Random(seed)
    selected_dates = rng.sample(available_dates, min(data.num_rounds, len(available_dates)))

    for i, date_str in enumerate(selected_dates):
        rnd = Round(
            simulation_id=sim.id,
            round_number=i + 1,
            hidden_date=date_str,
            status=RoundStatus.PENDING.value,
        )
        db.add(rnd)

    await db.commit()
    await db.refresh(sim)
    return sim


@router.get("", response_model=list[SimulationResponse])
async def list_simulations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation)
        .where(Simulation.user_id == user.id)
        .order_by(Simulation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{sim_id}", response_model=SimulationResponse)
async def get_simulation(
    sim_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _verify_sim_ownership(sim_id, user, db)


@router.get("/{sim_id}/rounds", response_model=list[RoundResponse])
async def list_rounds(
    sim_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_sim_ownership(sim_id, user, db)
    result = await db.execute(
        select(Round).where(Round.simulation_id == sim_id).order_by(Round.round_number)
    )
    return result.scalars().all()


@router.post("/{sim_id}/rounds/{round_id}/start", response_model=RoundResponse)
async def start_round(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sim, rnd = await _verify_round_ownership(sim_id, round_id, user, db)

    if rnd.status == RoundStatus.ACTIVE.value:
        return rnd

    # Fetch candles for this round's hidden date
    provider = get_provider(sim.market)
    date = datetime.strptime(rnd.hidden_date, "%Y-%m-%d")
    start_ms = int(date.timestamp() * 1000)
    end_ms = int((date + timedelta(days=1)).timestamp() * 1000)

    candles = await provider.get_candles(sim.symbol, start_ms, end_ms, sim.timeframe)
    candles = _filter_session(candles, sim.session_filter, sim.session_start, sim.session_end)

    if not candles:
        raise HTTPException(400, "No candles available for this date/session")

    engine = SimulationEngine(
        candles=candles,
        starting_capital=sim.starting_capital,
        fee_bps=sim.fee_bps,
        slippage_bps=sim.slippage_bps,
    )

    _engines[str(rnd.id)] = engine

    rnd.status = RoundStatus.ACTIVE.value
    rnd.total_candles = len(candles)
    rnd.current_index = 0
    rnd.started_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rnd)
    return rnd


@router.post("/{sim_id}/rounds/{round_id}/replay", response_model=RoundResponse)
async def replay_round(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replay a finished round from the beginning using the same hidden date/config."""
    sim, rnd = await _verify_round_ownership(sim_id, round_id, user, db)

    # Fetch candles
    provider = get_provider(sim.market)
    date = datetime.strptime(rnd.hidden_date, "%Y-%m-%d")
    start_ms = int(date.timestamp() * 1000)
    end_ms = int((date + timedelta(days=1)).timestamp() * 1000)
    candles = await provider.get_candles(sim.symbol, start_ms, end_ms, sim.timeframe)
    candles = _filter_session(candles, sim.session_filter, sim.session_start, sim.session_end)

    if not candles:
        raise HTTPException(400, "No candles available for this date/session")

    engine = SimulationEngine(
        candles=candles,
        starting_capital=sim.starting_capital,
        fee_bps=sim.fee_bps,
        slippage_bps=sim.slippage_bps,
    )
    _engines[str(rnd.id)] = engine

    # Reset round state
    rnd.status = RoundStatus.ACTIVE.value
    rnd.current_index = 0
    rnd.total_candles = len(candles)
    rnd.started_at = datetime.utcnow()
    rnd.finished_at = None
    await db.commit()
    await db.refresh(rnd)
    return rnd


@router.get("/{sim_id}/rounds/{round_id}/candle")
async def get_current_candle(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    engine = _get_engine(str(round_id))
    if not engine:
        raise HTTPException(400, "Round not started")
    candle = engine.current_candle
    if candle is None:
        return {"finished": True}
    return {
        "finished": False,
        "index": engine.current_index,
        "total": len(engine.candles),
        "candle": {
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        },
    }


@router.post("/{sim_id}/rounds/{round_id}/advance")
async def advance_round(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    engine = _get_engine(str(round_id))
    if not engine:
        raise HTTPException(400, "Round not started")

    # Process any pending orders first
    new_fills = engine.process_orders()

    # Take snapshot
    snap = engine.take_snapshot()

    # Advance
    next_candle = engine.advance()

    # Update DB
    result = await db.execute(select(Round).where(Round.id == round_id))
    rnd = result.scalar_one_or_none()
    if rnd:
        rnd.current_index = engine.current_index
        if engine.is_finished:
            rnd.status = RoundStatus.FINISHED.value
            rnd.finished_at = datetime.utcnow()

        # Save snapshot
        db_snap = Snapshot(
            round_id=rnd.id,
            ts_index=snap.ts_index,
            equity=snap.equity,
            cash=snap.cash,
            position_qty=snap.position_qty,
            avg_price=snap.avg_price,
            unrealized_pnl=snap.unrealized_pnl,
            realized_pnl=snap.realized_pnl,
        )
        db.add(db_snap)

        # Persist fills and update order statuses
        await _persist_fills_and_update_orders(db, new_fills, rnd.id)

        await db.commit()

    resp = {
        "index": engine.current_index,
        "total": len(engine.candles),
        "finished": engine.is_finished,
        "snapshot": {
            "equity": snap.equity,
            "cash": snap.cash,
            "position_qty": snap.position_qty,
            "avg_price": snap.avg_price,
            "unrealized_pnl": snap.unrealized_pnl,
            "realized_pnl": snap.realized_pnl,
        },
        "fills": [
            {
                "order_id": f.order_id,
                "fill_price": f.fill_price,
                "qty": f.qty,
                "fee": f.fee,
                "side": f.side,
            }
            for f in new_fills
        ],
    }

    if next_candle:
        resp["candle"] = {
            "timestamp": next_candle.timestamp,
            "open": next_candle.open,
            "high": next_candle.high,
            "low": next_candle.low,
            "close": next_candle.close,
            "volume": next_candle.volume,
        }

    return resp


@router.post("/{sim_id}/rounds/{round_id}/orders", response_model=OrderResponse)
async def place_order(
    sim_id: UUID,
    round_id: UUID,
    data: OrderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    engine = _get_engine(str(round_id))
    if not engine:
        raise HTTPException(400, "Round not started")
    if engine.is_finished:
        raise HTTPException(400, "Round is finished")

    import uuid

    order_id = str(uuid.uuid4())

    sim_order = SimOrder(
        id=order_id,
        side=data.side,
        type=data.type,
        qty=data.qty,
        limit_price=data.limit_price,
        ts_index=engine.current_index,
    )
    engine.submit_order(sim_order)

    # Save to DB
    db_order = Order(
        id=order_id,
        round_id=round_id,
        ts_index=engine.current_index,
        side=data.side,
        type=data.type,
        qty=data.qty,
        limit_price=data.limit_price,
        status=OrderStatus.PENDING.value,
    )
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    return db_order


@router.get("/{sim_id}/rounds/{round_id}/orders", response_model=list[OrderResponse])
async def list_orders(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    result = await db.execute(
        select(Order).where(Order.round_id == round_id).order_by(Order.created_at)
    )
    return result.scalars().all()


@router.get("/{sim_id}/rounds/{round_id}/fills", response_model=list[FillResponse])
async def list_fills(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    result = await db.execute(
        select(Fill).where(Fill.round_id == round_id).order_by(Fill.created_at)
    )
    return result.scalars().all()


@router.get("/{sim_id}/rounds/{round_id}/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_round_ownership(sim_id, round_id, user, db)
    result = await db.execute(
        select(Snapshot).where(Snapshot.round_id == round_id).order_by(Snapshot.ts_index)
    )
    return result.scalars().all()


@router.get("/{sim_id}/rounds/{round_id}/metrics")
async def round_metrics(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sim, rnd = await _verify_round_ownership(sim_id, round_id, user, db)

    # Try in-memory engine first
    engine = _get_engine(str(round_id))
    if engine and engine.snapshots:
        return engine.compute_metrics()

    # Fallback: compute from DB
    snap_result = await db.execute(
        select(Snapshot).where(Snapshot.round_id == round_id).order_by(Snapshot.ts_index)
    )
    snapshots = list(snap_result.scalars().all())

    fill_result = await db.execute(
        select(Fill).where(Fill.round_id == round_id).order_by(Fill.created_at)
    )
    fills = list(fill_result.scalars().all())

    return _compute_metrics_from_db(snapshots, fills, sim.starting_capital)


@router.get("/{sim_id}/metrics")
async def simulation_metrics(
    sim_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sim = await _verify_sim_ownership(sim_id, user, db)

    result = await db.execute(
        select(Round).where(Round.simulation_id == sim_id).order_by(Round.round_number)
    )
    rounds = result.scalars().all()

    all_metrics = []
    for rnd in rounds:
        if rnd.status != RoundStatus.FINISHED.value:
            continue

        # Try in-memory engine first
        engine = _get_engine(str(rnd.id))
        if engine and engine.snapshots:
            m = engine.compute_metrics()
            m["round_number"] = rnd.round_number
            all_metrics.append(m)
            continue

        # Fallback: compute from DB
        snap_result = await db.execute(
            select(Snapshot).where(Snapshot.round_id == rnd.id).order_by(Snapshot.ts_index)
        )
        snapshots = list(snap_result.scalars().all())

        fill_result = await db.execute(
            select(Fill).where(Fill.round_id == rnd.id).order_by(Fill.created_at)
        )
        fills = list(fill_result.scalars().all())

        if snapshots:
            m = _compute_metrics_from_db(snapshots, fills, sim.starting_capital)
            m["round_number"] = rnd.round_number
            all_metrics.append(m)

    if not all_metrics:
        return {"rounds": [], "total_pnl_dollar": 0, "total_pnl_pct": 0, "total_trades": 0}

    total_pnl = sum(m["pnl_dollar"] for m in all_metrics)
    total_trades = sum(m["num_trades"] for m in all_metrics)

    return {
        "total_pnl_dollar": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl / sim.starting_capital * 100, 2) if sim.starting_capital > 0 else 0,
        "total_trades": total_trades,
        "rounds": all_metrics,
    }
