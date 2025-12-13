from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pygame

from camera import update_camera
from config_io import load_json_config
from config_parsing import parse_legend, parse_player_config
from level_loader import find_level_config_path, load_level, resolve_level_name
from models import Level, TriggerTile
from player import Player
from rendering import render_frame
from utils import as_color, deep_get, deep_merge


class Game:
    """Top-level game orchestration (loading, loop, update, render)."""

    def __init__(self, cfg_path: Path) -> None:
        self.cfg_path = cfg_path
        self.base_cfg = load_json_config(cfg_path)

        self.levels_dir = Path(self.base_cfg.get("levels_dir", "levels"))

        self.current_level_name = str(self.base_cfg.get("currentLevel", "Level1"))
        self.pending_level_name: Optional[str] = None
        self.active_cfg: Dict[str, Any] = {}

        resolved, merged_cfg = self._merged_level_config(self.current_level_name)
        self.current_level_name = resolved
        self._apply_active_config(merged_cfg, is_initial=True)

        self._init_pygame()
        self._init_ui()

        self.level = self._build_level_from_active_cfg()
        self.player = self._create_player(self.level)

        self.camera = pygame.Vector2(0, 0)

    # ----------------------------
    # Initialization
    # ----------------------------

    def _init_pygame(self) -> None:
        """Initialize pygame and create window + clock."""
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_w, self.window_h))
        pygame.display.set_caption(self.title)
        self.clock = pygame.time.Clock()

    def _update_tile_font(self) -> None:
        """Create/update the font used for ASCII tile rendering."""
        size = max(12, int(self.tile_size * 0.7))
        self.tile_font = pygame.font.SysFont("monospace", size)

    def _init_ui(self) -> None:
        """Initialize UI resources."""
        self.font = pygame.font.Font(None, 28)
        self._update_tile_font()

    def _merged_level_config(self, name: str) -> Tuple[str, Dict[str, Any]]:
        """Return (resolved_name, merged_cfg) with level config overlaid on base config."""
        resolved = resolve_level_name(name, self.levels_dir)
        level_cfg_override: Dict[str, Any] = {}
        cfg_path = find_level_config_path(self.levels_dir, resolved)
        if cfg_path:
            level_cfg_override = load_json_config(cfg_path)
        merged_cfg = deep_merge(self.base_cfg, level_cfg_override)
        return resolved, merged_cfg

    def _apply_active_config(self, cfg: Dict[str, Any], is_initial: bool = False) -> None:
        """Apply merged config for the current level."""
        self.active_cfg = cfg
        self.tile_size = int(cfg.get("tile_size", 48))
        self.legend = parse_legend(cfg)
        self.ascii_text_mode = bool(deep_get(cfg, "render.ascii_text_mode", False))

        if is_initial:
            self.window_w = int(deep_get(cfg, "window.width", 1000))
            self.window_h = int(deep_get(cfg, "window.height", 600))
            self.title = str(deep_get(cfg, "window.title", "ASCII Side-Scroller"))

        self.bg = as_color(deep_get(cfg, "window.bg", [18, 20, 28]), (18, 20, 28))
        self.grid_color = as_color(deep_get(cfg, "window.grid", [126, 126, 126]), (126, 126, 126))
        self.show_grid = bool(deep_get(cfg, "render.show_grid", False))
        if hasattr(self, "tile_font"):
            self._update_tile_font()

    def _build_level_from_active_cfg(self) -> Level:
        """Build a level using the currently applied config."""
        return load_level(
            name=self.current_level_name,
            levels_dir=self.levels_dir,
            legend=self.legend,
            tile_size=self.tile_size,
        )

    def _create_player(self, level: Level) -> Player:
        """Create a player using config and level spawn."""
        pconf = parse_player_config(self.active_cfg.get("player", {}))
        return Player(pconf, level.spawn_px, self.tile_size)

    # ----------------------------
    # Level management
    # ----------------------------

    def _load_level(self, name: str) -> Level:
        """Load a level from disk applying any level-specific config."""
        resolved, merged_cfg = self._merged_level_config(name)
        self.current_level_name = resolved
        self._apply_active_config(merged_cfg)
        return self._build_level_from_active_cfg()

    def _switch_to_level(self, name: str) -> None:
        """Switch to a level and respawn the player."""
        self.level = self._load_level(name)
        self.player = self._create_player(self.level)

    # ----------------------------
    # Patching / triggers
    # ----------------------------

    def apply_patch(self, patch: Dict[str, Any]) -> None:
        """Apply a patch dict to the game and/or player."""
        if "player" in patch and isinstance(patch["player"], dict):
            self.player.apply_patch(patch["player"])
        if "currentLevel" in patch:
            self.pending_level_name = str(patch["currentLevel"])

    def _apply_trigger_if_colliding(self, trigger: TriggerTile, player_rect: pygame.Rect) -> None:
        """Apply trigger patch if the player collides with it."""
        if player_rect.colliderect(trigger.rect):
            self.apply_patch(trigger.spec.on_collision)

    def handle_triggers(self) -> None:
        """Check all triggers in the level and apply any collisions."""
        pr = self.player.rect
        for t in self.level.triggers:
            self._apply_trigger_if_colliding(t, pr)

    def switch_level_if_needed(self) -> None:
        """Switch to a pending level, if requested."""
        if not self.pending_level_name:
            return
        nxt = self.pending_level_name
        self.pending_level_name = None
        self._switch_to_level(nxt)

    # ----------------------------
    # Simulation
    # ----------------------------

    def restart_level(self) -> None:
        """Respawn the player at the current level's spawn."""
        self.player.respawn(self.level.spawn_px)

    def _is_player_below_death_line(self) -> bool:
        """Return True if the player has fallen far below the level."""
        death_y = self.level.height_tiles * self.tile_size + self.tile_size * 2
        return self.player.rect.top > death_y

    def _apply_fall_death(self) -> None:
        """Kill the player if they fell out of the world."""
        if self.player.alive and self._is_player_below_death_line():
            self.player.alive = False

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        """Update one simulation step."""
        self.player.update(dt, keys, self.level.solids)
        self.handle_triggers()
        self._apply_fall_death()
        self.switch_level_if_needed()
        update_camera(
            camera=self.camera,
            level=self.level,
            player_rect=self.player.rect,
            window_w=self.window_w,
            window_h=self.window_h,
            tile_size=self.tile_size,
        )

    # ----------------------------
    # Events / loop
    # ----------------------------

    def _tick_dt(self) -> float:
        """Return delta time in seconds with a 60 FPS cap."""
        return self.clock.tick(60) / 1000.0

    def _handle_keydown(self, key: int) -> bool:
        """Handle KEYDOWN events.

        Returns:
            False if the game should exit, True otherwise.
        """
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_r:
            self.restart_level()
        if key == pygame.K_t:
            self.ascii_text_mode = not self.ascii_text_mode
        return True

    def _handle_events(self) -> bool:
        """Process pygame events.

        Returns:
            False if the game should exit, True otherwise.
        """
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if not self._handle_keydown(e.key):
                    return False
        return True

    def run(self) -> None:
        """Run the main game loop."""
        running = True
        while running:
            dt = self._tick_dt()
            running = self._handle_events()

            keys = pygame.key.get_pressed()
            self.update(dt, keys)

            render_frame(
                screen=self.screen,
                bg=self.bg,
                level=self.level,
                legend=self.legend,
                player=self.player,
                camera=self.camera,
                window_w=self.window_w,
                window_h=self.window_h,
                tile_size=self.tile_size,
                show_grid=self.show_grid,
                grid_color=self.grid_color,
                font=self.font,
                ascii_text_mode=self.ascii_text_mode,
                tile_font=self.tile_font,
            )

        pygame.quit()
