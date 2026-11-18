"""Write this project's hand annotations into annotations.json (idempotent: it sets keys, it
never removes what dyn.py or a person added). Run it, then disasm.py and verify.py.

usage: python -I tools/annotate.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
data = open(ROM, "rb").read()[128:]


def byte(space, addr):
    bank = int(space[1])
    base = 0xC000 if space[0] == "f" else 0x8000
    return data[bank * 0x4000 + addr - base]


p = os.path.join(PROJ, "annotations.json")
d = json.load(open(p))

# --- bank switches whose value comes from a table (by level, $7D)
LEVEL = [1, 2, 3, 4, 5]
for loc in ("f7:F018", "f7:F171", "f7:F972", "f7:F8E0", "f7:FC37"):
    d.setdefault("banksw", {})[loc] = LEVEL
d["banksw"]["f7:F182"] = [3, 4, 5, 6]

# --- entries: the JMP tables (only where the byte is a JMP opcode)
ents = set(d["entries"])
for a in range(0xA000, 0xA02A, 3):
    if byte("b6", a) == 0x4C:
        ents.add("b6:%04X" % a)
for b in (1, 2, 3, 4, 5):
    for a in list(range(0xB200, 0xB21B, 3)) + [0x9C00, 0x9C15]:
        if byte("b%d" % b, a) == 0x4C or (a == 0x9C00 and byte("b%d" % b, a) == 0x20):
            ents.add("b%d:%04X" % (b, a))
if byte("b5", 0xB000) == 0x4C:
    ents.add("b5:B000")
for a in list(range(0xEC00, 0xEC18, 3)) + list(range(0xED00, 0xED15, 3)) + list(range(0xEA00, 0xEA06, 3)):
    if byte("f7", a) == 0x4C:
        ents.add("f7:%04X" % a)
d["entries"] = sorted(ents, key=lambda s: (s not in ("f7:DD67", "f7:F000"), s))

labels = {
    "f7:DD67": "ENTRY_Reset", "f7:F000": "ENTRY_Nmi",
    "f7:F009": "Dli_Top", "f7:F06A": "Dli_ZonePalette", "f7:F0F8": "Dli_Bottom",
    "f7:F111": "PauseSwitch", "f7:F15B": "PausedSilence", "f7:F16C": "Dli_RestoreBank",
    "f7:DDDD": "MainLoop", "f7:DDEA": "PauseSpin", "f7:DDC5": "StartGame", "f7:DDA5": "WarmStart",
    "f7:F19C": "BuildRowLists", "f7:F2A9": "DrawListAdd", "f7:F2E1": "NodeTake", "f7:F2F2": "NodeGiveBack",
    "f7:F8F7": "LevelBank", "f7:F194": "LevelBank2",
    "b6:8ED2": "SfxTick", "b6:8E02": "SfxStart", "b6:8E0E": "SfxStream",
    "b6:A71C": "NoteOn", "b6:A73C": "NoteOn_Pitched", "b6:A75D": "EnvStep",
    "b6:A778": "EnvVecLo", "b6:A77D": "EnvVecHi",
    "b6:A782": "Env_Attack", "b6:A7B5": "Env_Decay", "b6:A7E2": "Env_Sustain",
    "b6:A7F1": "Env_Release", "b6:A812": "Env_Off",
    "b6:A818": "VoiceTick", "b6:A825": "NextNote", "b6:A839": "NextPattern", "b6:A851": "TrackEnd",
    "b6:A86F": "MusicStart", "b6:A8DF": "VoiceBit", "b6:A8E7": "IncTrackPtr", "b6:A8EE": "IncPatPtr",
    "b6:A8F5": "MusicReset", "b6:A905": "ResetSongByLevel", "b6:A90E": "MusicTick", "b6:A935": "MusicSilent",
    "b6:A941": "DurTable", "b6:A951": "Instruments", "b6:AA51": "SongAudctl", "b6:AA61": "SongTracks",
    "b6:B640": "SongTable",
    "b6:B699": "TopDliBody", "b6:B70A": "Dli_Resync",
    "b6:A000": "Vec_SfxTick", "b6:A00F": "Vec_MusicReset", "b6:A012": "Vec_MusicTick", "b6:A018": "Vec_TopDliBody",
    "b6:A39B": "CopyTitleCodeToRam", "b6:A3B3": "TitleCodeImage",
    "b6:8CDB": "DrawListInit", "b6:8BA9": "ClearRam",
}
d.setdefault("labels", {}).update(labels)

ram = {
    "52": "SfxReq0", "53": "SfxReq1", "54": "SfxIdx0", "55": "SfxIdx1",
    "AE": "DliVecLo", "AF": "DliVecHi", "E2": "DliSeen", "F5": "PauseDown", "F6": "Paused",
    "7D": "Level", "B1": "ScrollRow", "B0": "ScrollFine", "79": "BuildBuffer", "FF": "ShownBuffer",
    "E3": "DrawHead", "E4": "DrawTail", "E5": "TrackPtr", "ED": "PatPtr",
    "2100": "NoteByte0", "2101": "NoteByte1", "2102": "EnvJmpLo", "2103": "EnvJmpHi",
    "2104": "SongNow", "2105": "VoiceMask", "2106": "VoiceStage", "2107": "VoiceDur",
    "210E": "VoiceIns", "210F": "VoiceStageCnt", "2116": "VoiceNotesLeft", "2117": "VoiceVol",
    "211E": "SongRequest",
    "1ACF": "ObjX", "1B06": "ObjY", "1B74": "ObjPalWidth", "24EA": "ObjState",
    "25D4": "NodePut", "25D5": "NodeGet", "25D6": "NodeRing",
}
d.setdefault("ram", {}).update(ram)

headers = {
    "b6:8ED2": "SfxTick: the whole TIA effects driver (67 bytes). X = channel 1 then 0. A request (SfxReq, an id 1-11)\n"
               "is taken only if its start offset in SfxStream is ABOVE the channel's current index: position in the\n"
               "blob is the priority, an idle channel has index 0. A refused request stays in SfxReq until the sound\n"
               "ends, which clears it. Stream: $00 end; $01-$0F set AUDC, no time; $10-$FF = AUDF (whole byte) with\n"
               "AUDV = its high nibble, one frame. Called from Dli_Bottom (vblank) unless paused. (live)",
    "b6:A90E": "MusicTick: once a frame from TopDliBody (inside the top DLI), skipped while Paused. A non-zero\n"
               "SongRequest starts that song and returns. Otherwise each voice in VoiceMask runs VoiceTick:\n"
               "envelope step, then the note's duration, then the next note / pattern / track end. SongNow = $FF\n"
               "writes AUDC = 0 on all four voices every frame. (live: model equal to the chip log for 11 songs)",
    "b6:A86F": "MusicStart: A = song. AUDCTL from SongAudctl (all 0 here), the song's 8-byte record (4 track\n"
               "pointers) to TrackPtr, VoiceMask from the non-zero pointers, AUDC = 0 on all four, first pattern\n"
               "and first note of each used voice.",
    "b6:A851": "TrackEnd: a track entry with a zero high byte ends it; its low byte is the command: 0 restart\n"
               "this song, $80-$FF stop (SongNow = $FF), n = start song n-1. The first voice to end decides.",
    "b6:A71C": "NoteOn: byte 0 = instrument (high nibble) and duration index (low nibble, DurTable, frames);\n"
               "byte 1 = AUDF, 0 = rest. A pitched note writes AUDF and the instrument's AUDC once; a rest goes\n"
               "straight to Env_Off. AUDF is never written again until the next pitched note.",
    "b6:A75D": "EnvStep: five stages through a jump table (JMP (EnvJmpLo)): attack (add to an 8-bit level up to the\n"
               "peak), decay (subtract down to the sustain level), sustain (counts, writes nothing), release\n"
               "(subtract to 0), off (AUDC = 0 every frame). AUDC = instrument byte 0 | level >> 4. A stage's\n"
               "length is a counter tested DEC / BPL, so a length of $80-$FF ends at once.",
    "b6:A8F5": "MusicReset: SKCTL = 0 then 3 (the only POKEY set-up besides the reset code's clear of\n"
               "$4000-$4010), then MusicStart with ResetSongByLevel,X (X = level 0-7, 8 = title).",
    "b6:B699": "TopDliBody: CTRL, the next DLI vector, eight palette colours, MusicTick (unless Paused), then a\n"
               "spin on DliSeen until Dli_Resync (the next DLI, taken INSIDE this handler) sets it: the music\n"
               "tick's variable time is absorbed before the first raster-timed writes.",
    "f7:F0F8": "Dli_Bottom: the last DLI (vblank work): flip DPPL to the finished list, the Pause switch (toggle\n"
               "Paused on release), bank 6 for the status code and SfxTick; while Paused it zeroes AUDV0/1 and\n"
               "POKEY $4000-$4008 every frame instead. Restores the level's bank from LevelBank.",
    "f7:F009": "Dli_Top: the first DLI. Switches bank 6 in for TopDliBody (music) and the level's bank back in\n"
               "(LevelBank by Level): an NMI that switches banks, not transferable to a BankSet cart.",
}
d.setdefault("headers", {}).update(headers)

comments = {
    "b6:8EDC": "accept only if the start offset is above the current index (priority = position)",
    "b6:8F0F": "the end of a sound also drops a refused request",
    "b6:A915": "SongRequest is the song number itself, so song 0 cannot be requested this way",
    "b6:A87D": "AUDCTL per song (every entry is 0: 64 kHz clock, no joins, no filters)",
    "b6:A7E2": "sustain: no register write at all",
    "f7:F163": "pause: AUDF1-4, AUDC1-4 and AUDCTL zeroed; a note held across the pause comes back with AUDF 0",
    "f7:DDEA": "the main loop parks here while Paused; the DLI chain keeps running",
    "b6:B6DA": "wait for the next DLI (Dli_Resync) to fire inside this one",
    "f7:D9AA": "song 3: level cleared",
    "f7:DF24": "song 6: game over",
    "f7:F85C": "song 2: the level's last fight",
    "f7:FA9F": "song 1: the player dies",
}
d.setdefault("comments", {}).update(comments)

blocks = [
    {"loc": "b6:8E02", "len": 12, "name": "SfxStart", "note": "start offset in SfxStream per effect id (0-11); also its priority (live)"},
    {"loc": "b6:8E0E", "end": "b6:8ED1", "name": "SfxStream", "note": "TIA effect streams, 196 bytes; index 0 is the idle terminator"},
    {"loc": "b6:A941", "len": 16, "name": "DurTable", "note": "note lengths in frames, longest first"},
    {"loc": "b6:A951", "len": 256, "name": "Instruments", "note": "16 x 16 bytes, 10 used: AUDC base, attack frames, peak, attack add, decay frames, sustain level, decay sub, sustain frames, release frames, release sub"},
    {"loc": "b6:AA51", "len": 16, "name": "SongAudctl", "note": "AUDCTL per song, all zero"},
    {"loc": "b6:AA61", "end": "b6:B63F", "name": "SongTracks", "note": "track lists (pattern pointers, ended by a zero high byte whose low byte is the command) then 43 count-prefixed patterns of 2-byte notes"},
    {"loc": "b6:B640", "len": 88, "name": "SongTable", "note": "11 songs x 4 track pointers (0 = voice unused)"},
    {"loc": "b6:A3B3", "end": "b6:A672", "name": "TitleCodeImage", "note": "copied to RAM $1D00-$1FBF by CopyTitleCodeToRam and run there (the title screen's loop and its NMI handler at $1DEA, which switch between banks 6 and 0); not disassembled in place because it is assembled for $1D00"},
]
have = {b["loc"] for b in d.get("blocks", [])}
for b in blocks:
    if b["loc"] not in have:
        d.setdefault("blocks", []).append(b)

d.setdefault("notes", {})["b6"] = ("Bank 6: sound (SfxTick b6:8ED2, music driver b6:A71C-A940, song data b6:A941-B698), the\n"
                                 "top DLI's body, title and copyright screens (their code is copied to RAM), init.\n"
                                 "Entered through the JMP table at b6:A000-A029.")
json.dump(d, open(p, "w"), indent=2)
print("annotations.json written: %d entries, %d labels, %d ram names, %d blocks" % (len(d["entries"]), len(d["labels"]), len(d["ram"]), len(d["blocks"])))
