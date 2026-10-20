"""What a controller returns each turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .geometry import DOWN, LEFT, RIGHT, UP


@dataclass
class Move:
    """One turn's decision: a direction, and an optional shout.

    You can also just return the bare string ``"up"`` from ``move`` — the runner
    accepts either. ``direction`` of ``None`` means "no decision", and the
    engine keeps your current heading (but it still counts as a missed move).
    """

    direction: Optional[str] = None
    shout: Optional[str] = None

    @staticmethod
    def up(shout: Optional[str] = None) -> "Move":
        return Move(UP, shout)

    @staticmethod
    def down(shout: Optional[str] = None) -> "Move":
        return Move(DOWN, shout)

    @staticmethod
    def left(shout: Optional[str] = None) -> "Move":
        return Move(LEFT, shout)

    @staticmethod
    def right(shout: Optional[str] = None) -> "Move":
        return Move(RIGHT, shout)

    def to_payload(self) -> dict:
        return {"move": self.direction, "shout": self.shout}
