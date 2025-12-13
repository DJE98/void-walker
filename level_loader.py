from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pygame

from models import Level, TileSpec, TriggerTile


def normalize_grid_lines(lines: List[str], pad_char: str = ".") -> Tuple[List[str], int, int]:
    """Normalize level lines to equal width.

    Args:
        lines: Raw level lines.
        pad_char: Character to pad short lines with.

    Returns:
        (normalized_lines, width_tiles, height_tiles)

    Raises:
        ValueError: If no lines are provided.
    """
    if not lines:
        raise ValueError("Level map is empty.")
    width_tiles = max(len(line) for line in lines)
    height_tiles = len(lines)
    normalized = [line.ljust(width_tiles, pad_char) for line in lines]
    return normalized, width_tiles, height_tiles


def build_level_from_grid(
    name: str,
    grid_lines: List[str],
    legend: Dict[str, TileSpec],
    tile_size: int,
) -> Level:
    """Build a Level (solids, triggers, spawn) from normalized grid lines.

    Args:
        name: Level name.
        grid_lines: Grid lines (will be normalized/padded).
        legend: Character-to-TileSpec mapping.
        tile_size: Tile size in pixels.

    Returns:
        A populated Level instance.
    """
    grid, width_tiles, height_tiles = normalize_grid_lines(grid_lines, pad_char=".")

    solids: List[pygame.Rect] = []
    triggers: List[TriggerTile] = []
    spawn_px = pygame.Vector2(tile_size, tile_size)

    for y, line in enumerate(grid):
        for x, ch in enumerate(line):
            spec = legend.get(ch, legend["."])
            world_rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)

            if ch == "S":
                spawn_px = pygame.Vector2(
                    world_rect.x + tile_size * 0.15,
                    world_rect.y + tile_size * 0.05,
                )

            if spec.solid:
                solids.append(world_rect)
            elif spec.on_collision:
                triggers.append(TriggerTile(rect=world_rect, spec=spec))

    return Level(
        name=name,
        grid=grid,
        width_tiles=width_tiles,
        height_tiles=height_tiles,
        solids=solids,
        triggers=triggers,
        spawn_px=spawn_px,
    )


def resolve_level_name(name: str, inline_levels: Dict[str, Any], levels_dir: Path) -> str:
    """Resolve a level name against inline levels or .txt files (case-insensitive)."""
    if name in inline_levels:
        return name
    for k in inline_levels.keys():
        if str(k).lower() == name.lower():
            return str(k)

    p = levels_dir / f"{name}.txt"
    if p.exists():
        return name

    if levels_dir.exists():
        for f in levels_dir.glob("*.txt"):
            if f.stem.lower() == name.lower():
                return f.stem

    return name


def read_level_lines_inline(resolved_name: str, inline_levels: Dict[str, Any]) -> Optional[List[str]]:
    """Read grid lines from inline config if present."""
    data = inline_levels.get(resolved_name)
    if not (isinstance(data, dict) and "map" in data):
        return None
    raw_map = str(data["map"])
    return [line.rstrip("\n") for line in raw_map.splitlines() if line.strip("\r") != ""]


def read_level_lines_file(resolved_name: str, levels_dir: Path) -> List[str]:
    """Read grid lines from a .txt file."""
    level_path = levels_dir / f"{resolved_name}.txt"
    if not level_path.exists():
        raise FileNotFoundError(
            f"Level '{resolved_name}' not found.\n"
            f"- Looked for inline cfg['levels']['{resolved_name}']['map']\n"
            f"- Looked for file: {level_path}"
        )
    return [line.rstrip("\n") for line in level_path.read_text(encoding="utf-8").splitlines()]


def read_level_lines(resolved_name: str, inline_levels: Dict[str, Any], levels_dir: Path) -> List[str]:
    """Read grid lines either from inline map or file."""
    inline = read_level_lines_inline(resolved_name, inline_levels)
    if inline is not None and inline is not "":
        return inline
    return read_level_lines_file(resolved_name, levels_dir)


def load_level(
    name: str,
    inline_levels: Dict[str, Any],
    levels_dir: Path,
    legend: Dict[str, TileSpec],
    tile_size: int,
) -> Level:
    """Load a level by name from inline config or disk."""
    resolved = resolve_level_name(name, inline_levels, levels_dir)
    grid_lines = read_level_lines(resolved, inline_levels, levels_dir)
    if not grid_lines:
        raise ValueError(f"Level '{resolved}' is empty.")
    return build_level_from_grid(resolved, grid_lines, legend, tile_size)

