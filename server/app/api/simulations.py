import random
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
from app.engine.simulator import SimulationEngine, SimOrder, Candle as EngineCandle

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# In-memory engine store (round_id -> engine)
_engines: dict[str, SimulationEngine] = {}


def _get_engine(round_id: str) -> SimulationEngine | None:
    return _engines.get(round_id)


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

    # Filter by session if needed
    rng = random.Random(seed)
    selected_dates = rng.sample(available_dates, min(data.num_rounds, len(available_dates)))

    for i, date_str in enumerate(selected_dates):
        rnd = Round(
            simulation_id=sim.id,
            round_number=i + 1,
            hidden_date=date_str,
            status=RoundStatus.PENDING,
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
    result = await db.execute(
        select(Simulation).where(Simulation.id == sim_id, Simulation.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(404, "Simulation not found")
    return sim


@router.get("/{sim_id}/rounds", response_model=list[RoundResponse])
async def list_rounds(
    sim_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(Simulation.id == sim_id, Simulation.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(404, "Simulation not found")
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
    # Validate ownership
    result = await db.execute(
        select(Simulation).where(Simulation.id == sim_id, Simulation.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(404, "Simulation not found")

    result = await db.execute(
        select(Round).where(Round.id == round_id, Round.simulation_id == sim_id)
    )
    rnd = result.scalar_one_or_none()
    if not rnd:
        raise HTTPException(404, "Round not found")

    if rnd.status == RoundStatus.ACTIVE:
        # Already started, return it
        return rnd

    # Fetch candles for this round's hidden date
    provider = get_provider(sim.market)
    date = datetime.strptime(rnd.hidden_date, "%Y-%m-%d")
    start_ms = int(date.timestamp() * 1000)
    end_ms = int((date + timedelta(days=1)).timestamp() * 1000)

    candles = await provider.get_candles(sim.symbol, start_ms, end_ms, sim.timeframe)

    # Apply session filter
    candles = _filter_session(candles, sim.session_filter, sim.session_start, sim.session_end)

    if not candles:
        raise HTTPException(400, "No candles available for this date/session")

    # Create engine
    engine_candles = candles
    engine = SimulationEngine(
        candles=engine_candles,
        starting_capital=sim.starting_capital,
        fee_bps=sim.fee_bps,
        slippage_bps=sim.slippage_bps,
    )

    _engines[str(rnd.id)] = engine

    rnd.status = RoundStatus.ACTIVE
    rnd.total_candles = len(candles)
    rnd.current_index = 0
    rnd.started_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rnd)
    return rnd


def _filter_session(candles, session_filter, session_start, session_end):
    """Filter candles by session time window."""
    if not session_filter and not session_start:
        return candles
    if session_filter == "regular":
        # 9:30-16:00 ET (approximate using UTC: 14:30-21:00)
        start_h, start_m = 14, 30
        end_h, end_m = 21, 0
    elif session_filter == "premarket":
        start_h, start_m = 9, 0
        end_h, end_m = 14, 30
    elif session_filter == "afterhours":
        start_h, start_m = 21, 0
        end_h, end_m = 25, 0  # wraps
    elif session_filter == "custom" and session_start and session_end:
        sp = session_start.split(":")
        ep = session_end.split(":")
        start_h, start_m = int(sp[0]), int(sp[1])
        end_h, end_m = int(ep[0]), int(ep[1])
    else:
        return candles

    filtered = []
    for c in candles:
        dt = datetime.utcfromtimestamp(c.timestamp / 1000)
        t = dt.hour * 60 + dt.minute
        s = start_h * 60 + start_m
        e = end_h * 60 + end_m
        if s <= t < e:
            filtered.append(c)
    return filtered


@router.get("/{sim_id}/rounds/{round_id}/candle")
async def get_current_candle(
    sim_id: UUID,
    round_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
            rnd.status = RoundStatus.FINISHED
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

        # Save fills
        for f in new_fills:
            db_fill = Fill(
                order_id=f.order_id,
                round_id=rnd.id,
                ts_index=f.ts_index,
                fill_price=f.fill_price,
                qty=f.qty,
                fee=f.fee,
            )
            db.add(db_fill)

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
        side=OrderSide(data.side),
        type=OrderType(data.type),
        qty=data.qty,
        limit_price=data.limit_price,
        status=OrderStatus.PENDING,
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
    engine = _get_engine(str(round_id))
    if not engine:
        raise HTTPException(400, "Round not started or engine expired")
    return engine.compute_metrics()


@router.get("/{sim_id}/metrics")
async def simulation_metrics(
    sim_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Round).where(Round.simulation_id == sim_id).order_by(Round.round_number)
    )
    rounds = result.scalars().all()

    all_metrics = []
    for rnd in rounds:
        engine = _get_engine(str(rnd.id))
        if engine:
            m = engine.compute_metrics()
            m["round_number"] = rnd.round_number
            all_metrics.append(m)

    if not all_metrics:
        return {"rounds": [], "total_pnl_dollar": 0, "total_pnl_pct": 0}

    result = await db.execute(
        select(Simulation).where(Simulation.id == sim_id)
    )
    sim = result.scalar_one()

    total_pnl = sum(m["pnl_dollar"] for m in all_metrics)
    total_trades = sum(m["num_trades"] for m in all_metrics)
    all_wins = [m for m in all_metrics if m["pnl_dollar"] > 0]
    all_losses = [m for m in all_metrics if m["pnl_dollar"] < 0]

    return {
        "total_pnl_dollar": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl / sim.starting_capital * 100, 2),
        "total_trades": total_trades,
        "rounds": all_metrics,
    }
