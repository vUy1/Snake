"""Run games and seed sets from Python.

Entrants are given by name and resolved in this order:

* a reference snake name (``"survivor"``, ``"hungry"``, …) — run natively;
* ``path/to/file.py`` or ``path/to/file.py:ClassName`` — a submission file;
* a :class:`~snake.controller.SnakeController` subclass or instance.

A roster may mix all three. Native snakes decide inside the engine; Python ones
are stepped here, timed against the profile's per-move deadline — and bounded
by a hard limit above it, so a move that never returns ends that snake's game
rather than the game itself. See :mod:`snake.deadline`.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from . import _engine as _native
from .controller import SnakeController
from .deadline import MoveClock
from .env import SnakeEnv
from .errors import SubmissionError
from .observation import Observation

Entrant = Union[str, SnakeController, type]


def baseline_names() -> List[str]:
    """The reference snakes you can name as opponents."""
    return list(_native.baseline_names())


def gauntlet_names() -> List[str]:
    """The practice ladder, weakest rung first.

    Three opponents of rising strength, each strictly a better player than the
    one below it. They live in the engine rather than in this package, which is
    the point of them: the ladder ships as a compiled binary, so it can be
    played as often as you like and not read. Read the others instead - they
    are in `examples/`, and they are meant to be.
    """
    return sorted(n for n in baseline_names() if n.startswith("gauntlet_"))


@dataclass
class SnakeOutcome:
    name: str
    placement: int
    survived: bool
    final_length: int
    max_length: int
    food_eaten: int
    kills: int
    last_turn: int
    death_cause: Optional[str]


@dataclass
class GameOutcome:
    seed: int
    map_id: str
    turns: int
    terminal_reason: str
    snakes: List[SnakeOutcome]
    replay_path: Optional[str]
    result: Dict[str, Any]
    #: Per snake, how many calls never came back at all - a move still running
    #: when the engine stopped waiting. Counted separately from the timeouts in
    #: `result`, which are moves that were merely late. See `snake.deadline`.
    stalls: Dict[str, int] = field(default_factory=dict)

    @property
    def winner(self) -> Optional[str]:
        firsts = [s for s in self.snakes if s.placement == 1]
        return firsts[0].name if len(firsts) == 1 else None

    def placement_of(self, name: str) -> Optional[int]:
        return next((s.placement for s in self.snakes if s.name == name), None)


# ---------------------------------------------------------------------------
# resolving entrants
# ---------------------------------------------------------------------------

def _split_spec(spec: str):
    """Split ``path[:Class]``, leaving a Windows drive letter alone.

    ``C:\\subs\\alice\\snake.py`` has a colon in it and no class; splitting on
    the first colon would look for a file called ``C``.
    """
    head, sep, tail = spec.rpartition(":")
    if sep and len(head) > 1 and tail.isidentifier():
        return head, tail
    return spec, ""


def load_controller(spec: Union[str, SnakeController, type]) -> SnakeController:
    """Turns a ``file.py[:Class]`` spec, a class, or an instance into a
    ready :class:`SnakeController`."""
    if isinstance(spec, SnakeController):
        return spec
    if isinstance(spec, type) and issubclass(spec, SnakeController):
        return spec()
    if not isinstance(spec, str):
        raise SubmissionError(f"cannot load a controller from {spec!r}")

    if spec.startswith("cmd:"):
        from .protocol import SubprocessSnake

        return SubprocessSnake(spec[4:])

    path_part, class_part = _split_spec(spec)
    path = Path(path_part)
    if not path.exists():
        raise SubmissionError(f"no such file: {path}")
    module_name = f"_snake_submission_{path.stem}_{abs(hash(str(path.resolve())))}"
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise SubmissionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import-time error
        raise SubmissionError(f"{path} failed to import: {exc}") from exc

    if class_part:
        obj = getattr(module, class_part, None)
        if obj is None:
            raise SubmissionError(f"{path} has no attribute {class_part!r}")
        candidates = [obj]
    else:
        candidates = [
            v
            for v in vars(module).values()
            if isinstance(v, type)
            and issubclass(v, SnakeController)
            and v is not SnakeController
        ]
    if not candidates:
        raise SubmissionError(
            f"{path} defines no SnakeController subclass. Did you subclass it?"
        )
    if len(candidates) > 1 and not class_part:
        names = ", ".join(c.__name__ for c in candidates)
        raise SubmissionError(
            f"{path} defines several controllers ({names}); name one with file.py:Class"
        )
    return candidates[0]()


def _classify(entrant: Entrant):
    if isinstance(entrant, str) and entrant in baseline_names():
        return ("native", entrant)
    return ("python", load_controller(entrant))


def _tell_deadline(observation: Observation, deadline_ms: float) -> None:
    """Put the profile's per-move deadline where a controller can read it.

    `obs.rules` is the engine's rule block, and the deadline is not one of the
    game's rules - it is a property of the run. It goes in under a leading
    underscore for that reason: visible to anything that wants to size its own
    clock, and marked as not part of the game.
    """
    observation.rules["_deadline_ms"] = deadline_ms


# ---------------------------------------------------------------------------
# playing
# ---------------------------------------------------------------------------

def play_game(
    entrants: Sequence[Entrant],
    seed: int = 1,
    config_path: Optional[str] = None,
    record_replay: Optional[str] = None,
    wrapped: Optional[bool] = None,
    on_turn=None,
    names: Optional[Sequence[str]] = None,
) -> GameOutcome:
    """Play one game. ``entrants`` length sets ``snakes_per_game``. ``names``,
    if given, overrides every snake's display name positionally — the league
    uses it to keep each entrant's identity stable across games."""
    kinds = [_classify(e) for e in entrants]
    default_names = [obj if kind == "native" else obj.name for kind, obj in kinds]
    display_names = list(names) if names is not None else default_names

    env = SnakeEnv(
        config_path=config_path,
        snakes_per_game=len(entrants),
        names=display_names,
        seed=seed,
        record_replay=record_replay,
        wrapped=wrapped,
    )
    # The profile's per-move deadline, which every controller is entitled to
    # know: an external one sizes its own read on it (see `snake.protocol`),
    # and the clock below sizes the hard limit on it.
    deadline_ms = float(env.config()["evaluation"]["per_move_timeout_ms"])

    py_controllers: Dict[int, SnakeController] = {}
    clocks: Dict[int, MoveClock] = {}
    for sid, (kind, obj) in enumerate(kinds):
        if kind == "native":
            env.use_baseline(sid, obj, display=display_names[sid])
        else:
            obj.name = display_names[sid]
            py_controllers[sid] = obj
            clocks[sid] = MoveClock(deadline_ms, label=display_names[sid])
            clocks[sid].setup(obj.reset, seed)

    obs = env.reset(seed)
    for sid, controller in py_controllers.items():
        if sid in obs:
            _tell_deadline(obs[sid], deadline_ms)
            clocks[sid].setup(controller.on_start, obs[sid])

    while not env.finished:
        moves: Dict[int, Any] = {}
        for sid, observation in obs.items():
            controller = py_controllers.get(sid)
            if controller is None:
                continue  # native snake, decided inside the engine
            _tell_deadline(observation, deadline_ms)
            # A move that overruns the deadline is late; one that overruns the
            # clock's hard limit is gone, and comes back here as a timeout with
            # nothing to play. Either way the engine's forfeit rule decides
            # what it costs - see `snake.deadline`.
            decision, elapsed_ms, err = clocks[sid].call(controller.move, observation)
            env.record_decision(sid, elapsed_ms, err)
            if err is None and decision is not None:
                moves[sid] = decision
        obs, _done = env.step(moves)
        if on_turn is not None:
            on_turn(env.snapshot())

    result = env.result()
    for sid, controller in py_controllers.items():
        clocks[sid].setup(controller.on_end, result)
    stalls = {display_names[sid]: c.abandoned for sid, c in clocks.items() if c.abandoned}
    for clock in clocks.values():
        clock.close()
    env.close()

    snakes = [
        SnakeOutcome(
            name=s["name"],
            placement=s["placement"],
            survived=s["survived"],
            final_length=s["final_length"],
            max_length=s.get("max_length", s["final_length"]),
            food_eaten=s["food_eaten"],
            kills=s["kills"],
            last_turn=s["last_turn"],
            death_cause=(s["death_cause"] or {}).get("kind") if s["death_cause"] else None,
        )
        for s in result["snakes"]
    ]
    return GameOutcome(
        seed=seed,
        map_id=result["map_id"],
        turns=result["turns"],
        terminal_reason=result["terminal_reason"],
        snakes=snakes,
        replay_path=result.get("replay_path"),
        result=result,
        stalls=stalls,
    )


