# Configuration 

## `config.json`

- **Top-level knobs**
  - `tile_size`: pixel size of a tile (affects render scale and hitboxes).
  - `debug`: `true/false` to run with verbose logging (toggle-able at runtime via config reloads).
  - `currentLevel`: starting level name (resolved case-insensitively against `levels_dir`).
  - `levels_dir`: optional alternate folder for levels (defaults to `levels`).
  - `scoreboard_file`: path for the append-only scoreboard TSV (defaults to `scoreboard.txt`).
  - `scoring.star_points`: optional fixed points per star pickup (currently unused; pickups usually grant score via their `on_collision` patch).
  - `scoring.exploration_points`: award +1 score whenever the player reaches a new max X/Y tile.

- **Window**
  - `window.width` / `window.height`: initial windowed resolution (ignored when fullscreen launches).
  - `window.title`: title bar text.
  - `window.bg`: background color `[r,g,b]`.
  - `window.grid`: grid line color `[r,g,b]` when enabled.
  - `window.fullscreen`: `true/false` to start in fullscreen; runtime toggle via `F11` or `F`.

- **Render**
  - `render.show_grid`: overlay a tile grid when `true`.
  - `render.mode`: `"ascii" | "flat" | "gradient"`; backward-compat flags `render.ascii_text_mode` or `render.gradient_mode` also map to these. Runtime toggle via `T`.
  - `render.color`: `"multicolor" | "gray"`; runtime toggle via `C`.

- **Player defaults**
  - `color`, `shape` (`rect|circle|triangle`), `orientation` (`up|down` for triangles), `ascii_char` (single glyph used in ASCII mode).
  - `gravity`: accepts a scalar (y-only), `[gx, gy]`, or `{x/gx, y/gy}`; defaults to `(0, 1700)`.
  - `max_fall`: clamps terminal velocity.
  - `upgrades`: starting upgrade levels for this run, e.g. `"player": { "upgrades": { "speed": 1 } }`.

- **Upgrade definitions** (referenced by `player.upgrades` and legend patches)
  - Each upgrade block supports `max_level` and a list of values indexed by level `0..max_level`.
  - Supported blocks: `high_jump.level` (jump strength; currently also drives horizontal speed), `speed.level` (parsed for future horizontal tuning), `double_jump.jumps` (extra jumps), `fireball.max_level` (flag only), `gliding.gravity_reduction` (percent reduction while falling & holding Shift), `extra_live.lives` (life count), `fall_damage.threshold_tiles` (tiles you can fall without losing a life), `gravity_transformation.angles` (gravity direction in degrees).

- **Music**
  - `music.dir`: folder containing tracks (default `music`).
  - `music.playlist`: list of filenames to loop globally; per-level playlists override this.
  - `music.fade_ms`: fade duration when switching playlists/levels.
  - `music.bitcrusher`: optional lo-fi mixer profile. Fields: `bits` (or `bit_depth`), `sample_rate` (or `sampleRate`). Supplying the block enables it; removing the block disables it.
  - Levels can provide their own `music.playlist` and `music.bitcrusher` in `levels/<name>/<name>.json`.

- **Legend**: tile definitions (the “rules engine”)
  - Required: single-character key mapping to `shape`, `orientation`, `color`, `solid`, and optional `on_collision` patch.
  - Optional: `title`/`description` overlay text; `consumable` (`true/false`) plus `consumable_as` (replacement glyph after pickup; previous configs may use `consumed_as`).

- **Introduction overlays** (global or per-level)
  - `introduction.title` / `description` (or `text`): overlay content shown before play starts.
  - `introduction.image`: optional image path (absolute, `<levels_dir>/<name>/...`, or `<levels_dir>/...`).
  - `introduction.button_text`: label for the dismiss button (defaults to `"Continue"`).
  - `introduction.next_level`: optional level name to jump to when the button is clicked.

## Project structure
- `config.json`: main configuration file with global settings and defaults; optional key `levels_dir` can point to a different levels folder (default: `levels`).
- `levels/` (or the folder named by `levels_dir`): ASCII maps and optional per-level config files. Map filenames are `<LevelName>.map` at the root or inside a matching subfolder (`levels/Level1/Level1.map`). Per-level config overrides live next to the map as `<LevelName>.json` or `config.json` in the level folder.
- `music/`: global soundtrack directory; override with `music.dir`.
- `assets/`: art used by level introductions or other overlays referenced in config.

## Levels
- **Format:** text grids of single-character tiles. Shorter rows are padded with `.` so the level becomes rectangular; unknown characters fall back to the `.` legend entry.
- **Selection & progression:** the game boots into the `currentLevel` from `config.json`. Level changes happen through trigger patches (e.g. a goal tile with `{"currentLevel":"Level2"}`) or by restarting.
- **File lookup:** level names are resolved case-insensitively to `<levels_dir>/<Name>.map` or `<levels_dir>/<Name>/<Name>.map`; per-level config is loaded from `<levels_dir>/<Name>.json` or `<levels_dir>/<Name>/config.json` if present and merged over the base config.
- **Per-level overrides:** level configs can tweak render mode, colors, introduction overlays, music playlists/bitcrusher, or legend entries without mutating the global defaults.

## Environment tiles (how to define and use them)
- **Empty (.)**: background; `shape: "none"`, `solid: false`; no trigger/rendering.
- **Blocks (#) / Platforms (=)**: solid geometry; typically `shape: "rect"` with a color and `solid: true`.
- **Spawn (S)**: player start marker; non-solid. Levels should have exactly one `S` (later occurrences win).
- **Goal (G)**: level completion trigger; non-solid; usually carries `on_collision: {"currentLevel": "NextLevel"}`.
- **Death trap (^)**: hazard trigger; non-solid; sets lives to zero (or similar) via `on_collision`.
- **Star (*)**: collectible pickup; non-solid; `consumable: true`, `consumable_as: "d"`, grants score in `on_collision`.
- **Disabled star (d)**: post-consumption marker; non-solid, no trigger.
- **Adding new tiles:** pick a single-character key, add it to `legend` with `shape`, `color`, `solid`, and optional `on_collision` patches (player changes or level transitions), then place that character in map files.

## Legend rules (tile definitions)
Each tile character maps to:
- `shape`: `"none" | "rect" | "circle" | "triangle"`
- `orientation`: `"up" | "down"` (mainly relevant for triangles)
- `color`: `[r,g,b]` (optional if `shape="none"`)
- `solid`: `true/false`
- `title` / `description` (optional): when present, a small overlay is rendered above the tile to explain what it does
- `on_collision`: optional patch applied when player overlaps the tile

## Patch targets supported by the engine
- `{"player": {...}}` — modifies player state/properties
- `{"currentLevel": "Level2"}` — requests a level switch

Example:
```json
"G": {
  "shape": "circle",
  "color": [255, 214, 90],
  "solid": false,
  "on_collision": { "currentLevel": "Level2" }
}
```
