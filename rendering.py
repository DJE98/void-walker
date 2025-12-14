from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _draw_flat_shape(
    surf: pygame.Surface, spec: TileSpec, r: pygame.Rect, tile_size: int
) -> None:
    """Draw a tile using flat colors (non-gradient)."""
    if spec.color is None:
        return
    _draw_shape_with_color(surf, spec, r, tile_size, spec.color)


def _vertical_gradient_surface(
    size: Tuple[int, int], top: Color, bottom: Color
) -> pygame.Surface:
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


def _draw_gradient_shape(
    surf: pygame.Surface, spec: TileSpec, r: pygame.Rect, tile_size: int
) -> None:
    """Draw a tile using a smooth vertical gradient derived from its base color."""
    base = spec.color
    if base is None:
        return

    def clamp(v: int) -> int:
        return max(0, min(255, v))

    top = (
        clamp(int(base[0] * 1.05)),
        clamp(int(base[1] * 1.05)),
        clamp(int(base[2] * 1.05)),
    )
    bottom = (
        clamp(int(base[0] * 0.55)),
        clamp(int(base[1] * 0.55)),
        clamp(int(base[2] * 0.55)),
    )

    grad = _vertical_gradient_surface((r.w, r.h), top, bottom)

    if spec.shape == "rect":
        surf.blit(grad, r)
        return

    mask = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    _draw_shape_with_color(
        mask, spec, pygame.Rect(0, 0, r.w, r.h), tile_size, (255, 255, 255)
    )
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, r.topleft)


