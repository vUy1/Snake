"""Small decision helpers built on :class:`~snake.observation.Observation`.

None of these decide for you — they are the arithmetic you would otherwise
rewrite. ``safe_moves`` is the usual first line of a ``move`` method.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .geometry import DIRECTIONS, Coord
from .observation import Observation, SnakeView


def safe_moves(obs: Observation, avoid_head_to_head: bool = True) -> List[str]:
    """Directions that do not walk into a wall or a body this turn, and —
    when ``avoid_head_to_head`` — do not step beside an equal-or-longer
    opponent's head, where a head-to-head could be lost.

    May be empty: sometimes every option is bad and you pick the least bad one.
    """
    head = obs.you.head
    out = []
    for d in DIRECTIONS:
        cell = obs.step(head, d)
        if not obs.is_free(cell):
            continue
        if avoid_head_to_head and _loses_head_to_head(obs, cell):
            continue
        out.append(d)
    return out


def _loses_head_to_head(obs: Observation, cell: Coord) -> bool:
    for opp in obs.opponents:
        if not opp.alive:
            continue
        if opp.length >= obs.you.length and obs.distance(opp.head, cell) == 1:
            return True
    return False


def direction_towards(obs: Observation, target: Coord, among: Optional[List[str]] = None) -> Optional[str]:
    """Of ``among`` (or all safe moves), the one that steps closest to
    ``target``. ``None`` if none get closer."""
    options = among if among is not None else safe_moves(obs)
    head = obs.you.head
    current = obs.distance(head, target)
    closer = [d for d in options if obs.distance(obs.step(head, d), target) < current]
    if not closer:
        return None
    return max(closer, key=lambda d: obs.reachable_area(obs.step(head, d), 400))


def roomiest_move(obs: Observation, among: Optional[List[str]] = None) -> Optional[str]:
    """The move leaving the most reachable free space next turn."""
    options = among if among is not None else safe_moves(obs)
    if not options:
        return None
    head = obs.you.head
    return max(options, key=lambda d: obs.reachable_area(obs.step(head, d), 512))


def nearest(frm: Coord, cells: List[Coord]) -> Optional[Coord]:
    if not cells:
        return None
    return min(cells, key=lambda c: frm.manhattan(c))


def flood_fill(obs: Observation, start: Coord, limit: int = 10_000) -> int:
    """Alias for :meth:`Observation.reachable_area`, the name students expect."""
    return obs.reachable_area(start, limit)


def bigger_opponents(obs: Observation) -> List[SnakeView]:
    return [o for o in obs.opponents if o.alive and o.length >= obs.you.length]


def smaller_opponents(obs: Observation) -> List[SnakeView]:
    return [o for o in obs.opponents if o.alive and o.length < obs.you.length]
