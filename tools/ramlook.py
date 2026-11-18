"""Look at a run's periodic RAM dumps (probe.lua RAMDUMP): series of chosen bytes, the bytes
that change in a range, and the 55-slot object table.

usage: python -I tools/ramlook.py RUN series ADDR[,ADDR...] [STEP]
       python -I tools/ramlook.py RUN changing LO HI          (hex; distinct values per byte)
       python -I tools/ramlook.py RUN objects FRAME           (the object table at one dump)
       python -I tools/ramlook.py RUN occupancy               (slots in use per dump, by range)
"""
import glob
import os
import sys

run = sys.argv[1]
rd = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "runs", run)
dumps = []
for p in sorted(glob.glob(os.path.join(rd, "ram_*.bin"))):
    dumps.append((int(os.path.basename(p)[4:9]), open(p, "rb").read()))

FIELDS = [0x1ACF, 0x1B06, 0x1B3D, 0x1B74, 0x1BAB, 0x1BE2, 0x2445, 0x247C, 0x24B3, 0x24EA, 0x2521, 0x2558]
cmd = sys.argv[2]
if cmd == "series":
    ads = [int(x, 16) for x in sys.argv[3].split(",")]
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    print("frame  " + " ".join("%04X" % a for a in ads))
    for f, d in dumps[::step]:
        print("%5d  " % f + " ".join("  %02X" % d[a] for a in ads))
elif cmd == "changing":
    lo, hi = int(sys.argv[3], 16), int(sys.argv[4], 16)
    for a in range(lo, hi + 1):
        vals = [d[a] for _, d in dumps]
        s = set(vals)
        if len(s) > 1:
            ups = sum(1 for i in range(1, len(vals)) if vals[i] > vals[i - 1])
            dn = sum(1 for i in range(1, len(vals)) if vals[i] < vals[i - 1])
            print("%04X: %3d values, up %3d down %3d, min %02X max %02X, first %s" % (a, len(s), ups, dn, min(s), max(s), " ".join("%02X" % v for v in vals[:16])))
elif cmd == "objects":
    fr = int(sys.argv[3])
    d = [x for f, x in dumps if f == fr][0]
    print("slot " + " ".join("%04X" % a for a in FIELDS))
    for s in range(55):
        row = [d[a + s] for a in FIELDS]
        if d[0x1ACF + s] != 0xB4 or d[0x24EA + s] not in (0, 1):
            print(" %2d   " % s + " ".join("  %02X" % v for v in row))
elif cmd == "occupancy":
    for f, d in dumps:
        act = [s for s in range(55) if d[0x1ACF + s] != 0xB4]
        print("%5d  %2d  %s" % (f, len(act), " ".join("%d" % s for s in act)))
