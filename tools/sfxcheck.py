"""Check the TIA effect stream model against a run (frames.txt must PEEK 52,53,54,55 and say
where they are with --cols, 0-based among the peeked bytes).

usage: python -I tools/sfxcheck.py RUN COL52
The model: after SfxTick, a channel whose index I ($54/$55) is non-zero has just played
blob[I-1] (b6:8E0E + I - 1): AUDF = that byte, AUDV = its high nibble, and AUDC = the last
byte below $10 before it in the stream. Prints frames checked, agreeing, and the ids seen
requested (a request that is still pending at the end of a frame, or taken, shows as the
index jumping to a start offset).
"""
import os
import sys

ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
data = open(ROM, "rb").read()[128:]
B6 = data[6 * 0x4000:7 * 0x4000]
BLOB = B6[0x0E0E:0x0ED2]
STARTS = B6[0x0E02:0x0E0E]

run, col = sys.argv[1], int(sys.argv[2])
rd = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "runs", run)
tia = {}
cur = (0,) * 6
rows = []
for l in open(os.path.join(rd, "tia.txt")):
    if l.startswith("#"):
        continue
    t = l.split()
    rows.append((int(t[0]), tuple(int(x, 16) for x in t[1:7])))
frames = []
for l in open(os.path.join(rd, "frames.txt")):
    t = l.split()
    frames.append((int(t[0]), [int(x, 16) for x in t[1:]]))
i = 0
checked = good = 0
bad = []
started = {0: {}, 1: {}}
prev = [0, 0]
for f, v in frames:
    while i < len(rows) and rows[i][0] <= f:
        cur = rows[i][1]
        i += 1
    for ch in (0, 1):
        idx = v[col + 2 + ch]
        if idx != prev[ch] and idx != (prev[ch] + 1) & 0xFF and idx:
            # a jump: a new sound; which id starts just before idx?
            for sid in range(1, 12):
                s = STARTS[sid]
                if s < idx <= s + 3:
                    started[ch][sid] = started[ch].get(sid, 0) + 1
                    break
        prev[ch] = idx
        if idx:
            b = BLOB[idx - 1]
            if b < 0x10:
                continue
            checked += 1
            audf = cur[2 + ch]
            audv = cur[4 + ch]
            if audf == b and audv == b >> 4:
                good += 1
            elif len(bad) < 5:
                bad.append((f, ch, idx, b, audf, audv))
print("run %s: %d channel-frames with a sound playing, %d agree with blob[index-1] (AUDF whole byte, AUDV its high nibble)" % (run, checked, good))
for b in bad:
    print("   frame %d ch %d index %02X blob %02X  AUDF %02X AUDV %02X" % b)
for ch in (0, 1):
    print("sounds started on TIA channel %d (id: times): %s" % (ch, ", ".join("%d: %d" % kv for kv in sorted(started[ch].items()))))
