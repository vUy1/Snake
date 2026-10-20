// Your snake. This file IS your submission - hand in exactly this, or a zip of
// this plus whatever classes you split out of it.
//
// It reads the board every turn and moves at random, which is the worst snake
// that still plays. Making it better is the assignment.
//
//   javac -d build my-snake/Snake.java
//   python -m snake.cli play "cmd:java -cp build Snake" survivor hungry wander --seed 1
//
// To find out whether a change helped, play it up the gauntlet - three built-in
// opponents of rising strength, which you can play as often as you like and
// cannot read the source of:
//
//   python -m snake.cli gauntlet "cmd:java -cp build Snake"
//
// Two things below are worth keeping when you rewrite the rest:
//
//   * the seeded random. The platform replays a game by playing it again from
//     its seed, so a snake that rolls unseeded dice plays a different game the
//     second time and cannot be watched back.
//   * System.out is the game's channel, not yours. Print anything that is not
//     a move and you have eaten your turn - use `log ` (see logging, below).
//
// Read docs/protocol.md for the wire format and docs/student-guide.md for the
// rest of the game.

import java.io.*;
import java.util.*;

public class Snake {
    static Random rng = null;

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));

        // ---- initialisation: "<snakes> <width> <height> <mode>", once -------
        String[] init = in.readLine().trim().split("\\s+");
        int snakeCount = Integer.parseInt(init[0]);
        int width = Integer.parseInt(init[1]);
        int height = Integer.parseInt(init[2]);
        int mode = Integer.parseInt(init[3]);

        while (true) {
            // ---- one game state ---------------------------------------------
            String first = in.readLine();
            if (first == null) return;                 // the game went away
            first = first.trim();
            if (first.equals("Game Over")) return;     // you have ~500ms here
            if (first.isEmpty()) continue;

            // Line 1: the apple, "x y".
            String[] apple = first.split("\\s+");
            int appleX = Integer.parseInt(apple[0]);
            int appleY = Integer.parseInt(apple[1]);

            // Line 2: which of the snakes below is you.
            int me = Integer.parseInt(in.readLine().trim());

            // Then one line per snake, in index order.
            String[] snakes = new String[snakeCount];
            for (int i = 0; i < snakeCount; i++) snakes[i] = in.readLine();

            if (rng == null) rng = new Random(first.hashCode());   // same game, same dice

            System.out.println(chooseMove(width, height, me, appleX, appleY, snakes));
            System.out.flush();
        }
    }

    /**
     * One turn. Everything the game told you is in the arguments; this reads a
     * little of it, ignores all of it, and moves at random.
     *
     * Replacing that is the assignment.
     */
    static String chooseMove(int width, int height, int me, int appleX, int appleY,
                             String[] snakes) {
        // Your own line: "alive 26 2 10,12 15,12 15,7" - status, length, kills,
        // then the coordinate chain, head first.
        String[] mine = snakes[me].trim().split("\\s+");
        boolean alive = mine[0].equals("alive");
        int length = Integer.parseInt(mine[1]);
        int kills = Integer.parseInt(mine[2]);
        int[][] myChain = parseCells(String.join(" ", Arrays.copyOfRange(mine, 3, mine.length)));
        int[] head = myChain.length > 0 ? myChain[0] : new int[] {0, 0};

        // Everyone else. Dead snakes are not on the board - skip them.
        for (int i = 0; i < snakes.length; i++) {
            if (i == me) continue;
            String[] other = snakes[i].trim().split("\\s+");
            if (!other[0].equals("alive")) continue;
            int otherLength = Integer.parseInt(other[1]);
            int[][] otherChain = parseCells(String.join(" ", Arrays.copyOfRange(other, 3, other.length)));
            // ... otherChain[0] is their head, same shape as yours.
        }

        // Nothing above is used. That is the whole of the assignment: work out
        // which way is worth going, and return that instead.
        //
        //   0 up     1 down     2 left     3 right        (north/south/west/east)
        //   4 left   5 straight 6 right                   (relative to your head)
        //
        // Asking for the direction you came from is not a reversal; you just
        // carry straight on.
        return String.valueOf(rng.nextInt(4));
    }

    /**
     * "10,12 15,12 15,7" into {{10,12},{15,12},{15,7}}.
     *
     * **A repeated point is a teleport.** The board wraps, so a body can leave
     * one edge and arrive at the opposite one. When the same point appears
     * twice in a row the run ends there and the snake comes back on at the next
     * point listed:
     *
     *     1,10  0,10  0,10  34,10  33,10
     *           ^^^^^^^^^^^ left at 0,10, came back at 34,10
     *
     * so that chain is four cells, not fifty. This method keeps the points as
     * they came; expanding a chain into the cells between them, teleports and
     * all, is yours to write - see the student guide, section 4.
     */
    static int[][] parseCells(String line) {
        if (line == null) return new int[0][];
        line = line.trim();
        if (line.isEmpty()) return new int[0][];
        String[] parts = line.split("\\s+");
        int[][] cells = new int[parts.length][2];
        for (int i = 0; i < parts.length; i++) {
            int comma = parts[i].indexOf(',');
            cells[i][0] = Integer.parseInt(parts[i].substring(0, comma));
            cells[i][1] = Integer.parseInt(parts[i].substring(comma + 1));
        }
        return cells;
    }

    /**
     * Your board. Empty on purpose.
     *
     * Picking fields out of those strings every turn stops being pleasant at
     * about the third question you want to ask. This is where to put the
     * answers: somewhere that reads the state once and then knows what is
     * where.
     *
     * What you will end up wanting, roughly in the order you will want it:
     *
     *   - the cells each snake actually occupies, which means expanding the
     *     coordinate chains - including the teleports;
     *   - a step that wraps: on a 35x35 board the cell below y = 34 is y = 0;
     *   - a distance that wraps with it, so "how far is the apple" is the
     *     short way round rather than the long one;
     *   - how much space a move leaves you, which is the difference between a
     *     gap and a coffin.
     *
     * None of it is written for you. Working out what belongs here is most of
     * the exercise, and a snake that answers these well is most of a good one.
     */
    static class Board {
        Board(int width, int height, String[] snakes) {
            // Read what you need out of the state, once, here.
        }
    }

    /** Anything you want to see later. It goes to my-snake.log, not to the game. */
    static void log(String message) {
        System.out.println("log " + message);
        System.out.flush();
    }
}
