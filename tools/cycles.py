"""CPU cycles of Commando's two sound ticks, counted by running the cartridge's own code in
the toolkit's 6502 core (tools/sim.py), outside any frame: no DMA, exact instruction cycles.

usage: python -I tools/cycles.py

Music: for each song, MusicStart (b6:A86F, A = song) then MusicTick (b6:A90E) once a
"frame" for the song's length; prints the start's cost and the tick's min, mean and max, and
how many frames reached each cost band. Effects: every sound id on each TIA channel through
SfxTick (b6:8ED2), with both channels busy for the worst case.
"""
import os
import sys

TK = os.environ.get("A7800_TOOLKIT", "a7800-toolkit/tools")
sys.path.insert(0, TK)
import cart as cartmod  # noqa: E402
import sim  # noqa: E402

ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")
SENT = 0x27F0          # a RAM address used as the return sentinel


def machine():
    c = cartmod.Cart(ROM)
    bus = sim.Bus(c)
    cpu = sim.CPU(bus)
    bus.write(0x8000, 6)
    return bus, cpu


def call(bus, cpu, addr, a=0, x=0, y=0, limit=200000):
    cpu.a, cpu.x, cpu.y = a, x, y
    cpu.s = 0xF0
    ret = SENT - 1
    cpu.push(ret >> 8)
    cpu.push(ret & 0xFF)
    cpu.pc = addr
    c0 = cpu.cycles
    n = 0
    while cpu.pc != SENT:
        cpu.step()
        n += 1
        if n > limit:
            raise RuntimeError("no return from %04X (pc %04X)" % (addr, cpu.pc))
    return cpu.cycles - c0


def music():
    lengths = {0: 576, 1: 96, 2: 216, 3: 456, 4: 960, 5: 960, 6: 288, 7: 192, 8: 1728, 9: 768, 10: 768}
    allc = []
    print("music: MusicStart b6:A86F and MusicTick b6:A90E, CPU cycles (JSR/RTS of the caller not included)")
    for s in range(11):
        bus, cpu = machine()
        st = call(bus, cpu, 0xA86F, a=s)
        cs = []
        for f in range(lengths[s] - 1):
            cs.append(call(bus, cpu, 0xA90E))
        allc += cs
        cs.sort()
        print("  song %2d: start %4d; tick min %3d  median %3d  mean %5.1f  95%% %3d  max %3d"
              % (s, st, cs[0], cs[len(cs) // 2], sum(cs) / len(cs), cs[int(len(cs) * 0.95)], cs[-1]))
    allc.sort()
    print("  all songs: mean %.1f, median %d, 95%% %d, 99%% %d, max %d over %d ticks"
          % (sum(allc) / len(allc), allc[len(allc) // 2], allc[int(len(allc) * 0.95)], allc[int(len(allc) * 0.99)], allc[-1], len(allc)))
    # idle (song $FF)
    bus, cpu = machine()
    bus.write(0x2104, 0xFF)
    print("  stopped (song $FF): tick %d" % call(bus, cpu, 0xA90E))


def sfx():
    print("effects: SfxTick b6:8ED2, CPU cycles")
    bus, cpu = machine()
    print("  both channels idle: %d" % call(bus, cpu, 0x8ED2))
    worst = 0
    for i in range(1, 12):
        bus, cpu = machine()
        bus.write(0x52, i)
        bus.write(0x53, i)
        cs = []
        n = 0
        while True:
            cs.append(call(bus, cpu, 0x8ED2))
            n += 1
            if bus.read(0x54) == 0 and bus.read(0x55) == 0:
                break
        worst = max(worst, max(cs))
        print("  id %2d on both channels: %3d frames, tick min %3d mean %5.1f max %3d" % (i, n, min(cs), sum(cs) / len(cs), max(cs)))
    print("  worst tick with both channels busy: %d" % worst)


if __name__ == "__main__":
    music()
    sfx()
