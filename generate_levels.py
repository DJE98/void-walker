#!/usr/bin/env python3
"""
generate_levels.py

Generates diverse, oldschool-looking ASCII platform maps.

Per generated level k:
- Creates:  levels/level{k}/
- Writes:   levels/level{k}/level{k}.json
- Writes:   levels/level{k}/level{k}.map

Key properties:
- Exactly one S (left, lower half)
- Exactly one G (near right border, varied height)
- Full cage border of '#'
- '.' fills empty
- '=' are platforms/solids (inside cage)
- '^' hazards (groups) that require going OVER (bridge) or UNDER (ceiling spikes)
- Early levels dense with platforms; later levels sparse with big void/pits
- Guaranteed reachable with BFS validation using level-scaled movement capability
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

LEVEL_DIR_RE = re.compile(r"^level(\d+)$", re.IGNORECASE)

PASSABLE_DEFAULT = "."
SOLID_TILES = {"#", "="}
HAZARD_TILE = "^"


def clamp_int(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def is_solid(ch: str) -> bool:
    return ch in SOLID_TILES


def is_hazard(ch: str) -> bool:
    return ch == HAZARD_TILE


def is_passable(ch: str) -> bool:
    # hazards are NOT passable (collision triggers)
    return (not is_solid(ch)) and (not is_hazard(ch))


@dataclass(frozen=True)
class MovementCapability:
    max_jump_up: int  # tiles
    max_gap: int  # gap tiles (landing dx = max_gap+1)
    max_drop: int  # intended drop in a move (soft cap)


@dataclass(frozen=True)
class LevelPaths:
    folder: Path
    json_path: Path
    map_path: Path


@dataclass
class GeneratedLevel:
    index: int
    width: int
    height: int
    rows: List[str]
    spawn: Tuple[int, int]
    goal: Tuple[int, int]
    cap: MovementCapability


# ----------------------------
# Index and sizing
# ----------------------------


class LevelIndexScanner:
    def __init__(self, levels_root: Path) -> None:
        self.levels_root = levels_root

    def last_level_index(self) -> int:
        if not self.levels_root.exists():
            return 0
        indices: List[int] = []
        for child in self.levels_root.iterdir():
            if not child.is_dir():
                continue
            m = LEVEL_DIR_RE.match(child.name)
            if not m:
                continue
            try:
                indices.append(int(m.group(1)))
            except ValueError:
                continue
        return max(indices) if indices else 0


class LevelSizeTracker:
    def __init__(self, levels_root: Path, rng: random.Random) -> None:
        self.levels_root = levels_root
        self.rng = rng

    def read_last_size(self, last_index: int) -> Tuple[int, int]:
        if last_index <= 0:
            return (42, 14)

        folder = self.levels_root / f"level{last_index}"
        map_path = folder / f"level{last_index}.map"
        txt_path = folder / f"level{last_index}.txt"
        path = (
            map_path if map_path.exists() else txt_path if txt_path.exists() else None
        )
        if path is None:
            return (42, 14)

        lines = [
            ln.rstrip("\n")
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip("\r") != ""
        ]
        if not lines:
            return (42, 14)
        return (max(len(l) for l in lines), len(lines))

    def next_size(self, prev_w: int, prev_h: int, level_index: int) -> Tuple[int, int]:
        # width grows by spec (+5..+20)
        w = prev_w + self.rng.randint(5, 20)

        # height always grows too (early smaller, later larger)
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)
        base_dh = 1 + int(diff * 3)  # 1..4
        dh = self.rng.randint(base_dh, base_dh + 2)  # e.g. 1..3 early; 3..6 later
        h = prev_h + dh

        w = clamp_int(w, 35, 280)
        h = clamp_int(h, 12, 80)
        return (w, h)


class CapabilityModel:
    """Assumed capability rises with level (persistent upgrades)."""

    def for_level(self, level_index: int) -> MovementCapability:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)
        max_jump_up = 1 + int(round(diff * 5.0))  # 1..6
        max_gap = 1 + int(round(diff * 7.0))  # 1..8
        max_drop = 2 + int(round(diff * 5.0))  # 2..7
        return MovementCapability(
            max_jump_up=clamp_int(max_jump_up, 1, 8),
            max_gap=clamp_int(max_gap, 1, 12),
            max_drop=clamp_int(max_drop, 2, 12),
        )


# ----------------------------
# Grid
# ----------------------------


class GridBuilder:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid: List[List[str]] = [
            [PASSABLE_DEFAULT for _ in range(width)] for _ in range(height)
        ]

    def add_cage(self) -> None:
        w, h = self.width, self.height
        for x in range(w):
            self.grid[0][x] = "#"
            self.grid[h - 1][x] = "#"
        for y in range(h):
            self.grid[y][0] = "#"
            self.grid[y][w - 1] = "#"

    def get(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return "#"

    def set(self, x: int, y: int, ch: str) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = ch

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        for y in range(max(1, y0), min(self.height - 1, y1 + 1)):
            for x in range(max(1, x0), min(self.width - 1, x1 + 1)):
                self.grid[y][x] = ch

    def clear_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        for y in range(max(1, y0), min(self.height - 1, y1 + 1)):
            for x in range(max(1, x0), min(self.width - 1, x1 + 1)):
                self.grid[y][x] = "."

    def rows(self) -> List[str]:
        return ["".join(r) for r in self.grid]


# ----------------------------
# Environment painting (beauty + density curve)
# ----------------------------


class EnvironmentPainter:
    """Paints layered platforms, islands, columns, dead-ends."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def paint(self, gb: GridBuilder, level_index: int) -> None:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)

        self._paint_floor_band(gb, diff)
        self._paint_platform_layers(gb, diff)
        self._paint_islands(gb, diff)
        self._paint_columns(gb, diff)
        self._paint_stair_connectors(gb, diff) 
        self._paint_dead_ends(gb, diff)

    def _paint_floor_band(self, gb: GridBuilder, diff: float) -> None:
        # Early: mostly solid floor band; Later: broken with pits.
        floor_y = gb.height - 2
        coverage = 0.92 - diff * 0.55  # 0.92 -> 0.37
        x = 1
        while x < gb.width - 1:
            if self.rng.random() < coverage:
                seg = self.rng.randint(5, 14)
                for xx in range(x, min(gb.width - 1, x + seg)):
                    gb.set(xx, floor_y, "=")
                x += seg
            else:
                gap = self.rng.randint(2, 10 if diff > 0.5 else 5)
                x += gap

    def _paint_platform_layers(self, gb: GridBuilder, diff: float) -> None:
        # More layers with height; early dense, later sparse.
        layers = 3 + (gb.height // 18) + int(diff * 4)  # scales with height and diff
        ys: List[int] = []
        for _ in range(layers * 2):
            y = self.rng.randint(2, gb.height - 5)
            if y not in ys:
                ys.append(y)
            if len(ys) >= layers:
                break
        ys.sort()

        base_coverage = 0.65 - diff * 0.35  # early 0.65, later 0.30
        for y in ys:
            x = 1
            while x < gb.width - 1:
                if self.rng.random() < base_coverage:
                    seg_min = 4 if diff < 0.5 else 2
                    seg_max = 14 if diff < 0.4 else 9
                    seg = self.rng.randint(seg_min, seg_max)
                    for xx in range(x, min(gb.width - 1, x + seg)):
                        if gb.get(xx, y) == ".":
                            gb.set(xx, y, "=")
                    x += seg
                else:
                    gap_min = 1 if diff < 0.4 else 3
                    gap_max = 5 if diff < 0.4 else 14
                    x += self.rng.randint(gap_min, gap_max)

    def _paint_islands(self, gb: GridBuilder, diff: float) -> None:
        # Early more islands, later fewer (world becomes emptier).
        count = int((gb.width * gb.height) * (0.0025 - diff * 0.0015))
        count = clamp_int(count, 4, 30)
        for _ in range(count):
            w = self.rng.randint(2, 6)
            h = 1
            x = self.rng.randint(2, gb.width - 3 - w)
            y = self.rng.randint(2, gb.height - 6)
            for xx in range(x, x + w):
                if gb.get(xx, y) == ".":
                    gb.set(xx, y, "=")

    def _paint_columns(self, gb: GridBuilder, diff: float) -> None:
        """
        OLD: tall solid '#' columns (blocked paths)
        NEW: stairs + broken 'ruin pillars' with windows (still looks cyber/ruined, but playable)
        """
        structure_count = clamp_int(int(gb.width * (0.10 - diff * 0.04)) + (gb.height // 18), 4, 24)

        for _ in range(structure_count):
            if self.rng.random() < 0.70:
                self._paint_staircase(gb, diff)
            else:
                self._paint_ruin_pillar_with_windows(gb, diff)

    def _paint_columns_old(self, gb: GridBuilder, diff: float) -> None:
        # Columns give that "old computer platformer" vibe.
        # Early: more columns; later: fewer.
        column_count = int(
            gb.width * (0.10 - diff * 0.06)
        )  # early ~10% of width, later ~4%
        column_count = clamp_int(column_count, 2, 18)

        for _ in range(column_count):
            x = self.rng.randint(2, gb.width - 3)
            # pick top and bottom
            top = self.rng.randint(2, gb.height // 2)
            bottom = self.rng.randint(gb.height // 2, gb.height - 3)
            # broken columns sometimes
            if self.rng.random() < (0.25 + diff * 0.25):
                # need at least 3 tiles of height to have a cut between (top+1 .. bottom-1)
                if (bottom - top) >= 3:
                    cut_y = self.rng.randint(top + 1, bottom - 1)
                    for y in range(top, cut_y):
                        gb.set(x, y, "#")
                    for y in range(cut_y + 2, bottom):
                        gb.set(x, y, "#")
                else:
                    # too short to split -> just draw a solid column
                    for y in range(top, bottom):
                        gb.set(x, y, "#")
            else:
                for y in range(top, bottom):
                    gb.set(x, y, "#")

    def _paint_staircase(self, gb: GridBuilder, diff: float) -> None:
        # stairs are '=' blocks in a diagonal (walk/jump 1-tile steps)
        steps = self.rng.randint(5, 10 + int(diff * 10))
        rise = self.rng.choice([-1, 1])  # -1 goes up, +1 goes down
        run_dir = self.rng.choice([1, -1])

        # choose a safe starting position
        x0 = self.rng.randint(2, gb.width - 3 - steps) if run_dir == 1 else self.rng.randint(2 + steps, gb.width - 3)
        y0 = self.rng.randint(3, gb.height - 6)

        # small landing at start
        for lx in range(0, self.rng.randint(2, 4)):
            xx = x0 + lx * run_dir
            if 1 <= xx <= gb.width - 2:
                gb.set(xx, y0, "=")

        x, y = x0, y0
        for _ in range(steps):
            if not (2 <= x <= gb.width - 3 and 2 <= y <= gb.height - 4):
                break
            gb.set(x, y, "=")
            x += run_dir
            y += rise

        # small landing at end
        for lx in range(0, self.rng.randint(2, 4)):
            xx = x + lx * run_dir
            if 1 <= xx <= gb.width - 2 and 1 <= y <= gb.height - 2:
                gb.set(xx, y, "=")


    def _paint_ruin_pillar_with_windows(self, gb: GridBuilder, diff: float) -> None:
        """
        A vertical structure that LOOKS like a pillar but has holes/windows so it doesn't block play.
        Uses '#' sparsely; keeps it from becoming a full wall.
        """
        x = self.rng.randint(2, gb.width - 3)
        top = self.rng.randint(2, gb.height // 2)
        bottom = self.rng.randint(gb.height // 2, gb.height - 3)

        # if too short, skip
        if bottom - top < 4:
            return

        window_rate = 0.45 + diff * 0.25  # more holes later (less blocking)
        for y in range(top, bottom):
            if self.rng.random() < window_rate:
                # hole
                if gb.get(x, y) == "#":
                    gb.set(x, y, ".")
            else:
                # solid segment (but only 1-tile wide)
                if gb.get(x, y) == ".":
                    gb.set(x, y, "#")

    def _paint_stair_connectors(self, gb: GridBuilder, diff: float) -> None:
        """
        Connects different platform layers using staircases.
        Early: more connectors (dense labyrinth)
        Late: fewer connectors (more void / risk)
        """
        # early dense, later sparser
        density = 0.10 - diff * 0.05
        count = clamp_int(int(gb.width * density) + (gb.height // 20), 3, 22)

        for _ in range(count):
            self._paint_staircase(gb, diff)

    def _paint_dead_ends(self, gb: GridBuilder, diff: float) -> None:
        # Adds platforms that lead to nowhere ("into nothingness").
        count = clamp_int(int(gb.width * (0.18 - diff * 0.06)), 3, 20)
        for _ in range(count):
            y = self.rng.randint(2, gb.height - 6)
            length = self.rng.randint(3, 10 if diff < 0.5 else 7)
            if self.rng.random() < 0.5:
                # from left going right
                x0 = self.rng.randint(2, gb.width // 2)
                for x in range(x0, min(gb.width - 2, x0 + length)):
                    if gb.get(x, y) == ".":
                        gb.set(x, y, "=")
            else:
                # from right going left
                x0 = self.rng.randint(gb.width // 2, gb.width - 3)
                for x in range(x0, max(1, x0 - length), -1):
                    if gb.get(x, y) == ".":
                        gb.set(x, y, "=")


class VoidCarver:
    """Carves larger pits/voids that increase with level difficulty (without touching borders)."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def carve(self, gb: GridBuilder, level_index: int) -> None:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)

        floor_y = gb.height - 2

        # later levels: more + wider pits
        pit_count = clamp_int(int(gb.width * (0.04 + diff * 0.10)), 1, 30)

        for _ in range(pit_count):
            pit_w = self.rng.randint(2, 4 + int(diff * 10))
            pit_h = self.rng.randint(3, 6 + int(diff * 18))

            x0 = self.rng.randint(2, gb.width - 3 - pit_w)
            y0 = clamp_int(floor_y - pit_h, 2, floor_y - 1)

            # clear a vertical "pit" area (keeps upper world nicer than clearing random mid rectangles)
            gb.clear_rect(x0, y0, x0 + pit_w, floor_y - 1)

    def carve_old(self, gb: GridBuilder, level_index: int) -> None:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)
        # early: little carving, late: lots
        shafts = int((gb.width / 25.0) * (0.6 + diff * 3.0))
        shafts = clamp_int(shafts, 1, 18)

        for _ in range(shafts):
            if self.rng.random() > (0.25 + diff * 0.70):
                continue

            x0 = self.rng.randint(2, gb.width - 8)
            w = self.rng.randint(3, 6 + int(diff * 10))
            y0 = self.rng.randint(gb.height // 2, gb.height - 6)
            h = self.rng.randint(4, 8 + int(diff * 18))

            gb.clear_rect(x0, y0, x0 + w, min(gb.height - 3, y0 + h))


# ----------------------------
# Main path (guaranteed route)
# ----------------------------


class MainPathPlanner:
    """Overlays a reliable route made of '=' (platform tiles)."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def build(
        self,
        gb: GridBuilder,
        spawn_x: int,
        spawn_y: int,
        goal_x: int,
        cap: MovementCapability,
        level_index: int,
    ) -> Tuple[int, List[Optional[int]]]:
        w, h = gb.width, gb.height
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)

        ground_y_for_x: List[Optional[int]] = [None] * w

        ground_y = clamp_int(spawn_y + 1, 2, h - 3)

        # path roughness scales with diff
        seg_min = 2
        seg_max = clamp_int(8 - int(diff * 4), 2, 8)
        gap_chance = 0.18 + diff * 0.45
        step_chance = 0.30 + diff * 0.55

        x = spawn_x
        target_end = max(spawn_x + 12, goal_x - 2)

        # stable start platform
        for xx in range(max(1, spawn_x - 1), min(w - 1, spawn_x + 6)):
            gb.set(xx, ground_y, "=")
            ground_y_for_x[xx] = ground_y

        x = min(w - 3, spawn_x + 5)

        while x < target_end:
            seg_len = self.rng.randint(seg_min, seg_max)
            for _ in range(seg_len):
                if x >= target_end:
                    break
                gb.set(x, ground_y, "=")
                ground_y_for_x[x] = ground_y
                x += 1

            if x >= target_end:
                break

            # gap in platforms (void to fall through), scaled but within cap
            if self.rng.random() < gap_chance:
                gap = self.rng.randint(0, cap.max_gap)
                x = min(target_end, x + gap)

            # step up/down
            if self.rng.random() < step_chance:
                up = cap.max_jump_up
                down = cap.max_drop
                step = self.rng.randint(-up, down)
                ground_y = clamp_int(ground_y + step, 2, h - 3)

        # reinforce near goal
        for xx in range(max(1, goal_x - 8), goal_x):
            gb.set(xx, ground_y, "=")
            ground_y_for_x[xx] = ground_y

        return ground_y, ground_y_for_x


# ----------------------------
# Hazards (groups + over/under patterns)
# ----------------------------


class HazardWeaver:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def weave(
        self,
        gb: GridBuilder,
        ground_y_for_x: Sequence[Optional[int]],
        spawn_x: int,
        goal_x: int,
        level_index: int,
        cap: MovementCapability,
    ) -> None:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)

        # more hazards as level increases and map grows
        base = int((gb.width / 18.0) * (0.8 + diff * 2.8))
        hazard_groups = clamp_int(base, 2, 28)

        for _ in range(hazard_groups):
            x0 = self._pick_path_x(ground_y_for_x, spawn_x, goal_x, margin=10)
            if x0 is None:
                return
            gy = ground_y_for_x[x0]
            if gy is None:
                continue

            # group length grows with diff, but keep sane
            length = self.rng.randint(3, 5 + int(diff * 8))
            x1 = min(goal_x - 2, x0 + length - 1)
            if x1 <= x0:
                continue

            pattern = "OVER" if self.rng.random() < (0.45 + diff * 0.25) else "UNDER"
            if pattern == "OVER":
                self._place_over_group(gb, x0, x1, gy)
            else:
                self._place_under_group(gb, x0, x1, gy)

    def _place_over_group(
        self, gb: GridBuilder, x0: int, x1: int, ground_y: int
    ) -> None:
        """
        OVER group:
        - spikes occupy the standable row above ground (player would die if walking there)
        - a bridge one tile higher is placed so player can jump up and cross
        """
        spike_y = ground_y - 1
        bridge_platform_y = ground_y - 1  # platform tile one higher than ground

        # Place spikes on the standable row (spike_y) above the ground.
        # Ensure ground exists.
        for x in range(x0, x1 + 1):
            if gb.get(x, ground_y) != "=":
                gb.set(x, ground_y, "=")
            if 1 <= spike_y <= gb.height - 2:
                gb.set(x, spike_y, "^")

        # Place bridge platform one tile above the spikes (so standable row becomes spike_y-1)
        upper_y = bridge_platform_y - 1
        if upper_y <= 1:
            return
        for x in range(x0 - 1, x1 + 2):
            if 1 <= x <= gb.width - 2:
                gb.set(x, upper_y, "=")

    def _place_under_group(
        self, gb: GridBuilder, x0: int, x1: int, ground_y: int
    ) -> None:
        """
        UNDER group:
        - spikes hang one tile above the player's head corridor (so jumping hits them)
        - walking under stays safe
        """
        ceiling_spike_y = ground_y - 2
        if ceiling_spike_y <= 1:
            return

        # Ensure ground corridor
        for x in range(x0, x1 + 1):
            if gb.get(x, ground_y) != "=":
                gb.set(x, ground_y, "=")

        # Hang spikes above corridor
        for x in range(x0, x1 + 1):
            gb.set(x, ceiling_spike_y, "^")

    def _pick_path_x(
        self,
        ground_y_for_x: Sequence[Optional[int]],
        spawn_x: int,
        goal_x: int,
        margin: int,
    ) -> Optional[int]:
        lo = spawn_x + margin
        hi = goal_x - margin
        if hi <= lo:
            return None
        candidates = [x for x in range(lo, hi) if ground_y_for_x[x] is not None]
        return self.rng.choice(candidates) if candidates else None


# ----------------------------
# Extras: stars + rare upgrades
# ----------------------------


class ExtrasPlacer:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def place(
        self,
        gb: GridBuilder,
        ground_y_for_x: Sequence[Optional[int]],
        spawn_x: int,
        goal_x: int,
        level_index: int,
    ) -> None:
        diff = min(1.0, (max(1, level_index) - 1) / 30.0)

        # stars rare but present
        stars = 1 if diff < 0.35 else self.rng.choice([1, 2])
        if self.rng.random() < 0.35:
            stars = 0

        for _ in range(stars):
            x = self._pick_x(ground_y_for_x, spawn_x, goal_x, margin=10)
            if x is None:
                return
            gy = ground_y_for_x[x]
            if gy is None:
                continue
            plat_y = clamp_int(gy - self.rng.randint(2, 4), 2, gb.height - 4)
            for xx in range(x, min(gb.width - 2, x + self.rng.randint(2, 4))):
                gb.set(xx, plat_y, "=")
            star_x = x + self.rng.randint(0, 2)
            star_y = plat_y - 1
            if gb.get(star_x, star_y) == ".":
                gb.set(star_x, star_y, "*")

        # upgrades/downgrades very rare
        orb_chars = ["1", "2", "3", "4", "5", "6", "7", "8"]

        # REQUIRED: at least 1 per level, up to width/30
        max_orbs = max(1, gb.width // 30)
        orb_count = self.rng.randint(1, max_orbs)

        placed = 0
        attempts = orb_count * 30  # plenty of tries to find valid spots
        while placed < orb_count and attempts > 0:
            attempts -= 1

            x = self._pick_x(ground_y_for_x, spawn_x, goal_x, margin=10)
            if x is None:
                break
            gy = ground_y_for_x[x]
            if gy is None:
                continue

            # put orb on a small optional platform (so it feels like a pickup)
            plat_y = clamp_int(gy - self.rng.randint(1, 3), 2, gb.height - 4)
            for xx in range(x, min(gb.width - 2, x + self.rng.randint(1, 3))):
                gb.set(xx, plat_y, "=")

            orb_x = x + self.rng.randint(0, 1)  # tiny variation
            orb_y = plat_y - 1
            if gb.get(orb_x, orb_y) == ".":
                gb.set(orb_x, orb_y, self.rng.choice(orb_chars))
                placed += 1

    def _pick_x(
        self,
        ground_y_for_x: Sequence[Optional[int]],
        spawn_x: int,
        goal_x: int,
        margin: int,
    ) -> Optional[int]:
        lo = spawn_x + margin
        hi = goal_x - margin
        if hi <= lo:
            return None
        xs = [x for x in range(lo, hi) if ground_y_for_x[x] is not None]
        return self.rng.choice(xs) if xs else None


# ----------------------------
# Reachability validation (respects hazards + jump arcs)
# ----------------------------


class ReachabilityValidator:
    def is_reachable(self, rows: Sequence[str], cap: MovementCapability) -> bool:
        if not rows:
            return False
        h = len(rows)
        w = max(len(r) for r in rows)
        grid = [r.ljust(w, ".") for r in rows]

        start = self._find_unique(grid, "S")
        goal = self._find_unique(grid, "G")
        if start is None or goal is None:
            return False

        sx, sy = start
        gx, gy = goal

        s_state = self._fall_to_standable(grid, sx, sy)
        g_state = self._fall_to_standable(grid, gx, gy)
        if s_state is None or g_state is None:
            return False

        from collections import deque

        q = deque([s_state])
        visited = {s_state}

        while q:
            x, y = q.popleft()
            if (x, y) == g_state:
                return True
            for nx, ny in self._neighbors(grid, x, y, cap):
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny))
        return False

    def _neighbors(
        self, grid: Sequence[str], x: int, y: int, cap: MovementCapability
    ) -> Iterable[Tuple[int, int]]:
        w, h = len(grid[0]), len(grid)

        def passable(xx: int, yy: int) -> bool:
            return 0 <= xx < w and 0 <= yy < h and is_passable(grid[yy][xx])

        def landable(xx: int, yy: int) -> bool:
            # cannot occupy hazard tile
            if not passable(xx, yy):
                return False
            return True

        def try_land(xx: int, yy: int) -> Optional[Tuple[int, int]]:
            if not (1 <= xx <= w - 2 and 1 <= yy <= h - 2):
                return None
            if not landable(xx, yy):
                return None
            return self._fall_to_standable(grid, xx, yy)

        # walk/step
        for dx in (-1, 1):
            for dy in (-1, 0, 1):
                cand = try_land(x + dx, y + dy)
                if cand is not None:
                    yield cand

        # jumps (dx up to max_gap+1, dy up to max_jump_up)
        max_dx = cap.max_gap + 1
        for dx in range(-max_dx, max_dx + 1):
            if dx == 0:
                continue
            for dy in range(-cap.max_jump_up, 1):
                tx, ty = x + dx, y + dy
                if not (1 <= tx <= w - 2 and 1 <= ty <= h - 2):
                    continue

                # corridor check at "jump apex height approximation":
                # use the higher of start/end (min y) so you can jump over low obstacles.
                corridor_y = min(y, ty)
                step = 1 if dx > 0 else -1
                ok = True
                for xx in range(x + step, tx + step, step):
                    if not passable(xx, corridor_y):
                        ok = False
                        break
                if not ok:
                    continue

                cand = try_land(tx, ty)
                if cand is None:
                    continue

                # avoid huge intentional drops
                if cand[1] - y > cap.max_drop:
                    continue

                yield cand

    def _fall_to_standable(
        self, grid: Sequence[str], x: int, y: int
    ) -> Optional[Tuple[int, int]]:
        w, h = len(grid[0]), len(grid)

        def passable(xx: int, yy: int) -> bool:
            return 0 <= xx < w and 0 <= yy < h and is_passable(grid[yy][xx])

        def solid(xx: int, yy: int) -> bool:
            return 0 <= xx < w and 0 <= yy < h and is_solid(grid[yy][xx])

        if not passable(x, y):
            return None

        yy = y
        while yy + 1 < h and passable(x, yy + 1):
            yy += 1

        if 1 <= x <= w - 2 and 1 <= yy <= h - 2 and solid(x, yy + 1):
            return (x, yy)
        return None

    def _find_unique(self, grid: Sequence[str], ch: str) -> Optional[Tuple[int, int]]:
        found: List[Tuple[int, int]] = []
        for y, row in enumerate(grid):
            for x, c in enumerate(row):
                if c == ch:
                    found.append((x, y))
        return found[0] if len(found) == 1 else None


# ----------------------------
# Writer
# ----------------------------


class LevelWriter:
    def __init__(self, levels_root: Path) -> None:
        self.levels_root = levels_root

    def paths_for(self, idx: int) -> LevelPaths:
        folder = self.levels_root / f"level{idx}"
        return LevelPaths(
            folder=folder,
            json_path=folder / f"level{idx}.json",
            map_path=folder / f"level{idx}.map",
        )

    def write(self, level: GeneratedLevel) -> None:
        paths = self.paths_for(level.index)
        paths.folder.mkdir(parents=True, exist_ok=False)

        payload = {
            "music": {
                "playlist": ["cool-hiphop-rap-beat-20230307-191928.mp3"],
                "bitcrusher": {"bits": 8, "sample_rate": 8000},
            },
            "currentLevel": f"Level{level.index}",
            "legend": {
                "G": {"on_collision": {"currentLevel": f"Level{level.index + 1}"}}
            },
        }
        paths.json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        paths.map_path.write_text("\n".join(level.rows) + "\n", encoding="utf-8")


# ----------------------------
# Generator orchestration
# ----------------------------


class LevelGenerator:
    def __init__(self, levels_root: Path, rng: random.Random) -> None:
        self.levels_root = levels_root
        self.rng = rng

        self.scanner = LevelIndexScanner(levels_root)
        self.sizer = LevelSizeTracker(levels_root, rng)
        self.cap_model = CapabilityModel()

        self.env = EnvironmentPainter(rng)
        self.void = VoidCarver(rng)
        self.path = MainPathPlanner(rng)
        self.hazards = HazardWeaver(rng)
        self.extras = ExtrasPlacer(rng)
        self.validator = ReachabilityValidator()
        self.writer = LevelWriter(levels_root)

    def generate(self, count: int) -> None:
        self.levels_root.mkdir(parents=True, exist_ok=True)

        last_idx = self.scanner.last_level_index()
        prev_w, prev_h = self.sizer.read_last_size(last_idx)

        for i in range(count):
            idx = last_idx + 1 + i
            cap = self.cap_model.for_level(idx)
            w, h = self.sizer.next_size(prev_w, prev_h, idx)

            level = self._generate_one(idx, w, h, cap)
            self.writer.write(level)

            print(
                f"Generated level{idx}: {w}x{h} | cap(jump_up={cap.max_jump_up}, gap={cap.max_gap})"
            )
            prev_w, prev_h = w, h

    def _generate_one(
        self, idx: int, w: int, h: int, cap: MovementCapability
    ) -> GeneratedLevel:
        attempts = 120
        while attempts > 0:
            attempts -= 1

            gb = GridBuilder(w, h)
            gb.add_cage()

            # Paint a rich world first
            self.env.paint(gb, idx)
            self.void.carve(gb, idx)

            # Spawn + goal anchors
            spawn_x = self.rng.randint(2, max(2, w // 6))
            spawn_y = self.rng.randint(h // 2, max(h // 2, h - 6))
            gb.set(spawn_x, spawn_y, "S")

            goal_x = w - 2

            # Build guaranteed main path overlay (so void/painting cannot break it)
            final_ground_y, ground_y_for_x = self.path.build(
                gb=gb,
                spawn_x=spawn_x,
                spawn_y=spawn_y,
                goal_x=goal_x,
                cap=cap,
                level_index=idx,
            )

            self._carve_corridor_along_main_path(gb, ground_y_for_x)

            # Place goal near right border at varied height (based on final path height)
            goal_y = clamp_int(final_ground_y - 1, 1, h - 3)
            # Ensure support under goal
            if gb.get(goal_x, goal_y + 1) == ".":
                gb.set(goal_x, goal_y + 1, "=")
            gb.set(goal_x, goal_y, "G")

            # Add hazard groups along the main route
            self.hazards.weave(gb, ground_y_for_x, spawn_x, goal_x, idx, cap)

            # Add stars + rare orbs on side platforms
            self.extras.place(gb, ground_y_for_x, spawn_x, goal_x, idx)

            rows = gb.rows()

            if self.validator.is_reachable(rows, cap):
                return GeneratedLevel(
                    index=idx,
                    width=w,
                    height=h,
                    rows=rows,
                    spawn=(spawn_x, spawn_y),
                    goal=(goal_x, goal_y),
                    cap=cap,
                )

        raise RuntimeError(
            f"Failed to generate a reachable map for level{idx} after many attempts."
        )
    
    def _carve_corridor_along_main_path(self, gb: GridBuilder, ground_y_for_x: Sequence[Optional[int]]) -> None:
        """
        Randomly punch openings through vertical '#' columns near the main path.
        Clears headroom above '=' but only at random x positions, and clears 1..3 columns wide.
        """
        for x, ground_y in enumerate(ground_y_for_x):
            if ground_y is None:
                continue

            # Random chance to carve at this x (tune these to taste)
            if self.rng.random() > 0.35:
                continue

            # Clear 1..3 columns wide centered near x
            half_span = self.rng.randint(0, 1)  # 0 => 1-wide, 1 => up to 3-wide
            x0 = clamp_int(x - half_span, 1, gb.width - 2)
            x1 = clamp_int(x + half_span, 1, gb.width - 2)

            for xx in range(x0, x1 + 1):
                # Clear 2-3 tiles of headroom (randomly 2 or 3)
                headroom = self.rng.randint(2, 3)
                for dy in range(1, headroom + 1):
                    y = ground_y - dy
                    if 1 <= y <= gb.height - 2 and gb.get(xx, y) == "#":
                        gb.set(xx, y, ".")



# ----------------------------
# CLI
# ----------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate Voidwalker procedural ASCII levels."
    )
    p.add_argument("count", type=int, help="How many new levels to generate.")
    p.add_argument(
        "--levels-root",
        type=str,
        default="levels",
        help="Levels folder (default: levels)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible generation.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.count <= 0:
        raise SystemExit("count must be > 0")
    rng = random.Random(args.seed)
    LevelGenerator(Path(args.levels_root), rng).generate(args.count)


if __name__ == "__main__":
    main()
