from __future__ import annotations

from typing import Any, Dict, Tuple

from models import PlayerConfig, TileSpec, UpgradesConfig
from utils import apply_color_mode, as_color


def _parse_upgrade_levels(raw: Any) -> Dict[str, int]:
    """
    Optional per-run starting levels (usually all 0).
    Allows config like:
      "player": { "upgrades": { "speed": 1, "high_jump": 2 } }
    """
    if not isinstance(raw, dict):
        return {}

    levels: Dict[str, int] = {}
    for name, value in raw.items():
        try:
            levels[str(name)] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return levels


def _parse_gravity(raw_gravity: Any) -> Tuple[float, float]:
    """Parse gravity into (gx, gy)."""
    default = (0.0, 1700.0)

    if isinstance(raw_gravity, (list, tuple)) and len(raw_gravity) >= 2:
        return float(raw_gravity[0]), float(raw_gravity[1])

    if isinstance(raw_gravity, dict):
        gx = raw_gravity.get("x", raw_gravity.get("gx", 0.0))
        gy = raw_gravity.get("y", raw_gravity.get("gy", 1700.0))
        return float(gx), float(gy)

    if raw_gravity is not None:
        return 0.0, float(raw_gravity)

    return default


def _parse_orientation(raw: Any) -> str:
    """Parse orientation into 'up' or 'down' (defaults to up)."""
    if isinstance(raw, str):
        val = raw.strip().lower()
        if val in ("up", "down"):
            return val
    return "up"


def parse_player_config(raw: Dict[str, Any], color_mode: str = "multicolor") -> PlayerConfig:
    """Parse player settings from config data.

    Args:
        raw: Dict containing player settings.
        color_mode: Color rendering mode (multicolor|gray).

    Returns:
        PlayerConfig with defaults applied.
    """
    color = as_color(raw.get("color", [235, 240, 255]), (235, 240, 255))
    color = apply_color_mode(color, color_mode)
    shape_raw = str(raw.get("shape", "rect")).lower()
    orientation = _parse_orientation(raw.get("orientation"))
    if "triangle" in shape_raw:
        shape = "triangle"
        if orientation == "up" and "down" in shape_raw:
            orientation = "down"
    elif shape_raw in ("rect", "circle"):
        shape = shape_raw
    else:
        shape = "rect"
    ascii_char_raw = raw.get("ascii_char", "@")
    ascii_char = "@" if ascii_char_raw is None else str(ascii_char_raw)
    ascii_char = ascii_char.strip() or "@"
    # Ensure a single glyph for ASCII mode.
    ascii_char = ascii_char[0]
    return PlayerConfig(
        color=color,
        shape=shape,
        orientation=orientation,
        ascii_char=ascii_char,
        gravity=_parse_gravity(raw.get("gravity")),
        max_fall=float(raw.get("max_fall", 1000)),
        upgrades=_parse_upgrade_levels(raw.get("upgrades", {})),
    )


def parse_upgrade_config(raw: Dict[str, Any]) -> UpgradesConfig:
    """Parse upgrade settings from config data.

    Args:
        raw: Dict containing upgrade settings.

    Returns:
        UpgradesConfig with defaults applied.
    """
    if not isinstance(raw, dict):
        raw = {}
    return UpgradesConfig.from_dict(raw)


def parse_legend(cfg: Dict[str, Any], color_mode: str = "multicolor") -> Dict[str, TileSpec]:
    """Parse the tile legend from config data."""
    legend_raw = cfg.get("legend", {})
    legend: Dict[str, TileSpec] = {}

    if not isinstance(legend_raw, dict):
        legend_raw = {}

    for ch, raw in legend_raw.items():
        if not isinstance(ch, str) or len(ch) != 1 or not isinstance(raw, dict):
            continue

        shape_raw = str(raw.get("shape", "none")).lower()
        orientation = _parse_orientation(raw.get("orientation"))
        if "triangle" in shape_raw:
            shape = "triangle"
            if orientation == "up" and "down" in shape_raw:
                orientation = "down"
        elif shape_raw in ("rect", "circle", "none"):
            shape = shape_raw
        else:
            shape = "none"
        solid = bool(raw.get("solid", False))
        base_color = None if shape == "none" else as_color(raw.get("color"), (200, 60, 220))
        color = apply_color_mode(base_color, color_mode) if base_color is not None else None

        title_raw = raw.get("title")
        title = str(title_raw).strip() if isinstance(title_raw, str) else None

        desc_raw = raw.get("description")
        description = str(desc_raw).strip() if isinstance(desc_raw, str) else None

        on_col = raw.get("on_collision", {})
        if not isinstance(on_col, dict):
            on_col = {}

        legend[ch] = TileSpec(
            char=ch,
            shape=shape,
            orientation=orientation,
            color=color,
            solid=solid,
            on_collision=on_col,
            title=title,
            description=description,
        )

    if "." not in legend:
        legend["."] = TileSpec(
            char=".",
            shape="none",
            orientation="up",
            color=None,
            solid=False,
            on_collision={},
            title=None,
            description=None,
        )

    return legend
