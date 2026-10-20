"""The coursework interface.

Subclass :class:`SnakeController` and implement ``move``. It is called once per
turn with an :class:`~snake.observation.Observation` and must return a direction
— ``"up"``, ``"down"``, ``"left"`` or ``"right"`` — or a
:class:`~snake.actions.Move`.

    from snake import SnakeController, Move

    class MySnake(SnakeController):
        name = "my_snake"

        def move(self, obs):
            safe = obs.free_directions()
            return safe[0] if safe else "up"
"""

from __future__ import annotations

from typing import Any, Dict, Union

from .actions import Move
from .observation import Observation

Decision = Union[str, Move]


class SnakeController:
    """Base class for a snake.

    Override ``move``. Optionally override ``on_start`` / ``on_end`` for
    per-game setup and teardown, and set ``name`` / ``version`` so results
    identify your snake. ``colour`` is cosmetic — the viewer uses it if set.
    """

    name: str = "unnamed_snake"
    version: str = "1"
    colour: str = ""

    def move(self, observation: Observation) -> Decision:
        """Decide this turn's move. Called every turn until you are eliminated."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement move(self, observation)"
        )

    def on_start(self, observation: Observation) -> None:
        """Called once, before the first move, with the opening position."""

    def on_end(self, result: Dict[str, Any]) -> None:
        """Called once after the game, with this game's result record."""

    def reset(self, seed: int) -> None:
        """Called before each game when reused across a seed set. Clear state."""

    def describe(self) -> str:
        return f"{self.name} v{self.version} ({type(self).__name__})"
