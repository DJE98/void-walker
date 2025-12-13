# Mistakes are permanent — ASCII Side-Scroller

A grid-based side-scrolling platformer where **levels are ASCII tile maps** and **tile behavior is defined in `config.json`**.  
The player moves left/right, jumps under gravity, **collides with solid tiles**, and **triggers non-solid tiles** that can modify player/game state (hazards, level transitions, pickups).

## Starting Game
- Dev shell: `nix-shell`
- Run: `python main.py`

## Project Structure
- `config.json`
  - Global settings (tile size, window, default player physics)
  - **Legend**: tile rules (appearance + collision + trigger patches)
  - Optional inline levels (if used)
- `levels/`
  - Level files: `Level1.txt`, `Level2.txt`, …
  - Each file is a **grid of single-character tiles**

## Controls & Core Mechanics
- **Left/Right (←/→ or A/D)**: horizontal movement (continuous, not step-by-step per tile)
- **Jump (↑ or W or Space)**: only when grounded on a solid tile
- **R**: restart current level (respawn at `S`)
- **ESC**: quit
- **T**: toggle rendering between colored shapes and ASCII text glyphs
- **F**: fire a fireball (if `fireball` upgrade enabled)
- **Shift**:
  - run faster (if `speed` upgrade affects “run mode”), or
  - glide while falling (if `gliding` enabled)

**Physics**
- Gravity accelerates the player downward.
- Fall speed is clamped by `max_fall`.
- Death happens when:
  - a hazard trigger sets `player.alive=false`, or
  - the player falls far below the map bounds.
- **Fall damage**: if the player falls more tiles than allowed → lose a life (or die if no lives remain).
- **Lives**: with `extra_live`, damage reduces lives and pushes the player back instead of instant death.

## Levels
### Level Format (current implementation)
- Each tile is **one character** in the text file (e.g. `.  #  =  S  G  ^  U  D  *  d  B`).
- Rows are padded to the same width using `.` so every level becomes rectangular.
- Unknown characters behave like `.` unless defined in `legend`.

### How levels are selected
- The game loads `currentLevel` from config (e.g. `"Level1"`).
- Level progression happens via **trigger patches**, typically on the goal tile:
  - `{"currentLevel": "Level2"}`
- There is **no automatic file-order level progression** unless added later.

## Configuration (`config.json`)
### Key sections
- `tile_size`: pixel size of a tile
- `window`: width/height/title/bg/grid color
- `render`: rendering tweaks (`show_grid`, `ascii_text_mode`)
- `player`: default movement/physics (speed, jump_strength, gravity, max_fall)
- `currentLevel`: starting level name
- `legend`: tile definitions (the “rules engine”)
- `music`:
  - `dir`: folder containing background tracks (defaults to `music`)
  - `playlist`: list of track filenames to loop as the global soundtrack
  - `fade_ms`: fade duration when switching playlists/levels
  - Levels can provide their own `music.playlist` in `levels/<name>/<name>.json`; level playlists override the global playlist, and the global playlist is used when no level playlist is defined.

### Legend rules (tile definitions)
Each tile character maps to:
- `shape`: `"none" | "rect" | "circle" | "triangle"`
- `color`: `[r,g,b]` (optional if `shape="none"`)
- `solid`: `true/false`
- `on_collision`: optional patch applied when player overlaps the tile

Patch targets supported by the engine
- `{"player": {...}}` — modifies player state/properties (e.g. `alive`)
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

## Environment Tiles (How to define and use them)

### Empty (.)

* Purpose: air/background
* Config:
  * `shape: "none"`
  * `solid: false`
* Behavior: no collision, no rendering.

### Blocks (#) / Platforms (=)

* Purpose: environment geometry
* Behavior: **solid**; player collides, can stand on top
* Config requirements:
  * `solid: true`
  * `shape: "rect"` (typical)
  * `color: [...]`
* Example:

```json
"#": { "shape": "rect", "color": [85, 90, 105], "solid": true },
"=": { "shape": "rect", "color": [110, 115, 135], "solid": true }
```

### Spawn Point (S)

* Purpose: player start location
* Behavior: not solid; usually rendered for debug/visibility
* Rule: **levels should contain exactly one `S`**
  (if multiple exist, the spawn marker found later in the file will win in the current build logic)
* Config example:

```json
"S": { "shape": "rect", "color": [70, 200, 110], "solid": false }
```

### Goal (G)

* Purpose: level completion trigger
* Behavior: not solid; when touched, it changes the level via `on_collision`
* Important: every level should include exactly one `G`.
* Config example (go to Level2):

```json
"G": {
  "shape": "circle",
  "color": [255, 214, 90],
  "solid": false,
  "on_collision": { "currentLevel": "Level2" }
}
```

### Death Traps (^)

* Purpose: hazard trigger
* Behavior: not solid; touching it applies a patch that kills the player
* Config example:

```json
"^": {
  "shape": "triangle",
  "color": [230, 80, 95],
  "solid": false,
  "on_collision": { "player": { "alive": false } }
}
```

