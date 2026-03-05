"""
WebSocket handler for real-time candle streaming.

Protocol:
  Client sends JSON messages:
    {"action": "start", "round_id": "...", "sim_id": "..."}
    {"action": "play"}
    {"action": "pause"}
    {"action": "step"}
    {"action": "speed", "value": 1.0}
    {"action": "order", "side": "buy"|"sell", "type": "market"|"limit", "qty": 1.0, "limit_price": null}

  Server sends JSON messages:
    {"type": "candle", "index": N, "total": T, "candle": {...}, "snapshot": {...}}
    {"type": "fill", ...}
    {"type": "finished", "metrics": {...}}
    {"type": "error", "message": "..."}
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.config import settings
from app.database import async_session
from app.models.tables import Simulation, Round, RoundStatus, Order, Fill, Snapshot, OrderSide, OrderType, OrderStatus
from app.engine.simulator import SimulationEngine, SimOrder
from app.providers.binance import get_provider
from app.api.simulations import _engines, _filter_session
from sqlalchemy import select


async def ws_handler(websocket: WebSocket):
    await websocket.accept()

    # Auth via query param or first message
    token = websocket.query_params.get("token")
    if not token:
        try:
            msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            token = msg.get("token")
        except Exception:
            await websocket.close(code=4001, reason="No token")
            return

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    playing = False
    speed = 1.0  # 1 candle per second at 1x
    engine: SimulationEngine | None = None
    round_id: str | None = None
    sim_id: str | None = None

    async def send_candle_update():
        if not engine or engine.is_finished:
            return
        # Process pending orders
        new_fills = engine.process_orders()
        snap = engine.take_snapshot()

        candle = engine.current_candle
        msg = {
            "type": "candle",
            "index": engine.current_index,
            "total": len(engine.candles),
            "candle": {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            } if candle else None,
            "snapshot": {
                "equity": round(snap.equity, 2),
                "cash": round(snap.cash, 2),
                "position_qty": snap.position_qty,
                "avg_price": round(snap.avg_price, 2),
                "unrealized_pnl": round(snap.unrealized_pnl, 2),
                "realized_pnl": round(snap.realized_pnl, 2),
            },
        }
        await websocket.send_json(msg)

        for f in new_fills:
            await websocket.send_json({
                "type": "fill",
                "order_id": f.order_id,
                "fill_price": round(f.fill_price, 2),
                "qty": f.qty,
                "fee": round(f.fee, 4),
                "side": f.side,
                "ts_index": f.ts_index,
            })

        # Save to DB
        async with async_session() as db:
            db_snap = Snapshot(
                round_id=round_id,
                ts_index=snap.ts_index,
                equity=snap.equity,
                cash=snap.cash,
                position_qty=snap.position_qty,
                avg_price=snap.avg_price,
                unrealized_pnl=snap.unrealized_pnl,
                realized_pnl=snap.realized_pnl,
            )
            db.add(db_snap)
            for f in new_fills:
                db.add(Fill(
                    order_id=f.order_id,
                    round_id=round_id,
                    ts_index=f.ts_index,
                    fill_price=f.fill_price,
                    qty=f.qty,
                    fee=f.fee,
                ))
            await db.commit()

    async def advance_and_send():
        nonlocal engine
        if not engine:
            return
        next_candle = engine.advance()
        if engine.is_finished:
            metrics = engine.compute_metrics()
            await websocket.send_json({"type": "finished", "metrics": metrics})
            # Update round status
            async with async_session() as db:
                result = await db.execute(select(Round).where(Round.id == round_id))
                rnd = result.scalar_one_or_none()
                if rnd:
                    rnd.status = RoundStatus.FINISHED
                    rnd.finished_at = datetime.utcnow()
                    rnd.current_index = engine.current_index
                    await db.commit()
            return
        await send_candle_update()
        # Update current index in DB
        async with async_session() as db:
            result = await db.execute(select(Round).where(Round.id == round_id))
            rnd = result.scalar_one_or_none()
            if rnd:
                rnd.current_index = engine.current_index
                await db.commit()

    try:
        while True:
            if playing and engine and not engine.is_finished:
                # Auto-advance with speed
                delay = 1.0 / speed
                try:
                    msg = await asyncio.wait_for(websocket.receive_json(), timeout=delay)
                except asyncio.TimeoutError:
                    await advance_and_send()
                    continue
            else:
                msg = await websocket.receive_json()

            action = msg.get("action")

            if action == "start":
                sim_id = msg.get("sim_id")
                round_id = msg.get("round_id")

                # Check if engine already exists
                if round_id in _engines:
                    engine = _engines[round_id]
                    await send_candle_update()
                    continue

                # Load and create engine
                async with async_session() as db:
                    result = await db.execute(select(Simulation).where(Simulation.id == sim_id))
                    sim = result.scalar_one_or_none()
                    if not sim:
                        await websocket.send_json({"type": "error", "message": "Simulation not found"})
                        continue

                    result = await db.execute(select(Round).where(Round.id == round_id))
                    rnd = result.scalar_one_or_none()
                    if not rnd:
                        await websocket.send_json({"type": "error", "message": "Round not found"})
                        continue

                    provider = get_provider(sim.market)
                    date = datetime.strptime(rnd.hidden_date, "%Y-%m-%d")
                    start_ms = int(date.timestamp() * 1000)
                    end_ms = int((date + timedelta(days=1)).timestamp() * 1000)
                    candles = await provider.get_candles(sim.symbol, start_ms, end_ms, sim.timeframe)
                    candles = _filter_session(candles, sim.session_filter, sim.session_start, sim.session_end)

                    if not candles:
                        await websocket.send_json({"type": "error", "message": "No candles for this date"})
                        continue

                    engine = SimulationEngine(
                        candles=candles,
                        starting_capital=sim.starting_capital,
                        fee_bps=sim.fee_bps,
                        slippage_bps=sim.slippage_bps,
                    )
                    _engines[round_id] = engine

                    rnd.status = RoundStatus.ACTIVE
                    rnd.total_candles = len(candles)
                    rnd.started_at = datetime.utcnow()
                    await db.commit()

                await send_candle_update()

            elif action == "play":
                playing = True

            elif action == "pause":
                playing = False

            elif action == "step":
                playing = False
                await advance_and_send()

            elif action == "speed":
                speed = float(msg.get("value", 1.0))
                speed = max(0.25, min(speed, 10.0))

            elif action == "order":
                if not engine or engine.is_finished:
                    await websocket.send_json({"type": "error", "message": "Cannot place order"})
                    continue
                order_id = str(uuid.uuid4())
                sim_order = SimOrder(
                    id=order_id,
                    side=msg["side"],
                    type=msg.get("type", "market"),
                    qty=float(msg["qty"]),
                    limit_price=float(msg["limit_price"]) if msg.get("limit_price") else None,
                    ts_index=engine.current_index,
                )
                engine.submit_order(sim_order)

                # Save to DB
                async with async_session() as db:
                    db.add(Order(
                        id=order_id,
                        round_id=round_id,
                        ts_index=engine.current_index,
                        side=OrderSide(msg["side"]),
                        type=OrderType(msg.get("type", "market")),
                        qty=float(msg["qty"]),
                        limit_price=float(msg["limit_price"]) if msg.get("limit_price") else None,
                        status=OrderStatus.PENDING,
                    ))
                    await db.commit()

                await websocket.send_json({
                    "type": "order_ack",
                    "order_id": order_id,
                    "side": msg["side"],
                    "qty": float(msg["qty"]),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
