# Commando (Atari 7800, NTSC, 1989): findings

ROM: `Commando (NTSC) (Atari) (1989) (CD1A98C5).a78`, 128K SuperGame, POKEY at `$4000`.
Addresses are `space:address` as `annotations.json` keys them: `f7` is the fixed bank
(`$C000-$FFFF`), `b0`-`b6` the banks in the `$8000-$BFFF` window. Levels are numbered as
the game does, 0-7.

Evidence tags: **(live)** watched in MAME (the fork `a78.exe`, windowless): a register log, a
trace, a RAM dump or a poke that changed behaviour. **(code)** read from the listing only.
**(hint)** a guess. Run folders are under `work/runs/`; each claim names its run.

Studied 2026-11-18. Sound first (questions 1-3), then the game's structure (question 4).
Dead ends and corrections are in the last section.

## What already existed

- Beside the ROM: `.log` is a POKEY register capture of the cartridge (the toolkit's
  `probes/audio.lua` format: one line per frame in which a register changed, 2,699 frames:
  the intro tune and the start of the level tune of a started game), `.trk` is that capture
  as a tracker song (`tracker.py capture`), and `.wav` is its rendering (40 s).
- `Documents\Atari 7800\commando-listen`: eleven WAV files, one per song (0-10), each
  exactly its song's length, named by where the tune plays ("00-intro-when-a-game-starts"
  ... "10-level-background"). They were used to name the songs by ear.
- The toolkit already describes the **song data format**: `formats/commando-pokey.json`
  (song table `b6:B640`, durations `b6:A941`, instruments `b6:A951`, the "adsr5" envelope,
  checked at 576/576 frames for song 0) and `docs/audio.md` "## The same engine on a different
  chip" (it is Midnight Mutants' music engine on POKEY).
- New here: the driver's code (where it runs, its size, RAM and cycles), the track-end
  commands, the request mailbox, every song checked against the chip, the effects driver,
  pause, no-POKEY behaviour, and the game around it.

## 1. The POKEY music driver

### Where it is and what it costs

- **Code:** `b6:A71C-A940`, 549 bytes including three small tables (`EnvVecLo/Hi` 10 bytes,
  `VoiceBit` 8, `ResetSongByLevel` 9). Entry points through bank 6's JMP table: `b6:A00F`
  MusicReset, `b6:A012` MusicTick. (code)
- **Data, all in bank 6:** `DurTable` `b6:A941` 16 bytes; `Instruments` `b6:A951` 256 bytes
  (16 x 16, ten bytes of each used); `SongAudctl` `b6:AA51` 16 bytes; tracks and patterns
  `b6:AA61-B63F` 3,039 bytes (tracks 200, 43 patterns 2,839); `SongTable` `b6:B640` 88 bytes.
  Total 3,415 bytes for 11 songs and 6,912 frames (115 s) of distinct music: about 30 bytes
  a second. `tools/songs.py` prints each song's bytes (the largest, song 8, is 34 + 662
  bytes for 1,728 frames). (code)
- **RAM:** 31 bytes at `$2100-$211E` and 16 bytes of zero page `$E5-$F4` (four track
  pointers, four pattern pointers). Per voice (X = 0, 2, 4, 6): `$2106,X` envelope stage,
  `$2107,X` frames left in the note, `$210E,X` instrument offset, `$210F,X` stage counter,
  `$2116,X` notes left in the pattern, `$2117,X` 8-bit volume level. Globals: `$2104` song
  now (`$FF` = none), `$2105` voice mask, `$211E` song request. (code; `$2104`, `$2105`,
  `$211E`, `$2106`, `$2107`, `$2117` peeked live in runs `attract`, `play1`, `play2`)
- **Cycles per frame:** MusicTick with four voices: mean 560, median 557, 95% under 757,
  maximum 1,395 (a frame in which every voice fetches a note and some change pattern). Two
  voices: mean about 360. Stopped: 73. MusicStart: 1,161. Counted by running the cartridge's
  own code in the toolkit's 6502 core (`tools/cycles.py`, 6,997 ticks over all 11 songs:
  exact CPU cycles, no DMA). MAME agrees: elapsed time from `b6:A012` to its return, median
  586-592 cycles' worth, maximum 2,232, DMA included (live, run `play2`).
