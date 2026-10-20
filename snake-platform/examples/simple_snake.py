"""The simplest thing that is still a policy: choose at random, but not suicide.

Weak on purpose, and weak in an instructive way. It has no plan at all — no
food, no opponents, no sense of space — so every game it wins is luck and every
game it loses tells you nothing. It is here to be the floor: the first snake
you write should beat this comfortably, and if it does not, the problem is in
your `move` rather than in your strategy.

There is exactly one idea in it worth keeping. **Seed your own randomness from
the game's seed.** The platform replays a game by playing it again from its
seed rather than by storing the frames, so a snake that rolls unseeded dice
plays a different game the second time and cannot be watched back. Take the
seed in `reset`, as here, and your games are reproducible.

The same policy is in the engine as the reference snake `wander`, so

    python -m snake.cli play examples/simple_snake.py wander wander wander

is this file against three copies of itself.

Next: `my-snake/Snake.java`, which has opinions - and then the gauntlet,
`python -m snake.cli gauntlet "cmd:java -cp build Snake"`, which is three opponents of
rising strength to measure them against.
"""

import random

from snake import SnakeController
from snake.helpers import safe_moves


class SimpleSnake(SnakeController):
    name = "simple"

    def __init__(self) -> None:
        self.rng = random.Random(0)

    def reset(self, seed: int) -> None:
        # Called before every game, with that game's seed. See the note above:
        # this one line is what makes the snake replayable.
        self.rng = random.Random(seed)

    def move(self, obs):
        # Of the moves that do not kill me this turn, any one will do. If every
        # move is fatal, take a legal one and find out which kind of death it
        # was.
        options = safe_moves(obs) or obs.free_directions() or ["up"]
        return self.rng.choice(options)
