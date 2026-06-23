def map_fear_greed_to_backdrop(payload: dict):
    data = payload.get("data") or []
    if not data:
        return None

    item = data[0] or {}

    value_raw = item.get("value")
    label = item.get("value_classification")
    ts_raw = item.get("timestamp")

    try:
        value = int(value_raw) if value_raw is not None else None
    except Exception:
        value = None

    return {
        "fearGreedValue": value,
        "fearGreedLabel": label,
        "source": "alternative-me-fng",
        "ts": str(ts_raw) if ts_raw is not None else None,
    }