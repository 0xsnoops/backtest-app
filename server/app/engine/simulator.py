"""
Simulation Engine

Fill convention: Market orders fill at CURRENT candle's close price.
Limit orders fill if price crosses during CURRENT candle (using OHLC).

No lookahead: fill logic only uses the current candle.
"""

from dataclasses import dataclass, field
from typing import Optional
from app.providers.base import Candle
import math


@dataclass
class Position:
    qty: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def is_flat(self) -> bool:
        return abs(self.qty) < 1e-10

    def unrealized_pnl(self, current_price: float) -> float:
        if self.is_flat:
            return 0.0
        return (current_price - self.avg_price) * self.qty


@dataclass
class SimOrder:
    id: str
    side: str  # "buy" or "sell"
    type: str  # "market" or "limit"
    qty: float
    limit_price: Optional[float] = None
    status: str = "pending"
    ts_index: int = 0


@dataclass
class SimFill:
    order_id: str
    ts_index: int
    fill_price: float
    qty: float
    fee: float
    side: str


@dataclass
class EquitySnapshot:
    ts_index: int
    equity: float
    cash: float
    position_qty: float
    avg_price: float
    unrealized_pnl: float
    realized_pnl: float


class SimulationEngine:
    """Core deterministic simulation engine."""

    def __init__(
        self,
        candles: list[Candle],
        starting_capital: float = 10000.0,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ):
        self.candles = candles
        self.starting_capital = starting_capital
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

        self.cash = starting_capital
        self.position = Position()
        self.current_index = 0
        self.pending_orders: list[SimOrder] = []
        self.fills: list[SimFill] = []
        self.snapshots: list[EquitySnapshot] = []
        self.all_orders: list[SimOrder] = []

    @property
    def current_candle(self) -> Optional[Candle]:
        if 0 <= self.current_index < len(self.candles):
            return self.candles[self.current_index]
        return None

    @property
    def is_finished(self) -> bool:
        return self.current_index >= len(self.candles)

    def equity(self, price: Optional[float] = None) -> float:
        if price is None:
            c = self.current_candle
            price = c.close if c else 0
        return self.cash + self.position.qty * price

    def submit_order(self, order: SimOrder) -> None:
        order.ts_index = self.current_index
        order.status = "pending"
        self.pending_orders.append(order)
        self.all_orders.append(order)

    def _apply_slippage(self, price: float, side: str) -> float:
        slip = price * (self.slippage_bps / 10000.0)
        return price + slip if side == "buy" else price - slip

    def _calc_fee(self, price: float, qty: float) -> float:
        return abs(price * qty) * (self.fee_bps / 10000.0)

    def _execute_fill(self, order: SimOrder, fill_price: float) -> SimFill:
        price_with_slippage = self._apply_slippage(fill_price, order.side)
        fee = self._calc_fee(price_with_slippage, order.qty)
        signed_qty = order.qty if order.side == "buy" else -order.qty

        # Update position
        if self.position.is_flat or (
            (self.position.qty > 0 and order.side == "buy")
            or (self.position.qty < 0 and order.side == "sell")
        ):
            # Adding to position
            total_cost = self.position.avg_price * self.position.qty + price_with_slippage * signed_qty
            new_qty = self.position.qty + signed_qty
            self.position.avg_price = total_cost / new_qty if abs(new_qty) > 1e-10 else 0
            self.position.qty = new_qty
        else:
            # Reducing / flipping position
            close_qty = min(abs(signed_qty), abs(self.position.qty))
            pnl = (price_with_slippage - self.position.avg_price) * close_qty
            if self.position.qty < 0:
                pnl = (self.position.avg_price - price_with_slippage) * close_qty
            self.position.realized_pnl += pnl

            remaining = abs(signed_qty) - close_qty
            if remaining > 1e-10:
                # Flip
                self.position.qty = remaining if order.side == "buy" else -remaining
                self.position.avg_price = price_with_slippage
            else:
                self.position.qty += signed_qty
                if abs(self.position.qty) < 1e-10:
                    self.position.qty = 0
                    self.position.avg_price = 0

        cost = price_with_slippage * signed_qty + fee
        self.cash -= cost

        sim_fill = SimFill(
            order_id=order.id,
            ts_index=self.current_index,
            fill_price=price_with_slippage,
            qty=order.qty,
            fee=fee,
            side=order.side,
        )
        self.fills.append(sim_fill)
        order.status = "filled"
        return sim_fill

    def process_orders(self) -> list[SimFill]:
        """Process pending orders against current candle. Called each tick."""
        candle = self.current_candle
        if candle is None:
            return []

        new_fills: list[SimFill] = []
        still_pending = []

        for order in self.pending_orders:
            if order.type == "market":
                fill = self._execute_fill(order, candle.close)
                new_fills.append(fill)
            elif order.type == "limit":
                if order.limit_price is None:
                    order.status = "cancelled"
                    continue
                filled = False
                if order.side == "buy" and candle.low <= order.limit_price:
                    fill_price = min(order.limit_price, candle.open)
                    fill = self._execute_fill(order, fill_price)
                    new_fills.append(fill)
                    filled = True
                elif order.side == "sell" and candle.high >= order.limit_price:
                    fill_price = max(order.limit_price, candle.open)
                    fill = self._execute_fill(order, fill_price)
                    new_fills.append(fill)
                    filled = True
                if not filled:
                    still_pending.append(order)
            else:
                still_pending.append(order)

        self.pending_orders = still_pending
        return new_fills

    def take_snapshot(self) -> EquitySnapshot:
        candle = self.current_candle
        price = candle.close if candle else 0
        snap = EquitySnapshot(
            ts_index=self.current_index,
            equity=self.equity(price),
            cash=self.cash,
            position_qty=self.position.qty,
            avg_price=self.position.avg_price,
            unrealized_pnl=self.position.unrealized_pnl(price),
            realized_pnl=self.position.realized_pnl,
        )
        self.snapshots.append(snap)
        return snap

    def advance(self) -> Optional[Candle]:
        """Advance to next candle. Returns the new candle or None if finished."""
        self.current_index += 1
        return self.current_candle

    def compute_metrics(self) -> dict:
        """Compute round metrics from fills and snapshots."""
        if not self.snapshots:
            return self._empty_metrics()

        equity_curve = [s.equity for s in self.snapshots]
        final_equity = equity_curve[-1] if equity_curve else self.starting_capital
        pnl_dollar = final_equity - self.starting_capital
        pnl_pct = (pnl_dollar / self.starting_capital) * 100

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Win/loss from round-trip trades
        wins, losses = [], []
        # Group fills into trades
        trade_pnls = self._compute_trade_pnls()
        for pnl in trade_pnls:
            if pnl > 0:
                wins.append(pnl)
            elif pnl < 0:
                losses.append(pnl)

        win_rate = len(wins) / len(trade_pnls) * 100 if trade_pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        # Basic Sharpe (using equity returns)
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
            "profit_factor": round(profit_factor, 2) if not math.isinf(profit_factor) else 999.99,
            "sharpe": round(sharpe, 2),
            "equity_curve": [round(e, 2) for e in equity_curve],
        }

    def _compute_trade_pnls(self) -> list[float]:
        """Compute PnL for each round-trip trade from fills."""
        pnls = []
        position = 0.0
        entry_cost = 0.0
        for fill in self.fills:
            signed = fill.qty if fill.side == "buy" else -fill.qty
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

    def _empty_metrics(self) -> dict:
        return {
            "pnl_dollar": 0, "pnl_pct": 0, "max_drawdown": 0, "win_rate": 0,
            "avg_win": 0, "avg_loss": 0, "num_trades": 0, "profit_factor": 0,
            "sharpe": 0, "equity_curve": [],
        }