- About 140 cycles a voice a frame: every access is `abs,X` or `(zp,X)` and the envelope goes
  through a `JMP (ram)` table.

### Where it is called from, and banking

- **From the first display interrupt of the frame, inside the NMI.** `ENTRY_Nmi` `f7:F000`
  pushes A, X, Y and does `JMP ($AE)` (a DLI chain kept in a RAM vector). The first handler,
  `Dli_Top` `f7:F009`, writes bank 6 to `$8000` (`f7:F00B`) and calls `b6:A018` (`TopDliBody`
  `b6:B699`), which sets CTRL and eight colours and then calls MusicTick unless `Paused`
  (`$F6`) (`b6:B6D3-B6D7`). Back at `f7:F013` it restores the level's bank from the table
  `LevelBank` `f7:F8F7` indexed by `Level` (`$7D`). (code; live: the tick starts on raster 27
  in all 1,678 gameplay frames timed in run `play2`, and `banks.txt` counts the writes at
  `f7:F00B`/`F018` once a frame)
- **This is an NMI that switches banks: not transferable to a BankSet cart as it is.** The
  driver and all its data sit in a switched bank and are reached only by paging them in from
  the interrupt.
- The title screen runs code copied to console RAM (image at `b6:A3B3`, 704 bytes, to
  `$1D00`); its NMI handler at `$1DEA` pages bank 6, calls `b6:A012`, then pages bank 0 for
  the title picture. (live: run `attract`, 1,800 switches each way in 900 frames)
- After the tick, `TopDliBody` spins on `$E2` until the *next* DLI (`Dli_Resync` `b6:B70A`,
  taken inside the first handler) sets it, then does its raster-timed colour writes. The
  tick's variable time is absorbed before anything that must hit a line. The first handler
  holds the CPU for about 4,580 cycles (about 40 lines) every frame. (live: run `play2`,
  `time.txt`, 4,569-4,725)

### Song data format

- **Song table** `b6:B640`: 8 bytes a song, four track pointers, voices 1 to 4; a zero
  pointer means the voice is unused (songs 1 and 2 use two voices). (code)
- **Track:** a list of 2-byte pattern pointers. An entry whose high byte is 0 ends the track,
  and its low byte is a command (`TrackEnd` `b6:A851`): **0 = restart this song; `$80-$FF` =
  stop** (`$2104 = $FF`, after which the tick writes AUDC = 0 to all four voices every
  frame, `b6:A935`); **n = start song n-1.** The first voice to reach its end decides for the
  whole song. (code; live: every case, see the table below)
