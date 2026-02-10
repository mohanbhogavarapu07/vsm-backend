"""Input validation helpers."""
from typing import Any, List, Optional, Tuple


def required_keys(data: dict, keys: List[str]) -> Optional[str]:
    """Return None if all keys present and non-empty (or 0); else error message."""
    if not data:
        return "Request body is required"
    missing = [k for k in keys if data.get(k) is None or (data.get(k) == "" and data.get(k) != 0)]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


def one_of(value: Any, allowed: tuple) -> bool:
    return value in allowed


def int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