def _draw_gradient_rect(
    surf: pygame.Surface, rect: pygame.Rect, color: Color, border_radius: int = 0
) -> None:
    """Draw a rounded rect with a smooth vertical gradient derived from base color."""

    def clamp(v: int) -> int:
        return max(0, min(255, v))

    top = (
        clamp(int(color[0] * 1.05)),
        clamp(int(color[1] * 1.05)),
        clamp(int(color[2] * 1.05)),
    )
    bottom = (
        clamp(int(color[0] * 0.55)),
        clamp(int(color[1] * 0.55)),
        clamp(int(color[2] * 0.55)),
    )

    grad = _vertical_gradient_surface((rect.w, rect.h), top, bottom)
    mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(
        mask,
        (255, 255, 255),
        pygame.Rect(0, 0, rect.w, rect.h),
        border_radius=border_radius,
    )
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, rect.topleft)


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    """Simple word-wrap helper returning list of wrapped lines."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for word in words:
        candidate = word if not cur else f"{cur} {word}"
        if font.size(candidate)[0] <= max_width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _scale_image_to_fit(
    image: pygame.Surface, max_width: int, max_height: int
) -> pygame.Surface:
    """Return the image scaled to fit within max dimensions (keeps aspect ratio)."""
    width, height = image.get_size()
    if width <= max_width and height <= max_height:
        return image
    scale = min(max_width / max(1, width), max_height / max(1, height))
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return pygame.transform.smoothscale(image, new_size)


def draw_introduction_overlay(
    surf: pygame.Surface,
    introduction: Dict[str, Any],
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    window_w: int,
    window_h: int,
) -> Optional[pygame.Rect]:
    """Draw a modal introduction overlay; returns the continue button rect."""
    if not introduction:
        return None

    dim = pygame.Surface((window_w, window_h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 230))
    surf.blit(dim, (0, 0))

    panel_w = min(int(window_w * 0.82), 900)
    panel_h = min(int(window_h * 0.82), 520)
    panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
    panel_rect.center = (window_w // 2, window_h // 2)

    pygame.draw.rect(surf, (0, 0, 0), panel_rect)
    pygame.draw.rect(surf, (255, 255, 255), panel_rect, width=2)

    padding = 22
    cursor_y = panel_rect.y + padding
    text_width = panel_rect.w - padding * 2

    title = introduction.get("title")
    if isinstance(title, str):
        title_surface = title_font.render(title, True, (255, 255, 255))
        title_rect = title_surface.get_rect()
        title_rect.centerx = panel_rect.centerx
        title_rect.top = cursor_y
        surf.blit(title_surface, title_rect.topleft)
        cursor_y += title_surface.get_height() + 12

    desc = introduction.get("description")
    desc_lines: list[str] = _wrap_text(desc, body_font, text_width) if isinstance(desc, str) else []
    desc_line_gap = 4
    desc_height = 0
    if desc_lines:
        desc_height = len(desc_lines) * body_font.get_height() + desc_line_gap * (len(desc_lines) - 1)

    image = introduction.get("image")
    if isinstance(image, pygame.Surface):
        button_space = 70 + desc_height
        available_h = panel_rect.bottom - padding - cursor_y - button_space
        if available_h > 40:
            scaled = _scale_image_to_fit(image, text_width, available_h)
            image_rect = scaled.get_rect()
            image_rect.centerx = panel_rect.centerx
            image_rect.top = cursor_y
            surf.blit(scaled, image_rect.topleft)
            cursor_y += scaled.get_height() + 14

    if desc_lines:
        if isinstance(image, pygame.Surface):
            cursor_y += 6
        for line in desc_lines:
            line_surface = body_font.render(line, True, (255, 255, 255))
            line_rect = line_surface.get_rect()
            line_rect.centerx = panel_rect.centerx
            line_rect.top = cursor_y
            surf.blit(line_surface, line_rect.topleft)
            cursor_y += line_surface.get_height() + desc_line_gap
        cursor_y += 8

    button_text = introduction.get("button_text") or "Continue"
    btn_w = max(180, title_font.size(button_text)[0] + 36)
    btn_h = 46
    button_rect = pygame.Rect(0, 0, btn_w, btn_h)
    button_rect.centerx = panel_rect.centerx
    button_rect.bottom = panel_rect.bottom - padding

    pygame.draw.rect(surf, (0, 0, 0), button_rect)
    pygame.draw.rect(surf, (255, 255, 255), button_rect, width=2)
    btn_label = title_font.render(button_text, True, (255, 255, 255))
    surf.blit(btn_label, btn_label.get_rect(center=button_rect.center))

    return button_rect


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


def draw_tile_labels(
    surf: pygame.Surface,
    level: Level,
    legend: Dict[str, TileSpec],
    camera: pygame.Vector2,
    window_w: int,
    window_h: int,
    tile_size: int,
    label_font: pygame.font.Font,
) -> None:
    """Draw title/description overlays above tiles when provided by the legend."""
    ts = tile_size
    padding = 6
    line_gap = 2
    default_spec = legend.get(
        ".",
        TileSpec(
            char=".",
            shape="none",
            color=None,
            solid=False,
            on_collision={},
            title=None,
            description=None,
        ),
    )

    for x, y, ch in iter_visible_tiles(level, camera, window_w, window_h, tile_size):
        spec = legend.get(ch, default_spec)
        text_surfaces = _build_label_surfaces(spec, label_font)
        if not text_surfaces:
            continue

        world_rect = pygame.Rect(x * ts, y * ts, ts, ts)
        screen_rect = world_to_screen(world_rect, camera)
        box_rect = _label_box_rect(
            screen_rect, text_surfaces, window_w, window_h, padding, line_gap
        )

        _blit_label_box(surf, text_surfaces, box_rect, padding, line_gap)


def _legend_label_lines(spec: TileSpec) -> list[str]:
    """Return cleaned title/description lines for a legend entry."""
    lines: list[str] = []
    for raw in (getattr(spec, "title", None), getattr(spec, "description", None)):
        if isinstance(raw, str):
            txt = raw.strip()
            if txt:
                lines.append(txt)
    return lines


def _build_label_surfaces(
    spec: TileSpec, label_font: pygame.font.Font
) -> list[pygame.Surface]:
    """Render label lines into surfaces; returns empty list when no label exists."""
    lines = _legend_label_lines(spec)
    if not lines:
        return []
    text_color = (255, 255, 255)
    return [label_font.render(line, True, text_color) for line in lines]


def _label_box_rect(
    screen_rect: pygame.Rect,
    text_surfaces: list[pygame.Surface],
    window_w: int,
    window_h: int,
    padding: int,
    line_gap: int,
) -> pygame.Rect:
    """Compute a clamped label box rectangle above the tile's screen rect."""
    max_w = max(surface.get_width() for surface in text_surfaces)
    total_h = sum(surface.get_height() for surface in text_surfaces)
    total_h += line_gap * (len(text_surfaces) - 1)

    box_w = max_w + padding * 2
    box_h = total_h + padding * 2
    box_rect = pygame.Rect(0, 0, box_w, box_h)
    box_rect.centerx = screen_rect.centerx
    box_rect.bottom = screen_rect.top - 4

    # Clamp label to stay within the visible window.
    box_rect.x = max(4, min(box_rect.x, window_w - box_rect.w - 4))
    box_rect.y = max(4, min(box_rect.y, window_h - box_rect.h - 4))
    return box_rect


