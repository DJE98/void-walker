from __future__ import annotations

from typing import Any, Dict, List

import pygame

from models import PlayerConfig
from utils import clamp_float


class Player:
    """Simple platformer player controller with AABB collision."""

    def __init__(self, cfg: PlayerConfig, spawn_px: pygame.Vector2, tile_size: int) -> None:
        self.cfg = cfg
        self.size = pygame.Vector2(tile_size * 0.70, tile_size * 0.90)
        self.pos = pygame.Vector2(spawn_px.x, spawn_px.y)
        self.vel = pygame.Vector2(0, 0)
        self.on_ground = False
        self.alive = True
        self._rect = pygame.Rect(0, 0, int(self.size.x), int(self.size.y))

    @property
    def rect(self) -> pygame.Rect:
        """Current player AABB in world coordinates."""
        self._rect.x = int(self.pos.x)
        self._rect.y = int(self.pos.y)
        self._rect.w = int(self.size.x)
        self._rect.h = int(self.size.y)
        return self._rect

    def respawn(self, spawn_px: pygame.Vector2) -> None:
        """Reset player state to a spawn point."""
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
            self.cfg.gravity = float(patch["gravity"])
        if "max_fall" in patch:
            self.cfg.max_fall = float(patch["max_fall"])

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
        """Update horizontal velocity from input."""
        move_dir = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_dir -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_dir += 1.0
        self.vel.x = move_dir * self.cfg.speed

    def _try_jump(self, keys: pygame.key.ScancodeWrapper) -> None:
        """Apply an instantaneous jump if pressed and grounded."""
        jump = keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]
        if jump and self.on_ground:
            self.vel.y = -self.cfg.jump_strength
            self.on_ground = False

    def _apply_gravity(self, dt: float) -> None:
        """Apply gravity and clamp terminal velocity."""
        self.vel.y += self.cfg.gravity * dt
        self.vel.y = clamp_float(self.vel.y, -99999.0, self.cfg.max_fall)

    def _move_and_resolve_x(self, dt: float, solids: List[pygame.Rect]) -> None:
        """Move on X axis and resolve collisions against solids."""
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
        """Move on Y axis and resolve collisions against solids."""
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

