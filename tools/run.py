"""Run one windowless scripted session of Commando on the MAME fork with tools/probe.lua.

usage: python -I tools/run.py NAME [KEY=VALUE ...] [--wav] [--lua other.lua] [--cart path]

The run folder is work/runs/NAME (wiped first). KEY=VALUE pairs are passed to the probe as
environment variables (SCRIPT, END, SNAPS, PEEK, POKES, WLOG, XT, TIME, RTAP: see probe.lua).
MAME never opens a window: -video none -sound none -nothrottle, a ui.ini with skip_warnings 1,
and its own cfg, nvram and snapshot folders. --wav adds -wavwrite audio.wav (still no audible
output). --cart runs another image (a patched copy kept inside work/).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
RUNS = os.path.join(PROJ, "work", "runs")
MAME = os.environ.get("A7800_MAME", "a78.exe")
ROM = (os.environ.get("A7800_ROMS", "roms") + "/Commando (NTSC) (Atari) (1989) (CD1A98C5).a78")


def main():
    args = sys.argv[1:]
    name = args.pop(0)
    env = dict(os.environ)
    wav = False
    lua = os.path.join(HERE, "probe.lua")
    cart = ROM
    while args:
        a = args.pop(0)
        if a == "--wav":
            wav = True
        elif a == "--lua":
            lua = os.path.abspath(args.pop(0))
        elif a == "--cart":
            cart = os.path.abspath(args.pop(0))
        else:
            k, v = a.split("=", 1)
            env[k] = v
    rd = os.path.join(RUNS, name)
    shutil.rmtree(rd, ignore_errors=True)
    os.makedirs(os.path.join(rd, "cfg"))
    with open(os.path.join(rd, "ui.ini"), "w") as f:
        f.write("skip_warnings 1\n")
    shutil.copy(cart, os.path.join(rd, "cart.a78"))
    cmd = [MAME, "a7800", "-cart", "cart.a78", "-bios", "skip", "-skip_gameinfo", "-video", "none",
           "-sound", "none", "-nothrottle", "-inipath", ".", "-cfg_directory", "cfg",
           "-nvram_directory", "nv", "-snapshot_directory", "snap"]
    if wav:
        cmd += ["-wavwrite", "audio.wav"]
    cmd += ["-autoboot_script", lua]
    with open(os.path.join(rd, "mame.out"), "w") as o:
        r = subprocess.run(cmd, cwd=rd, env=env, stdout=o, stderr=subprocess.STDOUT, timeout=3000)
    out = open(os.path.join(rd, "mame.out")).read()
    print(out[-1500:])
    print("exit", r.returncode, "files:", sorted(os.listdir(rd)))


if __name__ == "__main__":
    main()
