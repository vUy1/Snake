"""Turning a move that never comes back into a move that is merely late.

A submission is ordinary Python, called in this process, and ordinary Python
can loop forever:

    def move(self, obs):
        while True:            # a typo, a missing decrement, a bad `while`
            ...

Nothing in the engine can stop that. The engine already has a failure policy —
a move that overruns ``per_move_timeout_ms`` counts a failure, and
``max_consecutive_failures`` in a row forfeits the snake — but it only ever
sees the moves that *return*. A call that does not return is not a slow move;
it is a game that never finishes, a worker that never comes back, and a season
that stops on one student's typo.

So every controller call goes through a :class:`MoveClock`. The call runs on a
worker thread and the game waits on it for a **hard limit**, generously longer
than the profile's deadline: the deadline decides whether a move was late, and
the hard limit decides how long we are willing to find out. A call that misses
the hard limit is *abandoned* — reported to the engine as a timeout, which is
what it is, so the usual forfeit rule ends the snake's game after
``max_consecutive_failures`` of them and the game plays on without it.

An abandoned call is also asked to stop, with the interpreter's own
asynchronous exception (:func:`interrupt`). That reaches any loop running
Python bytecode, which is what a student's runaway ``while`` is. It cannot
reach a thread parked inside C — ``time.sleep(1e9)``, a blocking read — so the
thread is dropped rather than waited for, and the next call gets a fresh one.
There are at most ``max_consecutive_failures`` of those per snake per game,
because the snake is forfeited after that and never asked again.

None of this is a sandbox. It bounds *time*, and only time.
"""

from __future__ import annotations

import ctypes
import queue
import threading
import time
from typing import Any, Callable, Optional, Tuple

#: Hard limit as a multiple of the profile's per-move deadline. Wide on
#: purpose: a move that takes twice its deadline is already a failed move by
#: the engine's reckoning and needs no help from here. What this number bounds
#: is the pathological case — the move that is not late but absent — and
#: bounding it at ten deadlines costs a runaway snake about
#: `max_consecutive_failures` times that, once, at the end of its game.
HARD_LIMIT_FACTOR = 10.0

#: Floor for the hard limit, for profiles with a very short deadline. A hung
#: call is rare and a spurious abandonment is not: nothing is gained by being
#: quick to give up.
HARD_LIMIT_FLOOR_S = 0.5

#: What `on_start`, `reset` and `on_end` get. They are not timed against the
#: move deadline — a controller may spend real time setting itself up, and an
#: external program may be starting a JVM — but they are not allowed to hang.
SETUP_LIMIT_S = 10.0


class Abandoned(Exception):
    """Raised inside a call that overran its hard limit.

    A student's ``except Exception`` will, of course, catch it — at which point
    the thread carries on and is simply never waited on again.
    """


def interrupt(thread: threading.Thread) -> bool:
    """Ask `thread` to raise :class:`Abandoned` at its next bytecode.

    The documented use of ``PyThreadState_SetAsyncExc``. Returns whether the
    exception was planted; there is no way to make it *arrive*, and a thread
    blocked inside C will not see it until it returns to Python.
    """
    ident = thread.ident
    if ident is None or not thread.is_alive():
        return False
    try:
        set_async = ctypes.pythonapi.PyThreadState_SetAsyncExc
        set_async.argtypes = (ctypes.c_ulong, ctypes.py_object)
        planted = set_async(ctypes.c_ulong(ident), ctypes.py_object(Abandoned))
    except Exception:  # noqa: BLE001 — an interpreter without that C API
        return False
    if planted > 1:  # planted on more than one thread: undo it
        set_async(ctypes.c_ulong(ident), None)
        return False
    return planted == 1


class MoveClock:
    """One snake's calls, each bounded in wall-clock time.

    :meth:`call` returns ``(value, elapsed_ms, error)``. ``error`` is a string
    when the call raised and ``None`` otherwise; a call that was abandoned
    comes back as ``(None, elapsed_ms, None)`` with ``elapsed_ms`` well past
    the deadline, which is exactly how the engine reads a timeout.
    """

    def __init__(
        self,
        limit_ms: float = 100.0,
        factor: float = HARD_LIMIT_FACTOR,
        floor_s: float = HARD_LIMIT_FLOOR_S,
        label: str = "snake",
    ) -> None:
        self.limit_ms = float(limit_ms)
        self.hard_limit_s = max(floor_s, self.limit_ms / 1000.0 * factor)
        self.label = label
        #: How many calls never came back. Worth quoting in a report on its
        #: own: "three moves timed out" and "three moves never returned" are
        #: different problems behind the same forfeit.
        self.abandoned = 0
        self._jobs: "queue.Queue" = queue.Queue()
        self._done: "queue.Queue" = queue.Queue()
        self._retired = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- the worker -------------------------------------------------------

    @staticmethod
    def _serve(jobs: "queue.Queue", done: "queue.Queue", retired: threading.Event) -> None:
        while not retired.is_set():
            job = jobs.get()
            if job is None:
                return
            fn, args, kwargs = job
            try:
                done.put((fn(*args, **kwargs), None))
            except BaseException as exc:  # noqa: BLE001 — Abandoned included
                done.put((None, exc))
        # Abandoned, and the call has come back after all. Nobody is reading
        # this queue any more and there will be no further work on it, so the
        # thread ends here rather than parking on a queue nothing will fill.

    def _ensure_worker(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._retired = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            args=(self._jobs, self._done, self._retired),
            name=f"snake-move[{self.label}]",
            daemon=True,
        )
        self._thread.start()

    def _abandon(self) -> None:
        """Give up on the running call and start again with a fresh thread.

        The queues go with the thread. A call that finishes after we stopped
        waiting would otherwise leave its answer in front of the *next* turn's,
        and answering turn 40 with turn 39's move is worse than not answering.
        """
        lost, self._thread = self._thread, None
        self._retired.set()
        self._jobs, self._done = queue.Queue(), queue.Queue()
        self.abandoned += 1
        if lost is not None:
            interrupt(lost)

    # -- calling ----------------------------------------------------------

    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        limit_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Tuple[Any, float, Optional[str]]:
        limit = self.hard_limit_s if limit_s is None else limit_s
        self._ensure_worker()
        started = time.perf_counter()
        self._jobs.put((fn, args, kwargs))
        try:
            value, error = self._done.get(timeout=limit)
        except queue.Empty:
            self._abandon()
            return None, (time.perf_counter() - started) * 1000.0, None
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if error is not None:
            return None, elapsed_ms, f"{type(error).__name__}: {error}"
        return value, elapsed_ms, None

    def setup(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Optional[str]:
        """Run `fn` under the setup allowance. Returns an error, or None.

        A setup call that hangs is reported as one: unlike a move there is no
        turn to lose and no forfeit rule to lean on, so the caller is told.
        """
        before = self.abandoned
        _value, _ms, error = self.call(fn, *args, limit_s=SETUP_LIMIT_S, **kwargs)
        if self.abandoned > before:
            return f"did not return within {SETUP_LIMIT_S:.0f}s"
        return error

    def close(self) -> None:
        """Retire the worker. A thread still running is left alone — it is a
        daemon, and it has already been asked to stop."""
        thread, self._thread = self._thread, None
        if thread is None:
            return
        self._jobs.put(None)
        thread.join(timeout=0.25)

    def __enter__(self) -> "MoveClock":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        self.close()
        return False
