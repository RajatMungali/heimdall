from datetime import datetime, timezone

RECENCY_TIERS = [
    (30,  1.50),   # < 30 days   -> 1.5x recency boost
    (90,  1.00),   # 1-3 months  -> 1.0x baseline weight
    (180, 0.70),   # 3-6 months  -> 0.7x weight multiplier
    (365, 0.40),   # 6-12 months -> 0.4x weight multiplier
]
FALLBACK_MULTIPLIER = 0.10  # > 12 months -> 0.1x floor multiplier


def calculate_time_decay(event_date_str: str) -> tuple[float, str]:
    """
    Computes a recency factor and a string tracking indicator
    based on data age. (Fix 2)
    """
    if not event_date_str:
        return 0.50, "unknown"

    try:
        from dateutil import parser
        event_date = parser.parse(event_date_str)
        if event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)
    except Exception:
        return 0.50, "unknown"

    delta_days = (datetime.now(timezone.utc) - event_date).days

    for max_days, multiplier in RECENCY_TIERS:
        if delta_days <= max_days:
            label = "current" if max_days <= 30 else f"{delta_days}d_stale"
            return multiplier, label

    return FALLBACK_MULTIPLIER, "historical"
