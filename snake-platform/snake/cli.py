"""``python -m snake.cli`` — play, validate and evaluate from a terminal.

Prefer buttons? ``python tools/launcher/server.py`` opens a dashboard with a
live board.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from . import ENGINE_VERSION
from .profiles import profile_path
from .runner import baseline_names, evaluate, gauntlet_names, play_game
from .validate import validate


#: The opponents a local game fills its empty seats with, best-known first.
#:
#: `benchmark` leads: it is the bar a submission is meant to clear, so it
#: should be the snake a student sees themselves against without having to ask.
DEFAULT_OPPONENTS = ["benchmark", "survivor", "hungry", "wander"]


def _roster(entrants: List[str], config_path: str | None = None) -> List[str]:
    """The entrants given, topped up to a full board with default opponents.

    `play my-snake` used to seat exactly one snake and call it a game, which is
    a strange thing to watch and tells a student nothing. Naming fewer snakes
    than the profile seats now fills the rest in rather than playing a solo.
    """
    roster = list(entrants)
    seats = _seats(config_path)
    for name in DEFAULT_OPPONENTS:
        if len(roster) >= seats:
            break
        if name not in roster:
            roster.append(name)
    return roster


def _seats(config_path: str | None) -> int:
    """How many snakes the profile seats, defaulting to four."""
    path = config_path or profile_path()
    if not path:
        return 4
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10
        import tomli as tomllib
    try:
        with open(path, "rb") as handle:
            return int(tomllib.load(handle).get("game", {}).get("snakes_per_game", 4))
    except Exception:  # noqa: BLE001 - a profile we cannot read is a four-snake game
        return 4


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snake", description=__doc__)
    parser.add_argument("--version", action="version", version=f"snake {ENGINE_VERSION}")
    sub = parser.add_subparsers(dest="command")

    p_play = sub.add_parser("play", help="play one game and print the result")
    p_play.add_argument("entrants", nargs="*", help="snake names or file.py[:Class]")
    p_play.add_argument("--seed", type=int, default=1)
    p_play.add_argument("--config", help="rule profile (default: the league's)")
    p_play.add_argument("--replay", help="record a replay to this path")
    p_play.add_argument("--wrapped", action="store_true")

    p_watch = sub.add_parser("watch", help="play a game and print every turn as ASCII")
    p_watch.add_argument("entrants", nargs="*")
    p_watch.add_argument("--seed", type=int, default=1)
    p_watch.add_argument("--config", help="rule profile (default: the league's)")

    p_eval = sub.add_parser("evaluate", help="play a seed set and aggregate")
    p_eval.add_argument("entrants", nargs="*")
    p_eval.add_argument("--seeds", default="1..25", help="e.g. 1..50 or 1,2,3")
    p_eval.add_argument("--config", help="rule profile (default: the league's)")

    p_val = sub.add_parser("validate", help="check a submission file")
    p_val.add_argument("path", help="file.py or file.py:Class")
    p_val.add_argument("--config", help="rule profile (default: the league's)")

    p_gaunt = sub.add_parser(
        "gauntlet", help="play your snake against each of the three practice opponents"
    )
    p_gaunt.add_argument("path", help="file.py or file.py:Class")
    p_gaunt.add_argument("--seeds", default="1..25")
    p_gaunt.add_argument("--config", help="rule profile (default: the league's)")
    p_gaunt.add_argument(
        "--only", type=int, metavar="N", help="play only the Nth of them (1, 2 or 3)"
    )

    sub.add_parser("baselines", help="list the reference snakes")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "baselines":
        for name in baseline_names():
            print(name)
        return 0

    if args.command == "gauntlet":
        return _gauntlet(args)

    if args.command == "validate":
        report = validate(args.path, config_path=args.config)
        print(report.text())
        return 0 if report.ok else 1

    if args.command == "play":
        outcome = play_game(
            _roster(args.entrants, args.config or profile_path()),
            seed=args.seed,
            config_path=args.config or profile_path(),
            record_replay=args.replay,
            wrapped=args.wrapped or None,
        )
        _print_game(outcome)
        if args.replay:
            print(f"replay: {args.replay}")
        return 0

    if args.command == "watch":
        frames = []
        outcome = play_game(
            _roster(args.entrants, args.config or profile_path()),
            seed=args.seed,
            config_path=args.config or profile_path(),
            on_turn=frames.append,
        )
        for snap in frames:
            _print_ascii(snap)
        _print_game(outcome)
        return 0

    if args.command == "evaluate":
        seeds = _parse_seeds(args.seeds)
        report = evaluate(
            _roster(args.entrants, args.config or profile_path()),
            seeds=seeds,
            config_path=args.config or profile_path(),
        )
        rows = sorted(report["summary"]["per_snake"], key=lambda r: r["mean_placement"])
        print(f"{'snake':<20} {'wins':>5} {'mean_pl':>8} {'mean_len':>9}")
        for r in rows:
            print(f"{r['name']:<20} {r['wins']:>5} {r['mean_placement']:>8.2f} {r['mean_final_length']:>9.1f}")
        return 0

    parser.print_help()
    return 1


#: What counts as beating one of them. A table of four ranks 1 to 4, so the
#: average finish is 2.5 - a snake that finishes above it over a seed set has
#: the better of that opponent, and one that does not has not.
CLEARED_AT = 2.5


def _gauntlet(args) -> int:
    """Your snake against each of the three, three copies of it to one of you.

    Three copies rather than one, because the league seats four and a duel
    against a single opponent is a different game - one where hiding in a
    corner works. The seeds are the same for all three, so the three are
    comparable to each other as well as to you.

    They are three opponents, not three rungs of a ladder. The numbers do not
    track strength under the league's scoring - `gauntlet_1` currently does
    best of the three - so beating them in order is not expected, and beating
    one but not another says nothing much about progress.
    """
    from .runner import load_controller

    opponents = gauntlet_names()
    if args.only:
        if not 1 <= args.only <= len(opponents):
            print(f"there are {len(opponents)} of them; --only must be 1 to {len(opponents)}")
            return 1
        opponents = [opponents[args.only - 1]]
    seeds = _parse_seeds(args.seeds)
    config = args.config or profile_path()
    mine = load_controller(args.path).name

    print(f"the gauntlet: {len(seeds)} games each, three of them to one of you")
    print(f"{'opponent':<12} {'won':>5} {'mean place':>11} {'best len':>9}")
    beaten = 0
    for opponent in opponents:
        # The three opponents are the same snake, so they are named apart -
        # a game cannot seat three snakes called `gauntlet_1` and still say
        # which of them finished where.
        names = [mine, opponent, f"{opponent}#2", f"{opponent}#3"]
        places, lengths, wins = [], [], 0
        for seed in seeds:
            outcome = play_game(
                [args.path, opponent, opponent, opponent], seed=seed, config_path=config, names=names
            )
            row = next(s for s in outcome.snakes if s.name == mine)
            places.append(row.placement)
            lengths.append(row.max_length)
            wins += 1 if row.placement == 1 else 0
        mean_place = sum(places) / len(places)
        beat = mean_place < CLEARED_AT
        beaten += 1 if beat else 0
        print(
            f"{opponent:<12} {wins:>5} {mean_place:>11.2f} "
            f"{sum(lengths) / len(lengths):>9.1f}  {'beaten' if beat else 'not yet'}"
        )
    if len(opponents) > 1:
        print(f"\nbeat {beaten} of {len(opponents)}.")
        if beaten == len(opponents):
            print("All three. Your snake is somewhere near the top of a division.")
        elif beaten == 0:
            print("None yet. The three are not ordered by strength, so there is no")
            print("gentle one to start on - the thing that beats any of them is getting")
            print("longer than they do, and that tends to beat all three at once.")
    return 0


def _parse_seeds(text: str) -> List[int]:
    if ".." in text:
        lo, hi = text.split("..")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in text.split(",") if s.strip()]


def _print_game(outcome) -> None:
    print(
        f"map {outcome.map_id}  seed {outcome.seed}  {outcome.turns} turns  ({outcome.terminal_reason})"
    )
    print(f"{'#':<3} {'snake':<20} {'turns':>6} {'len':>4} {'food':>5} {'kills':>5}  died")
    for s in outcome.snakes:
        print(
            f"{s.placement:<3} {s.name:<20} {s.last_turn:>6} {s.final_length:>4} "
            f"{s.food_eaten:>5} {s.kills:>5}  {s.death_cause or 'survived'}"
        )


_GLYPHS = "ABCDEFGHIJKLMNOP"


def _print_ascii(snap: dict) -> None:
    w, h = snap["width"], snap["height"]
    grid = [["." for _ in range(w)] for _ in range(h)]

    def put(x, y, ch):
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = ch

    for o in snap["obstacles"]:
        put(o["x"], o["y"], "#")
    for f in snap["food"]:
        put(f["x"], f["y"], "*")
    for s in snap["snakes"]:
        if not s["alive"]:
            continue
        g = _GLYPHS[s["id"] % len(_GLYPHS)]
        for i, cell in enumerate(s["body"]):
            put(cell["x"], cell["y"], g if i == 0 else g.lower())
    print(f"-- turn {snap['turn']} --")
    for row in reversed(grid):
        print("  " + "".join(row))
    print()


if __name__ == "__main__":
    sys.exit(main())
