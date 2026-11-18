"""Raw scan of every bank for the sound request idioms (prints addresses and ids only).

  LDA #id / STA $52 or $53        an effect request, channel 0 or 1 (TIA)
  LDA #n  / STA $211E             a song request (the music mailbox)
  LDX #n  / JSR $A00F             MusicReset with X (bank 6 vector)
Also counts other stores to $52/$53 (STA zp, STX, STY, indexed) so a non-immediate request
is not missed. A raw scan can match data bytes: check a hit against the listing.

usage: python -I tools/requests.py
"""
import os
ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
data = open(ROM, "rb").read()[128:]

for bank in range(8):
    b = data[bank * 0x4000:(bank + 1) * 0x4000]
    base = 0xC000 if bank == 7 else 0x8000
    sp = "f7" if bank == 7 else "b%d" % bank
    for i in range(len(b) - 5):
        if b[i] == 0xA9 and b[i + 2] == 0x85 and b[i + 3] in (0x52, 0x53):
            print("%s:%04X  effect id %2d on TIA channel %d" % (sp, base + i, b[i + 1], b[i + 3] - 0x52))
        if b[i] == 0xA9 and b[i + 2] == 0x8D and b[i + 3] == 0x1E and b[i + 4] == 0x21:
            print("%s:%04X  song request %d" % (sp, base + i, b[i + 1]))
        if b[i] == 0xA2 and b[i + 2] == 0x20 and b[i + 3] == 0x0F and b[i + 4] == 0xA0:
            print("%s:%04X  MusicReset X=%d" % (sp, base + i, b[i + 1]))
        if b[i] == 0x20 and b[i + 1] == 0x0F and b[i + 2] == 0xA0 and not (i >= 2 and b[i - 2] == 0xA2):
            print("%s:%04X  JSR MusicReset, X not an immediate just before" % (sp, base + i))
        if b[i] in (0x86, 0x84, 0x95, 0x96, 0x94) and b[i + 1] in (0x52, 0x53):
            print("%s:%04X  other store to $%02X (opcode %02X)" % (sp, base + i, b[i + 1], b[i]))
        if b[i] == 0x85 and b[i + 1] in (0x52, 0x53) and not (i >= 2 and b[i - 2] == 0xA9):
            print("%s:%04X  STA $%02X, A not an immediate just before" % (sp, base + i, b[i + 1]))
        if b[i] == 0x8D and b[i + 1] == 0x1E and b[i + 2] == 0x21 and not (i >= 2 and b[i - 2] == 0xA9):
            print("%s:%04X  STA $211E, A not an immediate just before" % (sp, base + i))