### Upgrade Terminal (U)
- **Purpose:** lets the player pick **one** upgrade level (+1) from a selection menu
- **Behavior:** not solid; **consumable** (usable once)
- **After use:** replaces itself with **Disabled Upgrade (`D`)**
- **Legend keys to use:**
  - `consumable: true`, `consumed_as: "D"`
  - `on_collision` should request UI: `{"ui":{"open":"upgrade_menu"}}`
- **Visual:** green, distinct shape (recommended `circle`)

### Disabled Upgrade (D)
- **Purpose:** used-up upgrade terminal (inactive)
- **Behavior:** not solid; no trigger; does nothing
- **Visual:** same shape as `U`, greyed out

### Star (*)
- **Purpose:** collectible score pickup
- **Behavior:** not solid; **consumable**
- **On touch:** adds score (+100) and disables itself
- **After use:** replaces itself with **Disabled Star (`d`)**
- **Legend keys to use:**
  - `consumable: true`, `consumed_as: "d"`
  - `on_collision: {"score":{"add":100}}`
- **Visual:** yellow, distinct shape (triangle in current spec)

### Disabled Star (d)
- **Purpose:** collected star marker (inactive)
- **Behavior:** not solid; no trigger
- **Visual:** same shape as `*`, greyed out

### Destructible Block (B)
- **Purpose:** solid obstacle that can be destroyed (e.g. by fireball later)
- **Behavior:** **solid**
- **Destruction rule:** when destroyed, becomes `.`
- **Legend keys to use:**
  - `destructible: true`, `destroyed_as: "."`

### Adding new tiles (current engine-compatible pattern)

1. Choose a **single character** for the map.
2. Add it to `legend` with `shape`, `color`, `solid`.
3. If it should trigger behavior, add `on_collision` patch:

   * player changes: `{"player": {...}}`
   * level transition: `{"currentLevel": "SomeLevel"}`
4. Place the character in the ASCII level file.

## Camera & Side-Scrolling

* Camera follows the player and centers them when possible.
* Camera is clamped to map bounds (never shows outside the level).

## Feature: Upgrades (run-based progression layer)

Upgrades modify player abilities during a run (persistence/saving can be added later).

* Each upgrade has levels (0..N) and changes player abilities.
* Implementation direction:
  * Store upgrade levels in player state.
  * Apply upgrades as modifiers to base `player` config values.
  * Add pickup/trigger tiles or UI selection to grant upgrades.
* each Upgrade environment tile `U` can only be used once

### Jump Higher (`high_jump`)

Adds bonus to `jump_strength` depending on upgrade level:

* 0: 560 (default base)
* 1: +500
* 2: +350
* 3: +250
* 4: +200
* 5: +150
* 6: +100
* 7: +50
* 8: +25
* 9: +20
* 10: +5

### Faster running (`speed`)

Adds bonus to horizontal speed:

* 0: 260 (default base)
* 1: +200
* 2: +150
* 3: +110
* 4: +80
* 5: +60
* 6: +50
* 7: +40
* 8: +30
* 9: +20
* 10: +10

### Double Jump (`double_jump`)

Enables additional mid-air jumps per airtime:

* 0: disabled
* 1: +1 mid-air jump
* 2: +2 mid-air jumps
* 3: +3 mid-air jumps

### Fireball (`fireball`)

Enables projectile that can destroy obstacles:

* 0: disabled
* 1: enabled (press **F**)

### Gliding (`gliding`)

Reduces gravity while falling and allows more controlled lateral movement:

* 0: disabled (default)
* 1: enable gliding, gravity -500
* 2: gravity -850
* 3: gravity -1200

### Extra Live (`extra_live`)

Gives additional lives, up to max three total:

* 0: one life (default)
* 1: add second life
* 2: add third life

Damage rule (design): instead of instant death, reduce lives by 1 and push player back **if lives > 1**.

### Fall Damage (`fall_damage`)

Fall height threshold (in tiles) that causes damage:

* 0: 5 (default)
* 1: 10
* 2: 15
* 3: 18
* 4: 21
* 5: 24
* 6: 26
* 7: 27
* 8: 28
* 9: 29
* 10: 30

Damage rule (design): if fall distance > threshold → lose one life (or die if none remain).

### Gravity / Room Transformation (`gravity_transformation`)

One active transformation at a time:

* 1: 0° (default)
* 2: 90°
* 3: 180°
* 4: 270°

Effects (design):

* rotate gravity direction / rotate level space
* player keeps position, then “falls” until grounded in new direction


## Feature: Scoring
* Stars can be collected:
  * each star = **100 points**
* Exploration progress:
  * each block of progress in horizontal/vertical reach = **+1 point**
  * e.g. track max X reached and max Y reached, award points for each new tile threshold crossed
* On death:

  * show run score
  * add to persistent scoreboard/leaderboard

## Backlog Only: Monsters (next year)

General rules:

* Walk left/right
* Do not jump
* Do not walk off cliffs
* On touch: player loses one life

Types:

* Simple Monster
* Greater Monster
* Flying Monster
* Ceiling Monster
