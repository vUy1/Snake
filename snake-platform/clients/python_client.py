"""The Python skeleton for the course text protocol, for running out of process.

A Python submission is normally a `SnakeController` loaded in-process - see the
student guide. This is for running one as its own program, the way Java and C++
snakes are run:

    python -m snake.cli play "cmd:python clients/python_client.py" survivor hungry --seed 1

See docs/protocol.md for the wire format, including the wrapping rule.
"""
import random
import sys


def read():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return line.rstrip("\n")


def parse_cells(line):
    """"10,12 15,12" -> [(10, 12), (15, 12)]. A repeated point is a teleport."""
    cells = []
    for token in (line or "").split():
        x, _, y = token.partition(",")
        cells.append((int(x), int(y)))
    return cells


def log(message):
    """Goes to the log file, not to the game."""
    print("log", message, flush=True)


def main():
    snake_count, width, height, mode = (int(v) for v in read().split())
    rng = None

    while True:
        first = read()
        if first.strip() == "Game Over":
            return
        if not first.strip():
            continue

        apple_x, apple_y = (int(v) for v in first.split())
        me = int(read())
        snakes = [read() for _ in range(snake_count)]

        if rng is None:
            rng = random.Random(first)          # same game, same dice

        mine = snakes[me].split()
        alive, length, kills = mine[0] == "alive", int(mine[1]), int(mine[2])
        my_chain = parse_cells(" ".join(mine[3:]))

        # 0 up, 1 down, 2 left, 3 right; 4 left, 5 straight, 6 right.
        print(rng.randrange(4), flush=True)


if __name__ == "__main__":
    main()
