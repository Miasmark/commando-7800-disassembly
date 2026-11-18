"""Second pass of hand annotations (run after annotate.py): the frame, the map and the object
lists, and a note per bank. Idempotent.

usage: python -I tools/annotate2.py
"""
import json
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(PROJ, "annotations.json")
d = json.load(open(p))

d.setdefault("headers", {}).update({
    "f7:F06A": "Dli_ZonePalette: one per 16-line playfield zone (11 a frame). A byte per map row (level bank\n"
               "$9B80,Y for levels 0-3, $BB00,Y for 4-7): bits 5-6 pick the palette, bits 0-4 an entry of the\n"
               "RAM colour tables $2751/$2764/$2777. (code)",
    "f7:F19C": "BuildRowLists: for the 17 rows on screen (Y = ScrollRow + $10 down) copy the row's staged\n"
               "sprite headers into the hidden display list and add the background: ONE 5-byte indirect\n"
               "object, 20 two-byte characters, whose pointer is the map row itself in the level bank (20\n"
               "bytes a row). (code; the lists decoded live from a RAM dump)",
    "f7:F2A9": "DrawListAdd: A = object slot. Takes a node from the ring of 20 free node numbers (NodeTake),\n"
               "links it at the tail of a doubly linked list ($256F object, $2584 next, $2598 previous, head\n"
               "DrawHead, tail DrawTail), and marks the slot listed ($25AC). (code)",
    "f7:FBDD": "Fade out and display off: starts the palette fade (counter $FD, stepped in vblank by b6:B886),\n"
               "waits for it, then CTRL = $7F. The main thread changes bank only after this, so the NMIs can\n"
               "restore the bank from LevelBank,Level instead of a shadow. (code)",
})
d.setdefault("comments", {}).update({
    "b6:A109": "bonus items by map row: count b6:A163 and end index b6:A1A2 per level; rows b6:A16C, x b6:A187, sprite b6:A1AA, palette/width b6:A1C5, value b6:A1E0",
})
d.setdefault("notes", {}).update({
    "b0": "Bank 0: the title picture, a 160B bitmap (12 zones of 16 lines, 80 bytes a line, a page per\n"
          "line, $8000-$B0EF). Paged in only by the title code that runs in RAM. (live)",
    "b1": "Bank 1: levels 1 and 5 (LevelBank f7:F8F7 = 1 2 3 4 1 2 3 4 5). Map rows of 20 two-byte\n"
          "characters drawn in place, row tables at $9B00/$9B80 and $BA80/$BB00, sprites, set-piece code\n"
          "($9C00), and the common block $B200-$B6A2 that banks 1-5 all carry (JMP table at $B200).",
    "b2": "Bank 2: levels 2 and 6. Same layout as bank 1; traced statically only.",
    "b3": "Bank 3: levels 3 and 7. Same layout as bank 1; traced statically only.",
    "b4": "Bank 4: levels 4 and 8. Same layout as bank 1; traced statically only.",
    "b5": "Bank 5: entry 8 of LevelBank; its $B000 is called at each game and life start with DMA off.\n"
          "Carries the common block too. Role otherwise not established.",
})
MARK = "\n\nStudy notes:"
d["notes"]["f7"] = d["notes"].get("f7", "").split(MARK)[0] + (
    MARK + " fixed bank. Reset f7:DD67, main loop f7:DDDD, NMI f7:F000 -> JMP ($AE): Dli_Top f7:F009\n"
    "(bank 6: music), Dli_Resync b6:B70A, Dli_ZonePalette f7:F06A x11, Dli_Bottom f7:F0F8 (flip, pause,\n"
    "effects). Both sound ticks run inside NMIs that page bank 6 in and the level's bank back.")
d.setdefault("labels", {}).update({"f7:FBDD": "FadeOutDisplayOff", "b6:B886": "FadeStep"})
json.dump(d, open(p, "w"), indent=2)
print("second pass written: %d headers, %d notes" % (len(d["headers"]), len(d["notes"])))
