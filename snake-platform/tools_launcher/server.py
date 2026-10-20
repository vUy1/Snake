"""Local dashboard and browser viewer for the snake platform.

    python tools/launcher/server.py         # opens http://127.0.0.1:8795

No framework, no build step — the standard library only. Games run in a
background thread; the browser watches them over Server-Sent Events. Replays are
read straight from the engine.
"""

from __future__ import annotations

import http.server
import errno
import json
import shutil
import subprocess
import queue
import socketserver
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snake import baseline_names, read_replay  # noqa: E402
from snake.profiles import LEAGUE_PROFILE  # noqa: E402
from snake.runner import play_game  # noqa: E402

try:
    import tomllib  # noqa: E402
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore  # noqa: E402

HERE = Path(__file__).resolve().parent
PORT = 8795
REPLAY_DIR = ROOT / "replays"
CONFIG_DIR = ROOT / "configs"
SUBMISSION_DIR = ROOT / "tools" / "evaluator" / "submissions"

#: The student's own snake, and where its class files go. Named `my-snake` on
#: every surface so the dashboard, the roster and the error messages all call
#: it the same thing.
MY_SNAKE = "my-snake"
MY_SNAKE_DIR = ROOT / "my-snake"
MY_SNAKE_BUILD = ROOT / ".build" / "my-snake"

# game_id -> {"queue": Queue, "done": bool, "error": str | None, "frames": list}
GAMES: dict[str, dict] = {}
GAMES_LOCK = threading.Lock()


def my_snake_sources() -> list[Path]:
    """Every `.java` in `my-snake/`, or nothing if there is no snake there."""
    if not MY_SNAKE_DIR.is_dir():
        return []
    return sorted(p for p in MY_SNAKE_DIR.glob("*.java") if p.is_file())


def my_snake_spec() -> str:
    """Compile `my-snake/` if it needs it and return the command to run it.

    The dashboard seats the student's own snake by default, which means it has
    to be runnable without them having compiled anything first - the point is
    to unzip, start, and watch your snake play. Recompiled only when a source
    is newer than the class files, so a refresh is not a rebuild.

    Raises `RuntimeError` with the compiler's own message when it will not
    build; `_run_game` turns that into the error the page shows.
    """
    sources = my_snake_sources()
    if not sources:
        raise RuntimeError(
            f"no snake found: {MY_SNAKE_DIR} has no .java files in it"
        )
    entry = MY_SNAKE_DIR / "Snake.java"
    if not entry.is_file():
        raise RuntimeError(
            f"{MY_SNAKE_DIR} has no Snake.java - that is the file the game runs"
        )

    newest = max(p.stat().st_mtime for p in sources)
    built = MY_SNAKE_BUILD / "Snake.class"
    if not built.is_file() or built.stat().st_mtime < newest:
        javac = shutil.which("javac")
        if javac is None:
            raise RuntimeError(
                "javac is not on PATH, so your snake cannot be compiled.\n"
                "Install a JDK (17 or newer) and start this again."
            )
        MY_SNAKE_BUILD.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [javac, "-d", str(MY_SNAKE_BUILD), *(str(p) for p in sources)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "your snake did not compile:\n\n" + (proc.stdout + proc.stderr).strip()
            )

    java = shutil.which("java") or "java"
    return f'cmd:"{java}" -cp "{MY_SNAKE_BUILD}" Snake'


