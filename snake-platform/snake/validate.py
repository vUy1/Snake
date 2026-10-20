"""Check a submission before you upload it.

``snake validate my-snake/snake.py`` runs this. It loads the file the marker
would load, plays a few games with it under the league's own profile, and
reports timeouts, crashes and illegal moves — everything that would cost
placement in the league.

A move that never returns is reported too, and separately: the league does not
wait for it either (see :mod:`snake.deadline`), so a snake that loops forever
does not hang the marker — it forfeits, game after game, all season. That is a
failure worth naming rather than counting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .profiles import profile_path
from .runner import baseline_names, load_controller, play_game


@dataclass
class ValidationReport:
    ok: bool
    controller: str = ""
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def text(self) -> str:
        lines = [f"submission: {self.controller}"]
        for n in self.notes:
            lines.append(f"  - {n}")
        for w in self.warnings:
            lines.append(f"  ! {w}")
        for e in self.errors:
            lines.append(f"  x {e}")
        lines.append("PASS" if self.ok else "FAIL")
        return "\n".join(lines)


def validate(
    spec: str,
    opponents: List[str] | None = None,
    seeds: List[int] | None = None,
    config_path: str | None = None,
) -> ValidationReport:
    opponents = opponents or ["benchmark", "survivor", "hungry"]
    seeds = seeds or [1, 2, 3]
    # Check against the profile the league marks on, not the engine default.
    config_path = config_path or profile_path()
    report = ValidationReport(ok=True)

    try:
        controller = load_controller(spec)
    except Exception as exc:  # noqa: BLE001
        report.ok = False
        report.errors.append(f"could not load: {exc}")
        return report

    report.controller = controller.describe()
    if controller.name == "unnamed_snake":
        report.warnings.append("set a `name` on your controller so results identify it")

    total_decisions = 0
    total_failures = 0
    total_reversals = 0
    total_stalls = 0
    for seed in seeds:
        try:
            outcome = play_game([controller, *opponents], seed=seed, config_path=config_path)
        except Exception as exc:  # noqa: BLE001
            report.ok = False
            report.errors.append(f"seed {seed}: game crashed: {exc}")
            continue
        me = next((s for s in outcome.result["snakes"] if s["name"] == controller.name), None)
        if me is None:
            report.errors.append(f"seed {seed}: snake not found in result")
            report.ok = False
            continue
        total_decisions += me["decisions"]
        total_failures += me["failed_decisions"]
        total_reversals += me["reversals"]
        stalled = outcome.stalls.get(controller.name, 0)
        total_stalls += stalled
        # A stall is already counted among the timeouts - it is a move that
        # overran by every measure - so only the remainder is reported as one.
        late = me["timeouts"] - stalled
        if late > 0:
            report.warnings.append(f"seed {seed}: {late} move(s) over the time limit")
        if me["errors"]:
            report.ok = False
            report.errors.append(f"seed {seed}: {me['errors']} move(s) raised an exception")
        report.notes.append(
            f"seed {seed}: placed {me['placement']}/{len(outcome.snakes)}, "
            f"{me['last_turn']} turns, length {me['final_length']}"
        )

    if total_stalls:
        report.ok = False
        report.errors.append(
            f"{total_stalls} call(s) never returned — most likely a loop in `move` "
            "with no way out of it (`on_start` and `reset` are timed too). The "
            "league does not wait either: three of these in a row and your snake "
            "forfeits that game."
        )
    if total_decisions:
        rate = total_failures / total_decisions
        report.notes.append(f"failure rate: {rate:.1%} ({total_failures}/{total_decisions})")
        if rate > 0.05:
            report.ok = False
            report.errors.append("more than 5% of moves failed — fix before uploading")
    if total_reversals:
        report.warnings.append(
            f"{total_reversals} move(s) tried to reverse into your own neck (instant death)"
        )
    return report
