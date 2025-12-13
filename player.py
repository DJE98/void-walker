from __future__ import annotations

import re
from typing import Any, Dict, List

import pygame

from models import PlayerConfig, UpgradesConfig
from utils import clamp_float

_OP_RE = re.compile(r"^(up|down)(\d+)?$")


class Player:
    """Simple platformer player controller with AABB collision + per-run scoring."""

    def __init__(
        self,
        cfg: PlayerConfig,
        spawn_px: pygame.Vector2,
        tile_size: int,
        upgradesCfg: UpgradesConfig,
    ) -> None:
        self.cfg = cfg
        self._tile_size = tile_size
        self.size = pygame.Vector2(tile_size * 0.70, tile_size * 0.90)
        self.pos = pygame.Vector2(spawn_px.x, spawn_px.y)
        self.vel = pygame.Vector2(0, 0)
        self.on_ground = False
        self.alive = True
        self.score: int = 0
        self.lives: int = 1  # default; optionally overridden by config later
        self.upgrades: dict[str, Any] = {}  # populated from config["upgrades"]
        self.upgrades_cfg = upgradesCfg
        self._max_x_tile_reached: int = -1
        self._max_y_tile_reached: int = -1

        self._rect = pygame.Rect(0, 0, int(self.size.x), int(self.size.y))

    @property
    def rect(self) -> pygame.Rect:
        """Current player AABB in world coordinates."""
        self._rect.x = int(self.pos.x)
        self._rect.y = int(self.pos.y)
        self._rect.w = int(self.size.x)
        self._rect.h = int(self.size.y)
        return self._rect

    # ---------
    # Run state
    # ---------

    def reset_run(self, spawn_px: pygame.Vector2) -> None:
        """Start a new run (score/exploration reset). Use this for 'R' restart and new level loads."""
        self.pos.update(spawn_px.x, spawn_px.y)
        self.vel.update(0, 0)
        self.on_ground = False
        self.alive = True
        self.score = 0

    def respawn(self, spawn_px: pygame.Vector2) -> None:
        """Respawn without necessarily resetting run state (keep score)."""
        self.pos.update(spawn_px.x, spawn_px.y)
        self.vel.update(0, 0)
        self.on_ground = False
        self.alive = True

    def apply_patch(self, patch: Dict[str, Any]) -> None:
        """Apply a config patch onto the player.

        Args:
            patch: Dict with keys like alive, speed, jump_strength, gravity, max_fall.
        """
        if "alive" in patch:
            self.alive = bool(patch["alive"])
        if "speed" in patch:
            self.cfg.speed = float(patch["speed"])
        if "jump_strength" in patch:
            self.cfg.jump_strength = float(patch["jump_strength"])
        if "gravity" in patch:
            self.cfg.gravity = self._parse_gravity_patch(patch["gravity"])
        if "max_fall" in patch:
            self.cfg.max_fall = float(patch["max_fall"])

    def _parse_gravity_patch(self, val: Any) -> tuple[float, float]:
        """Parse gravity patch supporting scalar, list/tuple, or dict."""
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            return float(val[0]), float(val[1])
        if isinstance(val, dict):
            gx = val.get("x", val.get("gx", self.cfg.gravity[0]))
            gy = val.get("y", val.get("gy", self.cfg.gravity[1]))
            return float(gx), float(gy)
        return (self.cfg.gravity[0], float(val))

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper, solids: List[pygame.Rect]) -> None:
        """Advance the player simulation by dt.

        Args:
            dt: Delta time (seconds).
            keys: Current keyboard state.
            solids: Solid tile rects in world coordinates.
        """
        if not self.alive:
            return

        self._update_horizontal_velocity(keys)
        self._try_jump(keys)
        self._apply_gravity(dt)

        self._move_and_resolve_x(dt, solids)
        self._move_and_resolve_y(dt, solids)

    def _update_horizontal_velocity(self, keys: pygame.key.ScancodeWrapper) -> None:
        """Update horizontal velocity from input while keeping gravity influence."""
        move_dir = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_dir -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_dir += 1.0
        if move_dir != 0.0:
            self.vel.x = move_dir * self.cfg.speed
        elif self.cfg.gravity[0] == 0.0:
            self.vel.x = 0.0

    def _try_jump(self, keys: pygame.key.ScancodeWrapper) -> None:
        jump = keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]
        if jump and self.on_ground:
            # Use player's current upgrade level to index global bonus table.
            level = int(self.cfg.upgrades.get("high_jump", 0))
            level_score = self.upgrades_cfg.high_jump.level
            level = max(0, min(level, len(level_score) - 1))
            print(f"jump level {level} / {level_score[level]}")
            effective_jump_strength = float(level_score[level])
            self.vel.y = -effective_jump_strength
            self.on_ground = False

    def _apply_gravity(self, dt: float) -> None:
        """Apply gravity on both axes and clamp terminal velocity on Y."""
        gx, gy = self.cfg.gravity
        self.vel.x += gx * dt
        self.vel.y += gy * dt
        self.vel.y = clamp_float(self.vel.y, -self.cfg.max_fall, self.cfg.max_fall)

    def _move_and_resolve_x(self, dt: float, solids: List[pygame.Rect]) -> None:
        self.pos.x += self.vel.x * dt
        r = self.rect
        for s in solids:
            if r.colliderect(s):
                if self.vel.x > 0:
                    r.right = s.left
                elif self.vel.x < 0:
                    r.left = s.right
                self.pos.x = float(r.x)

    def _move_and_resolve_y(self, dt: float, solids: List[pygame.Rect]) -> None:
        self.pos.y += self.vel.y * dt
        r = self.rect

        self.on_ground = False
        for s in solids:
            if r.colliderect(s):
                if self.vel.y > 0:
                    r.bottom = s.top
                    self.on_ground = True
                elif self.vel.y < 0:
                    r.top = s.bottom
                self.pos.y = float(r.y)
                self.vel.y = 0.0

    def update_exploration_score(
        self, tile_size: int = 48, enabled: bool = True
    ) -> None:
        if not enabled or not self.alive:
            return

        x_tile = int(self.rect.centerx // tile_size)
        y_tile = int(self.rect.centery // tile_size)

        # award +1 for each new max tile reached in either direction
        if x_tile > self._max_x_tile_reached:
            self.score += (
                (x_tile - self._max_x_tile_reached)
                if self._max_x_tile_reached >= 0
                else 1
            )
            self._max_x_tile_reached = x_tile

        if y_tile > self._max_y_tile_reached:
            self.score += (
                (y_tile - self._max_y_tile_reached)
                if self._max_y_tile_reached >= 0
                else 1
            )
            self._max_y_tile_reached = y_tile


def parse_numeric_op(value: Any) -> int | None:
    """
    Returns a delta for "up", "down", "up100", "down25".
    None means "not an op".
    """
    if not isinstance(value, str):
        return None

    value = value.strip().lower()
    if value in ("up", "down"):
        return 1 if value == "up" else -1

    m = _OP_RE.match(value)
    if not m:
        return None
    direction, number = m.group(1), m.group(2)
    magnitude = int(number) if number is not None else 1
    return magnitude if direction == "up" else -magnitude
