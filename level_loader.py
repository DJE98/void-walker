from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def resolve_level_name(name: str, levels_dir: Path) -> str:
    """Resolve a level name against .map files in root or a level folder (case-insensitive)."""
    p_map = levels_dir / f"{name}.map"
    if p_map.exists():
        return name

    folder = levels_dir / name
    if folder.exists() and folder.is_dir():
        for candidate in [folder / f"{name}.map"]:
            if candidate.exists():
                return name

    if levels_dir.exists():
        for f in levels_dir.glob("*.map"):
            if f.stem.lower() == name.lower():
                return f.stem
        for entry in levels_dir.iterdir():
            if entry.is_dir() and entry.name.lower() == name.lower():
                # keep actual casing from disk
                return entry.name

    return name


def find_level_config_path(levels_dir: Path, level_name: str) -> Optional[Path]:
    """Return the path to a per-level .json config if it exists."""
    candidates = [
        levels_dir / level_name / f"{level_name}.json",
        levels_dir / level_name / "config.json",
        levels_dir / f"{level_name}.json",
    ]

    if levels_dir.exists():
        for entry in levels_dir.iterdir():
            if entry.is_dir() and entry.name.lower() == level_name.lower():
                candidates.append(entry / f"{entry.name}.json")
                candidates.append(entry / "config.json")
        for f in levels_dir.glob("*.json"):
            if f.stem.lower() == level_name.lower():
                candidates.append(f)

    for p in candidates:
        if p.exists():
            return p
    return None


def read_level_lines_file(resolved_name: str, levels_dir: Path) -> List[str]:
    """Read grid lines from a map file, preferring a level folder if present."""
    candidates = []
    folder = levels_dir / resolved_name
    if folder.exists() and folder.is_dir():
        candidates.extend(
            [
                folder / f"{resolved_name}.map",
            ]
            + list(folder.glob("*.map"))
        )
    candidates.append(levels_dir / f"{resolved_name}.map")

    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, Path):
            continue
        key = candidate.resolve() if candidate.exists() else candidate
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return [line.rstrip("\n") for line in candidate.read_text(encoding="utf-8").splitlines()]

    raise FileNotFoundError(
        f"Level '{resolved_name}' not found.\n"
        f"- Looked for {resolved_name}.map inside {folder}\n"
        f"- Looked for file: {levels_dir / f'{resolved_name}.map'}"
    )


def read_level_lines(resolved_name: str, levels_dir: Path) -> List[str]:
    """Read grid lines from a level file."""
    return read_level_lines_file(resolved_name, levels_dir)


def load_level(
    name: str,
    levels_dir: Path,
    legend: Dict[str, TileSpec],
    tile_size: int,
) -> Level:
    """Load a level by name from disk."""
    resolved = resolve_level_name(name, levels_dir)
    grid_lines = read_level_lines(resolved, levels_dir)
    if not grid_lines:
        raise ValueError(f"Level '{resolved}' is empty.")
    return build_level_from_grid(resolved, grid_lines, legend, tile_size)