def evaluate(
    entrants: Sequence[Entrant],
    seeds: Sequence[int] = range(1, 26),
    config_path: Optional[str] = None,
    record_replays: str = "never",
    replay_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Play every seed and aggregate. Uses the native fast path when the whole
    roster is reference snakes, otherwise loops in this process."""
    seeds = list(seeds)
    if all(isinstance(e, str) and e in baseline_names() for e in entrants):
        return _native.evaluate_baselines(
            list(entrants),
            seeds,
            None,
            config_path,
            None,
            record_replays,
            replay_dir,
        )

    games = []
    for i, seed in enumerate(seeds):
        replay = None
        if replay_dir and (record_replays == "always" or (record_replays != "never" and i < 3)):
            replay = str(Path(replay_dir) / f"seed-{seed}.rep")
        games.append(play_game(entrants, seed=seed, config_path=config_path, record_replay=replay))

    # Aggregate placements per name.
    agg: Dict[str, Dict[str, float]] = {}
    for g in games:
        for s in g.snakes:
            row = agg.setdefault(
                s.name, {"games": 0, "wins": 0, "mean_placement": 0.0, "mean_final_length": 0.0}
            )
            row["games"] += 1
            row["wins"] += 1 if s.placement == 1 else 0
            row["mean_placement"] += s.placement
            row["mean_final_length"] += s.final_length
    for row in agg.values():
        if row["games"]:
            row["mean_placement"] /= row["games"]
            row["mean_final_length"] /= row["games"]
    return {
        "games": [g.result for g in games],
        "summary": {"per_snake": [{"name": k, **v} for k, v in agg.items()]},
    }
