from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ScoreEntry:
    timestamp: str
    level: str
    score: int


class ScoreboardFile:
    """Append-only local scoreboard in a simple TSV text file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, entry: ScoreEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = f"{entry.timestamp}\t{entry.level}\t{entry.score}\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)

    def top_scores(self, limit: int = 10) -> list[ScoreEntry]:
        if not self.path.exists():
            return []

        entries: list[ScoreEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            ts, lvl, sc = parts
            try:
                entries.append(ScoreEntry(ts, lvl, int(sc)))
            except ValueError:
                continue

        entries.sort(key=lambda e: e.score, reverse=True)
        return entries[:limit]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
