"""What you can see before you move.

An :class:`Observation` reports the board — every snake's body, the food, the
the walls — and the fixed rules. It does **not** tell you where
to go, which food to contest, who is a threat or whether a gap is a trap. Those
are decisions, and writing them is the assignment.

The flood-fill and pathing helpers here call into the engine so a reference
snake and your submission compute "how much space is through that gap" from the
same code.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterator, List, Optional

from .geometry import DIRECTIONS, Coord, as_coord


class SnakeView:
    """One snake on the board, you or an opponent."""

    def __init__(self, data: dict) -> None:
        self._d = data
        self.id: int = data["id"]
        self.name: str = data["name"]
        self.length: int = data["length"]
        self.alive: bool = data["alive"]
        self.shout: Optional[str] = data.get("shout")
        self.latency_ms: float = data.get("latency_ms", 0.0)
        self.body: List[Coord] = [as_coord(c) for c in data["body"]]

    @property
    def head(self) -> Coord:
        return self.body[0]

    @property
    def tail(self) -> Coord:
        return self.body[-1]

    def __repr__(self) -> str:
        return f"SnakeView(id={self.id}, name={self.name!r}, len={self.length})"


class Board:
    def __init__(self, data: dict) -> None:
        self.width: int = data["width"]
        self.height: int = data["height"]
        self.wrapped: bool = data["wrapped"]
        self.food: List[Coord] = [as_coord(c) for c in data["food"]]
        self.obstacles: List[Coord] = [as_coord(c) for c in data["obstacles"]]
        self.snakes: List[SnakeView] = [SnakeView(s) for s in data["snakes"]]


class Observation:
    """The whole picture for one snake on one turn."""

    def __init__(self, data: dict) -> None:
        self._d = data
        self.turn: int = data["turn"]
        self.max_turns: int = data["max_turns"]
        self.you: SnakeView = SnakeView(data["you"])
        self.board: Board = Board(data["board"])
        self.rules: dict = data["rules"]
        self.events: List[dict] = data.get("events", [])
        # Fast membership sets, built once.
        self._bodies = {c for s in self.board.snakes for c in s.body}
        self._obstacles = set(self.board.obstacles)
        self._food = set(self.board.food)

    # -- other snakes -----------------------------------------------------

    @property
    def opponents(self) -> List[SnakeView]:
        return [s for s in self.board.snakes if s.id != self.you.id]

    def snake(self, snake_id: int) -> Optional[SnakeView]:
        return next((s for s in self.board.snakes if s.id == snake_id), None)

    # -- geometry -------------------------------------------------------------

    def step(self, cell: Coord, direction: str) -> Coord:
        """One cell in ``direction`` from ``cell``, wrapping if this board does."""
        nxt = cell.step(direction)
        if self.board.wrapped:
            return Coord(nxt.x % self.board.width, nxt.y % self.board.height)
        return nxt

    def in_bounds(self, cell: Coord) -> bool:
        if self.board.wrapped:
            return True
        return 0 <= cell.x < self.board.width and 0 <= cell.y < self.board.height

    def is_wall(self, cell: Coord) -> bool:
        return cell in self._obstacles

    def is_food(self, cell: Coord) -> bool:
        return cell in self._food

    def is_snake(self, cell: Coord) -> bool:
        return cell in self._bodies

    def is_free(self, cell: Coord) -> bool:
        """Nothing static blocks this cell right now: on the board, no wall, no
        snake body. Says nothing about where snakes will move next."""
        return self.in_bounds(cell) and cell not in self._obstacles and cell not in self._bodies

    def free_directions(self, cell: Optional[Coord] = None) -> List[str]:
        """Directions from ``cell`` (your head by default) onto a free cell."""
        start = self.you.head if cell is None else cell
        return [d for d in DIRECTIONS if self.is_free(self.step(start, d))]

    def distance(self, a: Coord, b: Coord) -> int:
        """Manhattan distance, wrap-aware on a wrapped board."""
        if not self.board.wrapped:
            return a.manhattan(b)
        dx = abs(a.x - b.x)
        dy = abs(a.y - b.y)
        return min(dx, self.board.width - dx) + min(dy, self.board.height - dy)

    # -- classic helpers ---------------------------------------------------

    def nearest_food(self, frm: Optional[Coord] = None) -> Optional[Coord]:
        start = self.you.head if frm is None else frm
        if not self.board.food:
            return None
        return min(self.board.food, key=lambda f: self.distance(start, f))

    def reachable_area(self, start: Coord, limit: int = 10_000) -> int:
        """Free cells reachable from ``start`` by orthogonal steps, capped at
        ``limit``. Run it on each candidate next cell and pick the roomiest —
        the standard "am I about to wall myself in?" check.

        ``start`` counts even if a body sits on it now (so you can flood from
        your own head); expansion only enters currently-free cells.
        """
        if not self.in_bounds(start) or start in self._obstacles:
            return 0
        seen = {start}
        q = deque([start])
        while q and len(seen) < limit:
            cell = q.popleft()
            for d in DIRECTIONS:
                nxt = self.step(cell, d)
                if nxt not in seen and self.is_free(nxt):
                    seen.add(nxt)
                    q.append(nxt)
        return len(seen)

    def shortest_path(self, start: Coord, goal: Coord, max_nodes: int = 4000) -> Optional[List[Coord]]:
        """A breadth-first path of free cells from ``start`` to ``goal``,
        or ``None`` if there is none. Returns the cells including both ends."""
        if start == goal:
            return [start]
        seen = {start}
        q: deque = deque([(start, [start])])
        while q and len(seen) < max_nodes:
            cell, path = q.popleft()
            for d in DIRECTIONS:
                nxt = self.step(cell, d)
                if nxt == goal:
                    return path + [nxt]
                if nxt not in seen and self.is_free(nxt):
                    seen.add(nxt)
                    q.append((nxt, path + [nxt]))
        return None

    def __repr__(self) -> str:
        return (
            f"Observation(turn={self.turn}, you={self.you.name!r} "
            f"len={self.you.length}, "
            f"opponents={len(self.opponents)})"
        )
