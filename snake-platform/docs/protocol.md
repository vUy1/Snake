# The stdio protocol

Your snake is a program. It reads the board from **stdin** and writes a move to
**stdout** — plain text, one item per line, no libraries and no parsing beyond
`split`. It is the format this course has always used, so last year's notes and
helper classes still apply; the one new rule is for wrapping, and it is at the
bottom of this page.

`clients/` in your download has a skeleton in each language that reads all of
this and moves at random. `my-snake/Snake.java` is
the same thing with the commentary left in.

## Initialisation — once, before anything else

```
4 35 35 1
```

The number of snakes, the board width, the board height, and the mode. For this
course that line is always `4 35 35 1`.

## Every turn — the game state

```
24 25
0
alive 26 2 10,12 15,12 15,7 5,7 5,2
dead 6 6 14,13 19,13
alive 2 1 12,13 12,14
alive 17 1 31,14 21,14 15,14 15,13
```

Line by line:

| Line | What it is |
| --- | --- |
| 1 | the apple, `x y` — there is exactly one, always |
| 2 | which of the snakes below is you, `0` to `3` |
| 3–6 | one line per snake, in index order |

The board is bare: one apple, four snakes, nothing else. No walls, no
obstacles, no hazards.

**`(0, 0)` is the top-left square and `y` grows downwards**, so `board[y][x]`
indexes it the way you would expect from the screen.

### A snake

```
alive|dead  length  kills  headX,headY  ...  tailX,tailY
```

First whether it is alive — **dead snakes are not on the board, so ignore
them** — then its current length, then how many snakes it has killed. What
follows is its coordinate chain.

The chain is **not** a list of cells. It lists the head, then every corner, then
the tail; the cells between two listed points are body too. So

```
alive 2 1 12,13 12,14
```

is a two-cell snake with its head at `(12, 13)` and its tail at `(12, 14)` —
travelling upwards, since the head's `y` is the smaller.

## Wrapping — the one new rule

The board is a **torus**: walk off the right edge and you come back on the left,
off the top and you come back at the bottom. The format was written for a board
with walls, and a chain of corners cannot say on its own whether

```
0,10 34,10
```

means *a straight run of thirty-five cells across the whole row* or *one step through
the edge*. Both are real snakes, so the ambiguity has to be settled explicitly.

**A repeated coordinate is a teleport.** When the same point appears twice in a
row, the run ends there and the snake comes back on at the next point listed,
which is the cell on the opposite edge:

```
1,10  0,10  0,10  34,10  33,10
      ^^^^^^^^^^^ left the board at 0,10, came back on at 34,10
```

Those five points describe exactly four cells — `(1,10) (0,10) (34,10)
(48,10)` — where the same five read as plain runs would describe fifty-two. A
point never repeats for any other reason: a straight run to the cell you are
already standing on is not a thing, and a snake that has just eaten carries its
tail twice internally but is sent to you with the duplicate removed.

So the full-row snake and the three-cell one are now different on the wire:

| The snake | On the wire |
| --- | --- |
| thirty-five cells filling row 10 | `0,10 34,10` |
| three cells stepping through the edge | `34,10 34,10 0,10 1,10` |

Expanding a chain into cells — teleports and all — is the first thing worth
writing. Every coordinate you are sent is inside the board: never negative,
never past the edge, so indexing an array with one is always safe.

## Making a move

Print **one integer** and flush.

| | Move |
| --- | --- |
| `0` | up — north, towards `y = 0` |
| `1` | down — south |
| `2` | left — west |
| `3` | right — east |
| `4` | left, relative to the way your head is pointing |
| `5` | straight on |
| `6` | right, relative to your head |

Asking for the direction you came from is not a reversal — you simply carry
straight on.

## Logging

Two files are written for each agent: one taking anything your program prints
to **stderr**, and one taking anything it prints to stdout behind `log `:

```java
System.out.println("log length is " + length);   // goes to the log file
```

Anything else on stdout that is not a move is discarded, so a stray `println`
costs you nothing — but it does not reach you either. Use `log `.

## Game over

When the game ends you are sent a single line:

```
Game Over
```

You have about half a second to write anything out and exit before you are
stopped.

## The clock

You have **50 ms per move**. Miss it and your previous move is repeated and a
failure is counted; **3 failures in a row and you forfeit the game**. Never
answering is the same failure — the engine stops waiting well short of forever,
so a program stuck in a loop forfeits rather than hanging the marker. Your
program is started **once per game**, not once per turn, so keep your state in
memory.

Flush after every line. A buffered answer is a late answer.

## Submitting a Java snake

You hand in **one file**: either `Snake.java` on its own, or a zip of the Java
files your snake is made of.

```
Snake.java                 snake.zip  ->  Snake.java, Board.java, Search.java
```

Use the zip when one file stops being enough. There is no limit on how many
classes you put in it, and no build file to write: the marker hands every
`.java` in the archive to `javac` at once.

**`Snake.java` is still the entry point.** Whatever else is in the zip, the
marker looks for a file named exactly `Snake.java` and runs the `Snake` class in
it, with `main(String[] args)` as it is now. A zip without a `Snake.java` is
refused when you upload it, not silently failed later. Two details, if you want
them:

* Your files may sit in a folder inside the zip (`my-snake/Snake.java`) — the
  marker finds them. If two files are named `Snake.java`, the one nearest the
  top of the zip is the entry point.
* If `Snake.java` declares a `package`, the marker runs the packaged name
  (`package za.ac.wits;` → `za.ac.wits.Snake`). Declare no package and it is
  plain `Snake`, which is the simpler thing to do.

C++ and Python are one file each — `snake.cpp` or `snake.py` — and neither may
be a zip.

The marker compiles what you submit and runs the result through this protocol:

| Submitted | Build | Run |
| --- | --- | --- |
| `Snake.java` | `javac -d <out> Snake.java` | `java -cp <out> Snake` |
| `snake.zip` | `javac -d <out> <every .java in it>` | `java -cp <out> Snake` |
| `snake.cpp` | `g++ -O2 -std=c++17 -o <out>/snake snake.cpp` | `<out>/snake` |

So: no build files, no libraries beyond the standard one, no compiler flags of
your own, and — for Java — a `public` class named for the file it is in.

A note on randomness, if you use any: the platform replays a game by playing it
again from its seed rather than by storing the frames, so a program that rolls
unseeded dice plays a different game the second time and cannot be watched back.
There is no seed on the wire — the skeletons seed themselves from the opening
state instead, which is a function of the seed and therefore just as
reproducible.

Test it exactly as the marker will:

```bash
javac -d build *.java        # every file your snake is made of
python -m snake.cli play "cmd:java -cp build Snake" survivor hungry wander \
    --config configs/league-arena.toml --seed 1
```
