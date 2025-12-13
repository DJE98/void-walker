from __future__ import annotations

from typing import Dict, Iterable, Tuple

import pygame

from camera import world_to_screen
from game_types import Color
from models import Level, TileSpec
from player import Player


def visible_tile_bounds(
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
) -> Tuple[int, int, int, int]:
    """Compute visible tile bounds (left, top, right, bottom)."""
    ts = tile_size
    left = int(camera.x // ts)
    top = int(camera.y // ts)
    right = int((camera.x + window_w) // ts) + 1
    bottom = int((camera.y + window_h) // ts) + 1
    return left, top, right, bottom


def iter_visible_tiles(
    level: Level,
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
) -> Iterable[Tuple[int, int, str]]:
    """Yield (x, y, char) for tiles within the visible viewport."""
    left, top, right, bottom = visible_tile_bounds(
        camera, window_w, window_h, tile_size
    )
    for y in range(top, min(bottom, level.height_tiles)):
        row = level.grid[y]
        for x in range(left, min(right, level.width_tiles)):
            yield x, y, row[x]


def draw_tile(
    surf: pygame.Surface,
    spec: TileSpec,
    world_rect: pygame.Rect,
    camera: pygame.Vector2,
    tile_size: int,
    render_mode: str,
    tile_font: pygame.font.Font,
) -> None:
    """Draw a single tile based on its TileSpec."""
    ascii_mode = render_mode == "ascii"
    gradient_mode = render_mode == "gradient"

    if ascii_mode:
        if spec.shape == "none" and spec.char == ".":
            return

        screen_rect = world_to_screen(world_rect, camera)
        color = spec.color if spec.color is not None else (220, 220, 235)
        glyph = spec.char if spec.char else "?"
        text = tile_font.render(glyph, True, color)
        surf.blit(text, text.get_rect(center=screen_rect.center))
        return

    if spec.shape == "none" or spec.color is None:
        return

    r = world_to_screen(world_rect, camera)

    if gradient_mode:
        _draw_gradient_shape(surf, spec, r, tile_size)
        return

    _draw_flat_shape(surf, spec, r, tile_size)


def _draw_shape_with_color(
    surf: pygame.Surface, spec: TileSpec, r: pygame.Rect, tile_size: int, color: Color
) -> None:
    """Draw a tile using the provided color."""
    if spec.shape == "rect":
        pygame.draw.rect(surf, color, r)
        return

    if spec.shape == "circle":
        radius = int(min(r.w, r.h) * 0.33)
        pygame.draw.circle(surf, color, r.center, radius)
        return

    if spec.shape == "triangle":
        pad = int(tile_size * 0.15)
        p1 = (r.centerx, r.top + pad)
        p2 = (r.left + pad, r.bottom - pad)
        p3 = (r.right - pad, r.bottom - pad)
        pygame.draw.polygon(surf, color, [p1, p2, p3])
        return

    pygame.draw.rect(surf, color, r)


def _draw_flat_shape(surf: pygame.Surface, spec: TileSpec, r: pygame.Rect, tile_size: int) -> None:
    """Draw a tile using flat colors (non-gradient)."""
    if spec.color is None:
        return
    _draw_shape_with_color(surf, spec, r, tile_size, spec.color)


def _vertical_gradient_surface(size: Tuple[int, int], top: Color, bottom: Color) -> pygame.Surface:
    """Create a vertical gradient surface from top to bottom."""
    w, h = size
    grad = pygame.Surface((w, h), pygame.SRCALPHA)

    def lerp(a: int, b: int, t: float) -> int:
        return int(a + (b - a) * t)

    for y in range(h):
        t = y / max(1, h - 1)
        color = (
            lerp(top[0], bottom[0], t),
            lerp(top[1], bottom[1], t),
            lerp(top[2], bottom[2], t),
        )
        grad.fill(color, pygame.Rect(0, y, w, 1))
    return grad


def _draw_gradient_shape(surf: pygame.Surface, spec: TileSpec, r: pygame.Rect, tile_size: int) -> None:
    """Draw a tile using a smooth vertical gradient derived from its base color."""
    base = spec.color
    if base is None:
        return

    def clamp(v: int) -> int:
        return max(0, min(255, v))

    top = (clamp(int(base[0] * 1.05)), clamp(int(base[1] * 1.05)), clamp(int(base[2] * 1.05)))
    bottom = (clamp(int(base[0] * 0.55)), clamp(int(base[1] * 0.55)), clamp(int(base[2] * 0.55)))

    grad = _vertical_gradient_surface((r.w, r.h), top, bottom)

    if spec.shape == "rect":
        surf.blit(grad, r)
        return

    mask = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    _draw_shape_with_color(mask, spec, pygame.Rect(0, 0, r.w, r.h), tile_size, (255, 255, 255))
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, r.topleft)


def _draw_gradient_rect(
    surf: pygame.Surface, rect: pygame.Rect, color: Color, border_radius: int = 0
) -> None:
    """Draw a rounded rect with a smooth vertical gradient derived from base color."""
    def clamp(v: int) -> int:
        return max(0, min(255, v))

    top = (clamp(int(color[0] * 1.05)), clamp(int(color[1] * 1.05)), clamp(int(color[2] * 1.05)))
    bottom = (clamp(int(color[0] * 0.55)), clamp(int(color[1] * 0.55)), clamp(int(color[2] * 0.55)))

    grad = _vertical_gradient_surface((rect.w, rect.h), top, bottom)
    mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255), pygame.Rect(0, 0, rect.w, rect.h), border_radius=border_radius)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, rect.topleft)


