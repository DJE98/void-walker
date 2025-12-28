# Voidwalker: Mistakes are permanent — a ASCII Side-Scroller

Voidwalker is an experimental virus born in the late digital age, drifting between systems never meant to talk to each other. Each new machine is hostile, unstable, and full of outdated logic traps. To survive, Voidwalker must adapt—rewriting itself through stolen upgrades, slipping through memory gaps, and exploiting imperfect firewalls. A grid-based side-scrolling platformer where **levels are ASCII tile maps** and **tile behavior is defined in `config.json`**. The player moves left/right, jumps under gravity, **collides with solid tiles**, and **triggers non-solid tiles** that can modify player/game state (hazards, level transitions, pickups).

## Starting Game
- Dev shell: `nix-shell`
- Run: `python main.py`


## Controls & Core Mechanics
- **Left/Right (←/→ or A/D)**: horizontal movement (continuous, not step-by-step per tile)
- **Jump (↑ or W or Space)**: only when grounded on a solid tile
- **R**: restart current level (respawn at `S`)
- **ESC**: quit
- **T**: cycle render modes (ASCII → Flat Color → Gradient)
- **C**: toggle render color mode (Multicolor ↔ Gray) — shown in the HUD
- **Shift**: glide while falling (when the `gliding` upgrade is active)


## Configuration
See [CONFIGURATION.md](CONFIGURATION.md) for folder layout, level format, and all config keys.

## Backlog
Backlog details moved to [BACKLOG.md](BACKLOG.md).
