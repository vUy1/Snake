// The Java skeleton for the course text protocol: read the state, print a move.
// The same shape as `my-snake/Snake.java`, with the commentary stripped out.
//
//   javac -d build Snake.java
//   python -m snake.cli play "cmd:java -cp build Snake" survivor hungry wander --seed 1
//
// See docs/protocol.md for the wire format, including the wrapping rule.

import java.io.*;
import java.util.*;

public class Snake {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String[] init = in.readLine().trim().split("\\s+");
        int snakeCount = Integer.parseInt(init[0]);
        int width = Integer.parseInt(init[1]);
        int height = Integer.parseInt(init[2]);

        Random rng = null;
        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.equals("Game Over")) return;
            if (line.isEmpty()) continue;

            String[] apple = line.split("\\s+");
            int appleX = Integer.parseInt(apple[0]), appleY = Integer.parseInt(apple[1]);
            int me = Integer.parseInt(in.readLine().trim());
            String[] snakes = new String[snakeCount];
            for (int i = 0; i < snakeCount; i++) snakes[i] = in.readLine();

            if (rng == null) rng = new Random(line.hashCode());

            // 0 up, 1 down, 2 left, 3 right; 4 left, 5 straight, 6 right.
            System.out.println(rng.nextInt(4));
            System.out.flush();
        }
    }

    /** "10,12 15,12" -> {{10,12},{15,12}}. A repeated point is a teleport. */
    static int[][] parseCells(String line) {
        if (line == null || line.trim().isEmpty()) return new int[0][];
        String[] parts = line.trim().split("\\s+");
        int[][] cells = new int[parts.length][2];
        for (int i = 0; i < parts.length; i++) {
            int comma = parts[i].indexOf(',');
            cells[i][0] = Integer.parseInt(parts[i].substring(0, comma));
            cells[i][1] = Integer.parseInt(parts[i].substring(comma + 1));
        }
        return cells;
    }
}
