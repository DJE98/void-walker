from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pygame

from game_types import Color
from utils import clamp_int


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


@dataclass(frozen=True)
class BitcrusherSettings:
    """Normalized mixer settings with an optional lo-fi profile."""

    enabled: bool
    bits: int
    sample_rate: int

    @classmethod
    def from_raw(cls, raw: Optional[Dict[str, Any]]) -> "BitcrusherSettings":
        if not isinstance(raw, dict):
            return cls(enabled=False, bits=16, sample_rate=44100)

        bits = clamp_int(int(raw.get("bits", raw.get("bit_depth", 8))), 4, 32)
        freq = clamp_int(int(raw.get("sample_rate", raw.get("sampleRate", 12000))), 4000, 192000)
        return cls(enabled=True, bits=bits, sample_rate=freq)

    @staticmethod
    def _mixer_sample_size(bits: int) -> int:
        """Return a pygame-supported signed mixer size (8, 16, or 32)."""
        if bits <= 8:
            return 8
        if bits <= 16:
            return 16
        return 32

    def mixer_kwargs(self) -> Dict[str, Any]:
        bits = self.bits if self.enabled else 16
        freq = self.sample_rate if self.enabled else 44100
        size = -abs(self._mixer_sample_size(bits))
        return {"frequency": int(freq), "size": size, "channels": 2}
