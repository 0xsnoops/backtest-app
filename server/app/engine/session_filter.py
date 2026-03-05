"""Session time-window filtering for candles."""

from datetime import datetime


def filter_session(candles, session_filter, session_start, session_end):
    """Filter candles by session time window. Supports overnight wrapping."""
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
        end_h, end_m = 1, 0  # next day 1am UTC -> wraps overnight
    elif session_filter == "custom" and session_start and session_end:
        sp = session_start.split(":")
        ep = session_end.split(":")
        start_h, start_m = int(sp[0]), int(sp[1])
        end_h, end_m = int(ep[0]), int(ep[1])
    else:
        return candles

    s = start_h * 60 + start_m
    e = end_h * 60 + end_m

    filtered = []
    for c in candles:
        dt = datetime.utcfromtimestamp(c.timestamp / 1000)
        t = dt.hour * 60 + dt.minute
        if s <= e:
            # Normal same-day window
            if s <= t < e:
                filtered.append(c)
        else:
            # Overnight window (start > end means wrap around midnight)
            if t >= s or t < e:
                filtered.append(c)
    return filtered
