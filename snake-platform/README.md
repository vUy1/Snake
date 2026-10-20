# Snake Platform

Unzip this, then:

* Windows: double-click `START.cmd`
* macOS / Linux: `bash start.sh`

The dashboard opens. Your snake is `my-snake/Snake.java` — that file is
your submission. When one file stops being enough, split it up and hand
in a zip of the folder instead; `Snake.java` stays the entry point.
`clients/java/` holds the bare skeleton and a random-move floor to
compare against. See `docs/student-guide.md`.

League games use `configs/league-arena.toml` — the Pillars map, four
snakes, a wrapped board, respawns on. Pass
`--config configs/league-arena.toml` when you practise.

```
javac -d build my-snake/Snake.java
python launch.py play "cmd:java -cp build Snake" survivor hungry wander --config configs/league-arena.toml --seed 1
python launch.py gauntlet "cmd:java -cp build Snake"
```

That last one plays your snake up the gauntlet: three opponents of rising
strength, built into the engine. Their source is not in here, on purpose —
you can play them as often as you like and you cannot read the answer.
