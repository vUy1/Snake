"""The text protocol an external snake speaks: the course's long-standing format.

One line of numbers in, one number out. It predates this platform by several
years and students' notes, helper classes and muscle memory are all written
against it, so it is the format the engine speaks rather than a translation of
something newer.

    initialisation      4 35 35 1            snakes, width, height, mode
    every turn          the game state below, then one digit back
    end of game         Game Over

The state, one item per line::

    <appleX> <appleY>
    <your snake index, 0-3>
    <snake 0>
    <snake 1>
    <snake 2>
    <snake 3>

and a snake is::

    alive|dead  length  kills  headX,headY  kinkX,kinkY ...  tailX,tailY

**Coordinates are screen coordinates**: ``(0, 0)`` is the TOP-LEFT square and
``y`` grows downwards. The engine's own grid has its origin at the bottom left,
so every coordinate is flipped on the way out and every move is named by its
compass direction rather than by the sign of a `y`.

The coordinate chain is a compression, not a list of cells: consecutive points
are the ends of a straight run, and everything between them is body too. Only
the corners are listed.

Wrapping
--------

The board this format was written for had walls. This one is a torus, so a body
can leave one edge and arrive at the opposite one, and a chain of corners alone
cannot say whether ``34,10 0,10`` means *a run of thirty-five cells across the whole
row* or *one step through the edge*. Both are real snakes.

**A repeated coordinate is a teleport.** When the same point appears twice in a
row, the run ends there and the snake reappears at the next point listed, which
is the cell on the far edge:

    1,10  0,10  0,10  34,10  33,10
          ^^^^^^^^^^^ left the board at 0,10 and came back at 34,10

so those five points describe exactly four cells: ``(1,10) (0,10) (34,10)
(48,10)``. A point cannot repeat for any other reason - a straight run to the
cell you are already on is not a thing - so the marker is unambiguous, and a
reader that ignores the rule sees a snake thirty-five cells long instead of four.

Everything stays inside the board: no coordinate is ever negative or past the
edge, so indexing a ``board[y][x]`` array with anything from this protocol is
always safe.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[int, int]

#: The move numbers, as the course has always written them.
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
TURN_LEFT, STRAIGHT, TURN_RIGHT = 4, 5, 6

#: Compass directions clockwise, which is what a relative turn rotates through.
CLOCKWISE = ("up", "right", "down", "left")

#: Absolute move number -> the engine's name for that compass direction. The
#: engine's `+y` is north and this protocol's `+y` is south, but "up" means
#: north in both: the flip is in the coordinates, not in the names.
ABSOLUTE = {UP: "up", DOWN: "down", LEFT: "left", RIGHT: "right"}

OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


def flip_y(y: int, height: int) -> int:
    """Between the engine's bottom-left origin and this protocol's top-left one.

    Its own inverse, which is why one function serves both directions.
    """
    return height - 1 - y


def _xy(cell) -> Point:
    """`(x, y)` from a cell, however it arrives.

    The engine hands the raw board over as `{"x": .., "y": ..}` dictionaries,
    while the SDK's own `Coord` is a tuple. Both reach this module, so both are
    read here rather than at every call site.
    """
    if isinstance(cell, dict):
        return (cell["x"], cell["y"])
    return (cell[0], cell[1])


def _point(cell, height: int) -> Point:
    x, y = _xy(cell)
    return (x, flip_y(y, height))


def _dedupe(cells: Sequence) -> List[Point]:
    """Drop repeated cells.

    A body carries its tail twice on the turn a snake eats, and a repeated
    point means something specific in this format - so the duplicates have to
    go before the chain is built, or a snake would appear to teleport every
    time it ate.
    """
    out: List[Point] = []
    for cell in cells:
        point = _xy(cell)
        if not out or out[-1] != point:
            out.append(point)
    return out


def _wrapped_step(a: Point, b: Point, width: int, height: int) -> bool:
    """True when the step from `a` to `b` went through an edge."""
    return abs(a[0] - b[0]) > 1 or abs(a[1] - b[1]) > 1


def _direction(a: Point, b: Point) -> Point:
    """The unit step from `a` to `b`, for a step that did not wrap."""
    return (_sign(b[0] - a[0]), _sign(b[1] - a[1]))


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def chain(body: Sequence, width: int, height: int) -> List[Point]:
    """The coordinate chain for one body: head, every corner, the tail.

    Points are already flipped into screen coordinates. A wrap is written as
    the repeated point described in the module docstring.
    """
    cells = [_point(c, height) for c in _dedupe(body)]
    if not cells:
        return []
    if len(cells) == 1:
        return [cells[0]]

    points: List[Point] = [cells[0]]
    run_direction: Optional[Point] = None
    for i in range(1, len(cells)):
        previous, current = cells[i - 1], cells[i]
        if _wrapped_step(previous, current, width, height):
            # End the run on the cell it leaves from, say so twice, and start
            # again where the snake comes back on.
            if points[-1] != previous:
                points.append(previous)
            points.append(previous)
            points.append(current)
            run_direction = None
            continue
        step = _direction(previous, current)
        if run_direction is not None and step != run_direction:
            points.append(previous)      # a corner: the run turned here
        run_direction = step
    if points[-1] != cells[-1]:
        points.append(cells[-1])
    return points


def expand(points: Sequence[Point], width: int, height: int) -> List[Point]:
    """The inverse of :func:`chain` - every cell a chain describes.

    Here so the format has one reference reader, and so a test can prove a body
    survives the round trip rather than only that it serialises to something.
    """
    if not points:
        return []
    cells: List[Point] = [tuple(points[0])]
    i = 1
    while i < len(points):
        point = tuple(points[i])
        if point == cells[-1]:
            # Repeated point: a teleport. The next one is where it lands.
            i += 1
            if i < len(points):
                cells.append(tuple(points[i]))
                i += 1
            continue
        step = _direction(cells[-1], point)
        guard = 0
        while cells[-1] != point:
            cells.append((cells[-1][0] + step[0], cells[-1][1] + step[1]))
            guard += 1
            if guard > width * height:
                raise ValueError(f"chain never reaches {point}: {points}")
        i += 1
    return cells


def _snake_line(view, width: int, height: int, alive: bool) -> str:
    points = chain(view["body"], width, height)
    drawn = " ".join(f"{x},{y}" for x, y in points)
    status = "alive" if alive else "dead"
    return f"{status} {view['length']} {view['kills']} {drawn}".rstrip()


def initialisation(snakes: int, width: int, height: int, mode: int = 1) -> str:
    return f"{snakes} {width} {height} {mode}"


def game_state(observation, remembered: Dict[int, dict], snakes_at_start: int) -> str:
    """The whole per-turn message.

    `remembered` carries the last line seen for each snake so a dead one can
    still be described: the engine stops reporting a snake the turn it dies,
    and this format wants all four every turn.
    """
    board = observation._d["board"]
    width, height = board["width"], board["height"]

    food = board["food"]
    apple = _point(food[0], height) if food else (-1, -1)

    alive_now = {s["id"]: s for s in board["snakes"]}
    for snake_id, view in alive_now.items():
        remembered[snake_id] = view

    lines = [f"{apple[0]} {apple[1]}", str(observation.you.id)]
    for snake_id in range(snakes_at_start):
        view = alive_now.get(snake_id) or remembered.get(snake_id)
        if view is None:
            lines.append("dead 0 0")
        else:
            lines.append(_snake_line(view, width, height, snake_id in alive_now))
    return "\n".join(lines)


def heading(observation) -> str:
    """Which way the snake is pointing, as a compass direction.

    From the head and the cell behind it, so it survives a wrap: the step is
    read as the short way round rather than as the long difference.
    """
    body = observation.you.body
    if len(body) < 2:
        return "up"
    head, neck = body[0], body[1]
    width = observation.board.width
    height = observation.board.height
    dx = (head[0] - neck[0]) % width
    dy = (head[1] - neck[1]) % height
    if dx == 1:
        return "right"
    if dx == width - 1:
        return "left"
    if dy == 1:
        return "up"
    if dy == height - 1:
        return "down"
    return "up"


def decode_move(number: int, observation) -> str:
    """One of the seven move numbers, as a direction the engine understands."""
    facing = heading(observation)
    if number in ABSOLUTE:
        chosen = ABSOLUTE[number]
        # "a move that is opposite to the direction you're currently headed"
        # is not a reversal, it is a turn that never happened.
        return facing if chosen == OPPOSITE[facing] else chosen
    if number in (TURN_LEFT, STRAIGHT, TURN_RIGHT):
        if number == STRAIGHT:
            return facing
        offset = -1 if number == TURN_LEFT else 1
        return CLOCKWISE[(CLOCKWISE.index(facing) + offset) % 4]
    raise ValueError(f"a move is a number from 0 to 6, not {number}")
