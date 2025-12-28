from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import pygame

from models import PlayerConfig, UpgradesConfig
from utils import clamp_float


logger = logging.getLogger(__name__)

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
        self.score: int = 0
        self._max_x_tile_reached: int = -1
        self._max_y_tile_reached: int = -1
        self._rect = pygame.Rect(0, 0, int(self.size.x), int(self.size.y))
        self.upgrades_cfg = upgradesCfg

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
        self.score = 0

    def respawn(self, spawn_px: pygame.Vector2) -> None:
        """Respawn without necessarily resetting run state (keep score)."""
        self.pos.update(spawn_px.x, spawn_px.y)
        self.vel.update(0, 0)
        self.on_ground = False

    def apply_patch(self, patch: Dict[str, Any], upgrades_cfg: dict[str, Any]) -> None:
        """
        New semantics:
        - numeric/bool values -> set (backwards compatible)
        - "up/down/up100/down25" -> add/subtract on numeric fields
        - "upgrade" -> increment upgrade level (clamped)
        """
        for key, value in patch.items():
            logger.debug("patch received %s -> %s", key, value)

            # Upgrade operations: {"high_jump": "upgrade"}
            if isinstance(value, str) and value.strip().lower() == "upgrade":
                self._upgrade_one_level(key, upgrades_cfg)
                continue

            # Upgrade operations: {"extra_live": "downgrade"}
            if isinstance(value, str) and value.strip().lower() == "downgrade":
                self._downgrade_one_level(key, upgrades_cfg)
                continue

            # Numeric ops: {"score": "up100"}, {"extra_live": "down"}
            delta = parse_numeric_op(value)
            if delta is not None:
                self._apply_numeric_delta(key, delta)
                continue

            # Fallback: old behavior (direct set)
            self._apply_direct_set(key, value)

    def _apply_numeric_delta(self, key: str, delta: int) -> None:
        if key == "score":
            self.score = max(0, self.score + delta)
            return
        if key == "gravity":
            self.gravity = delta
            return

        # allow future numeric fields to be delta-updated if they exist
        if hasattr(self, key):
            current = getattr(self, key)
            if isinstance(current, (int, float)):
                setattr(self, key, current + delta)

    def _apply_direct_set(self, key: str, value: Any) -> None:
        # Keep your previous patch keys:
        if key == "score":
            self.score = int(value)
        elif key == "gravity":
            self.cfg.gravity = self._parse_gravity_patch(value)
        elif key == "max_fall":
            self.cfg.max_fall = float(value)
        else:
            # keep old optional physics tuning via patches if you had it
            if hasattr(self, key):
                setattr(self, key, value)

    def _upgrade_one_level(
        self, upgrade_name: str, upgrades_cfg: dict[str, Any]
    ) -> None:
        if upgrade_name not in upgrades_cfg:
            logger.debug("upgrade name not in config: %s", upgrade_name)
            return
        max_level = int(upgrades_cfg[upgrade_name].get("max_level", 0))
        current = int(self.cfg.upgrades.get(upgrade_name, 0))
        self.cfg.upgrades[upgrade_name] = min(max_level, current + 1)
        logger.debug("upgrade %s to %s", upgrade_name, min(max_level, current + 1))

    def _downgrade_one_level(
        self, upgrade_name: str, upgrades_cfg: dict[str, Any]
    ) -> None:
        if upgrade_name not in upgrades_cfg:
            logger.debug("downgrade name not in config: %s", upgrade_name)
            return
        current = int(self.cfg.upgrades.get(upgrade_name, 0))
        self.cfg.upgrades[upgrade_name] = max(0, current - 1)
        logger.debug("downgrade %s to %s", upgrade_name, max(0, current - 1))
        # push back on hurt
        if upgrade_name == "extra_live":
            self.vel.x = self.vel.x * -1.0

    def _parse_gravity_patch(self, val: Any) -> tuple[float, float]:
        """Parse gravity patch supporting scalar, list/tuple, or dict."""
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            return float(val[0]), float(val[1])
        if isinstance(val, dict):
            gx = val.get("x", val.get("gx", self.cfg.gravity[0]))
            gy = val.get("y", val.get("gy", self.cfg.gravity[1]))
            return float(gx), float(gy)
        return (self.cfg.gravity[0], float(val))

    def update(
        self, dt: float, keys: pygame.key.ScancodeWrapper, solids: List[pygame.Rect]
    ) -> None:
        """Advance the player simulation by dt.

        Args:
            dt: Delta time (seconds).
            keys: Current keyboard state.
            solids: Solid tile rects in world coordinates.
        """
        if self.cfg.upgrades["extra_live"] <= 0:
            logger.info("player died with %s lives", self.cfg.upgrades["extra_live"])
            return

        self._update_horizontal_velocity(keys)
        self._try_jump(keys)
        dx, dy = self._apply_gravity(dt, keys)

        self._move_and_resolve_x(dx, solids)
        self._move_and_resolve_y(dy, solids)

    def _update_horizontal_velocity(self, keys: pygame.key.ScancodeWrapper) -> None:
        """Update horizontal velocity from input while keeping gravity influence."""
        move_dir = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_dir -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_dir += 1.0
        if move_dir != 0.0:
            level = int(self.cfg.upgrades.get("speed", 0))
            level_score = self.upgrades_cfg.high_jump.level
            level = max(0, min(level, len(level_score) - 1))
            # print(f"speed level {level} / {level_score[level]}")
            effective_speed = float(level_score[level])
            self.vel.x = move_dir * effective_speed

        elif self.cfg.gravity[0] == 0.0:
            self.vel.x = 0.0

    def _try_jump(self, keys: pygame.key.ScancodeWrapper) -> None:
        jump = keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]
        if jump and self.on_ground:
            # Use player's current upgrade level to index global bonus table.
            level = int(self.cfg.upgrades.get("high_jump", 0))
            level_score = self.upgrades_cfg.high_jump.level
            level = max(0, min(level, len(level_score) - 1))
            logger.debug("jump level %s / %s", level, level_score[level])
            effective_jump_strength = float(level_score[level])
            self.vel.y = -effective_jump_strength
            self.on_ground = False

    def _apply_gravity(self, dt: float, keys: pygame.key.ScancodeWrapper) -> tuple[float, float]:
        """Apply gravity and clamp terminal velocity.
        Gliding reduces gravity ONLY while moving along gravity direction (falling).
        Returns the displacement (dx, dy) computed with y(t)=v0*t - 0.5*g*t^2 style kinematics.
        """
        gravity_x, gravity_y = self.cfg.gravity

        # Cache velocities before acceleration for displacement calculation.
        initial_vx = self.vel.x
        initial_vy = self.vel.y

        # Determine if we're "falling" = moving in the same direction as gravity
        moving_with_gravity = (gravity_y != 0.0) and ((initial_vy * gravity_y) > 0.0)

        level = int(self.cfg.upgrades.get("gliding", 0))
        level_score = self.upgrades_cfg.gliding.gravity_reduction
        level = max(0, min(level, len(level_score) - 1)) 
        glide_percent = max(0, min(level_score[level], 100))# 0..100

        glide_held = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        glide_active = glide_held and glide_percent > 0 and moving_with_gravity
        if glide_active:
            # e.g. 30% => apply only 70% of gravity while falling
            gravity_y *= (1.0 - glide_percent / 100.0)

        # Use kinematic displacement: y(t) = v0*t + 0.5*a*t^2 (sign of g handled by gy).
        dx = initial_vx * dt + 0.5 * gravity_x * dt * dt
        dy = initial_vy * dt + 0.5 * gravity_y * dt * dt

        self.vel.x = initial_vx + gravity_x * dt
        self.vel.y = clamp_float(
            initial_vy + gravity_y * dt, -self.cfg.max_fall, self.cfg.max_fall
        )
        return dx, dy

    def _move_and_resolve_x(self, dx: float, solids: List[pygame.Rect]) -> None:
        self.pos.x += dx
        r = self.rect
        for s in solids:
            if r.colliderect(s):
                if self.vel.x > 0:
                    r.right = s.left
                elif self.vel.x < 0:
                    r.left = s.right
                self.pos.x = float(r.x)

    def _move_and_resolve_y(self, dy: float, solids: List[pygame.Rect]) -> None:
        self.pos.y += dy
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
        if not enabled or self.cfg.upgrades["extra_live"] <= 0:
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
