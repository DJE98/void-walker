from __future__ import annotations

from typing import Tuple

import pygame

from models import Level
from utils import clamp_float


def world_size_px(level: Level, tile_size: int) -> Tuple[int, int]:
    """Return (world_width_px, world_height_px)."""
    return (level.width_tiles * tile_size, level.height_tiles * tile_size)


def camera_target(player_rect: pygame.Rect, window_w: int, window_h: int) -> Tuple[float, float]:
    """Return desired camera (x, y) target based on player center."""
    target_x = player_rect.centerx - window_w / 2
    target_y = player_rect.centery - window_h / 2
    return target_x, target_y


def update_camera(
    camera: pygame.Vector2,
    level: Level,
    player_rect: pygame.Rect,
    window_w: int,
    window_h: int,
    tile_size: int,
) -> None:
    """Update the camera position with clamping to world bounds."""
    world_w, world_h = world_size_px(level, tile_size)
    target_x, target_y = camera_target(player_rect, window_w, window_h)
    camera.x = clamp_float(target_x, 0.0, max(0.0, world_w - window_w))
    camera.y = clamp_float(target_y, 0.0, max(0.0, world_h - window_h))


def world_to_screen(rect: pygame.Rect, camera: pygame.Vector2) -> pygame.Rect:
    """Convert a world rect to a screen rect using the camera offset."""
    return pygame.Rect(rect.x - int(camera.x), rect.y - int(camera.y), rect.w, rect.h)

