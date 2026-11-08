import java.io.*;
import java.util.*;

public class Snake {

    static double P(String k, double d) {
        try {
            String v = System.getProperty(k);
            return v == null ? d : Double.parseDouble(v);
        } catch (Exception e) {
            return d;
        }
    }

    static double WT = P("WT", 0.65);
    static double WA = P("WA", 600);
    static double WC = P("WC", 28);
    static double WD = P("WD", 5);
    static double TRAPK = P("TRAPK", 100);
    static double PREY = P("PREY", 5);
    static double DANGER = P("DANGER", 100000);
    static double NOOPT = P("NOOPT", 200000);
    static double NOSAFE = P("NOSAFE", 1300);
    static double ONESAFE = P("ONESAFE", 100);
    static double SAFEOPT = P("SAFEOPT", 18);
    static double AREAMIN = P("AREAMIN", 4);
    static int TAILOFF = (int) P("TAILOFF", 1);

    static int SURV = (int) P("SURV", 0);
    static double SURVK = P("SURVK", 1.0);
    static double SURVPEN = P("SURVPEN", 3000);
    static double ENDT = P("ENDT", 0);
    static double RESPLEN = P("RESPLEN", 0);
    static double RESPRISK = P("RESPRISK", 0.3);
    static int SOFTD = (int) P("SOFTD", 0);
    static double PAPPLE = P("PAPPLE", 0.75);
    static double RACE = P("RACE", 0);
    static double EATSAFE = P("EATSAFE", 0);
    static int PEAKAWARE = (int) P("PEAKAWARE", 0);
    static double APT = P("APT", 60);
    static double BUDGET_MS = P("BUDGET", 25);
    static int GROWEAT = (int) P("GROWEAT", 0);
    static int RIVGROW = (int) P("RIVGROW", 0);
    static int SAFEGATE = (int) P("SAFEGATE", 1);
    static double SAFEPEN = P("SAFEPEN", 50000);
    static double GATEFRAC = P("GATEFRAC", 0.25);
    static int POS = (int) P("POS", 0);
    static double POSW = P("POSW", 2.0);
    static int LOOK = (int) P("LOOK", 1);
    static double LOOKW = P("LOOKW", 0.5);
    static double W2 = P("W2", 0);

    static final int INF = 1 << 20;
    static final int MAXT = 2000;

    static Random rng = null;
    static int statesSeen = 0;
    static int turnEst = 0;
    static int lastLen = 0;
    static int myPeak = 0;
    static int[] peakOf = new int[8];
    static double maxMs = 0;
    static long deadline;
    static int TESTLAG = (int) P("TESTLAG", -1);

    static int hPrev = -1, facPrev = 0, ansPrev = -1, ansPrev2 = -1, lagEvidence = 0, resyncs = 0;

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String[] init = in.readLine().trim().split("\\s+");
        int snakeCount = Integer.parseInt(init[0]);
        int width = Integer.parseInt(init[1]);
        int height = Integer.parseInt(init[2]);

