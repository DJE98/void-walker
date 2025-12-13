from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pygame

from game_types import Color


@dataclass(frozen=True)
class TileSpec:
    char: str
    shape: str  # none|rect|circle|triangle
    color: Optional[Color]  # None if shape == none
    solid: bool
    on_collision: Dict[str, Any]


@dataclass
class TriggerTile:
    rect: pygame.Rect
    spec: TileSpec


@dataclass
class Level:
    name: str
    grid: List[str]
    width_tiles: int
    height_tiles: int
    solids: List[pygame.Rect]
    triggers: List[TriggerTile]
    spawn_px: pygame.Vector2


@dataclass
class PlayerConfig:
    color: Color
    speed: float
    jump_strength: float
    gravity: Tuple[float, float]
    max_fall: float
