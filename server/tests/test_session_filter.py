"""Tests for session filter logic including overnight/wrapping windows."""
import pytest
from app.providers.base import Candle
from app.engine.session_filter import filter_session as _filter_session


def _candle_at_utc_hour(hour: int, minute: int = 0) -> Candle:
    """Create a candle at the given UTC hour:minute on a fixed date (2024-01-15)."""
    from datetime import datetime
    dt = datetime(2024, 1, 15, hour, minute, 0)
    ts_ms = int(dt.timestamp() * 1000)
    return Candle(timestamp=ts_ms, open=100, high=101, low=99, close=100, volume=1000)


class TestSessionFilterSameDay:
    def test_regular_hours(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "regular", None, None)
        # Regular: 14:30 - 21:00 UTC -> hours 14(if :30+), 15, 16, 17, 18, 19, 20
        hours = [14, 15, 16, 17, 18, 19, 20]
        # The 14:00 candle is at minute 0, which is < 14:30, so excluded
        assert len(filtered) == 6  # 15,16,17,18,19,20

    def test_premarket(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "premarket", None, None)
        # Premarket: 9:00 - 14:30 UTC
        assert len(filtered) == 6  # 9,10,11,12,13,14

    def test_no_filter_returns_all(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, None, None, None)
        assert len(filtered) == 24

    def test_empty_string_filter_returns_all(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "", None, None)
        assert len(filtered) == 24

    def test_custom_same_day(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "custom", "10:00", "14:00")
        assert len(filtered) == 4  # 10, 11, 12, 13


class TestSessionFilterOvernight:
    def test_afterhours_wraps_overnight(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "afterhours", None, None)
        # Afterhours: 21:00 - 01:00 UTC (wraps overnight)
        # Should include hours 21, 22, 23, 0
        assert len(filtered) == 4

    def test_afterhours_includes_late_night(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "afterhours", None, None)
        hours = sorted([
            int(c.timestamp / 1000 / 3600) % 24
            for c in filtered
        ])
        # Should wrap: 0, 21, 22, 23
        assert 0 in hours
        assert 21 in hours
        assert 23 in hours

    def test_custom_overnight_window(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        # Custom window: 22:00 - 06:00 (overnight)
        filtered = _filter_session(candles, "custom", "22:00", "06:00")
        # Should include: 22, 23, 0, 1, 2, 3, 4, 5
        assert len(filtered) == 8

    def test_custom_overnight_excludes_daytime(self):
        candles = [_candle_at_utc_hour(h) for h in range(24)]
        filtered = _filter_session(candles, "custom", "22:00", "06:00")
        for c in filtered:
            from datetime import datetime
            dt = datetime.utcfromtimestamp(c.timestamp / 1000)
            # All should be in [22,23] or [0,5]
            assert dt.hour >= 22 or dt.hour < 6


class TestSessionFilterEdgeCases:
    def test_empty_candles(self):
        filtered = _filter_session([], "regular", None, None)
        assert filtered == []

    def test_candle_at_exact_boundary_start_included(self):
        # 14:30 exactly should be included in regular
        candle = _candle_at_utc_hour(14, 30)
        filtered = _filter_session([candle], "regular", None, None)
        assert len(filtered) == 1

    def test_candle_at_exact_boundary_end_excluded(self):
        # 21:00 exactly should be excluded from regular (< not <=)
        candle = _candle_at_utc_hour(21, 0)
        filtered = _filter_session([candle], "regular", None, None)
        assert len(filtered) == 0
