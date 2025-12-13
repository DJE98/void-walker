from __future__ import annotations

from pathlib import Path


def main() -> None:
    """Entrypoint for running the game from the command line."""
    import sys

    cfg_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("config.json")
    from game import Game  # local import keeps module load side effects minimal

    Game(cfg_path).run()


if __name__ == "__main__":
    main()

