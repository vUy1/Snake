# Student guide

You write **one Java class**. It contains one decision — which way to move —
made every turn. Everything else is done for you.

Your submission is `Snake.java`, or — once one file stops being enough — a
**zip** of the Java files your snake is split across, with `Snake.java` among
them:

| Submitted | What it is |
| --- | --- |
| `Snake.java` | a program that speaks the [stdio protocol](protocol.md) |
| `snake.zip` | the same, split across as many classes as you like |

No build scripts, no libraries beyond the standard one, no compiler flags of
your own: the marking machine compiles you with plain `javac` and runs the
`Snake` class. **The assignment is Java only** — the platform will run a Python
or C++ snake, but not as a hand-in for this one. See §8.

---

## 1. Set up

Download the platform zip from the course site. It contains the engine already
compiled for Windows, macOS and Linux — **there is nothing to build**. You need
a JDK (17 or newer) for your snake, and Python 3.8 or newer to run the platform
around it.

| You are on | Start it with |
| --- | --- |
| Windows | double-click `START.cmd` |
| macOS or Linux | `bash start.sh` |

Either opens the dashboard: pick snakes, press run, watch the board. That is the
whole loop.

```
my-snake/       your snake — Snake.java. That file IS your submission.
clients/        a bare skeleton and a random-move floor to compare against
examples/       the same floor in Python, if you are reading along
docs/           this guide
START.cmd       Windows
start.sh        macOS / Linux
```

`javac -version` should answer before you start. You write no Python: it is only
what runs the dashboard and the engine around your snake.

---

## 2. The interface

Your program is started **once per game** and talks to the engine over stdin and
stdout: plain text in, one number out. No JSON, no libraries — everything you
read comes apart with `split`.

```java
public class Snake {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));

        // Once: "<snakes> <width> <height> <mode>", always "4 35 35 1" here.
        String[] init = in.readLine().trim().split("\\s+");
        int snakeCount = Integer.parseInt(init[0]);
        int width  = Integer.parseInt(init[1]);
        int height = Integer.parseInt(init[2]);

        while (true) {
            String first = in.readLine();
            if (first == null || first.trim().equals("Game Over")) return;

            String[] apple = first.trim().split("\\s+");   // the apple, "x y"
            int me = Integer.parseInt(in.readLine().trim());
            String[] snakes = new String[snakeCount];
            for (int i = 0; i < snakeCount; i++) snakes[i] = in.readLine();

            System.out.println(chooseMove(/* ... */));      // one integer, 0-6
            System.out.flush();
        }
    }
}
```

`my-snake/Snake.java` is exactly this with the parsing written out. Print one
integer a turn:

| | Move | | Move |
| --- | --- | --- | --- |
| `0` | up (north) | `4` | left, relative to your head |
| `1` | down (south) | `5` | straight on |
| `2` | left (west) | `6` | right, relative to your head |
| `3` | right (east) | | |

Asking for the direction you came from is not a reversal — you carry straight
on. Answer late or not at all and your previous move is repeated and a failure
counted: **three failures in a row and you forfeit the game**.

Three rules the starter already follows. Keep them:

* **Flush after every line.** A buffered answer is a late answer.
* **Nothing but the move on stdout.** Anything else is discarded, and a stray
  `println` eats your turn. To record something, print `log ` and then your
  message — it goes to a log file beside the game, along with anything you
  write to `System.err`.
* **Keep state in fields.** You are started once per game, not once per turn.

---

## 3. What you can see — the game state

Every turn arrives as six lines:

```
24 25
0
alive 26 2 10,12 15,12 15,7 5,7 5,2
dead 6 6 14,13 19,13
alive 2 1 12,13 12,14
alive 17 1 31,14 21,14 15,14 15,13
```

| Line | What it is |
| --- | --- |
| 1 | the apple, `x y` — there is exactly one, always |
| 2 | which of the four snakes below is you, `0` to `3` |
| 3–6 | one line per snake, in index order |

That is the whole board: one apple, four snakes, and nothing else on it.

**`(0, 0)` is the top-left square and `y` grows downwards**, so `board[y][x]`
works the way it looks on screen.

A snake's line is

```
alive|dead  length  kills  headX,headY  ...  tailX,tailY
```

— whether it is still on the board (**ignore the dead ones**), how long it is,
how many snakes it has killed, and then its coordinate chain.

### The chain is corners, not cells

The chain lists the head, then every corner, then the tail. The cells between
two listed points are body too. `alive 2 1 12,13 12,14` is a two-cell snake with
its head at `(12,13)` and its tail at `(12,14)`, pointing upwards.