- **Pattern:** a count byte, then that many 2-byte notes. Patterns are stored once and
  listed as often as needed (song 5's drum track lists one pattern nine times). (code)
- **Note:** byte 0 = instrument (high nibble) and duration index (low nibble); byte 1 = AUDF,
  0 = rest. (code)
- **Durations** (`b6:A941`, frames): `$60 $48 $40 $30 $24 $20 $18 $12 $10 $0C $09 $08 $06
  $04 $03 $02`. No tempo variable: a quarter note is 24 frames (150 a minute) in every song,
  with dotted and triplet values in the table. A PAL retime would be these 16 bytes. (code)
- No loops inside a track, no transposition, no per-note volume.

### How the registers are set

- **AUDCTL:** one byte per song from `SongAudctl` `b6:AA51`, written at song start
  (`b6:A87A-A87D`). **All eleven are 0**: the 64 kHz clock, no 16-bit joins, no high-pass
  filters. The log shows `$00` only (live, all runs). The table is a feature the game does
  not use.
- **AUDF:** the note's second byte, written **once at note-on** (`b6:A73C`) and never again.
  Range `$1F-$F3` (about 1 kHz down to 131 Hz). No vibrato, no slides, no arpeggio. (code;
  live: the only AUDF writer is `b6:A73C`, run `play1` `audiopc.txt`)
- **AUDC:** instrument byte 0 OR the volume level's high nibble. Only two distortions occur:
  `$A0` (pure tone) for every pitched voice including the bass, and `$80` (noise) for the
  drums on voice 4 (instruments 2 and 4, AUDF `$23-$2F`). No distortion `$C0` or `$60` bass.
  (code + live values in `audiopc.txt`)
- **Voices:** fixed by the arrangement: 1-3 chords and melody, 4 bass or drums.
- **Envelope** (`EnvStep` `b6:A75D`, five stages by jump table; instrument bytes 1-9):
  1. attack: level += byte 3 up to the peak (byte 2), for byte 1 + 1 frames;
  2. decay: level -= byte 6 down to the sustain level (byte 5), for byte 4 + 1 frames;
  3. sustain: counts byte 7 + 1 frames and **writes nothing**;
  4. release: level -= byte 9 down to 0, for byte 8 + 1 frames;
  5. off: AUDC = 0 every frame.
  The level is 8 bits; its high nibble is the volume. A stage counter is tested with
  `DEC / BPL`, so a length of `$80-$FF` ends at once (most instruments have sustain length
  `$FF`, meaning "none"). A rest jumps straight to stage 5. (code; live through the model)
- **Loudness:** every instrument peaks at volume 8 (5 or 6 for three of them) for a frame or
  two and falls to a sustain of 2-4. Over a whole song the mean volume per voice is 2.5-3.9
  of 15 and the four voices together average 10-13 (maximum 32 of 60). (the model, which
  equals the live log)

### Requests

- **Mailbox** `$211E` (`SongRequest`): game code stores a song number; the next tick starts
  it and clears the byte (`b6:A90E-A918`). The byte is the song number itself, so **song 0
  cannot be requested**; only MusicReset starts it. (code; live: pokes of 1-10 each started
  that song, runs `song1`-`song10`)
- **MusicReset** `b6:A8F5` (X = level 0-7, or 8 for the title): SKCTL = 0 then 3, then starts
  `ResetSongByLevel,X` (`b6:A905`): song 0 for levels 0-2 and 4-6, song 5 for levels 3 and 7,
  song 9 for the title. Called at power-up (`f7:DDBF`), game start (`f7:DDCF`) and each new
  life or level (`f7:F8CA`, `F93B`, `FC1D`). (code; live: 7 SKCTL pairs in run `play1`)
- **Request sites** (`tools/requests.py`, then read in the listing): song 1 at `f7:FA9F`
  (the player's state goes to dying), `b5:BF83`, `b6:A6F6`; song 2 at `f7:F85C`; song 3 at
  `f7:D9AA`, guarded by `$211F` so it is requested once; song 6 at `f7:DF24` (no lives left);
  song 10 at `f7:FD8A`; a non-constant request at `b4:9C3E`. (code)

### The songs, each checked against the chip

`tools/songs.py --model` is the driver transcribed; `tools/compare.py` compares it with a
run's POKEY log on all eight AUDF/AUDC registers, frame by frame.

| Song | Voices | Frames | Ends with | Where it plays | Checked (live) |
|---|---|---|---|---|---|
| 0 | 4 | 576 | start song 8 | start of a game and of each life (levels 0-2, 4-6) | 880/880 with its chain into 8 (run `attract`) |
| 1 | 2 | 96 | start song 7 | the player dies | 2,280/2,280 through 1 -> 7 -> 8 -> 8 |
| 2 | 2 | 216 | loop | the level's last fight (`f7:F85C`) | 2,280/2,280 |
| 3 | 4 | 456 | stop | level cleared (`f7:D9AA`) | 2,280/2,280 |
| 4 | 4 | 960 | stop | not placed | 2,280/2,280 |
| 5 | 4 | 864 | loop | levels 3 and 7 from the start | 2,280/2,280 |
| 6 | 4 | 288 | stop | game over (`f7:DF24`; frame 5904 of run `play1`) | 2,280/2,280 |
| 7 | 4 | 192 | start song 8 | lead-in after the death tune | 2,280/2,280 |
| 8 | 4 | 1,728 | start song 8 | the main level tune | 2,280/2,280 |
| 9 | 4 | 768 | loop | title screen | 1,790/1,790 (run `attract`) and 2,280/2,280 |
| 10 | 4 | 768 | loop | not placed (`f7:FD8A`) | 2,280/2,280 |

- 25,470 frames compared, all agree. 2,424 of them are not byte-exact, and only in the AUDF
  of a voice whose AUDC is `00`: the driver never writes AUDF for a rest or an unused voice,
  so the previous song's value stays in the register (songs 1, 2 and 10).
- Song 5's voice 3 is 960 frames long against 864 for the others: voice 4 ends first and
  restarts the song, so voice 3's last 96 frames never play. (code; the model reproduces the
  live log with that rule)
- "Where it plays" for songs 2, 3, 5 and 10 is from the request sites (code), not from play;
  songs 0, 1, 6, 8 and 9 were heard in place (live, runs `attract` and `play1`). In play the
  death tune never reached its chain: a new life calls MusicReset 95 frames after the request
  (song 1 is 96 frames long), and the last death is followed by song 6 after 63 frames.

## 2. Effects against music

- **Effects are on the TIA only, music on the POKEY only.** In 7,200 frames of play the only
  writers of POKEY registers are the music driver (`b6:A73C-A939`), the reset loop
  (`f7:DD78`) and the pause code (`f7:F163/F166`); the only TIA writers are `SfxTick`
  (`b6:8EFA-8F0B`), the warm start (`f7:DDA7/DDA9`) and the pause code (`f7:F15D/F15F`).
  (live: `audiopc.txt` of runs `play1` and `play2`, a write tap that names the PC and bank)
- So there is **no borrowing, no channel return and no priority between music and effects.**
  A jingle replaces the tune by a song request, and the tune comes back through the jingle's
  track-end command (1 -> 7 -> 8) or through MusicReset.
- The balance is by arrangement: the tune's voices sit at volume 2-4 most of the time, the
  effects play at 12-15. (live values; how loud the two chips are against each other on a
  console is not measured: hint)

### The TIA effects driver: `SfxTick` `b6:8ED2-8F14`, 67 bytes

- Called once a frame from the last DLI (`Dli_Bottom` `f7:F14A`, vblank) unless paused, and
  from the copyright screen's handler. (code; live: rasters 243-259 and 1-2, run `play2`)
- **State:** per TIA channel one request byte (`$52`, `$53`) and one stream index (`$54`,
  `$55`). Four bytes of zero page in all.
- **Data:** `SfxStart` `b6:8E02`, 12 bytes: the start offset of each effect id (0-11) in the
  stream blob; `SfxStream` `b6:8E0E`, 196 bytes, all effects end to end. Offset 0 holds a
  `$00`, so index 0 is "idle".
- **Stream bytes:** `$00` end (AUDV = 0, index = 0); `$01-$0F` set AUDC and take no time;
  `$10-$FF` one frame: AUDF = the byte (the TIA keeps the low five bits) and AUDV = its high
  nibble. This is the format the sound-drivers skill records as "MM's mailbox stream".
  (live: 1,459 of 1,459 channel-frames in run `play2` and 1,358 of 1,358 in run `sfxprio`
  have AUDF and AUDV equal to `blob[index-1]`, `tools/sfxcheck.py`)
- **Priority is the position in the blob.** A request is taken only if its start offset is
  greater than the channel's current index (`b6:8ED9-8EE6`: `CMP $54,X / BCC / BEQ`). An idle
  channel has index 0, so anything starts. A sound stored later in the blob interrupts one
  stored earlier; a sound cannot interrupt a later one, nor restart itself while it plays.
  A refused request stays in the request byte, can never be taken later (the index only
  grows), and is cleared when the playing sound ends (`b6:8F0F`). (code; live, run
  `sfxprio`, pokes of `$52` during play: id 2 cut id 10 and id 1; id 10 was refused during
  itself and its request byte was cleared at the end; id 1 cut id 8)
- Priority order, lowest first, with length in frames: 8 (4) < 1 (8) < 6 (19) < 3 (24) <
  4 (21) < 5 (38) < 7 = 9 (3) < 10 = 11 (8) < 2 (46). Ids 7/9 and 10/11 share their streams.
- **The channel is chosen at the call site**: `LDA #id / STA $52` or `STA $53`. The same id
  can go to both channels to make it louder (id 8, the copyright screen's text tick, at
  `b6:884B/8852`; live: 168 starts on each channel). Sites found (`tools/requests.py`):
  channel 0 gets ids 2, 5, 8, 10; channel 1 gets 2, 3, 4, 6, 8, 9.
- What the ids are: 8 text tick (live); 2 the long noise at `f7:D5D3` and in bank 2
  (explosion: hint); 3 a bonus item collected, beside the score add at `b6:A08F/A0BB/A222`
  (code); 4 an object's state set to `$E0`/`$F0` (hit: code, `b6:A717`, `f7:FABC`); 10
  requested every few frames from RAM-resident code at the start of a level (helicopter:
  hint); 1 on channel 1 while fire is held (gunshot: hint).
- **Cost:** 88 cycles a frame with both channels idle (an idle channel still runs the "end"
  path and writes AUDV = 0), 130-180 typical with both playing, 286 at most
  (`tools/cycles.py`). MAME's elapsed time for the call: 97-413 (live).
- An effect can alternate two AUDC values frame by frame (id 4 switches between 7 and 12),
  since an AUDC byte costs no time.

### No POKEY fitted

- **No detection and no fallback.** The game never reads a POKEY register (the only reads at
  `$4000-$400F` are the dummy reads of `STA $4000,X`). (live: read tap, `audiopc.txt`)
- With the POKEY bit cleared in a copy of the cartridge's header
  (`work/commando-nopokey.a78`), 3,600 frames of attract mode give the same TIA log, the same
  RAM state by frame and the same stores to `$4000-$400F` as the real cartridge. So without
  the chip the game runs unchanged, with all its effects and no music. (live, run `nopokey`
  against run `attract`: three files identical)

## 3. Initialisation and housekeeping

- **Reset** `f7:DD67`: INPTCTRL = 7, CTRL = `$7F`, then `$4000-$4010` cleared (17 stores,
  `f7:DD74-DD7C`), later AUDV0 = AUDV1 = 0 (`f7:DDA5`). (live)
- **SKCTL:** 0 then 3 in MusicReset (`b6:A8F5-A8FC`), at power-up and at every game start,
  life and level. Nothing else of POKEY is set up: no IRQEN, no STIMER, no timers. (live)
- **AUDCTL:** 0 from the per-song table at every song start. (live)
- **Pause** (`Dli_Bottom` `f7:F111-F16A`): the Pause switch is read in the last DLI; the flag
  `$F6` toggles when the switch is **released**. While paused:
  - the main loop parks in `PauseSpin` `f7:DDEA` (`LDA $F6 / BNE`); the DLI chain keeps the
    picture up;
  - MusicTick and SfxTick are skipped, so their state is frozen;
  - every frame AUDV0 = AUDV1 = 0 and `$4000-$4008` = 0 (AUDF1-4, AUDC1-4, AUDCTL).
  (live, run `play2`: paused from frame 2008 to 2208; all nine POKEY registers `00` from
  2009, `$2107` and `$2117` unchanged for 200 frames)
- **A flaw on resume:** the driver writes AUDF only at note-on, and the pause zeroed it. A
  note that was sounding comes back with its AUDC but AUDF = 0 (a 32 kHz tone, inaudible) and
  stays lost until that voice's next note. In run `play2` voices 1-2 were silent for 6 frames
  after the resume and voice 3 for 12; a `$60` note would lose up to 96. An effect cut by the
  pause resumes mid-stream with AUDC and AUDF intact (the TIA's were not zeroed). (live)
- **Game over:** song 6 is requested (`f7:DF24`); its track ends with "stop", after which
  the tick writes AUDC = 0 on all four voices each frame; 34 frames later the title tune
  starts. (live, run `play1`, frames 5904, 6192, 6226)
- **Timing:** everything is counted in frames. The PAL cartridge was not examined.

## 4. The game around the sound

### Frame

- **DLI chain through a RAM vector** (`$AE/$AF`, `JMP ($AE)` at `f7:F006`); 14 NMIs a frame
  in play: `Dli_Top` `f7:F009` (raster 26) -> `Dli_Resync` `b6:B70A` -> `Dli_ZonePalette`
  `f7:F06A` eleven times (through the JMP at `f7:EC0C`) -> `Dli_Bottom` `f7:F0F8`. Each
  handler stores the next one's address. (live: the indirect jumps in `exectrace.log`)
- **Double buffer:** two DLLs of 23 entries at `$1800` and `$1845` in one page, flipped by
  DPPL (`$00`/`$45`) in `Dli_Bottom` from `$79`; the main loop builds the other set and waits
  at `f7:DE4E` until `$FF` (shown) equals `$79`. (live: RAM dump at frame 2000, run `play3`)
- **A palette per map row:** each of the eleven zone DLIs loads the three colours of one
  palette. A byte per map row (level bank `$9B80,Y` for levels 0-3, `$BB00,Y` for 4-7) holds
  the palette number (bits 5-6) and an index (bits 0-4) into three RAM colour tables
  `$2751/$2764/$2777`. (code, `f7:F03C-F069` and `F06A-F0B0`)
- **Fades and bank safety:** `FadeOutDisplayOff` `f7:FBDD` starts a fade (counter `$FD`,
  stepped in vblank by `b6:B886`), waits for it, then turns DMA off (CTRL = `$7F`). The main
  thread leaves the level's bank (music reset in bank 6, bank 5's `$B000`) only after that,
  which is why the NMIs can restore the bank from a table instead of a shadow. (code)

### Scroll and map

- Vertical only. `$B1` is the map row at the top of the playfield (level 0 starts at `$70`
  and counts down as the player advances: 71 steps in 3,100 frames of run `play3`); `$B0` is
  the fine offset, 1-15 in odd steps. (live)
- The playfield is a first zone whose height is the fine offset (DLL byte `$4B` for 12 lines
  at `$B0 = $0B`), then 16-line zones. **Each zone's background is a single 5-byte indirect
  object, 20 two-byte characters wide, whose pointer is the map row itself in ROM**: `$9474`,
  `$9488`, `$949C`... stepping 20 bytes a row in the level's bank. Scrolling a row is adding
  20 to the pointers. (live: decoded lists of run `play3`, frame 2000) The pseudo3d skill
  already has this ("character backgrounds scrolled through their headers").
- A level's map is about 130 rows x 20 bytes in its bank, used in place.

### Objects

- **55 slots, struct of arrays, 55 bytes apart:** `$1ACF` x, `$1B06` y, `$1B3D`, `$1B74`
  palette and width (a display-list byte), `$1BAB`, `$1BE2`, `$2445`, `$247C`, `$24B3`,
  `$24EA` state (high nibble: `$E0`/`$F0` dying; low nibble kind), `$2521`, `$2558`. A free
  slot is parked at x = `$B4`. (code: `b6:8BEE`, `f7:FBFD`; live: table dumps of run `play3`,
  8 to 23 slots in use)
- **Slot ranges are fixed by role:** 0 the player, 1-2 always in use, 4-15 set pieces written
  by absolute address from level code (`b1:BC81`), 21-37 and 42-54 soldiers, shots and items
  (roles of 4-54 read off the occupancy log: hint).
- **Draw list:** a doubly linked list of up to 20 objects (`$256F` object, `$2584` next,
  `$2598` previous, head `$E3`, tail `$E4`, `$25C0` object-to-node, `$25AC` listed flag),
  whose nodes come from a 20-entry ring of free node numbers (`$25D6`; take at `$25D5`,
  `f7:F2E1`; give back at `$25D4`, `f7:F2F2`; add `f7:F2A9`). (code; the ring's two indexes
  move in the dumps of run `play3`)

### Spawning from the map

No single spawn table. Three mechanisms, all keyed on the map row `$B1`:
1. **Bonus items, by table** (`b6:A109`): per level a count (`b6:A163`) and an end index
   (`b6:A1A2`) into parallel arrays: trigger row (`b6:A16C`), x (`b6:A187`), sprite
   (`b6:A1AA`), palette and width (`b6:A1C5`), value (`b6:A1E0`); 27 entries. The item goes
   in the fixed slot 42, rewritten every frame the row matches. Two more per-level row tables
   at `b6:8F53` and `b6:8FA2` do the same for two other items. (code)
2. **Set pieces, by code in the level's bank** (`b1:9C18`, `b1:BC62`): compares of `$B1`
   (and `$B0`) against constants, a row window, a stage byte (`$25EA`) and `JMP ($6D)`
   through a lo/hi table (`b1:ACC0/ACC5`) to the stage's routine, which writes fixed slots.
   (code; the targets `b1:BC81`, `BCF8`, `BD83` were taken live in run `play1`)
3. Ordinary soldiers: not decoded.

### Bank map

| Bank | Holds | Evidence |
|---|---|---|
| 0 | the title picture: a 160B bitmap, 12 zones of 16 lines, 80 bytes a line, a page per line (`$8000-$B0EF`) | live (title lists, run `titledump`; paged in only by the title's RAM code) |
| 1-4 | levels: level n uses bank (n mod 4) + 1 (`LevelBank` `f7:F8F7` = 1 2 3 4 1 2 3 4 5), two levels a bank (row tables at `$9B00/$9B80` and `$BA80/$BB00`); maps, sprites, set-piece code, and a common block `$B200-$B6A2` (1,187 bytes, identical in banks 1-5, entered through JMPs at `$B200-$B218`) | code; only bank 1 seen live |
| 5 | entry 8 of the table; its `$B000` is called at each game and life start with DMA off; carries the common block too | code + live switch counts; role otherwise unknown |
| 6 | sound (effects driver and streams `$8E02-$8F14`, music driver and songs `$A71C-$B698`), the top DLI's body, copyright and title code (copied to RAM), option text, bonus-item tables, cold init | live |
| 7 | fixed: reset, main loop, NMI entry and DLI handlers, list builder, collision, graphics | live |

Switches in play: bank 6 and back to the level's bank twice a frame, both inside NMIs
(`f7:F00B/F018` and `f7:F140/F171`); the main thread switches only with DMA off.

## Coverage, stated honestly

- Byte-identical round trip: `verify.py` passes for all banks (`work/src`, generated).
- Reached as code after two live traces (attract mode, and one game on level 0 to game over;
  5,421 distinct instructions executed): bank 1 20.9%, bank 2 19.0%, bank 3 12.5%, bank 4
  14.7%, bank 5 25.5%, bank 6 20.5%, fixed bank 47.8%; bank 0 is all data. That is 26,370
  bytes of 131,072 (20%); most of the rest is graphics and maps, not declared as blocks.
- Read closely: both sound drivers and their data, the NMI entry and four DLI handlers,
  reset, pause, the main loop's outline, the list builder's outline, the draw list.
  Skimmed: level code in bank 1. Not read: banks 2-5 beyond request sites, collision, AI,
  scoring, two-player handling.
- Banks 2-4 are traced statically only (entry points assumed equal to bank 1's); levels 1-7
  were never played.

## Dead ends and corrections

- **"Effects must borrow POKEY channels"** was the working assumption; wrong. The write tap
  shows two disjoint drivers on two chips.
- **"Id 10 is the player's shot"** (it starts 37 times on channel 0 in run `play2` with fire
  held): retracted. Run `sfxprio` has it requested continuously with no input from frame
  1299, from code that runs in RAM (`b6:BC9B` is inside the image copied to `$1D30`). Left as
  a hint (helicopter).
- **The first model comparison of songs 1, 2 and 10 failed** (780 and 0 of 2,280 frames):
  the model started from zeroed registers, while the chip keeps the last song's AUDF on
  voices the new song leaves silent. The comparison now ignores the AUDF of a voice whose
  AUDC is `00` and reports byte-exact frames separately.
- **Stage counters:** a first transcription treated a length of `$FF` as 255 frames; the
  code's `DEC / BPL` makes `$80-$FF` end at once. Found before the first comparison.
- **`dyn.py` refused my trace** ("the disassembler failed after merging"): my probe logs code
  run from RAM as `ram:xxxx`, which the tool does not know. RAM lines are filtered out first
  (`work/exectrace-*-rom.log`). The same probe labels RAM PCs as `f7:1Dxx` in `banks.txt`;
  read those as RAM.
- **The cycle harness wrote `$52` straight into the simulator's RAM array** and no effect
  started: zero page is a mirror of `$2040-$20FF` there. It now goes through `bus.write`.
- **The music timer in `time.txt` has no title-screen rows**: there the tick is called from
  RAM, so the return address the timer waits for never comes. Gameplay rows are complete.
- **A heredoc mangled the backslashes** of a patch to `tools/annotate.py`; the second pass
  of annotations is its own file, `tools/annotate2.py`, written whole.
- **The study's agent could not write this file or the techniques file** (its file tool
  refuses report files); both were handed back as text and saved by the main session.
- **Not determined:** which events request effect ids 1, 5, 6, 9, 10 (and whether 7 and 11
  are requested at all: no immediate request was found); where songs 4 and 10 play; bank 5's
  role; ordinary soldier spawning; the PAL build; how loud the POKEY is against the TIA on a
  console.
