from __future__ import annotations

from typing import Any, Dict

from models import PlayerConfig, TileSpec
from utils import as_color


def parse_player_config(raw: Dict[str, Any]) -> PlayerConfig:
    """Parse player settings from config data.

    Args:
        raw: Dict containing player settings.

    Returns:
        PlayerConfig with defaults applied.
    """
    return PlayerConfig(
        color=as_color(raw.get("color", [235, 240, 255]), (235, 240, 255)),
        speed=float(raw.get("speed", 260)),
        jump_strength=float(raw.get("jump_strength", 560)),
        gravity=float(raw.get("gravity", 1700)),
        max_fall=float(raw.get("max_fall", 1000)),
    )


def parse_legend(cfg: Dict[str, Any]) -> Dict[str, TileSpec]:
    """Parse the tile legend from config data."""
    legend_raw = cfg.get("legend", {})
    legend: Dict[str, TileSpec] = {}

    if not isinstance(legend_raw, dict):
        legend_raw = {}

    for ch, raw in legend_raw.items():
        if not isinstance(ch, str) or len(ch) != 1 or not isinstance(raw, dict):
            continue

        shape = str(raw.get("shape", "none")).lower()
        solid = bool(raw.get("solid", False))
        color = None if shape == "none" else as_color(raw.get("color"), (200, 60, 220))

        on_col = raw.get("on_collision", {})
        if not isinstance(on_col, dict):
            on_col = {}

        legend[ch] = TileSpec(char=ch, shape=shape, color=color, solid=solid, on_collision=on_col)

    if "." not in legend:
        legend["."] = TileSpec(char=".", shape="none", color=None, solid=False, on_collision={})

    return legend