**A repeated point is a teleport.** The board wraps (§5), so a body can leave
one edge and arrive at the opposite one — and a chain of corners alone cannot
say whether `0,10 34,10` is a run of thirty-five cells across the row or one step
through the edge. So when the same point appears twice in a row, the run ends
there and the snake comes back on at the next point listed:

```
1,10  0,10  0,10  34,10  33,10
      ^^^^^^^^^^^ left at 0,10, came back at 34,10
```

Four cells, not fifty-two. A point never repeats for any other reason.

| The snake | On the wire |
| --- | --- |
| thirty-five cells filling row 10 | `0,10 34,10` |
| three cells stepping through the edge | `34,10 34,10 0,10 1,10` |

Every coordinate you are sent is inside the board — never negative, never past
the edge — so indexing an array with one is always safe.

At the end of the game you are sent a single line, `Game Over`, and have about
half a second to write anything out before you are stopped.

---

## 4. Where your work goes

`chooseMove` gets the state and returns a move. The starter's reads a few
pieces of it, ignores them all, and moves at random:

```java
static String chooseMove(int width, int height, int me, int appleX, int appleY,
                         String[] snakes) {
    String[] mine = snakes[me].trim().split("\\s+");
    int length = Integer.parseInt(mine[1]);
    int kills  = Integer.parseInt(mine[2]);
    // ... the chain, the other snakes, the apple ...

    return String.valueOf(rng.nextInt(4));      // <- replace this
}
```

That is the whole of what you are given. It never walks into anything on
purpose, and it never avoids anything on purpose either — it dies constantly,
and any judgement at all beats it.

### Write a `Board`

Reading fields out of the message by hand stops being pleasant at about the
third question you want to ask of it. `my-snake/Snake.java` has an empty `Board`
class at the bottom for that reason:

```java
static class Board {
    Board(int width, int height, String[] snakes) {
        // Read what you need out of the state, once, here.
    }
}
```

Filling it in is most of the exercise. What you will end up wanting, roughly in
the order you will want it:

| You want to ask | So you need |
| --- | --- |
| where is everyone? | the chains expanded into cells — **including the teleports** (§3) |
| would this move kill me? | which of those cells are occupied — every snake's body, yours included |
| what is next to me? | a step that **wraps**: the cell below `y = 34` is `y = 0` (§5) |
| how far is that? | a distance that wraps with it — not `abs(x1 - x2) + abs(y1 - y2)` |
| is that gap a trap? | how many cells you can still reach from it — a flood fill |
| can I win this fight? | your `length` against theirs, and whose head is next to whose |

None of it is written for you, in any language. Working out what belongs there,
and what to do with the answers, is the assignment — and a snake that answers
those six well is most of a good one.

The first one is where everybody starts, and it is the one the format makes you
think about: a chain is corners, so the cells in between are yours to fill in,
and a repeated point means the run jumped to the far edge rather than carrying
on.

The last two are where the marks are. Everything above them is bookkeeping that
any correct snake has; deciding *when a gap is worth entering* and *when a fight
is worth taking* is the part that is actually a policy.

### When one file stops being enough

Split it. Put `Board` in `Board.java`, leave `Snake` in
`Snake.java` — each needs `import java.util.*;` at the top and the `static`
dropped from its class line — and hand in a zip of those files:

```bash
cd my-snake && zip ../snake.zip *.java
```

That zip is what you submit. Zip the `.java` files themselves, not a folder
containing them — though the marker copes with either.

There is no limit on how many classes you add and no build file to write — the
marker compiles every `.java` in the zip together, exactly as
`javac -d build my-snake/*.java` does here. `Snake.java` stays the entry point,
so `chooseMove` keeps its place. See §8 for the full contract.

---

## 5. The board wraps

League games are played on `configs/league-arena.toml`, and **that board is a
torus**. Walk off the right edge and you come back on the left. Walk off the
top and you come back at the bottom, and the same in reverse. There are no
walls and there are no wall deaths.

This changes more than it sounds like it does:

* **You are never cornered by geometry.** Being in a "corner" means nothing; the
  cell at `(0, 0)` has the same four neighbours as the middle of the board.
* **Distances wrap.** The short way to a piece of food may be backwards through
  an edge. A distance that subtracts coordinates is wrong on this board; the
  wrap-aware one is the second thing §4 tells you to write, and this is why.
* **So does your own body.** A snake long enough to cross the board can meet its
  own tail coming the other way. Self-collision is the most common death on this
  board.
* **You can be cut off across an edge.** An opponent lying along a column walls
  off a region that looks open if you think in rectangles. Your flood fill has
  to wrap too; your intuition will not.

