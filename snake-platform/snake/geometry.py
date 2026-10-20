"""Grid geometry: coordinates and the four directions.

The board origin ``(0, 0)`` is the bottom-left cell. ``+x`` is right, ``+y`` is
up. Everything is integer — there are no half-cells.
"""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Tuple

UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"

#: The four moves you can return, in a stable order.
DIRECTIONS: Tuple[str, str, str, str] = (UP, DOWN, LEFT, RIGHT)

_DELTA: Dict[str, Tuple[int, int]] = {
    UP: (0, 1),
    DOWN: (0, -1),
    LEFT: (-1, 0),
    RIGHT: (1, 0),
}
_OPPOSITE: Dict[str, str] = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}


def opposite(direction: str) -> str:
    """The reverse of a direction. Moving there is moving onto your own neck."""
    return _OPPOSITE[direction]


def delta(direction: str) -> "Coord":
    dx, dy = _DELTA[direction]
    return Coord(dx, dy)


class Coord(tuple):
    """An ``(x, y)`` cell. A tuple subclass, so it hashes, compares and unpacks
    like one — ``x, y = coord`` works, and it is usable as a dict/set key."""

    __slots__ = ()

    def __new__(cls, x: int, y: int) -> "Coord":
        return super().__new__(cls, (int(x), int(y)))

    @property
    def x(self) -> int:
        return self[0]

    @property
    def y(self) -> int:
        return self[1]

    # -- arithmetic -----------------------------------------------------------

    def __add__(self, other: Iterable[int]) -> "Coord":  # type: ignore[override]
        ox, oy = other
        return Coord(self.x + ox, self.y + oy)

    def __sub__(self, other: Iterable[int]) -> "Coord":
        ox, oy = other
        return Coord(self.x - ox, self.y - oy)

    # -- moves --------------------------------------------------------------

    def step(self, direction: str) -> "Coord":
        """One cell in ``direction``. No wrap or bounds handling."""
        dx, dy = _DELTA[direction]
        return Coord(self.x + dx, self.y + dy)

    def neighbours(self) -> List["Coord"]:
        """The four orthogonally adjacent cells, in :data:`DIRECTIONS` order."""
        return [self.step(d) for d in DIRECTIONS]

    def manhattan(self, other: Iterable[int]) -> int:
        ox, oy = other
        return abs(self.x - ox) + abs(self.y - oy)

    def direction_to(self, other: Iterable[int]) -> str | None:
        """The direction from this cell to an adjacent one, or ``None``."""
        ox, oy = other
        step = (ox - self.x, oy - self.y)
        for name, d in _DELTA.items():
            if d == step:
                return name
        return None

    def __repr__(self) -> str:
        return f"Coord({self.x}, {self.y})"


def as_coord(value: Iterable[int]) -> Coord:
    """Accepts a ``Coord``, an ``(x, y)`` tuple/list, or a ``{"x":, "y":}``
    dict (the wire form) and returns a ``Coord``."""
    if isinstance(value, Coord):
        return value
    if isinstance(value, dict):
        return Coord(value["x"], value["y"])
    x, y = value
    return Coord(x, y)


def line(a: Coord, b: Coord) -> Iterator[Coord]:
    """Cells on the straight orthogonal/diagonal line from ``a`` to ``b``,
    inclusive. Useful for quick line-of-sight checks."""
    ax, ay = a
    bx, by = b
    steps = max(abs(bx - ax), abs(by - ay))
    if steps == 0:
        yield a
        return
    for i in range(steps + 1):
        yield Coord(round(ax + (bx - ax) * i / steps), round(ay + (by - ay) * i / steps))
