# Commando (Atari 7800) disassembly notes

An annotated disassembly project for *Commando* (NTSC, Atari, 1989; `Commando (NTSC) (Atari) (1989) (CD1A98C5).a78`, 128K SuperGame with a POKEY at `$4000`).

## How this was made, and how far to trust it

This is the output of **one automated research pass** on 2026-11-18: a single AI agent
session (Claude, working through the a7800-toolkit and MAME) given a list of questions and
about half an hour, not a long-running hand disassembly like
[galaga-7800-disassembly](https://github.com/Miasmark/galaga-7800-disassembly) and its
siblings. A second session then checked the report's main tables and routines against the
ROM's bytes; they matched. Nothing here was checked on a console.

Treat a **live** tag as "one agent saw this in MAME once", a **code** tag as a reading, and
the coverage figures below as what the tracer reached, not what was understood.

## Effort: sound in depth, the rest in outline

| | |
|---|---|
| Session | one agent, about 27 minutes, about 100 tool calls |
| Questions asked | the POKEY music driver; effects against music; initialisation and pause; then the game around it |
| Coverage | about 20% of the ROM reached as code (fixed bank 48%, bank 6 21%, level banks 13-26%); most of the rest is undeclared graphics and maps. Round trip byte-identical |
| Read closely | both sound drivers and their data, the NMI entry and four DLI handlers, reset, pause |
| Outlined only | the main loop, the list builder, the draw list, level code in bank 1 |
| Not read | banks 2-5 beyond request sites, collision, AI, scoring, two players |
| Live checks | all 11 songs against the chip, frame by frame (25,470 frames, all agree); the effects driver against its model; pause; a no-POKEY run; 131 entries, 58 labels |
| Not determined | which events request five of the effect ids; where songs 4 and 10 play; bank 5's role. Only the first level was played |

## What is here, and what is not

- `annotations.json`: entry points, labels, RAM names, data blocks and comments, in the
  [a7800-toolkit](https://github.com/Miasmark/a7800-toolkit)'s format.
- `docs/FINDINGS.md`: what the code does, with addresses, record formats and an evidence
  tag on every claim: **live** (watched in MAME: a tap, a trace, a RAM model, a poke that
  changed behaviour), **code** (read from the listing only), **hint** (a guess). Dead ends
  and corrections are kept in it.
- `tools/`: the probes and scripts the findings were made with.

**No ROM is here, and no listing.** A listing is the game's machine code in readable form;
it is rebuilt from `annotations.json` and your own legally owned dump with the toolkit's
`disasm.py`, and checked byte for byte with its `verify.py`. Captures, memory dumps,
renders of the graphics and traces are left out for the same reason.

## Running the tools

The scripts look for three things in the environment:

| Variable | What | Default |
|---|---|---|
| `A7800_ROMS` | the folder with your ROM dumps, named as below | `roms` |
| `A7800_TOOLKIT` | the a7800-toolkit's `tools` folder | `a7800-toolkit/tools` |
| `A7800_MAME` | a MAME with the Atari 7800 driver | `a78.exe` |

The live runs were made on [Miasmark/mame-Atari8bit7800](https://github.com/Miasmark/mame-Atari8bit7800),
windowless (`-video none -sound none -nothrottle`).

## Licence

MIT (see `LICENSE`) for the annotations, the findings and the tools. It does not cover the
games, which belong to their owners; nothing of theirs is distributed here.

## The session's own notes

A study of *Commando* (NTSC, Atari, 1989; 128K SuperGame with a POKEY at `$4000`), made
with the a7800-toolkit and the MAME fork as a measuring instrument. The sound was the
reason for it: this is one of the two retail 7800 cartridges with a POKEY.

**The ROM is not here.** The tools read
`Commando (NTSC) (Atari) (1989) (CD1A98C5).a78` from the ROM library (the path is at the
top of each script). Nothing in this folder may leave it: `work/` holds generated listings,
run folders with copies of the cartridge, and register logs of its music.

## Layout

- `annotations.json`: every judgement about the ROM, in the toolkit's format (labels, RAM
  names, routine headers, data blocks, entry points and bank-switch pins observed live).
- `docs/FINDINGS.md`: what the game does, with evidence tags.
- `tools/`:
  - `run.py` + `probe.lua`: one windowless scripted MAME session (inputs by frame, pokes,
    RAM peeks and dumps, POKEY and TIA logs with the writer's PC and bank, execution trace,
    timers). Each run gets its own folder under `work/runs/`.
  - `songs.py`: walks the song data and prints its structure and sizes; `--model` is the
    music driver transcribed, frame by frame.
  - `compare.py`: the model against a run's POKEY log.
  - `sfxcheck.py`: the effect stream model against a run's TIA log.
  - `cycles.py`: CPU cycles of both sound ticks, in the toolkit's 6502 core.
  - `requests.py`: every sound and song request site, by raw scan.
  - `bankmap.py`: entropy by block, ranges duplicated between banks, level-to-bank tables.
  - `ramlook.py`: series, changing bytes and the object table from periodic RAM dumps.
  - `annotate.py`, then `annotate2.py`: write this project's hand annotations into
    `annotations.json` (sound first; then the frame, the map, the lists and a note per bank).
- `work/`: `src/` (the generated listing, disposable), `runs/` (MAME run folders),
  execution traces, and a copy of the cartridge with the POKEY bit cleared in its header.

## Reproducing

```
T="a7800-toolkit/tools"
R=".../Commando (NTSC) (Atari) (1989) (CD1A98C5).a78"
python -I "$T/disasm.py" "$R" -c annotations.json -o work/src
python -I "$T/verify.py" "$R" -d work/src          # ROUND-TRIP PASSED
python -I tools/songs.py                            # song structure and sizes
python -I tools/run.py attract END=3600             # a run; see probe.lua for the options
python -I tools/compare.py attract 9 898 1790       # title tune: model against the chip
```

MAME is always run with `-video none -sound none -nothrottle`, a `ui.ini` holding
`skip_warnings 1`, and its own cfg, nvram and snapshot folders in the run folder.

## Coverage

The round trip is byte-identical for every bank. About 20% of the ROM is reached as code
(fixed bank 48%, bank 6 21%, level banks 13-26%); most of the rest is graphics and maps and
is not declared. The two sound drivers and all their data are read completely and checked
live; the rest of the game is outlined only. Only level 1 was played.