def _blit_label_box(
    surf: pygame.Surface,
    text_surfaces: list[pygame.Surface],
    box_rect: pygame.Rect,
    padding: int,
    line_gap: int,
) -> None:
    """Draw the translucent label background and its text lines."""
    overlay = pygame.Surface((box_rect.w, box_rect.h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 230))
    surf.blit(overlay, box_rect.topleft)
    pygame.draw.rect(surf, (255, 255, 255), box_rect, width=1)

    cursor_y = box_rect.y + padding
    for surface in text_surfaces:
        surf.blit(surface, (box_rect.x + padding, cursor_y))
        cursor_y += surface.get_height() + line_gap


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
    hud_font: pygame.font.Font,
    level_name: str,
    player_lives: int,
    player_score: int,
    render_mode: str,
    color_mode: str,
) -> None:
    """Draw HUD text."""
    # Match intro overlay style: monospace, high-contrast white on black.
    bar_height = hud_font.get_height() + 12
    bar = pygame.Surface((surf.get_width(), bar_height), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 230))
    surf.blit(bar, (0, 0))

    if render_mode == "ascii":
        mode_label = "ASCII"
    elif render_mode == "gradient":
        mode_label = "Gradient"
    else:
        mode_label = "Flat"

    color_label = "Gray" if color_mode == "gray" else "Multicolor"
    txt = (
            f"{level_name} | Score: {player_score} | Lives: {int(player_lives)} | Mode (T): {mode_label} | Color (C): {color_label} "
        "| R: restart | ESC: quit"
    )
    surf.blit(hud_font.render(txt, True, (255, 255, 255)), (12, 6))
    if player_lives <= 0:
        surf.blit(hud_font.render("You died! Press R.", True, (255, 120, 120)), (12, bar_height + 4))


class GameRenderer:
    """Renderer that centralizes fonts and shared styling for overlays/HUD."""

    def __init__(
        self,
        window_w: int,
        window_h: int,
        font: pygame.font.Font,
        label_font: pygame.font.Font,
        tile_font: pygame.font.Font,
    ) -> None:
        self.window_w = window_w
        self.window_h = window_h
        self.update_fonts(font, label_font, tile_font)

    def update_fonts(
        self,
        font: pygame.font.Font,
        label_font: pygame.font.Font,
        tile_font: pygame.font.Font,
    ) -> None:
        """Refresh stored fonts and derived monospace variants."""
        self.font = font
        self.label_font = label_font
        self.tile_font = tile_font
        self.hud_font = pygame.font.SysFont("monospace", font.get_height())
        self.label_overlay_font = pygame.font.SysFont("monospace", label_font.get_height())
        title_size = max(font.get_height(), int(font.get_height() * 1.4))
        body_size = max(label_font.get_height(), int(label_font.get_height() * 1.3))
        self.intro_title_font = pygame.font.SysFont("monospace", title_size)
        self.intro_body_font = pygame.font.SysFont("monospace", body_size)

    def render_frame(
        self,
        screen: pygame.Surface,
        bg: Color,
        level: Level,
        legend: Dict[str, TileSpec],
        player: Player,
        camera: pygame.Vector2,
        tile_size: int,
        show_grid: bool,
        grid_color: Color,
        render_mode: str,
        color_mode: str,
        introduction: Optional[Dict[str, Any]] = None,
    ) -> Optional[pygame.Rect]:
        """Render and present a full frame."""
        mode = render_mode if render_mode in ("ascii", "flat", "gradient") else "flat"
        screen.fill(bg)
        draw_level_tiles(
            screen,
            level,
            legend,
            camera,
            self.window_w,
            self.window_h,
            tile_size,
            mode,
            self.tile_font,
        )
        draw_player(screen, player, camera, mode)
        draw_grid(screen, show_grid, camera, self.window_w, self.window_h, tile_size, grid_color)
        draw_tile_labels(
            screen,
            level,
            legend,
            camera,
            self.window_w,
            self.window_h,
            tile_size,
            self.label_overlay_font,
        )
        draw_hud(
            screen,
            self.hud_font,
            level.name,
            player.cfg.upgrades["extra_live"],
            player.score,
            mode,
            color_mode,
        )
        button_rect = None
        if introduction:
            button_rect = draw_introduction_overlay(
                screen,
                introduction,
                self.intro_title_font,
                self.intro_body_font,
                self.window_w,
                self.window_h,
            )
        pygame.display.flip()
        return button_rect