def _playable_configs() -> list[dict]:
    """Every ``configs/*.toml`` the engine can actually play as a single game.

    A profile needs a ``[game]`` block with ``snakes_per_game``; ``league.toml``
    has only a ``[league]`` block (it drives the evaluator, not the engine) and
    is filtered out so it can't be picked in the dashboard. The snake count
    rides along so the browser can size the roster correctly per profile.

    **The league's profile is listed first**, because it is the one a student is
    marked on and therefore the only sensible default. Anything else is a board
    they are not playing: `standard` used to be the default here, which put a
    first run on an 11x11 board scattered with food and nothing like the game
    the league actually plays.
    """
    out = []
    for path in sorted(CONFIG_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        game = data.get("game")
        if not isinstance(game, dict) or "snakes_per_game" not in game:
            continue
        out.append({"name": path.stem, "snakes": int(game["snakes_per_game"])})
    out.sort(key=lambda c: (c["name"] != LEAGUE_PROFILE, c["name"]))
    return out


def _run_game(game_id: str, entrants: list[str], seed: int, config: str | None) -> None:
    state = GAMES[game_id]
    # No profile named means the league's, never the engine's built-in default -
    # which is a small walled board with food everywhere and not what anybody
    # here is playing.
    chosen = config or LEAGUE_PROFILE
    candidate = CONFIG_DIR / f"{chosen}.toml"
    config_path = str(candidate) if candidate.is_file() else None
    replay_path = str(REPLAY_DIR / f"{game_id}.rep")
    REPLAY_DIR.mkdir(exist_ok=True)

    def on_turn(snap: dict) -> None:
        state["frames"].append(snap)
        state["queue"].put(snap)

    try:
        # Resolve submission folder shorthands: "sub:alice" -> its snake.py
        resolved = []
        for e in entrants:
            if e == MY_SNAKE:
                resolved.append(my_snake_spec())
            elif e.startswith("sub:"):
                resolved.append(str(SUBMISSION_DIR / e[4:] / "snake.py"))
            else:
                resolved.append(e)
        # Name each snake by what was picked, not by what it resolves to - a
        # student's own entry showed up on the board as "java", after the first
        # word of the command used to run it.
        outcome = play_game(
            resolved,
            seed=seed,
            config_path=config_path,
            record_replay=replay_path,
            on_turn=on_turn,
            names=list(entrants),
        )
        state["result"] = outcome.result
    except Exception as exc:  # noqa: BLE001
        state["error"] = f"{exc}\n{traceback.format_exc()}"
    finally:
        state["done"] = True
        state["queue"].put(None)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # quiet
        pass

    # -- helpers --------------------------------------------------------------

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- routes -------------------------------------------------------------

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        route = url.path
        params = urllib.parse.parse_qs(url.query)

        if route in ("/", "/index.html"):
            return self._send_file(HERE / "index.html", "text/html; charset=utf-8")
        if route == "/viewer.html":
            return self._send_file(HERE / "viewer.html", "text/html; charset=utf-8")
        if route == "/api/baselines":
            return self._send_json({"baselines": baseline_names()})
        if route == "/api/configs":
            return self._send_json({"configs": _playable_configs()})
        if route == "/api/submissions":
            subs = (
                sorted(p.name for p in SUBMISSION_DIR.iterdir() if (p / "snake.py").exists())
                if SUBMISSION_DIR.exists()
                else []
            )
            return self._send_json(
                {"submissions": subs, "my_snake": bool(my_snake_sources())}
            )
        if route == "/api/replays":
            reps = sorted(
                (p.name for p in REPLAY_DIR.glob("*.rep")),
                key=lambda n: (REPLAY_DIR / n).stat().st_mtime,
                reverse=True,
            )
            return self._send_json({"replays": reps})
        if route == "/api/replay":
            name = params.get("name", [""])[0]
            path = REPLAY_DIR / name
            if not path.exists():
                return self._send_json({"error": "no such replay"}, 404)
            try:
                data = read_replay(str(path), include_frames=True)
            except Exception as exc:  # noqa: BLE001
                # A replay this engine cannot read is a thing to say out loud.
                # Returning nothing showed the viewer a blank board with no
                # clue why, which is how an unreadable recording looked like a
                # broken dashboard.
                return self._send_json(
                    {"error": f"this replay could not be read: {exc}"}, 422
                )
            return self._send_json(data)
        if route == "/api/game":
            gid = params.get("id", [""])[0]
            with GAMES_LOCK:
                state = GAMES.get(gid)
            if state is None:
                return self._send_json({"error": "no such game"}, 404)
            return self._send_json(
                {
                    "done": state["done"],
                    "error": state["error"],
                    "result": state.get("result"),
                    "frames": state["frames"],
                }
            )
        if route == "/api/stream":
            return self._stream(params.get("id", [""])[0])

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/api/run":
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        entrants = payload.get("entrants") or ["benchmark", "survivor", "hungry", "wander"]
        seed = int(payload.get("seed", 1))
        config = payload.get("config") or None

        game_id = f"game-{int(time.time() * 1000)}"
        with GAMES_LOCK:
            GAMES[game_id] = {
                "queue": queue.Queue(),
                "done": False,
                "error": None,
                "frames": [],
            }
            # keep the map from growing forever
            for old in list(GAMES)[:-12]:
                GAMES.pop(old, None)
        threading.Thread(
            target=_run_game, args=(game_id, entrants, seed, config), daemon=True
        ).start()
        self._send_json({"game_id": game_id})

    def _stream(self, game_id: str):
        with GAMES_LOCK:
            state = GAMES.get(game_id)
        if state is None:
            return self._send_json({"error": "no such game"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        # Replay whatever already happened, then follow live.
        sent = 0
        try:
            while True:
                frames = state["frames"]
                while sent < len(frames):
                    self._sse(frames[sent])
                    sent += 1
                if state["done"]:
                    payload = {"type": "end", "result": state.get("result"), "error": state["error"]}
                    self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
                    self.wfile.flush()
                    return
                try:
                    item = state["queue"].get(timeout=1.0)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    continue
        except (BrokenPipeError, ConnectionResetError):
            return

    def _sse(self, snap: dict):
        self.wfile.write(f"data: {json.dumps({'type': 'frame', 'snapshot': snap})}\n\n".encode())
        self.wfile.flush()


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    try:
        server = ThreadingServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        # Nearly always a dashboard that is already up - a second `start.sh`,
        # or one left running in another window. The traceback this used to
        # print made a working dashboard look like a broken download.
        if exc.errno != errno.EADDRINUSE:
            raise
        print(f"\nport {PORT} is already in use, so the dashboard did not start.", file=sys.stderr)
        print("Something is already listening there - most likely the dashboard", file=sys.stderr)
        print("itself, started earlier. Two ways out:\n", file=sys.stderr)
        print(f"  open it        http://127.0.0.1:{PORT}/", file=sys.stderr)
        print("  or stop it     close the window it is running in, or:\n", file=sys.stderr)
        print(f"    macOS/Linux  lsof -i :{PORT}      then  kill <pid>", file=sys.stderr)
        print(f"    Windows      netstat -ano | findstr :{PORT}", file=sys.stderr)
        raise SystemExit(1) from None

    url = f"http://127.0.0.1:{PORT}/"
    # Flushed, because a student watching a terminal for a URL should see it
    # the moment it exists rather than whenever the buffer happens to drain.
    print(f"snake dashboard -> {url}", flush=True)
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
