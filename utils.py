from __future__ import annotations

from typing import Any, Dict

from game_types import Color


def clamp_int(v: int, lo: int, hi: int) -> int:
    """Clamp an integer value into the inclusive range [lo, hi]."""
    return lo if v < lo else hi if v > hi else v


def clamp_float(v: float, lo: float, hi: float) -> float:
    """Clamp a float value into the inclusive range [lo, hi]."""
    return lo if v < lo else hi if v > hi else v


def as_color(value: Any, default: Color) -> Color:
    """Parse a value into an RGB color tuple.

    Args:
        value: A list/tuple-like value with at least 3 items (r, g, b).
        default: The color to return if parsing fails.

    Returns:
        A clamped (r, g, b) tuple in the range [0, 255].
    """
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        r = clamp_int(int(value[0]), 0, 255)
        g = clamp_int(int(value[1]), 0, 255)
        b = clamp_int(int(value[2]), 0, 255)
        return (r, g, b)
    return default


def deep_get(d: Dict[str, Any], path: str, default: Any) -> Any:
    """Get a nested value from a dict using a dotted path.

    Args:
        d: Source dictionary.
        path: Dot-separated key path (e.g. "window.width").
        default: Value to return if any path segment is missing.

    Returns:
        The found value or default.
    """
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

