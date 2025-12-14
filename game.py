from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pygame

from camera import update_camera
from config_io import load_json_config
from config_parsing import parse_legend, parse_player_config, parse_upgrade_config
from level_loader import find_level_config_path, load_level, resolve_level_name
from models import Level, TriggerTile
from music_controller import MusicController
from player import Player
from rendering import GameRenderer
from scoreboard import ScoreboardFile, ScoreEntry, now_iso
from utils import apply_color_mode, as_color, deep_get, deep_merge
from game_types import Color


class Game:
    """Top-level game orchestration (loading, loop, update, render)."""

    def __init__(self, glob_cfg_path: Path) -> None:
        self.debug_consumption = True
        self.base_cfg = load_json_config(glob_cfg_path)   # NEVER changes during a run
        self.active_cfg = self.base_cfg                   # current merged level cfg
        self.levels_dir = Path(self.active_cfg.get("levels_dir", "levels"))
        self.current_level_name = str(self.active_cfg.get("currentLevel", "Level1"))
        self.pending_level_name: Optional[str] = None

        resolved, merged_cfg, level_cfg_override = self._merged_level_config(
            self.current_level_name
        )
        self.current_level_name = resolved
        self.current_level_override = level_cfg_override
        self._apply_active_config(merged_cfg, is_initial=True)
        self.upgrades_cfg: dict[str, Any] = (
            merged_cfg.get("upgrades", {})
            if isinstance(merged_cfg.get("upgrades"), dict)
            else {}
        )
        self.scoring_cfg: dict[str, Any] = (
            merged_cfg.get("scoring", {})
            if isinstance(merged_cfg.get("scoring"), dict)
            else {}
        )
        self.exploration_scoring_enabled: bool = bool(
            self.scoring_cfg.get("exploration_points", False)
        )
        self.scoreboard = ScoreboardFile(
            Path(merged_cfg.get("scoreboard_file", "scoreboard.txt"))
        )
        self._was_alive_last_frame: bool = True

        self._init_pygame()
        self._init_ui()
        self._prepare_introduction_overlay()
        self._init_music()
        self.renderer = GameRenderer(
            self.window_w, self.window_h, self.font, self.label_font, self.tile_font
        )

        self.level = self._build_level_from_active_cfg()
        self.player = self._create_player(self.level)

        self.camera = pygame.Vector2(0, 0)

    # ----------------------------
    # Initialization
    # ----------------------------

    def _init_pygame(self) -> None:
        """Initialize pygame and create window + clock."""
        pygame.init()
        self._apply_display_mode()
        self.clock = pygame.time.Clock()

    def _apply_display_mode(self) -> None:
        """Create or recreate the display surface with the current mode."""
        flags = pygame.FULLSCREEN if getattr(self, "fullscreen", False) else 0
        self.screen = pygame.display.set_mode((self.window_w, self.window_h), flags)
        # Capture the actual size in case the platform adjusted it.
        self.window_w, self.window_h = self.screen.get_size()
        if hasattr(self, "renderer"):
            self.renderer.update_window_size(self.window_w, self.window_h)
        pygame.display.set_caption(self.title)

    def _update_tile_font(self) -> None:
        """Create/update the font used for ASCII tile rendering."""
        size = max(12, int(self.tile_size * 0.7))
        self.tile_font = pygame.font.SysFont("monospace", size)
        if hasattr(self, "renderer"):
            self.renderer.update_fonts(self.font, self.label_font, self.tile_font)

    def _init_ui(self) -> None:
        """Initialize UI resources."""
        self.font = pygame.font.Font(None, 28)
        self.label_font = pygame.font.Font(None, 22)
        self._update_tile_font()

    def _merged_level_config(
        self, name: str
    ) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Return (resolved_name, merged_cfg, override_cfg) with level config overlaid on base config."""
        resolved = resolve_level_name(name, self.levels_dir)
        level_cfg_override: Dict[str, Any] = {}
        level_cfg_path = find_level_config_path(self.levels_dir, resolved)
        if level_cfg_path:
            level_cfg_override = load_json_config(level_cfg_path)
        merged_cfg = deep_merge(self.active_cfg, level_cfg_override)
        return resolved, merged_cfg, level_cfg_override

    def _apply_active_config(
        self, cfg: Dict[str, Any], is_initial: bool = False
    ) -> None:
        """Apply merged config for the current level."""
        self.active_cfg = cfg
        self.tile_size = int(cfg.get("tile_size", 48))
        self.color_mode = self._parse_color_mode(cfg)
        self._apply_render_mode(cfg)

        if is_initial:
            self.window_w = int(deep_get(cfg, "window.width", 1000))
            self.window_h = int(deep_get(cfg, "window.height", 600))
            self.windowed_size = (self.window_w, self.window_h)
            self.title = str(deep_get(cfg, "window.title", "ASCII Side-Scroller"))
        fullscreen_cfg = bool(deep_get(cfg, "window.fullscreen", False))
        if is_initial or not hasattr(self, "fullscreen"):
            self.fullscreen = fullscreen_cfg

        self.bg = as_color(deep_get(cfg, "window.bg", [18, 20, 28]), (18, 20, 28))
        self.grid_color = as_color(
            deep_get(cfg, "window.grid", [126, 126, 126]), (126, 126, 126)
        )
        self.show_grid = bool(deep_get(cfg, "render.show_grid", False))
        self._refresh_colors()
        if hasattr(self, "tile_font"):
            self._update_tile_font()

    def _prepare_introduction_overlay(self) -> None:
        """Load introduction overlay content for the active level."""
        intro_raw = self.active_cfg.get("introduction", {})
        self.introduction: Optional[Dict[str, Any]] = None
        self.intro_visible: bool = False
        self.intro_button_rect: Optional[pygame.Rect] = None

        if not isinstance(intro_raw, dict):
            return

        def _clean(value: Any) -> Optional[str]:
            if isinstance(value, str):
                txt = value.strip()
                return txt if txt else None
            return None

        title = _clean(intro_raw.get("title"))
        description = _clean(intro_raw.get("description") or intro_raw.get("text"))
        image_path_raw = _clean(intro_raw.get("image"))
        button_text = _clean(intro_raw.get("button_text")) or "Continue"
        next_level = _clean(intro_raw.get("next_level"))

        if not any([title, description, image_path_raw]):
            return

        image_surface = None
        if image_path_raw:
            image_surface = self._load_intro_image(image_path_raw)

        self.introduction = {
            "title": title,
            "description": description,
            "image": image_surface,
            "button_text": button_text,
            "next_level": next_level,
        }
        self.intro_visible = True

    def _load_intro_image(self, path_str: str) -> Optional[pygame.Surface]:
        """Load an introduction image safely."""
        candidates = []
        raw_path = Path(path_str)
        candidates.append(raw_path)
        if not raw_path.is_absolute():
            candidates.append(self.levels_dir / raw_path)
            candidates.append(self.levels_dir / self.current_level_name / raw_path)

        for img_path in candidates:
            try:
                if img_path.exists():
                    return pygame.image.load(img_path.as_posix()).convert_alpha()
            except pygame.error:
                continue
        return None

    def _apply_render_mode(self, cfg: Dict[str, Any]) -> None:
        """Apply render mode string with backward compatibility for old flags."""
        mode_raw = deep_get(cfg, "render.mode", None)
        ascii_flag = bool(deep_get(cfg, "render.ascii_text_mode", False))
        gradient_flag = bool(deep_get(cfg, "render.gradient_mode", False))

        if isinstance(mode_raw, str):
            mode = mode_raw.lower()
        elif ascii_flag:
            mode = "ascii"
        elif gradient_flag:
            mode = "gradient"
        else:
            mode = "flat"

        if mode not in ("ascii", "flat", "gradient"):
            mode = "flat"

        self.render_mode = mode

    def _parse_color_mode(self, cfg: Dict[str, Any]) -> str:
        """Return the configured color mode (multicolor|gray)."""
        color_mode = deep_get(cfg, "render.color", "multicolor")
        if isinstance(color_mode, str):
            color_mode = color_mode.lower()
        else:
            color_mode = "multicolor"
        if color_mode not in ("multicolor", "gray"):
            color_mode = "multicolor"
        return color_mode

    def _apply_color_mode(self, color: Color) -> Color:
        """Transform a color according to the current color mode."""
        return apply_color_mode(color, self.color_mode)

    def _refresh_colors(self) -> None:
        """Recompute colorized resources for the current color mode."""
        self.legend = parse_legend(self.active_cfg, self.color_mode)
        base_bg = as_color(
            deep_get(self.active_cfg, "window.bg", [18, 20, 28]), (18, 20, 28)
        )
        self.bg = self._apply_color_mode(base_bg)
        base_grid = as_color(
            deep_get(self.active_cfg, "window.grid", [126, 126, 126]), (126, 126, 126)
        )
        self.grid_color = self._apply_color_mode(base_grid)

        if hasattr(self, "player"):
            base_player_color = as_color(
                deep_get(self.active_cfg, "player.color", [235, 240, 255]),
                (235, 240, 255),
            )
            self.player.cfg.color = self._apply_color_mode(base_player_color)

    def _init_music(self) -> None:
        """Initialize music controller and start playback."""
        music_dir = Path(deep_get(self.active_cfg, "music.dir", "music"))
        fade_ms = int(deep_get(self.active_cfg, "music.fade_ms", 800))
        bitcrusher_cfg = deep_get(self.active_cfg, "music.bitcrusher", None)
        self.music_controller = MusicController(music_dir, fade_ms, bitcrusher_cfg)
        self._update_music_playlist()

    def _select_playlist(self) -> List[str]:
        """Pick the playlist for the active level (level overrides global)."""
        level_playlist = deep_get(self.current_level_override, "music.playlist", None)
        if isinstance(level_playlist, list) and len(level_playlist) > 0:
            return [str(track) for track in level_playlist if isinstance(track, str)]

        global_playlist = deep_get(self.active_cfg, "music.playlist", [])
        if isinstance(global_playlist, list):
            return [str(track) for track in global_playlist if isinstance(track, str)]
        return []

    def _update_music_playlist(self) -> None:
        """Update music playback to match the active level playlist."""
        if hasattr(self, "music_controller"):
            self.music_controller.set_playlist(self._select_playlist())

    def _update_music_settings(self) -> None:
        """Apply music-related settings that depend on the active config."""
        if hasattr(self, "music_controller"):
            bitcrusher_cfg = deep_get(self.active_cfg, "music.bitcrusher", None)
            self.music_controller.set_bitcrusher(bitcrusher_cfg)

    def _update_music(self) -> None:
        """Tick music controller (advance songs when needed)."""
        if hasattr(self, "music_controller"):
            self.music_controller.update()

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
        pconf = parse_player_config(
            self.active_cfg.get("player", {}), color_mode=self.color_mode
        )
        uconf = parse_upgrade_config(self.active_cfg.get("upgrades", {}))
        return Player(pconf, level.spawn_px, self.tile_size, uconf)

    # ----------------------------
    # Level management
    # ----------------------------

    def _load_level(self, name: str) -> Level:
        """Load a level from disk applying any level-specific config."""
        resolved, merged_cfg, level_cfg_override = self._merged_level_config(name)
        self.current_level_name = resolved
        self.current_level_override = level_cfg_override
        self._apply_active_config(merged_cfg)
        self._prepare_introduction_overlay()
        # refresh per-level upgrade/scoring definitions (static)
        self.upgrades_cfg = merged_cfg.get("upgrades", {}) if isinstance(merged_cfg.get("upgrades"), dict) else {}
        self.scoring_cfg = merged_cfg.get("scoring", {}) if isinstance(merged_cfg.get("scoring"), dict) else {}
        self.exploration_scoring_enabled = bool(self.scoring_cfg.get("exploration_points", False))
        return self._build_level_from_active_cfg()

    def _switch_to_level(self, name: str) -> None:
        """Switch to a level and respawn the player, keeping run-state (upgrades/score)."""
        # --- capture run-state BEFORE player recreation ---
        carried_upgrades = dict(self.player.cfg.upgrades)
        carried_score = int(getattr(self.player, "score", 0))

        # --- load new level ---
        self.level = self._load_level(name)
        self.player = self._create_player(self.level)

        # --- restore run-state onto the new player instance ---
        self.player.cfg.upgrades = carried_upgrades
        self.player.score = carried_score

        # music refresh
        self._update_music_settings()
        self._update_music_playlist()

        # debug
        if getattr(self, "debug_consumption", False):
            print(f"[run-debug] switched to {name} | score={self.player.score} | upgrades={self.player.cfg.upgrades}")


    # ----------------------------
    # Patching / triggers
    # ----------------------------

    def apply_patch(self, patch: Dict[str, Any]) -> None:
        """Apply a patch dict to the game and/or player."""
        if "player" in patch and isinstance(patch["player"], dict):
            self.player.apply_patch(patch["player"], upgrades_cfg=self.upgrades_cfg)
        if "currentLevel" in patch:
            self.pending_level_name = str(patch["currentLevel"])

    def _apply_trigger_if_colliding(
        self, trigger: TriggerTile, player_rect: pygame.Rect
    ) -> bool:
        """Apply trigger patch if the player collides with it.
        Returns True if the trigger was consumed and should be removed.
        """
        if not player_rect.colliderect(trigger.rect):
            return False

        tx, ty = self._tile_xy_from_world_rect(trigger.rect)
        current_char = self._get_level_char(tx, ty)
        legend_entry = self._legend_entry_for_char(current_char)

        # self._dbg(
        #    f"TRIGGER HIT at (tx={tx}, ty={ty}) "
        #    f"char='{current_char}' legend_keys={list(legend_entry.keys())}"
        # )

        # Apply the configured behavior (score/upgrades/etc.)
        self.apply_patch(trigger.spec.on_collision)

        # IMPORTANT: consumable info is in active_cfg legend, not in trigger.spec (usually)
        is_consumable = bool(legend_entry.get("consumable", False))
        as_consumable = str(legend_entry.get("consumable_as", "."))

        if not is_consumable:
            # self._dbg(
            #    f"not consumable: char='{current_char}' consumable={legend_entry.get('consumable')}"
            # )
            return False

        # For now: always consume into '.' (as requested)
        # self._dbg(f"CONSUME: char='{current_char}' -> '{as_consumable}'")
        self._set_level_char(tx, ty, as_consumable)

        return True

    def handle_triggers(self) -> None:
        """Check all triggers in the level and apply any collisions. Consumed triggers are removed."""
        pr = self.player.rect

        remaining: list[TriggerTile] = []
        for t in self.level.triggers:
            consumed = self._apply_trigger_if_colliding(t, pr)
            if not consumed:
                remaining.append(t)
            # else:
            #    self._dbg("trigger removed from active trigger list")

        self.level.triggers = remaining

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
        self.player.cfg.upgrades["extra_live"] = 1
        self._was_alive_last_frame = True
        self.player.respawn(self.level.spawn_px)

    def _is_player_below_death_line(self) -> bool:
        """Return True if the player has fallen far below the level."""
        death_y = self.level.height_tiles * self.tile_size + self.tile_size * 2
        return self.player.rect.top > death_y

    def _apply_fall_death(self) -> None:
        """Kill the player if they fell out of the world."""
        if (
            self.player.cfg.upgrades["extra_live"] > 0
            and self._is_player_below_death_line()
        ):
            self.player.cfg.upgrades["extra_live"] = 0

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        """Update one simulation step."""
        self.player.update(dt, keys, self.level.solids)
        self.player.update_exploration_score(
            self.tile_size, enabled=self.exploration_scoring_enabled
        )
        self.handle_triggers()
        self._apply_fall_death()

        if (
            self._was_alive_last_frame
            and not self.player.cfg.upgrades["extra_live"] > 0
        ):
            self.scoreboard.append(
                ScoreEntry(
                    timestamp=now_iso(), level=self.level.name, score=self.player.score
                )
            )
        self._was_alive_last_frame = self.player.cfg.upgrades["extra_live"] > 0

        self.switch_level_if_needed()
        self._update_music()
        update_camera(
            camera=self.camera,
            level=self.level,
            player_rect=self.player.rect,
            window_w=self.window_w,
            window_h=self.window_h,
            tile_size=self.tile_size,
        )

    def _set_level_tile_at_rect(self, tile_rect: pygame.Rect, new_char: str) -> None:
        """Change the in-memory level grid character at tile_rect to new_char."""
        tx = tile_rect.x // self.tile_size
        ty = tile_rect.y // self.tile_size

        if ty < 0 or ty >= len(self.level.grid):
            return

        row = self.level.grid[ty]
        if tx < 0 or tx >= len(row):
            return

        self._dbg(f"set_level_char at tx={tx}, ty={ty}")
        row_list = list(row)
        row_list[tx] = new_char
        self.level.grid[ty] = "".join(row_list)

    def _dbg(self, msg: str) -> None:
        # Toggle by setting self.debug_consumption = True somewhere (e.g. in __init__)
        if getattr(self, "debug_consumption", False):
            print(f"[consume-debug] {msg}")

    def _legend_entry_for_char(self, ch: str) -> Dict[str, Any]:
        legend = self.active_cfg.get("legend", {})
        if not isinstance(legend, dict):
            return {}
        entry = legend.get(ch, {})
        return entry if isinstance(entry, dict) else {}

    def _tile_xy_from_world_rect(self, world_rect: pygame.Rect) -> tuple[int, int]:
        tx = int(world_rect.x // self.tile_size)
        ty = int(world_rect.y // self.tile_size)
        return tx, ty

    def _get_level_char(self, tx: int, ty: int) -> str:
        if ty < 0 or ty >= len(self.level.grid):
            return "."
        row = self.level.grid[ty]
        if tx < 0 or tx >= len(row):
            return "."
        return row[tx]

    def _set_level_char(self, tx: int, ty: int, new_char: str) -> None:
        if ty < 0 or ty >= len(self.level.grid):
            # self._dbg(f"set_level_char ignored (out of bounds): tx={tx}, ty={ty}")
            return
        row = self.level.grid[ty]
        if tx < 0 or tx >= len(row):
            # self._dbg(
            #    f"set_level_char ignored (out of bounds): tx={tx}, ty={ty}, row_len={len(row)}"
            # )
            return

        old_char = row[tx]
        row_list = list(row)
        row_list[tx] = new_char
        self.level.grid[ty] = "".join(row_list)

        self._dbg(f"tile changed at (tx={tx}, ty={ty}): '{old_char}' -> '{new_char}'")

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
            self._toggle_render_mode()
        if key == pygame.K_c:
            self._toggle_color_mode()
        if key in (pygame.K_F11, pygame.K_f):
            self._toggle_fullscreen()
        return True

    def _toggle_render_mode(self) -> None:
        """Cycle render mode between ascii -> flat -> gradient."""
        order = ["ascii", "flat", "gradient"]
        try:
            idx = order.index(self.render_mode)
        except ValueError:
            idx = 0
        nxt = order[(idx + 1) % len(order)]
        self.render_mode = nxt

    def _toggle_color_mode(self) -> None:
        """Toggle render color mode between multicolor and gray."""
        self.color_mode = "gray" if self.color_mode == "multicolor" else "multicolor"
        self._refresh_colors()

    def _toggle_fullscreen(self) -> None:
        """Toggle between windowed and fullscreen display modes."""
        self.fullscreen = not getattr(self, "fullscreen", False)
        if self.fullscreen:
            # Remember the last windowed size so we can restore it.
            self.windowed_size = (self.window_w, self.window_h)
            info = pygame.display.Info()
            self.window_w = info.current_w
            self.window_h = info.current_h
        else:
            self.window_w, self.window_h = getattr(
                self, "windowed_size", (self.window_w, self.window_h)
            )
        self._apply_display_mode()

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
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._handle_mouse_click(e.pos)
        return True

    def _handle_mouse_click(self, pos: Tuple[int, int]) -> None:
        """Handle mouse input (used for intro overlay button)."""
        if self.intro_visible and self.intro_button_rect and self.intro_button_rect.collidepoint(pos):
            self._dismiss_introduction()

    def _dismiss_introduction(self) -> None:
        """Hide the introduction overlay and honor any intro-specific requests."""
        self.intro_visible = False
        self.intro_button_rect = None
        if self.introduction and self.introduction.get("next_level"):
            self.pending_level_name = str(self.introduction["next_level"])

    def run(self) -> None:
        """Run the main game loop."""
        running = True
        while running:
            dt = self._tick_dt()
            running = self._handle_events()

            intro_data = self.introduction if self.intro_visible else None
            if intro_data:
                # Pause simulation while the intro overlay is visible.
                self._update_music()
                self.intro_button_rect = self.renderer.render_frame(
                    screen=self.screen,
                    bg=self.bg,
                    level=self.level,
                    legend=self.legend,
                    player=self.player,
                    camera=self.camera,
                    tile_size=self.tile_size,
                    show_grid=self.show_grid,
                    grid_color=self.grid_color,
                    render_mode=self.render_mode,
                    color_mode=self.color_mode,
                    introduction=intro_data,
                )
                continue

            keys = pygame.key.get_pressed()
            self.update(dt, keys)

            self.intro_button_rect = self.renderer.render_frame(
                screen=self.screen,
                bg=self.bg,
                level=self.level,
                legend=self.legend,
                player=self.player,
                camera=self.camera,
                tile_size=self.tile_size,
                show_grid=self.show_grid,
                grid_color=self.grid_color,
                render_mode=self.render_mode,
                color_mode=self.color_mode,
            )

        pygame.quit()
