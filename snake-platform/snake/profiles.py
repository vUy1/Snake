"""Finding the rule profiles that ship beside the SDK.

The league marks on one profile - `configs/league-arena.toml` - and it is not
the engine's built-in default, so anything claiming to check a snake "the way the
marker does" has to go and find it. It sits in `configs/` next to the package,
both in this repository and in the student zip.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

#: The profile league games are played under.
LEAGUE_PROFILE = "league-arena"

_HERE = Path(__file__).resolve().parent


def config_dir() -> Optional[Path]:
    """The `configs/` folder shipped with this SDK, if there is one."""
    for base in _HERE.parents:
        candidate = base / "configs"
        if candidate.is_dir():
            return candidate
    return None


def profile_path(name: str = LEAGUE_PROFILE) -> Optional[str]:
    """Path to `configs/<name>.toml`, or None if it is not beside us."""
    folder = config_dir()
    if folder is None:
        return None
    path = folder / f"{name}.toml"
    return str(path) if path.exists() else None
