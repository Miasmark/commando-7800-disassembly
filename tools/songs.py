"""Walk Commando's POKEY song data (bank 6) and print its structure and sizes.

usage: python -I tools/songs.py [--model N OUT]   (N = song number; writes the model's
       per-frame register state for song N as "frame f1 c1 f2 c2 f3 c3 f4 c4" lines,
       following chains and loops for --frames F frames, default 3000)

Prints structure and statistics only (no note data): per song the voices used, the
patterns each track lists, the terminator's meaning, the length in frames and the bytes.
The model is the driver at b6:A71C-A940 transcribed (see docs/FINDINGS.md).
"""
import os
import sys

ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
data = open(ROM, "rb").read()[128:]
B6 = data[6 * 0x4000:7 * 0x4000]


def rb(a):
    return B6[a - 0x8000]


def rw(a):
    return rb(a) | (rb(a + 1) << 8)


DUR = 0xA941
INS = 0xA951
CTL = 0xAA51
SONGS = 0xB640
NSONGS = 11


def track(ptr):
    """-> (list of pattern addresses, terminator low byte, bytes used)"""
    pats = []
    a = ptr
    while True:
        lo, hi = rb(a), rb(a + 1)
        if hi == 0:
            return pats, lo, a + 2 - ptr
        pats.append(lo | (hi << 8))
        a += 2


def pattern(p):
    n = rb(p)
    notes = [(rb(p + 1 + 2 * i), rb(p + 2 + 2 * i)) for i in range(n)]
    return notes


def term_text(lo):
    if lo == 0:
        return "loop (restart this song)"
    if lo & 0x80:
        return "stop (song = $FF, all AUDC = 0)"
    return "chain to song %d" % (lo - 1)


def summary():
    allpat = {}
    total_track = 0
    print("song table b6:%04X, %d songs x 8 bytes (4 track pointers); AUDCTL per song at b6:%04X" % (SONGS, NSONGS, CTL))
    for s in range(NSONGS):
        ptrs = [rw(SONGS + 8 * s + 2 * v) for v in range(4)]
        print("song %2d  AUDCTL $%02X" % (s, rb(CTL + s)))
        mine = set()
        tb = 0
        for v, p in enumerate(ptrs):
            if p == 0:
                print("   voice %d: unused" % (v + 1))
                continue
            pats, lo, used = track(p)
            tb += used
            frames = 0
            insts = set()
            pit = []
            for q in pats:
                notes = pattern(q)
                allpat.setdefault(q, 1 + 2 * len(notes))
                mine.add(q)
                for b0, b1 in notes:
                    frames += rb(DUR + (b0 & 15))
                    if b1:
                        insts.add(b0 >> 4)
                        pit.append(b1)
            print("   voice %d: track b6:%04X, %2d patterns (%2d distinct), %5d frames, instruments %s, AUDF $%02X-$%02X, end: %s"
                  % (v + 1, p, len(pats), len(set(pats)), frames, sorted(insts), min(pit) if pit else 0, max(pit) if pit else 0, term_text(lo)))
        pb = sum(allpat[q] for q in mine)
        total_track += tb
        print("   bytes: tracks %d + patterns %d (patterns shared with other songs count in each)" % (tb, pb))
    print("distinct patterns: %d, %d bytes; tracks %d bytes; song table %d; instruments 256; durations 16; AUDCTL table 16"
          % (len(allpat), sum(allpat.values()), total_track, NSONGS * 8))
    print("instruments (b6:%04X, 16 bytes each, 10 used): AUDC base, attack frames, peak, attack add, decay frames, sustain level, decay sub, sustain frames, release frames, release sub" % INS)
    for i in range(16):
        r = [rb(INS + 16 * i + k) for k in range(10)]
        print("   %2d: %s" % (i, " ".join("%02X" % x for x in r)))


class Voice:
    def __init__(self):
        self.on = False