        while (true) {
            String first = in.readLine();
            if (first == null) return;
            first = first.trim();
            if (first.equals("Game Over")) {
                System.err.println("maxms " + maxMs + " resyncs " + resyncs);
                System.err.flush();
                return;
            }
            if (first.isEmpty()) continue;
            String[] apple = first.split("\\s+");
            int appleX = Integer.parseInt(apple[0]);
            int appleY = Integer.parseInt(apple[1]);
            int me = Integer.parseInt(in.readLine().trim());
            String[] snakes = new String[snakeCount];
            for (int i = 0; i < snakeCount; i++) snakes[i] = in.readLine();
            if (rng == null) rng = new Random(first.hashCode());

            long t0 = System.nanoTime();
            int mv;
            try {
                if (statesSeen == 0) warmUp(width, height, me, appleX, appleY, snakes);
                deadline = t0 + (long) (BUDGET_MS * 1e6);
                mv = decide(width, height, me, appleX, appleY, snakes, true);
            } catch (Throwable e) {
                mv = 5;
            }
            if (statesSeen - 1 == TESTLAG) { try { Thread.sleep(150); } catch (InterruptedException e) { } }
            if (mv >= 0) {
                System.out.println(mv);
                System.out.flush();
            }
            if (statesSeen > 1) maxMs = Math.max(maxMs, (System.nanoTime() - t0) / 1e6);
        }
    }

    static void warmUp(int w, int h, int me, int ax, int ay, String[] snakes) {
        long end = System.nanoTime() + 1_000_000_000L;
        Random saved = rng;
        rng = new Random(1);
        int savedSeen = statesSeen, savedTurn = turnEst, savedLast = lastLen, savedPeak = myPeak;
        int[] savedPeaks = peakOf.clone();
        for (int i = 0; i < 400 && System.nanoTime() < end; i++) {
            deadline = System.nanoTime() + 40_000_000L;
            decide(w, h, me, ax, ay, snakes, false);
        }
        rng = saved;
        statesSeen = savedSeen; turnEst = savedTurn; lastLen = savedLast; myPeak = savedPeak;
        peakOf = savedPeaks;
    }

    static int decide(int w, int h, int me, int ax, int ay, String[] lines, boolean real) {
        Board.appleCell = ay * w + ax;
        Board b = Board.get(w, h, lines, me);
        boolean skip = real && b.alive[me] && b.ncell[me] > 0 && lagged(b);
        if (real) {

            if (statesSeen > 0) turnEst++;
            if (statesSeen > 0 && b.alive[me] && b.len[me] < lastLen) turnEst += 5;
            statesSeen++;
            lastLen = b.len[me];
            for (int i = 0; i < b.k; i++) if (b.alive[i]) peakOf[i] = Math.max(peakOf[i], b.len[i]);
            myPeak = peakOf[me];
        }
        if (!b.alive[me] || b.ncell[me] == 0) return 0;
        int mv = new Eval(b, ay * w + ax).best();
        if (real) {
            hPrev = skip ? -1 : b.head[me];
            facPrev = b.ncell[me] < 2 ? 0 : opposite(b.reverseDir(me));
            ansPrev2 = skip ? -1 : ansPrev;
            ansPrev = skip ? -1 : mv;
        }
        return skip ? -1 : mv;
    }

    static int opposite(int d) { return d ^ 1; }

    static int applied(int a, int f) { return a == opposite(f) ? f : a; }

    static boolean lagged(Board b) {
        int me = b.me, hNow = b.head[me];
        if (hPrev < 0 || b.len[me] < lastLen) { lagEvidence = 0; return false; }
        boolean adjacent = false;
        for (int d = 0; d < 4; d++) if (b.step(hPrev, d) == hNow) adjacent = true;
        if (!adjacent || ansPrev < 0) { lagEvidence = 0; return false; }
        boolean sync = hNow == b.step(hPrev, applied(ansPrev, facPrev));
        boolean lag = ansPrev2 >= 0 && hNow == b.step(hPrev, applied(ansPrev2, facPrev));
        if (sync) lagEvidence = 0;
        else if (lag) lagEvidence++;
        if (lagEvidence >= 2) {
            lagEvidence = 0;
            resyncs++;
            return true;
        }
        return false;
    }

    static class Eval {
        final Board b;
        final int N, me, L, head;
        int apple;
        int[] rt, rl;
        final double risk;

        Eval(Board b, int apple) {
            this.b = b;
            N = b.n;
            me = b.me;
            L = b.len[me];
            head = b.head[me];
            this.apple = apple;
            rt = new int[N];
            rl = new int[N];
            Arrays.fill(rt, INF);
            for (int r = 0; r < b.k; r++) {
                if (r == me || !b.alive[r] || b.ncell[r] == 0) continue;
                int[] t = b.flood(b.head[r], 0, b.until, b.tmpA);
                for (int c = 0; c < N; c++) {
                    if (t[c] < rt[c] || (t[c] == rt[c] && b.len[r] > rl[c])) {
                        rt[c] = t[c];
                        rl[c] = b.len[r];
                    }
                }
            }
            risk = riskScale();
        }

        double riskScale() {
            double s = 1.0;
            int left = MAXT - turnEst;
            if (PEAKAWARE == 1) {

                double growth = 5.0 * left / APT;
                if (L >= myPeak) {

                    if (ENDT > 0) s = Math.min(s, Math.max(0.0, left / ENDT));
                } else if (L + growth < myPeak) {

                    s = Math.min(s, 0.05);
                }
            } else if (ENDT > 0) s = Math.min(s, Math.max(0.0, left / ENDT));
            if (RESPLEN > 0 && L < RESPLEN) s = Math.min(s, RESPRISK);
            return s;
        }

        int best() {
            int bestMove = -1;
            double bestScore = -Double.MAX_VALUE;
            int fallback = 0, fallbackUntil = Integer.MAX_VALUE;
            int rev = b.reverseDir(me);
            for (int d = 0; d < 4; d++) {
                if (d == rev) continue;
                int c = b.step(head, d);
                if (b.until[c] > 1) {
                    if (b.until[c] < fallbackUntil) { fallbackUntil = b.until[c]; fallback = d; }
                    continue;
                }
                double score = score(c);
                if (LOOK == 1 && c != apple && System.nanoTime() < deadline) {
                    score = (1 - LOOKW) * score + LOOKW * lookahead(c);
                }
                score += rng.nextDouble() * 0.001;
                if (score > bestScore) { bestScore = score; bestMove = d; }
            }
            if (bestMove < 0) bestMove = fallback;
            return bestMove;
        }

        int[] dA;

        double lookahead(int c) {
            if (dA == null) dA = b.flood(apple, 0, b.until, new int[N]).clone();
            int[] savedUntil = b.until.clone();
            int[] savedRt = rt, savedRl = rl;
            int[] savedHeads = b.head.clone();
            int savedApple = apple;
            for (int x = 0; x < N; x++) if (b.until[x] > 0) b.until[x]--;
            b.until[c] = Math.max(b.until[c], L);
            boolean appleTaken = false;
            for (int r = 0; r < b.k; r++) {
                if (r == me || !b.alive[r] || b.ncell[r] == 0) continue;
                int hd = savedHeads[r], rev = b.reverseDir(r), pick = -1, bestD = Integer.MAX_VALUE;
                for (int e = 0; e < 4; e++) {
                    if (e == rev) continue;
                    int m = b.step(hd, e);
                    if (savedUntil[m] > 1 || m == c) continue;
                    if (dA[m] < bestD) { bestD = dA[m]; pick = m; }
                }
                if (pick < 0) continue;
                b.head[r] = pick;
                b.until[pick] = Math.max(b.until[pick], b.len[r]);
                if (pick == savedApple) appleTaken = true;
            }
            int[] nrt = new int[N], nrl = new int[N];
            Arrays.fill(nrt, INF);
            for (int r = 0; r < b.k; r++) {
                if (r == me || !b.alive[r] || b.ncell[r] == 0) continue;
                int[] t = b.flood(b.head[r], 0, b.until, b.tmpA);
                for (int x = 0; x < N; x++)
                    if (t[x] < nrt[x] || (t[x] == nrt[x] && b.len[r] > nrl[x])) { nrt[x] = t[x]; nrl[x] = b.len[r]; }
            }
            rt = nrt;
            rl = nrl;
            if (appleTaken) apple = c;
            double best2 = -1e7;
            int fromDir = -1;
            for (int e = 0; e < 4; e++) if (b.step(c, e) == head) fromDir = e;
            for (int e = 0; e < 4; e++) {
                if (e == fromDir) continue;
                int m = b.step(c, e);
                if (b.until[m] > 1) continue;
                best2 = Math.max(best2, score(m));
            }
            System.arraycopy(savedUntil, 0, b.until, 0, N);
            System.arraycopy(savedHeads, 0, b.head, 0, b.k);
            rt = savedRt;
            rl = savedRl;
            apple = savedApple;
            return best2;
        }

        double score(int c) {
            boolean eats = GROWEAT == 1 && c == apple;
            if (eats) for (int j = 0; j < b.ncell[me]; j++) b.until[b.body[me][j]] += 5;
            double s = score0(c);
            if (eats) for (int j = 0; j < b.ncell[me]; j++) b.until[b.body[me][j]] -= 5;
            return s;
        }

        double score0(int c) {
            double score = 0;
            double caution = risk;
            if (W2 > 0) {
                for (int r = 0; r < b.k; r++)
                    if (r != me && b.alive[r] && b.ncell[r] > 0 && b.len[r] >= L && b.wrapDist(b.head[r], c) == 2) score -= W2;
            }
            if (SAFEGATE == 1) {
                int growth = c == apple ? 5 : 0;
                int needRoom = L + growth + (int) (L * GATEFRAC);
                if (b.mine == null) {
                    b.mine = new boolean[N];
                    for (int j = 0; j < b.ncell[me]; j++) b.mine[b.body[me][j]] = true;
                }
                int room = b.floodTerr(c, rt, b.mine);
                if (room < needRoom && !b.lastReachedTail) score -= SAFEPEN * caution;
            }

            double dangerP = 0;
            boolean prey = false;
            for (int r = 0; r < b.k; r++) {
                if (r == me || !b.alive[r] || b.ncell[r] == 0) continue;
                double p = moveProb(r, c);
                if (p <= 0) continue;
                if (b.len[r] >= L) dangerP = Math.max(dangerP, SOFTD == 1 ? p : 1.0);
                else prey = true;
            }
            if (dangerP > 0) score -= DANGER * dangerP * caution;
            else if (prey) score += PREY;

            int[] t = b.flood(c, 1, b.until, b.tmpB);
            int area = 0, territory = 0;
            for (int x = 0; x < N; x++) {
                if (t[x] >= INF) continue;
                area++;
                if (t[x] < rt[x] || (t[x] == rt[x] && L > rl[x])) territory++;
            }

            if (area >= AREAMIN) {
                int saved = b.until[c];
                b.until[c] = INF;
                int best2 = 0, nextOptions = 0, safeNext = 0;
                for (int e = 0; e < 4; e++) {
                    int m = b.step(c, e);
                    if (b.until[m] > 2) continue;
                    nextOptions++;
                    if (rt[m] > 2 || rl[m] < L) safeNext++;
                    int[] t2 = b.flood(m, 2, b.until, b.tmpC);
                    int a2 = 0;
                    for (int x = 0; x < N; x++) if (t2[x] < INF) a2++;
                    best2 = Math.max(best2, a2);
                }
                b.until[c] = saved;
                area = Math.min(area, best2 + 1);
                if (nextOptions == 0) score -= NOOPT * caution;
                else if (safeNext == 0) score -= NOSAFE * caution;
                else if (safeNext == 1) score -= ONESAFE * caution;
                score += safeNext * SAFEOPT;
            }

            int need = L;
            if (SURV == 1 && area < 3 * L + 10) {

                int K = (int) Math.min(Math.max(8, SURVK * L), 60);
                int got = b.survive(c, K, me, 20000);
                if (got < K) score -= (K - got) * SURVPEN * caution;
                if (got >= K) area = Math.max(area, need);
            }
            if (area < need) score -= (need - area) * TRAPK * caution;
            if (area < AREAMIN) score -= 1000000 * caution;
            score += territory * WT;

            int at = t[apple];
            if (at < INF) {
                int ar = rt[apple];
                if (RACE > 0) {
                    double margin = (ar >= INF ? 50 : ar - at) + (ar == at ? (L > rl[apple] ? 0.5 : -0.5) : 0);
                    double pwin = 1.0 / (1.0 + Math.exp(-margin / RACE));
                    score += pwin * (WA - at * WC) - (1 - pwin) * at * WD;
                } else if (at < ar || (at == ar && L > rl[apple])) {
                    score += WA - at * WC;
                } else if (POS == 1) {
                    score += territory * WT * (POSW - 1);
                } else {
                    score -= at * WD;
                }
            }
            return score;
        }

        double moveProb(int r, int c) {
            int hd = b.head[r];
            boolean adjacent = false;
            for (int e = 0; e < 4; e++) if (b.step(hd, e) == c) adjacent = true;
            if (!adjacent) return 0;
            if (SOFTD == 0) return 1;
            int rev = b.reverseDir(r);
            int nLegal = 0, nToward = 0;
            boolean cToward = false;
            int dHead = b.wrapDist(hd, apple);
            for (int e = 0; e < 4; e++) {
                if (e == rev) continue;
                int m = b.step(hd, e);
                if (b.until[m] > 1) continue;
                nLegal++;
                if (b.wrapDist(m, apple) < dHead) {
                    nToward++;
                    if (m == c) cToward = true;
                }
            }
            if (nLegal == 0) return 0;
            if (nToward == 0 || nToward == nLegal) return 1.0 / nLegal;
            return cToward ? PAPPLE / nToward : (1 - PAPPLE) / (nLegal - nToward);
        }
    }

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

    static class Board {
        final int w, h, n, k, me;

        final int[] until;
        final int[] head, len, ncell, pending;
        final boolean[] alive;
        final int[][] body;
        final int[] tmpA, tmpB, tmpC, queue, onPath;
        static final int[] DX = {0, 0, -1, 1};
        static final int[] DY = {-1, 1, 0, 0};
        int[] stepTab;

        private static Board cache;
        static int appleCell = -1;
        boolean[] mine;

        static Board get(int w, int h, String[] lines, int me) {
            Board b = new Board(w, h, lines, me, cache);
            cache = b;
            return b;
        }

        private Board(int w, int h, String[] lines, int me, Board old) {
            this.w = w;
            this.h = h;
            this.n = w * h;
            this.k = lines.length;
            this.me = me;
            boolean reuse = old != null && old.n == n;
            until = new int[n];
            tmpA = reuse ? old.tmpA : new int[n];
            tmpB = reuse ? old.tmpB : new int[n];
            tmpC = reuse ? old.tmpC : new int[n];
            queue = reuse ? old.queue : new int[n];
            onPath = reuse ? old.onPath : new int[n];
            stepTab = reuse ? old.stepTab : buildSteps();
            head = new int[k];
            len = new int[k];
            ncell = new int[k];
            pending = new int[k];
            alive = new boolean[k];
            body = new int[k][];
            for (int i = 0; i < k; i++) {
                String s = lines[i];
                if (s == null) { body[i] = new int[0]; continue; }
                String[] p = s.trim().split("\\s+");
                if (p.length < 4 || !p[0].equals("alive")) { body[i] = new int[0]; continue; }
                alive[i] = true;
                len[i] = Integer.parseInt(p[1]);
                List<int[]> cells = expand(parseCells(String.join(" ", Arrays.copyOfRange(p, 3, p.length))));
                int m = cells.size();
                body[i] = new int[m];
                for (int j = 0; j < m; j++) body[i][j] = cells.get(j)[1] * w + cells.get(j)[0];
                ncell[i] = m;
                if (m > 0) head[i] = body[i][0];
                pending[i] = Math.max(0, len[i] - m);
                for (int j = 0; j < m; j++) {
                    int free = pending[i] + (m - 1 - j) + TAILOFF;
                    if (RIVGROW == 1 && i != me && appleCell >= 0 && wrapDist(head[i], appleCell) < free) free += 5;
                    int c = body[i][j];
                    if (free > until[c]) until[c] = free;
                }
            }
        }

        int[] buildSteps() {
            int[] s = new int[n * 4];
            for (int c = 0; c < n; c++) {
                int x = c % w, y = c / w;
                for (int d = 0; d < 4; d++) {
                    int nx = (x + DX[d] + w) % w, ny = (y + DY[d] + h) % h;
                    s[c * 4 + d] = ny * w + nx;
                }
            }
            return s;
        }

        int step(int c, int d) { return stepTab[c * 4 + d]; }

        int wrapDist(int a, int c) {
            int dx = Math.abs(a % w - c % w), dy = Math.abs(a / w - c / w);
            return Math.min(dx, w - dx) + Math.min(dy, h - dy);
        }

        int reverseDir(int s) {
            if (ncell[s] < 2) return 1;
            int hd = body[s][0], nk = body[s][1];
            for (int d = 0; d < 4; d++) if (step(hd, d) == nk) return d;
            return -1;
        }

        static List<int[]> expand(int[][] chain) {
            List<int[]> out = new ArrayList<>();
            int cnt = chain.length;
            int i = 0;
            while (i < cnt) {
                out.add(chain[i]);
                int j = i;
                while (j + 1 < cnt && !(chain[j + 1][0] == chain[j][0] && chain[j + 1][1] == chain[j][1])) {
                    int x0 = chain[j][0], y0 = chain[j][1];
                    int x1 = chain[j + 1][0], y1 = chain[j + 1][1];
                    int sx = Integer.signum(x1 - x0), sy = Integer.signum(y1 - y0);
                    if (sx != 0 && sy != 0) {
                        out.add(chain[j + 1]);
                    } else {
                        int x = x0, y = y0;
                        while (x != x1 || y != y1) {
                            x += sx;
                            y += sy;
                            out.add(new int[] {x, y});
                        }
                    }
                    j++;
                }
                i = j + 2;
            }
            return out;
        }

        boolean lastReachedTail;

        int floodTerr(int seed, int[] rt, boolean[] mine) {
            int[] t = tmpC;
            Arrays.fill(t, INF);
            int qh = 0, qt = 0;
            t[seed] = 1;
            queue[qt++] = seed;
            lastReachedTail = false;
            while (qh < qt) {
                int c = queue[qh++];
                int nt = t[c] + 1;
                int base = c * 4;
                for (int d = 0; d < 4; d++) {
                    int x = stepTab[base + d];
                    if (t[x] != INF || until[x] > nt || rt[x] <= nt) continue;
                    t[x] = nt;
                    queue[qt++] = x;
                    if (mine[x]) lastReachedTail = true;
                }
            }
            return qt;
        }

        int[] flood(int seed, int seedTime, int[] until, int[] t) {
            Arrays.fill(t, INF);
            int qh = 0, qt = 0;
            t[seed] = seedTime;
            queue[qt++] = seed;
            while (qh < qt) {
                int c = queue[qh++];
                int nt = t[c] + 1;
                int base = c * 4;
                for (int d = 0; d < 4; d++) {
                    int x = stepTab[base + d];
                    if (t[x] != INF || until[x] > nt) continue;
                    t[x] = nt;
                    queue[qt++] = x;
                }
            }
            return t;
        }

        int pathStamp = 1;
        int nodes;

        int survive(int c, int K, int me, int nodeBudget) {
            nodes = nodeBudget;
            pathStamp++;
            if (pathStamp > 1_000_000_000) { Arrays.fill(onPath, 0); pathStamp = 1; }
            return dfs(c, 1, K);
        }

        private int dfs(int c, int t, int K) {
            if (t >= K) return K;
            if (--nodes <= 0 || System.nanoTime() > deadline) return K;
            onPath[c] = pathStamp;
            int best = t;
            int base = c * 4;

            for (int d = 0; d < 4 && best < K; d++) {
                int x = stepTab[base + d];
                if (onPath[x] == pathStamp || until[x] > t + 1) continue;
                int r = dfs(x, t + 1, K);
                if (r > best) best = r;
            }
            onPath[c] = 0;
            return best;
        }
    }
}