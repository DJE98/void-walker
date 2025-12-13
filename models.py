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
    upgrades: Dict[str, int]


@dataclass(frozen=True)
class HighJumpUpgradeConfig:
    max_level: int
    level: List[int]


@dataclass(frozen=True)
class SpeedUpgradeConfig:
    max_level: int
    level: List[int]


@dataclass(frozen=True)
class DoubleJumpUpgradeConfig:
    max_level: int
    jumps: List[int]


@dataclass(frozen=True)
class FireballUpgradeConfig:
    max_level: int


@dataclass(frozen=True)
class GlidingUpgradeConfig:
    max_level: int
    gravity_reduction: List[int]


@dataclass(frozen=True)
class ExtraLiveUpgradeConfig:
    max_level: int
    lives: List[int]


@dataclass(frozen=True)
class FallDamageUpgradeConfig:
    max_level: int
    threshold_tiles: List[int]


@dataclass(frozen=True)
class GravityTransformationUpgradeConfig:
    max_level: int
    angles: List[int]


@dataclass(frozen=True)
class UpgradesConfig:
    high_jump: HighJumpUpgradeConfig
    speed: SpeedUpgradeConfig
    double_jump: DoubleJumpUpgradeConfig
    fireball: FireballUpgradeConfig
    gliding: GlidingUpgradeConfig
    extra_live: ExtraLiveUpgradeConfig
    fall_damage: FallDamageUpgradeConfig
    gravity_transformation: GravityTransformationUpgradeConfig

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "UpgradesConfig":
        hj = raw.get("high_jump", {}) if isinstance(raw.get("high_jump"), dict) else {}
        sp = raw.get("speed", {}) if isinstance(raw.get("speed"), dict) else {}
        dj = (
            raw.get("double_jump", {})
            if isinstance(raw.get("double_jump"), dict)
            else {}
        )
        fb = raw.get("fireball", {}) if isinstance(raw.get("fireball"), dict) else {}
        gl = raw.get("gliding", {}) if isinstance(raw.get("gliding"), dict) else {}
        el = (
            raw.get("extra_live", {}) if isinstance(raw.get("extra_live"), dict) else {}
        )
        fd = (
            raw.get("fall_damage", {})
            if isinstance(raw.get("fall_damage"), dict)
            else {}
        )
        gt = (
            raw.get("gravity_transformation", {})
            if isinstance(raw.get("gravity_transformation"), dict)
            else {}
        )

        return UpgradesConfig(
            high_jump=HighJumpUpgradeConfig(
                max_level=int(hj.get("max_level", 10)),
                level=[
                    int(x)
                    for x in hj.get(
                        "level", [700, 500, 350, 250, 200, 150, 100, 50, 25, 20, 5]
                    )
                ],
            ),
            speed=SpeedUpgradeConfig(
                max_level=int(sp.get("max_level", 10)),
                level=[
                    int(x)
                    for x in sp.get(
                        "level", [0, 200, 150, 110, 80, 60, 50, 40, 30, 20, 10]
                    )
                ],
            ),
            double_jump=DoubleJumpUpgradeConfig(
                max_level=int(dj.get("max_level", 3)),
                jumps=[int(x) for x in dj.get("jumps", [0, 1, 2, 3])],
            ),
            fireball=FireballUpgradeConfig(
                max_level=int(fb.get("max_level", 1)),
            ),
            gliding=GlidingUpgradeConfig(
                max_level=int(gl.get("max_level", 3)),
                gravity_reduction=[
                    int(x) for x in gl.get("gravity_reduction", [0, 500, 850, 1200])
                ],
            ),
            extra_live=ExtraLiveUpgradeConfig(
                max_level=int(el.get("max_level", 2)),
                lives=[int(x) for x in el.get("lives", [1, 2, 3])],
            ),
            fall_damage=FallDamageUpgradeConfig(
                max_level=int(fd.get("max_level", 10)),
                threshold_tiles=[
                    int(x)
                    for x in fd.get(
                        "threshold_tiles", [5, 10, 15, 18, 21, 24, 26, 27, 28, 29, 30]
                    )
                ],
            ),
            gravity_transformation=GravityTransformationUpgradeConfig(
                max_level=int(gt.get("max_level", 4)),
                angles=[int(x) for x in gt.get("angles", [0, 90, 180, 270])],
            ),
        )

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