Every league game is on the same board: **35x35, bare**. No obstacles, no map
pool and no draw — the only things in play are the four snakes and one apple, so
you can tune for this one board and nothing else.

**You start five cells long, and every apple adds five more.** A meal is a real
event on this board, not a rounding error — two of them and you are long enough
to cut the board in half, which is as much a weapon as it is a score.

**There is exactly one piece of food on it at any moment.** It is replaced the
turn it is eaten, never doubled, and never absent. On 1225 cells that single
square is the main reason four snakes end up in the same place — which makes
"who gets there first, and what does it cost me to try" most of the game.

And the board fills up. Four snakes growing five cells a meal, over two thousand
turns, run out of room: by the end a long game is mostly snake, and the thing
that kills you is no longer a careless step but having nowhere left to put
yourself. Length is the score *and* the hazard.

## 6. How you die — and come back

* **Body** — your head enters any snake's body, yours included. Reversing onto
  your own neck counts.
* **Head-to-head** — two heads enter the same cell: the strictly longer snake
  lives, the other dies; equal length, both die. Avoiding the ones you would
  lose means checking every other head next to the cell you are entering.
* **Forfeit** — three failed or missed moves in a row (a timeout, a crash, no
  answer). You are out, and unlike an ordinary death this one is permanent: a
  forfeited snake is not respawned. **A `chooseMove` that never returns counts
  here.** The league does not wait for it: past a hard limit well above the
  deadline the engine stops waiting, takes the turn as a timeout, and after
  three of them your snake is out of that game — so an infinite loop is not a
  hung marker, it is a season of forfeits.

**Eating grows you by five.** Your tail stays put for the next five turns
while the new length unspools behind you, so a meal is worth contesting and a
snake that eats twice is suddenly a wall.

**In the league, death costs you tempo, not the game.** Respawns are on: five
turns after you are eliminated you come back at a safe cell, reset to length 5,
and the turn message's `events` carries a `"respawned"` entry. Every game runs
the full 2000-turn cap.

**You are ranked on the longest you ever got.** Not the length you finish with —
the high-water mark, taken across the whole game. Kills break a tie and nothing
else counts: not food, not deaths, not how long you survived.

That makes dying cheap in one specific sense and expensive in another. The
eighty you reached is banked and cannot be taken off you, so a death does not
undo the game you played. But you come back at five, and climbing back to eighty
is most of a game's work — so the snake that grows and *keeps* growing is the
one that wins, and a risk worth taking is one that gets you longer, not one that
merely keeps you alive.

`configs/classic.toml` is the same wrapped board with respawns *off* — last
snake standing, ranked on survival. It is worth practising on to sharpen your
safety, but it is not what you are marked on.

---

## 7. Test it

Compile first, then play. `javac -d` makes the output folder for you:

```bash
javac -d build my-snake/*.java
```

Everything below plays under the league's rules by default — the same board,
the same four snakes, the same clock the marker uses. **There is nothing to
configure.**

### Start with the gauntlet

Three built-in opponents — `gauntlet_1`, `gauntlet_2` and `gauntlet_3` — and the
measure to work against:

```bash
python -m snake.cli gauntlet "cmd:java -cp build Snake"             # all three
python -m snake.cli gauntlet "cmd:java -cp build Snake" --only 1    # just one of them
python -m snake.cli gauntlet "cmd:java -cp build Snake" --seeds 1..60
```

Each is played three-to-one against you, over a seed set. You have the better of
one when you finish above the middle of the table across those games — not
something a single lucky game gets you.

**The numbers are names, not a ranking.** They are three different players of
broadly similar strength, so there is no gentle one to start on and no order to
work through: beating one but not another says nothing much. If anything
`gauntlet_1` is currently the hardest of the three.

They live in the compiled engine, and **their source is not in your download**.
That is on purpose: you can play them as often as you like and you cannot read
the answer, which makes them the one honest measure of your snake you have
before the table. Holding your own against all three puts you somewhere near the
top of a division.

So the loop is: **play the gauntlet, change something, play it again** — and
when it is holding its own, hand it in and watch the table.

### Watching a single game

When the gauntlet says you are losing and you want to see why:

```bash
ME="cmd:java -cp build Snake"
python -m snake.cli play  $ME survivor hungry wander --seed 3
python -m snake.cli watch $ME survivor --seed 3            # ASCII, turn by turn
python -m snake.cli evaluate $ME survivor hungry wander --seeds 1..50
```

`evaluate` over fifty seeds is the number worth trusting. One game tells you
almost nothing: spawn order and food both move with the seed.