def draw_level_tiles(
    surf: pygame.Surface,
    level: Level,
    legend: Dict[str, TileSpec],
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
    render_mode: str,
    tile_font: pygame.font.Font,
) -> None:
    """Draw all visible tiles for the current level."""
    ts = tile_size
    for x, y, ch in iter_visible_tiles(level, camera, window_w, window_h, tile_size):
        spec = legend.get(ch, legend["."])
        world_rect = pygame.Rect(x * ts, y * ts, ts, ts)
        draw_tile(surf, spec, world_rect, camera, tile_size, render_mode, tile_font)


def draw_player(
    surf: pygame.Surface, player: Player, camera: pygame.Vector2, render_mode: str
) -> None:
    """Draw the player."""
    rect = world_to_screen(player.rect, camera)
    if render_mode == "gradient":
        _draw_gradient_rect(surf, rect, player.cfg.color, border_radius=8)
    else:
        pygame.draw.rect(surf, player.cfg.color, rect, border_radius=8)


def draw_grid(
    surf: pygame.Surface,
    show_grid: bool,
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
    grid_color: Color,
) -> None:
    """Draw the debug grid overlay if enabled."""
    if not show_grid:
        return

    ts = tile_size
    start_x = int(camera.x // ts) * ts
    start_y = int(camera.y // ts) * ts
    end_x = int((camera.x + window_w) // ts + 1) * ts
    end_y = int((camera.y + window_h) // ts + 1) * ts

    cam_x = int(camera.x)
    cam_y = int(camera.y)

    for x in range(start_x, end_x + 1, ts):
        sx = x - cam_x
        pygame.draw.line(surf, grid_color, (sx, 0), (sx, window_h), 1)

    for y in range(start_y, end_y + 1, ts):
        sy = y - cam_y
        pygame.draw.line(surf, grid_color, (0, sy), (window_w, sy), 1)


def draw_hud(
    surf: pygame.Surface,
    font: pygame.font.Font,
    level_name: str,
    player_alive: bool,
    player_score: int,
    render_mode: str,
    color_mode: str,
) -> None:
    """Draw HUD text."""
    if render_mode == "ascii":
        mode_label = "ASCII"
    elif render_mode == "gradient":
        mode_label = "Gradient"
    else:
        mode_label = "Flat"

    color_label = "Gray" if color_mode == "gray" else "Multicolor"
    txt = (
        f"Level: {level_name} | Score: {player_score} | Alive: {player_alive} | Mode: {mode_label} | Color: {color_label} "
        "| T: ASCII/Flat/Gradient | C: Multicolor/Gray | R: restart | ESC: quit"
    )
    surf.blit(font.render(txt, True, (220, 220, 235)), (12, 10))
    if not player_alive:
        surf.blit(font.render("You died! Press R.", True, (255, 120, 120)), (12, 40))


def render_frame(
    screen: pygame.Surface,
    bg: Color,
    level: Level,
    legend: Dict[str, TileSpec],
    player: Player,
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
    show_grid: bool,
    grid_color: Color,
    font: pygame.font.Font,
    render_mode: str,
    tile_font: pygame.font.Font,
    color_mode: str,
) -> None:
    """Render and present a full frame."""
    mode = render_mode if render_mode in ("ascii", "flat", "gradient") else "flat"
    screen.fill(bg)
    draw_level_tiles(
        screen,
        level,
        legend,
        camera,
        window_w,
        window_h,
        tile_size,
        mode,
        tile_font,
    )
    draw_player(screen, player, camera, mode)
    draw_grid(screen, show_grid, camera, window_w, window_h, tile_size, grid_color)
    draw_hud(screen, font, level.name, player.alive, player.score, mode, color_mode)
    pygame.display.flip()
