from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json_config(path: Path) -> Dict[str, Any]:
    """Load a JSON config file or raise a helpful error.

    Args:
        path: Path to the JSON configuration file.

    Returns:
        Parsed JSON data as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        SystemExit: If JSON is invalid, with a friendly message.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        msg = (
            f"\nERROR: Your config is not valid JSON.\n"
            f"File: {path}\n"
            f"Line {e.lineno}, Col {e.colno}\n"
            f"{e.msg}\n\n"
            f"Common fix: maps must use \\n inside strings, or put maps in .txt files.\n"
        )
        raise SystemExit(msg)

