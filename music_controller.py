from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pygame


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
        self.bitcrusher_cfg = self._normalize_bitcrusher_cfg(bitcrusher_cfg)
        self.playlist: List[Path] = []
        self.index = -1
        self.enabled = self._init_mixer()

    def _normalize_bitcrusher_cfg(self, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Coerce raw bitcrusher config into a stable structure."""
        if isinstance(raw, dict):
            enabled = True
        else:
            raw = {}
            enabled = False
        bits_default = 8 if enabled else 16
        freq_default = 12000 if enabled else 44100

        bits = int(raw.get("bits", raw.get("bit_depth", bits_default)))
        bits = max(4, min(bits, 32))

        freq = int(raw.get("sample_rate", raw.get("sampleRate", freq_default)))
        freq = max(4000, min(freq, 192000))

        return {"enabled": enabled, "bits": bits, "sample_rate": freq}

    def _mixer_sample_size(self, bits: int) -> int:
        """Return a pygame-supported signed mixer size (8, 16, or 32)."""
        if bits <= 8:
            return 8
        if bits <= 16:
            return 16
        return 32

    def _mixer_kwargs(self) -> Dict[str, Any]:
        """Build mixer init kwargs, applying bitcrusher if enabled."""
        cfg = self.bitcrusher_cfg
        freq = cfg["sample_rate"] if cfg["enabled"] else 44100
        bits = cfg["bits"] if cfg["enabled"] else 16
        size = -abs(self._mixer_sample_size(int(bits)))
        return {"frequency": int(freq), "size": size, "channels": 2}

    def _init_mixer(self) -> bool:
        """Initialize pygame mixer; return False if unavailable."""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(**self._mixer_kwargs())
            return True
        except pygame.error as e:
            print(f"[music] pygame mixer disabled (bitcrusher={self.bitcrusher_cfg}): {e}")
            return False

    def _set_bitcrusher(self, cfg: Optional[Dict[str, Any]]) -> None:
        """Reconfigure the mixer if bitcrusher settings change."""
        new_cfg = self._normalize_bitcrusher_cfg(cfg)
        if new_cfg == self.bitcrusher_cfg:
            return

        was_playing = self.enabled and pygame.mixer.music.get_busy()
        if was_playing:
            try:
                pygame.mixer.music.fadeout(self.fade_ms)
            except pygame.error:
                pass

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
        if resolved == self.playlist and pygame.mixer.music.get_busy():
            return

        if pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(self.fade_ms)

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
