"""Run a snake that is a separate program, over the course's text protocol.

This is how a Java or C++ snake — or a Python one you would rather run in its
own process — joins a game. The engine writes the game state to the program's
stdin and reads one number back from its stdout, within the deadline.

The wire format itself lives in :mod:`snake.legacy_wire`, which is also where
the wrapping rule is written down. See ``docs/protocol.md`` for the student
version and ``tools/protocol/clients/`` for ready skeletons.
"""

from __future__ import annotations

import os
import queue
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

from . import legacy_wire
from .controller import SnakeController
from .errors import PolicyError

#: Extra time the first move of a game is allowed, on top of the deadline.
#: This protocol has no opening handshake to hide a cold start behind, so the
#: JVM that is still unpacking itself when the first state arrives would
#: otherwise collect a timeout it did not earn. Paid once per game, not per
#: turn, and only on the first move.
STARTUP_GRACE_S = 5.0

#: Anything a snake prints after this prefix is a log line, not a move.
LOG_PREFIX = "log "

#: What a snake gets to finish up in after `Game Over`, before it is stopped.
GAME_OVER_GRACE_S = 0.5


class SubprocessSnake(SnakeController):
    """Bridges an external program to the :class:`SnakeController` interface."""

    def __init__(self, command: str, name: Optional[str] = None) -> None:
        self.command = command
        self.name = name or _first_token(command)
        self.version = "external"
        self._proc: Optional[subprocess.Popen] = None
        self._lines: "queue.Queue[Optional[str]]" = queue.Queue()
        self._reader: Optional[threading.Thread] = None
        self._started_game = False
        self._first_move = True
        #: The last line seen for each snake, so a dead one can still be
        #: described: the engine stops reporting a snake the turn it dies and
        #: this format wants all four of them every turn.
        self._remembered: Dict[int, dict] = {}
        self._log: Optional[object] = None
        self._errors: Optional[object] = None
        #: The answer to the first state, asked for in `on_start` so a cold
        #: start is not charged to the first move.
        self._pending_move: Optional[int] = None
        self._pending_turn: Optional[int] = None

    # -- process lifecycle ----------------------------------------------------

    def _spawn(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        args = command_args(self.command)
        self._open_logs(args)
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._errors or subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._lines = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._lines.put(line.strip())
        self._lines.put(None)

    def _open_logs(self, args: List[str]) -> None:
        """The two files the course promises every agent.

        "the game creates two files per agent" - an error file carrying anything
        the program writes to stderr, and a log file carrying whatever it prints
        behind `log `. For a student with no debugger on a marking machine these
        are the only way to see what their snake was thinking, so they are
        opened even when nothing ever writes to them.

        They land in the working directory rather than beside the executable.
        The course wording says "the same directory as your program", which was
        the same place when a program was one interpreted file; a Java snake is
        run as `java -cp build Snake`, whose executable is `/usr/bin/java`, and
        writing a student's log into `/usr/bin` is neither possible nor wanted.
        """
        self._close_logs()
        try:
            folder = Path.cwd()
            stem = _safe_stem(self.name)
            self._log = open(folder / f"{stem}.log", "a", encoding="utf-8", errors="replace")
            self._errors = open(folder / f"{stem}.err", "a", encoding="utf-8", errors="replace")
        except OSError:
            # A read-only drop of student work is not a reason to refuse to
            # play. Lose the logs, keep the game.
            self._log = None
            self._errors = None

    def _close_logs(self) -> None:
        for handle in (self._log, self._errors):
            try:
                if handle is not None:
                    handle.close()
            except Exception:  # noqa: BLE001
                pass
        self._log = None
        self._errors = None

    def _note(self, text: str) -> None:
        if self._log is None:
            return
        try:
            self._log.write(text + "\n")
            self._log.flush()
        except Exception:  # noqa: BLE001
            pass

    def _send(self, text: str) -> None:
        if not (self._proc and self._proc.stdin):
            raise PolicyError("external snake process is not running")
        try:
            self._proc.stdin.write(text + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise PolicyError(f"external snake closed its input: {exc}") from exc

    def _read_move(self, timeout: float) -> int:
        """The next line that is a move, with log lines taken out on the way.

        A snake is allowed to talk: `log ` lines go to its log file and are not
        answers. Anything else that is not a number is chatter on stdout, which
        the course has always said is discarded - so it is skipped too, rather
        than failing the turn for a stray `println`.
        """
        deadline_slices = 8
        for _ in range(deadline_slices):
            try:
                line = self._lines.get(timeout=timeout)
            except queue.Empty as exc:
                raise PolicyError("external snake did not answer before the deadline") from exc
            if line is None:
                raise PolicyError("external snake exited")
            line = line.strip()
            if not line:
                continue
            if line.startswith(LOG_PREFIX):
                self._note(line[len(LOG_PREFIX):])
                continue
            if line == "log":
                continue
            try:
                return int(line)
            except ValueError:
                self._note(f"[ignored, not a move] {line}")
                continue
        raise PolicyError("external snake never sent a move")

    # -- controller interface ----------------------------------------------

    def reset(self, seed: int) -> None:
        self._close()
        self._started_game = False
        self._first_move = True
        self._remembered = {}
        self._pending_move = None
        self._pending_turn = None

    def on_start(self, observation) -> None:
        """Spawn the program and send the initialisation line.

        `4 35 35 1` - snakes, width, height, mode. Nothing is read back: this
        protocol has no handshake, so the cold start is paid for by the extra
        time the first move gets instead.
        """
        self._spawn()
        snakes_at_start = int(
            observation.rules.get("snakes_at_start", len(observation.board.snakes))
        )
        self._send(
            legacy_wire.initialisation(
                snakes_at_start, observation.board.width, observation.board.height
            )
        )
        self._started_game = True
        self._first_move = True

        # The first exchange happens here, where it is not timed, and the
        # answer is kept for the `move` that follows.
        #
        # This protocol has no handshake, so there is nothing else to hide a
        # cold start behind: a JVM that is still unpacking itself when the
        # first state arrives would spend its startup inside the first move's
        # deadline and collect a timeout it did not earn. `on_start` is handed
        # the same observation `move` is about to be given, so asking here and
        # remembering the answer costs the snake nothing and charges it
        # nothing.
        self._send(legacy_wire.game_state(observation, self._remembered, snakes_at_start))
        deadline = max(0.05, observation.rules.get("_deadline_ms", 100) / 1000.0)
        try:
            self._pending_move = self._read_move(deadline + STARTUP_GRACE_S)
            self._pending_turn = observation.turn
        except PolicyError:
            # A snake that cannot answer its first state is in trouble, but the
            # game decides that, not the bridge. Fall through and let `move`
            # ask again and fail in the ordinary way.
            self._pending_move = None
            self._pending_turn = None

    def move(self, observation):
        if not self._started_game:
            self.on_start(observation)
        deadline = max(0.05, observation.rules.get("_deadline_ms", 100) / 1000.0) + 0.05
        if self._first_move:
            deadline += STARTUP_GRACE_S
            self._first_move = False
        if self._pending_move is not None and self._pending_turn == observation.turn:
            number, self._pending_move, self._pending_turn = self._pending_move, None, None
        else:
            snakes_at_start = int(
                observation.rules.get("snakes_at_start", len(observation.board.snakes))
            )
            self._send(legacy_wire.game_state(observation, self._remembered, snakes_at_start))
            number = self._read_move(deadline)
        try:
            direction = legacy_wire.decode_move(number, observation)
        except ValueError as exc:
            raise PolicyError(str(exc)) from exc
        return {"move": direction, "shout": None}

    def on_end(self, result) -> None:
        """Say the game is over, then let the program finish on its own.

        The course promises a last half-second here - "If you do not exit after
        500 milliseconds, you will be forcibly shut down" - which is what makes
        `Game Over` worth sending at all: it is the moment a snake writes out
        whatever it has been learning. Sending it and killing the process in
        the same breath would make the whole message a lie.
        """
        try:
            if self._proc and self._proc.poll() is None:
                self._send("Game Over")
                try:
                    self._proc.wait(timeout=GAME_OVER_GRACE_S)
                except subprocess.TimeoutExpired:
                    pass
        except PolicyError:
            pass
        self._close()

    def _close(self) -> None:
        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:  # noqa: BLE001
                try:
                    self._proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            self._proc = None


def command_args(command: str) -> List[str]:
    windows = sys.platform.startswith("win")
    # On Windows `shlex` must keep backslashes (they are path separators, not
    # escapes), which means posix=False - and that leaves the quotes on a
    # quoted token. Strip them here, or a path with a space in it reaches
    # CreateProcess still wearing its quotes and cannot be found.
    args = shlex.split(command, posix=not windows)
    if windows:
        args = [_unquote(a) for a in args]
    if args and (os.sep in args[0] or "/" in args[0]):
        # A relative program path: normalise separators and make it absolute so
        # CreateProcess / execvp can find it regardless of the working dir.
        candidate = os.path.normpath(args[0])
        # `isfile`, not `exists`: `cmd:./snake` next to the SDK's own `snake/`
        # package would otherwise resolve to the directory, and CreateProcess
        # answers that with a bare "access denied".
        # The `.exe` pass is because `g++ -o snake` writes `snake.exe` on
        # Windows, so the command a student is told to run names a file that is
        # not quite there.
        for suffix in ("", ".exe") if windows else ("",):
            if os.path.isfile(candidate + suffix):
                args[0] = os.path.abspath(candidate + suffix)
                break
    return args


def _unquote(arg: str) -> str:
    if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "\"'":
        return arg[1:-1]
    return arg


def _safe_stem(name: str) -> str:
    """A file name from a snake's name, for its two log files."""
    kept = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    return kept.strip("._") or "snake"


def _first_token(command: str) -> str:
    try:
        return shlex.split(command)[0].rsplit("/", 1)[-1]
    except Exception:  # noqa: BLE001
        return command.split()[0]
