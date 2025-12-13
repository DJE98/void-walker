from __future__ import annotations

from typing import Dict, Iterable, Tuple

import pygame

from camera import world_to_screen
from models import Level, TileSpec
from player import Player
from game_types import Color


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
    left, top, right, bottom = visible_tile_bounds(camera, window_w, window_h, tile_size)
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
    ascii_text_mode: bool,
    tile_font: pygame.font.Font,
) -> None:
    """Draw a single tile based on its TileSpec."""
    if ascii_text_mode:
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

    if spec.shape == "rect":
        pygame.draw.rect(surf, spec.color, r)
        return

    if spec.shape == "circle":
        radius = int(min(r.w, r.h) * 0.33)
        pygame.draw.circle(surf, spec.color, r.center, radius)
        return

    if spec.shape == "triangle":
        pad = int(tile_size * 0.15)
        p1 = (r.centerx, r.top + pad)
        p2 = (r.left + pad, r.bottom - pad)
        p3 = (r.right - pad, r.bottom - pad)
        pygame.draw.polygon(surf, spec.color, [p1, p2, p3])
        return

    pygame.draw.rect(surf, spec.color, r)


def draw_level_tiles(
    surf: pygame.Surface,
    level: Level,
    legend: Dict[str, TileSpec],
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
    ascii_text_mode: bool,
    tile_font: pygame.font.Font,
) -> None:
    """Draw all visible tiles for the current level."""
    ts = tile_size
    for x, y, ch in iter_visible_tiles(level, camera, window_w, window_h, tile_size):
        spec = legend.get(ch, legend["."])
        world_rect = pygame.Rect(x * ts, y * ts, ts, ts)
        draw_tile(surf, spec, world_rect, camera, tile_size, ascii_text_mode, tile_font)


def draw_player(surf: pygame.Surface, player: Player, camera: pygame.Vector2) -> None:
    """Draw the player."""
    pygame.draw.rect(
        surf,
        player.cfg.color,
        world_to_screen(player.rect, camera),
        border_radius=8,
    )


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
    ascii_text_mode: bool,
) -> None:
    """Draw HUD text."""
    mode_label = "ASCII" if ascii_text_mode else "Shapes"
    txt = (
        f"Level: {level_name} | Alive: {player_alive} | Mode: {mode_label} "
        "| T: toggle mode | R: restart | ESC: quit"
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
    ascii_text_mode: bool,
    tile_font: pygame.font.Font,
) -> None:
    """Render and present a full frame."""
    screen.fill(bg)
    draw_level_tiles(
        screen,
        level,
        legend,
        camera,
        window_w,
        window_h,
        tile_size,
        ascii_text_mode,
        tile_font,
    )
    draw_player(screen, player, camera)
    draw_grid(screen, show_grid, camera, window_w, window_h, tile_size, grid_color)
    draw_hud(screen, font, level.name, player.alive, ascii_text_mode)
    pygame.display.flip()