def model(song, nframes):
    """Transcription of the driver. Yields per-frame (audf1, audc1, ... audc4)."""
    reg = [0] * 8
    st = {"song": song, "v": [None] * 4}

    def note_on(v, b0, b1):
        V = st["v"][v]
        V["dur"] = rb(DUR + (b0 & 15))
        if b1 == 0:
            V["stage"] = 4
            V["cnt"] = rb(INS + V["ins"] + 8)
            return
        reg[2 * v] = b1
        V["stage"] = 0
        V["vol"] = 0
        V["ins"] = b0 & 0xF0
        V["cnt"] = rb(INS + V["ins"] + 1)
        reg[2 * v + 1] = rb(INS + V["ins"])

    def next_note(v):
        V = st["v"][v]
        V["pp"] += 1
        b0 = rb(V["pp"])
        V["pp"] += 1
        b1 = rb(V["pp"])
        note_on(v, b0, b1)

    def start(song):
        st["song"] = song
        ptrs = [rw(SONGS + 8 * song + 2 * v) for v in range(4)]
        for v in (3, 2, 1, 0):
            reg[2 * v + 1] = 0
            if ptrs[v] == 0:
                st["v"][v] = None
                continue
            V = {"tp": ptrs[v], "ins": 0, "stage": 4, "vol": 0, "cnt": 0, "dur": 0}
            st["v"][v] = V
            V["pp"] = rw(V["tp"])
            V["tp"] += 1
            V["left"] = rb(V["pp"])
            next_note(v)

    def env(v):
        V = st["v"][v]
        i = INS + V["ins"]
        s = min(V["stage"], 4)
        if s == 0:
            a = rb(i + 3) + V["vol"]
            if a > 255 or a >= rb(i + 2):
                a = rb(i + 2)
            V["vol"] = a
            reg[2 * v + 1] = (a >> 4) | rb(i)
            V["cnt"] = (V["cnt"] - 1) & 0xFF
            if V["cnt"] & 0x80:
                V["cnt"] = rb(i + 4)
                V["stage"] += 1
                V["vol"] = rb(i + 2)
        elif s == 1:
            a = V["vol"] - rb(i + 6)
            if a < 0 or a < rb(i + 5):
                a = rb(i + 5)
            V["vol"] = a
            reg[2 * v + 1] = (a >> 4) | rb(i)
            V["cnt"] = (V["cnt"] - 1) & 0xFF
            if V["cnt"] & 0x80:
                V["cnt"] = rb(i + 7)
                V["stage"] += 1
        elif s == 2:
            V["cnt"] = (V["cnt"] - 1) & 0xFF
            if V["cnt"] & 0x80:
                V["cnt"] = rb(i + 8)
                V["stage"] += 1
        elif s == 3:
            a = V["vol"] - rb(i + 9)
            if a < 0:
                a = 0
            V["vol"] = a
            reg[2 * v + 1] = (a >> 4) | rb(i)
            V["cnt"] = (V["cnt"] - 1) & 0xFF
            if V["cnt"] & 0x80:
                V["stage"] += 1
        else:
            reg[2 * v + 1] = 0
        # the stage counters are bytes tested with DEC / BPL: a length of $80-$FF ends at once

    start(song)
    yield tuple(reg)
    for _ in range(nframes - 1):
        if st["song"] == 0xFF:
            for v in range(4):
                reg[2 * v + 1] = 0
            yield tuple(reg)
            continue
        restart = None
        for v in (3, 2, 1, 0):
            V = st["v"][v]
            if V is None:
                continue
            env(v)
            V["dur"] = (V["dur"] - 1) & 0xFF
            if V["dur"]:
                continue
            V["left"] = (V["left"] - 1) & 0xFF
            if V["left"]:
                next_note(v)
                continue
            V["tp"] += 1
            lo = rb(V["tp"])
            V["tp"] += 1
            hi = rb(V["tp"])
            if hi:
                V["pp"] = lo | (hi << 8)
                V["left"] = rb(V["pp"])
                next_note(v)
                continue
            if lo == 0:
                restart = st["song"]
            elif lo & 0x80:
                st["song"] = 0xFF
            else:
                restart = lo - 1
            break            # the driver leaves the voice loop (X = 0)
        if restart is not None:
            start(restart)
        yield tuple(reg)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--model":
        n = int(sys.argv[2])
        out = sys.argv[3]
        frames = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[4] == "--frames" else 3000
        with open(out, "w") as f:
            for i, r in enumerate(model(n, frames)):
                f.write("%d %s\n" % (i, " ".join("%02X" % x for x in r)))
    else:
        summary()
