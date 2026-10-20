"""Thin wrapper over the compiled engine.

``render_mode`` does not exist here: there is no window and no live viewer in
the SDK. To watch a game, record a replay and open it in the dashboard
(``python tools/launcher/server.py``), or run the launcher's live view.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import _engine as _native
from .observation import Observation


class SnakeEnv:
    """One game, stepped a turn at a time.

        env = SnakeEnv(names=["me", "them"], snakes_per_game=2)
        obs = env.reset(seed=1)
        while not env.finished:
            moves = {sid: my_snake.move(o) for sid, o in obs.items()}
            obs, done = env.step(moves)
        result = env.result()
        env.close()
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_toml: Optional[str] = None,
        snakes_per_game: Optional[int] = None,
        max_turns: Optional[int] = None,
        seed: Optional[int] = None,
        names: Optional[List[str]] = None,
        record_replay: Optional[str] = None,
        per_move_timeout_ms: Optional[float] = None,
        game_id: Optional[str] = None,
        wrapped: Optional[bool] = None,
    ) -> None:
        self._env = _native.SnakeEnv(
            config_path=config_path,
            config_toml=config_toml,
            snakes_per_game=snakes_per_game,
            max_turns=max_turns,
            seed=seed,
            names=names,
            record_replay=record_replay,
            per_move_timeout_ms=per_move_timeout_ms,
            game_id=game_id,
            wrapped=wrapped,
        )
        self._closed = False

    def use_baseline(self, snake_id: int, name: str, display: Optional[str] = None) -> None:
        """Drive one snake with a native reference controller. ``display``
        overrides the name shown in results."""
        self._env.use_baseline(snake_id, name, display)

    def reset(self, seed: Optional[int] = None) -> Dict[int, Observation]:
        return {sid: Observation(d) for sid, d in self._env.reset(seed=seed).items()}

    def observations(self) -> Dict[int, Observation]:
        return {sid: Observation(d) for sid, d in self._env.observations().items()}

    def step(self, moves: Dict[Any, Any]):
        payload = {}
        for key, value in moves.items():
            if hasattr(value, "to_payload"):
                payload[key] = value.to_payload()
            elif hasattr(value, "direction"):
                payload[key] = {"move": value.direction, "shout": getattr(value, "shout", None)}
            else:
                payload[key] = value
        raw, done = self._env.step(payload)
        return {sid: Observation(d) for sid, d in raw.items()}, done

    def record_decision(self, snake_id: int, elapsed_ms: float, error: Optional[str] = None) -> None:
        self._env.record_decision(snake_id, elapsed_ms, error)

    def snapshot(self) -> Dict[str, Any]:
        return self._env.snapshot()

    def result(self) -> Dict[str, Any]:
        return self._env.result()

    def config(self) -> Dict[str, Any]:
        return self._env.config()

    def state_hash(self) -> int:
        return self._env.state_hash()

    def close(self) -> None:
        if not self._closed:
            self._env.close()
            self._closed = True

    def __enter__(self) -> "SnakeEnv":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        self.close()
        return False

    # -- state ----------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self._env.finished

    @property
    def turn(self) -> int:
        return self._env.turn

    @property
    def seed(self) -> int:
        return self._env.seed

    @property
    def map_id(self) -> str:
        return self._env.map_id

    @property
    def alive_ids(self) -> List[int]:
        return list(self._env.alive_ids)

    @property
    def names(self) -> List[str]:
        return list(self._env.names)

    @property
    def snakes_per_game(self) -> int:
        return self._env.snakes_per_game

    @property
    def max_turns(self) -> int:
        return self._env.max_turns

    @property
    def board(self):
        return self._env.board

    @property
    def config_hash(self) -> str:
        return self._env.config_hash

    @property
    def engine_version(self) -> str:
        return self._env.engine_version

    def __repr__(self) -> str:
        return repr(self._env)
