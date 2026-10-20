"""Student SDK for the competitive snake platform.

Write a snake by subclassing :class:`SnakeController` and implementing ``move``:

    from snake import SnakeController, Move
    from snake.helpers import safe_moves, roomiest_move

    class MySnake(SnakeController):
        name = "my_snake"

        def move(self, obs):
            options = safe_moves(obs)
            if obs.nearest_food():
                return direction_towards(obs, obs.nearest_food(), options) or roomiest_move(obs)
            return roomiest_move(obs, options) or "up"

Then play it::

    python -m snake.cli play my_snake.py --seed 3

Everything authoritative — resolution, collisions, the failure policy,
the replay format — is in the compiled engine. This package is a convenience
layer, so a game run here obeys the exact rules the league server applies.
"""

from __future__ import annotations

import importlib.util
import platform
import sys
from pathlib import Path


def _platform_tag() -> str:
    """`macos-arm64`, `linux-x86_64`, `windows-x86_64` - how engines are filed.

    A compiled extension is named the same on Linux and macOS
    (``_engine.abi3.so``), so a download that carries both cannot simply put
    them side by side. They are filed under ``snake/_engines/<tag>/`` instead,
    and this is the tag for the machine asking.
    """
    machine = platform.machine().lower()
    arch = {
        "x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64",
        "arm64": "arm64", "aarch64": "arm64",
    }.get(machine, machine or "unknown")
    if sys.platform == "darwin":
        return f"macos-{arch}"
    if sys.platform.startswith("win"):
        return f"windows-{arch}"
    return f"linux-{arch}"


def _bundled_engine():
    """Load the engine built for this machine out of ``snake/_engines/``."""
    folder = Path(__file__).resolve().parent / "_engines" / _platform_tag()
    if folder.is_dir():
        for candidate in sorted(folder.iterdir()):
            if candidate.name.startswith("_engine") and candidate.suffix in (".so", ".pyd", ".dylib"):
                spec = importlib.util.spec_from_file_location(__name__ + "._engine", candidate)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[__name__ + "._engine"] = module
                    spec.loader.exec_module(module)
                    return module
    return None


def _no_engine(exc: Exception) -> ImportError:
    """The message somebody actually gets when nothing here will run."""
    root = Path(__file__).resolve().parent / "_engines"
    have = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    lines = [
        f"This download has no engine for your machine ({_platform_tag()}).",
        "",
    ]
    if have:
        lines += [f"It carries engines for: {', '.join(have)}.", ""]
    lines += [
        "Ask for a build for your platform, or build one yourself with a Rust",
        "toolchain (https://rustup.rs) from the platform repository:",
        "",
        "    maturin develop --release",
    ]
    return ImportError("\n".join(lines))


try:
    from . import _engine
except ImportError as exc:  # pragma: no cover - depends on what was downloaded
    _engine = _bundled_engine()
    if _engine is None:
        raise _no_engine(exc) from exc

from ._engine import ENGINE_VERSION, config_hash, read_replay
from .actions import Move
from .controller import SnakeController
from .env import SnakeEnv
from .errors import PolicyError, SnakeError, SubmissionError
from .geometry import (
    DIRECTIONS,
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Coord,
    as_coord,
    delta,
    opposite,
)
from .helpers import (
    bigger_opponents,
    direction_towards,
    flood_fill,
    nearest,
    roomiest_move,
    safe_moves,
    smaller_opponents,
)
from .observation import Board, Observation, SnakeView
from .runner import (
    GameOutcome,
    SnakeOutcome,
    baseline_names,
    evaluate,
    gauntlet_names,
    load_controller,
    play_game,
)

__version__ = ENGINE_VERSION

__all__ = [
    "Board",
    "Coord",
    "DIRECTIONS",
    "DOWN",
    "ENGINE_VERSION",
    "GameOutcome",
    "LEFT",
    "Move",
    "Observation",
    "PolicyError",
    "RIGHT",
    "SnakeController",
    "SnakeEnv",
    "SnakeError",
    "SnakeOutcome",
    "SnakeView",
    "SubmissionError",
    "UP",
    "__version__",
    "as_coord",
    "baseline_names",
    "bigger_opponents",
    "config_hash",
    "delta",
    "direction_towards",
    "evaluate",
    "flood_fill",
    "gauntlet_names",
    "load_controller",
    "nearest",
    "opposite",
    "play_game",
    "read_replay",
    "roomiest_move",
    "safe_moves",
    "smaller_opponents",
]