The `cmd:` prefix is how you hand the platform a program rather than a file —
everything after it is the command line the engine starts, exactly as the marker
will start it. If that command works here, your submission works there.

**`benchmark` is the one to beat.** It plays the simplest policy worth
writing: go straight at the apple, unless that step walks into something. It is
in every local game by default, so you are measured against it whether you ask
or not. It eats more than anything else here and dies more than anything else
here, because it never looks at the shape of the space it is entering — and
beating it means thinking exactly one step further than that.

The rest, to practise against: `wander`, `hungry`, `survivor`, `coward`,
`hunter`, `ouroboros`, `edgerunner`, `do_nothing`. Each makes one clear decision
and they are all beatable; `python -m snake.cli baselines` lists them.

There are other rule profiles in `configs/` if you want to try something odd —
a bigger board, no respawns — with `--config`. You do not need them, and nothing
you are marked on uses them.

### Before you hand it in

Compile from clean and play the exact command the marker runs. A snake that
plays here is one the league accepts:

```bash
rm -rf build && javac -d build my-snake/*.java
python -m snake.cli gauntlet "cmd:java -cp build Snake"
```

Then zip it if you are handing in more than one file:

```bash
cd my-snake && zip ../snake.zip *.java && cd ..
```

Hand in the `.java` files or the zip — never the `build/` folder. The marker
compiles your source again from scratch.

---

## 8. Python and C++

> **Not for this assignment.** The second-year assignment is marked in **Java**:
> hand in `Snake.java`, or a zip of Java files with `Snake.java` among them.
> A submission in another language is not accepted for it.

The platform itself does still run Python and C++ snakes, so they are there for
playing about with outside the assignment — a snake you write for fun, or one
you want to test an idea in quickly.

| File | What it is |
| --- | --- |
| `snake.cpp` | a stdio-protocol program, exactly as in §2–§3, built with `g++ -O2 -std=c++17` |
| `snake.py` | a `SnakeController` subclass, loaded in-process rather than over the protocol |

`clients/cpp/snake.cpp` is the same skeleton as the Java one:

```bash
g++ -O2 -std=c++17 -o mysnake clients/cpp/snake.cpp
python -m snake.cli play "cmd:./mysnake" survivor hungry wander
```

Do not call the binary `snake` — there is already a `snake/` folder here (the
SDK), and you would be asking the engine to run a directory. On Windows `g++`
adds `.exe`; write either name in the `cmd:` and it will be found.

Python is the odd one out: it does not speak the protocol at all. A
`SnakeController` is handed a parsed `Observation` in-process, with the geometry
of §4 already written — `obs.step`, `obs.distance`, `obs.is_free`,
`obs.nearest_food`, `obs.reachable_area` — which is most of why it is not what
the assignment is marked in. `examples/simple_snake.py` is the floor to start
from.

## 9. The league

Your snake goes into a division and plays a game each round against three others
from that division. A game is four snakes on the bare 35x35 board, wrapped, with respawns on
and the full turn cap: **the longest length you reached** is what feeds your
Elo rating, with kills breaking a tie. Each round the top of a division is promoted and the bottom relegated, and
the arena site shows the standings and your rating over time.

Watch the clock: you have **50 ms per move** — the engine measures every one of
them, and a slow snake is told so on its own page on the site. A move that never finishes at all is a forfeit rather than a pause —
see section 6. And keep any state you need between turns: the engine does not
reset you mid-game.

### Are you getting better?

Your rating alone cannot tell you, and this catches people out. A rating is
*relative*: the class improves all term, so a snake that has genuinely got
better — eating more, surviving longer, winning more of its games — can finish
the term on roughly the rating it started with. That is not a term wasted, and
the table is the wrong place to look for it.

Your snake's page, under **Across the seasons**, is the right place. Three
things there, all of them every season you have played, oldest on the left:

- **your rating**, season by season, with the seasons you went up or down marked;
- **where your games finished** — one column a season, the games you won at the
  floor of it in the darkest gold. If you are improving, the gold grows up the
  column. It is the fastest read on the page;
- **how it plays** — six panels: games won, food a game, kills a game, longest,
  turns alive and decision time. Hover anywhere and all six jump to the same
  season, so you can see what a good season was made of.

Each of those six panels carries a second, quieter line: **the middle of the
class that season**. That is the line to watch. Eating more apples every season
while the class eats more still is not improvement, and only the two lines
together say so. Under each panel is the change since your first season, green
when it went the right way — which for decision time is *down*.

The numbers behind the panels are in the table under them, season by season, if
you would rather read them than look at them.
