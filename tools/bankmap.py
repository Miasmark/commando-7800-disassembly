"""Bank map helpers for Commando: per-bank fill and entropy by 4K, ranges that are identical
between banks at the same address (duplicated code or tables), and the level-to-bank tables.

usage: python -I tools/bankmap.py
"""
import os
import math

ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
data = open(ROM, "rb").read()[128:]
banks = [data[i * 0x4000:(i + 1) * 0x4000] for i in range(8)]


def ent(b):
    c = [0] * 256
    for x in b:
        c[x] += 1
    n = len(b)
    return -sum(k / n * math.log2(k / n) for k in c if k)


print("entropy by 4K block (bits/byte), zero bytes %")
for i, b in enumerate(banks):
    base = 0xC000 if i == 7 else 0x8000
    print("bank %d: %s" % (i, "  ".join("%04X %.1f %2d%%" % (base + k * 0x1000, ent(b[k * 0x1000:(k + 1) * 0x1000]),
                                                             100 * b[k * 0x1000:(k + 1) * 0x1000].count(0) // 0x1000) for k in range(4))))

print("\nidentical runs of 64 bytes or more at the same address in two window banks:")
for i in range(7):
    for j in range(i + 1, 7):
        a, b = banks[i], banks[j]
        k = 0
        runs = []
        while k < 0x4000:
            if a[k] == b[k]:
                s = k
                while k < 0x4000 and a[k] == b[k]:
                    k += 1
                if k - s >= 64 and len(set(a[s:k])) > 4:
                    runs.append((s, k))
            else:
                k += 1
        if runs:
            tot = sum(e - s for s, e in runs)
            print("  banks %d,%d: %5d bytes: %s" % (i, j, tot, " ".join("%04X-%04X" % (0x8000 + s, 0x8000 + e - 1) for s, e in runs[:12])))

f7 = banks[7]
print("\nlevel -> bank tables in the fixed bank:")
print("  f7:F8F7 (bank restored by the NMIs, by level $7D):", " ".join("%d" % f7[0xF8F7 - 0xC000 + i] for i in range(9)))
print("  f7:F194 (bank for the F17A handler, by level):   ", " ".join("%d" % f7[0xF194 - 0xC000 + i] for i in range(8)))
