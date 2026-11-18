"""Compare a run's POKEY log with the driver model in songs.py, frame by frame.

usage: python -I tools/compare.py RUN SONG START [FRAMES]
  RUN    a folder under work/runs (its pokey.txt is the per-frame-changed log)
  SONG   the song the model starts with
  START  the frame the song was requested in (the model's frame 0 is searched for in the
         8 frames after it)
  FRAMES how many frames to compare (default: to the end of the log)
Prints the alignment found, frames compared, frames where all 8 registers (AUDF1-4,
AUDC1-4) agree, and the first few disagreements.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import songs  # noqa: E402


def load(run):
    p = os.path.join(os.path.dirname(HERE), "work", "runs", run, "pokey.txt")
    st = {}
    last = 0
    cur = None
    rows = []
    for l in open(p):
        if l.startswith("#"):
            continue
        t = l.split()
        rows.append((int(t[0]), tuple(int(x, 16) for x in t[1:10])))
    return rows


def expand(rows, lo, hi):
    out = {}
    i = 0
    cur = (0,) * 9
    for f in range(1, hi + 1):
        while i < len(rows) and rows[i][0] <= f:
            cur = rows[i][1]
            i += 1
        if f >= lo:
            out[f] = cur
    return out


def same(lv, m):
    """Equal, except that a voice's AUDF is ignored while its AUDC is 00 on both sides: the
    driver never writes AUDF for a rest or an unused voice, so the last song's value stays."""
    if lv is None or lv[0] is None:
        return False
    for v in range(4):
        if lv[2 * v + 1] != m[2 * v + 1]:
            return False
        if lv[2 * v] != m[2 * v] and lv[2 * v + 1] != 0:
            return False
    return True


def main():
    run, song, start = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rows = load(run)
    end = rows[-1][0]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else end - start - 8
    live = expand(rows, start, start + n + 16)
    mod = list(songs.model(song, n))
    best = None
    for off in range(0, 9):
        ok = sum(1 for i in range(min(n, 60)) if same(live.get(start + off + i), mod[i]))
        if best is None or ok > best[1]:
            best = (off, ok)
    off = best[0]
    good = 0
    exact = 0
    bad = []
    ctl = set()
    for i in range(n):
        lv = live.get(start + off + i)
        if lv is None:
            n = i
            break
        ctl.add(lv[8])
        if lv[:8] == mod[i]:
            good += 1
            exact += 1
        elif same(lv, mod[i]):
            good += 1
        elif len(bad) < 6:
            bad.append((start + off + i, i, lv[:8], mod[i]))
    print("run %s song %d: model frame 0 = frame %d; %d of %d frames agree (%d byte-exact; the rest differ only in the AUDF of a voice whose AUDC is 00); AUDCTL values seen %s"
          % (run, song, start + off, good, n, exact, sorted("%02X" % c for c in ctl)))
    for f, i, lv, m in bad:
        print("   frame %d (model %d): live %s  model %s" % (f, i, " ".join("%02X" % x for x in lv), " ".join("%02X" % x for x in m)))


if __name__ == "__main__":
    main()
