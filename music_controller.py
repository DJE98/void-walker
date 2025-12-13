from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pygame

from models import BitcrusherSettings


class MusicController:
    """Lightweight background music helper with playlists and fades."""

    def __init__(
        self,
        music_dir: Path,
        fade_ms: int = 800,
        bitcrusher_cfg: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.music_dir = music_dir
        self.fade_ms = fade_ms
        self.bitcrusher_cfg = BitcrusherSettings.from_raw(bitcrusher_cfg)
        self.playlist: List[Path] = []
        self.index = -1
        self.enabled = self._init_mixer()

    def _init_mixer(self) -> bool:
        """Initialize pygame mixer; return False if unavailable."""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(**self.bitcrusher_cfg.mixer_kwargs())
            return True
        except pygame.error as e:
            print(f"[music] pygame mixer disabled (bitcrusher={self.bitcrusher_cfg}): {e}")
            return False

    def _set_bitcrusher(self, cfg: Optional[Dict[str, Any]]) -> None:
        """Reconfigure the mixer if bitcrusher settings change."""
        new_cfg = BitcrusherSettings.from_raw(cfg)
        if new_cfg == self.bitcrusher_cfg:
            return

        was_playing = self.enabled and self._is_playing
        if was_playing:
            self._fadeout_current()

        self.bitcrusher_cfg = new_cfg
        self.enabled = self._init_mixer()

        if was_playing and self.enabled:
            self._play_current(fade_in=True)

    def _resolve_track(self, raw: str) -> Optional[Path]:
        """Resolve a track name to a real file path."""
        raw_path = Path(raw)
        candidates = []
        if not raw_path.is_absolute():
            candidates.append(self.music_dir / raw_path)
        candidates.append(raw_path)

        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _resolve_playlist(self, names: Sequence[str]) -> List[Path]:
        """Filter/resolve playlist entries into existing file paths."""
        resolved: List[Path] = []
        seen = set()
        for raw in names:
            if not isinstance(raw, str):
                continue
            track = self._resolve_track(raw)
            if not track:
                continue
            key = track.resolve()
            if key in seen:
                continue
            seen.add(key)
            resolved.append(track)
        return resolved

    @property
    def _is_playing(self) -> bool:
        return pygame.mixer.music.get_busy()

    def _fadeout_current(self) -> None:
        try:
            pygame.mixer.music.fadeout(self.fade_ms)
        except pygame.error:
            pass

    def _play_current(self, fade_in: bool) -> None:
        if not self.enabled or not self.playlist:
            return
        track = self.playlist[self.index % len(self.playlist)]
        pygame.mixer.music.load(track)
        pygame.mixer.music.play(loops=0, fade_ms=self.fade_ms if fade_in else 0)

    def _advance_and_play(self) -> None:
        if not self.playlist:
            return
        self.index = (self.index + 1) % len(self.playlist)
        self._play_current(fade_in=False)

    def set_playlist(self, names: Sequence[str]) -> None:
        """Switch to a new playlist, fading out any current music."""
        if not self.enabled:
            return

        resolved = self._resolve_playlist(names)
        if resolved == self.playlist and self._is_playing:
            return

        if self._is_playing:
            self._fadeout_current()

        self.playlist = resolved
        self.index = 0

        if not self.playlist:
            return

        self._play_current(fade_in=True)

    def set_bitcrusher(self, cfg: Optional[Dict[str, Any]]) -> None:
        """Public wrapper to update bitcrusher config."""
        self._set_bitcrusher(cfg)

    def update(self) -> None:
        """Advance the playlist when a track finishes."""
        if not self.enabled or not self.playlist:
            return
        if not pygame.mixer.music.get_busy():
            self._advance_and_play()
