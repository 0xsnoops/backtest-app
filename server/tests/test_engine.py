"""Tests for the simulation engine: fills, fees, slippage, no-lookahead."""
import pytest
from app.engine.simulator import SimulationEngine, SimOrder
from app.providers.base import Candle


def make_candles(data: list[tuple]) -> list[Candle]:
    """Create candles from (open, high, low, close, volume) tuples."""
    return [
        Candle(timestamp=i * 60000, open=d[0], high=d[1], low=d[2], close=d[3], volume=d[4])
        for i, d in enumerate(data)
    ]


SAMPLE_CANDLES = make_candles([
    (100, 105, 98, 102, 1000),   # 0
    (102, 110, 100, 108, 1200),  # 1
    (108, 112, 106, 110, 900),   # 2
    (110, 115, 108, 112, 1100),  # 3
    (112, 113, 105, 106, 800),   # 4
])


class TestMarketOrderFill:
    def test_buy_fills_at_close_with_slippage(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=10,
            slippage_bps=5,
        )
        order = SimOrder(id="o1", side="buy", type="market", qty=10)
        engine.submit_order(order)
        fills = engine.process_orders()

        assert len(fills) == 1
        fill = fills[0]
        # Close is 102, slippage adds 0.05% -> 102 * 1.0005 = 102.051
        expected_price = 102 * (1 + 5 / 10000)
        assert abs(fill.fill_price - expected_price) < 0.01
        assert fill.qty == 10
        assert fill.fee > 0
        assert order.status == "filled"

    def test_sell_fills_at_close_with_slippage(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=10,
            slippage_bps=5,
        )
        # First buy
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=10))
        engine.process_orders()
        engine.advance()

        # Then sell
        engine.submit_order(SimOrder(id="o2", side="sell", type="market", qty=10))
        fills = engine.process_orders()

        assert len(fills) == 1
        fill = fills[0]
        # Close at index 1 is 108, slippage subtracts
        expected_price = 108 * (1 - 5 / 10000)
        assert abs(fill.fill_price - expected_price) < 0.01


class TestLimitOrderFill:
    def test_buy_limit_fills_when_low_touches(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # Limit buy at 99 - candle 0 low is 98, should fill
        order = SimOrder(id="o1", side="buy", type="limit", qty=5, limit_price=99)
        engine.submit_order(order)
        fills = engine.process_orders()

        assert len(fills) == 1
        # Should fill at min(limit, open) = min(99, 100) = 99
        assert fills[0].fill_price == 99

    def test_buy_limit_not_filled_when_price_above(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # Limit buy at 95 - candle 0 low is 98, should NOT fill
        order = SimOrder(id="o1", side="buy", type="limit", qty=5, limit_price=95)
        engine.submit_order(order)
        fills = engine.process_orders()

        assert len(fills) == 0
        assert order.status == "pending"

    def test_sell_limit_fills_when_high_touches(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # First buy to have position
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=5))
        engine.process_orders()

        # Limit sell at 104 - candle 0 high is 105, should fill
        order = SimOrder(id="o2", side="sell", type="limit", qty=5, limit_price=104)
        engine.submit_order(order)
        fills = engine.process_orders()

        assert len(fills) == 1
        # Should fill at max(limit, open) = max(104, 100) = 104
        assert fills[0].fill_price == 104


class TestFees:
    def test_fee_calculation(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=10,
            slippage_bps=0,
        )
        order = SimOrder(id="o1", side="buy", type="market", qty=10)
        engine.submit_order(order)
        fills = engine.process_orders()

        fill = fills[0]
        # fee = price * qty * (10/10000) = 102 * 10 * 0.001 = 1.02
        expected_fee = 102 * 10 * (10 / 10000)
        assert abs(fill.fee - expected_fee) < 0.01

    def test_zero_fees(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        order = SimOrder(id="o1", side="buy", type="market", qty=10)
        engine.submit_order(order)
        fills = engine.process_orders()
        assert fills[0].fee == 0


class TestSlippage:
    def test_slippage_increases_buy_price(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=50,  # 0.5%
        )
        order = SimOrder(id="o1", side="buy", type="market", qty=1)
        engine.submit_order(order)
        fills = engine.process_orders()

        expected = 102 * (1 + 50 / 10000)
        assert abs(fills[0].fill_price - expected) < 0.01

    def test_slippage_decreases_sell_price(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=50,
        )
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=1))
        engine.process_orders()

        engine.submit_order(SimOrder(id="o2", side="sell", type="market", qty=1))
        fills = engine.process_orders()

        expected = 102 * (1 - 50 / 10000)
        assert abs(fills[0].fill_price - expected) < 0.01


class TestNoLookahead:
    def test_engine_only_provides_current_candle(self):
        engine = SimulationEngine(candles=SAMPLE_CANDLES, starting_capital=10000)

        # At index 0, should only see candle 0
        assert engine.current_index == 0
        assert engine.current_candle.close == 102

        # After advance, at index 1
        engine.advance()
        assert engine.current_index == 1
        assert engine.current_candle.close == 108

    def test_no_access_to_future_candles_via_engine(self):
        engine = SimulationEngine(candles=SAMPLE_CANDLES, starting_capital=10000)

        # The engine's public API only exposes current_candle
        # Verify the current candle matches index 0
        assert engine.current_candle == SAMPLE_CANDLES[0]
        assert engine.current_index == 0

        # Verify we can't get candle at index 2 without advancing
        engine.advance()
        assert engine.current_index == 1
        # Still no access to index 2 without another advance

    def test_fills_use_only_current_candle(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # Market order at index 0 fills at close of candle 0 (102), not candle 1 (108)
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=1))
        fills = engine.process_orders()

        assert fills[0].fill_price == 102  # candle 0 close, not future


class TestPositionTracking:
    def test_buy_then_sell_round_trip_pnl(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # Buy at candle 0 close (102)
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=10))
        engine.process_orders()
        engine.take_snapshot()
        engine.advance()

        # Sell at candle 1 close (108)
        engine.submit_order(SimOrder(id="o2", side="sell", type="market", qty=10))
        engine.process_orders()
        snap = engine.take_snapshot()

        assert engine.position.is_flat
        # PnL = (108 - 102) * 10 = 60
        assert abs(engine.position.realized_pnl - 60) < 0.01
        # Cash should be starting + profit
        assert abs(engine.cash - 10060) < 0.01


class TestMetrics:
    def test_metrics_computation(self):
        engine = SimulationEngine(
            candles=SAMPLE_CANDLES,
            starting_capital=10000,
            fee_bps=0,
            slippage_bps=0,
        )
        # Buy and sell for a winning trade
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=10))
        engine.process_orders()
        engine.take_snapshot()
        engine.advance()

        engine.submit_order(SimOrder(id="o2", side="sell", type="market", qty=10))
        engine.process_orders()
        engine.take_snapshot()

        metrics = engine.compute_metrics()
        assert metrics["pnl_dollar"] == 60
        assert metrics["num_trades"] >= 1
        assert len(metrics["equity_curve"]) == 2


class TestEdgeCases:
    def test_finished_engine(self):
        engine = SimulationEngine(candles=SAMPLE_CANDLES[:1], starting_capital=10000)
        engine.advance()
        assert engine.is_finished
        assert engine.current_candle is None

    def test_order_on_finished_engine(self):
        engine = SimulationEngine(candles=SAMPLE_CANDLES[:1], starting_capital=10000)
        engine.advance()
        engine.submit_order(SimOrder(id="o1", side="buy", type="market", qty=1))
        fills = engine.process_orders()
        assert len(fills) == 0
