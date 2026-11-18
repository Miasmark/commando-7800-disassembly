-- probe.lua: one windowless scripted Commando session on the MAME fork.
-- Run by tools/run.py (cwd = the run folder). Everything is optional except END.
--   SCRIPT  "frames:stick:buttons;..."  stick: letters of l r u d (or -);
--           buttons: 1 fire, 2 button 2 (grenade), +4 Pause, +8 Select, +16 Reset
--   END     frame to exit on
--   SNAPS   "a,b,c" frames to snapshot
--   PEEK    hex addresses "2104,2105,..." -> frames.txt (one line a frame, hex bytes)
--   POKES   "frame:addr=val,addr=val;..." (hex addr/val) written at that frame's end
--   WLOG    "from-to": every audio register write in those frames -> writes.txt
--           (frame line pc reg val)
--   RAMDUMP "a,b,c" or "every:N:from:to": RAM $0000-$27FF after those frames -> ram_<frame>.bin
--   XT      1: exectrace.log in the toolkit's exectrace.lua format (X/J/S lines)
--   TIME    "name=entry:exit,..." hex PCs in the form b6:A90E or f7:F000: time between a fetch
--           at entry and the next fetch at exit, in CPU cycles (machine time * 1.789772 MHz,
--           so DMA-stolen time is included), per frame -> time.txt (frame name line cycles)
--   RTAP    "lo-hi" hex: data reads (PC ~= address) in that range -> reads.txt summary
--           (address: count, reader PCs)
-- Always written: pokey.txt (frame f1 c1 f2 c2 f3 c3 f4 c4 ctl, when changed, the toolkit's
-- audio.lua format with the "# chip pokey" header), tia.txt (frame c0 c1 f0 f1 v0 v1 when
-- changed), audiopc.txt (who writes each audio register: pc, reg, count, first frame, values),
-- banks.txt (bank-select writes by PC and value).
local M = manager.machine
local cpu = M.devices[":maincpu"]
local mem = cpu.spaces["program"]
local P = M.ioport.ports
local scr
for _, s in pairs(M.screens) do scr = s break end

local function fld(n)
  for _, t in ipairs({":JOYSTICKS", ":BUTTONS", ":joysticks", ":buttons"}) do
    local f = P[t] and P[t].fields[n]
    if f then return f end
  end
end
local stick = {l = fld("P1 Left"), r = fld("P1 Right"), u = fld("P1 Up"), d = fld("P1 Down")}
local fire, fire2 = fld("P1 Button 1"), fld("P1 Button 2")
local pause, select, reset
for _, t in ipairs({":CONSOLE", ":console", ":console_buttons"}) do
  if P[t] then
    pause = P[t].fields["Pause"] or pause
    select = P[t].fields["Select"] or select
    reset = P[t].fields["Reset"] or reset
  end
end
local steps = {}
for n, s, b in string.gmatch(os.getenv("SCRIPT") or "", "(%d+):([lrud%-]+):(%d+)") do
  steps[#steps + 1] = {tonumber(n), s, tonumber(b)}
end
local END = tonumber(os.getenv("END") or "600")
local snaps = {}
for w in string.gmatch(os.getenv("SNAPS") or "", "%d+") do snaps[tonumber(w)] = true end
local peek = {}
for a in string.gmatch(os.getenv("PEEK") or "", "[^,]+") do peek[#peek + 1] = tonumber(a, 16) end
local pokes = {}
for fr, list in string.gmatch(os.getenv("POKES") or "", "(%d+):([^;]+)") do
  local t = pokes[tonumber(fr)] or {}
  for ad, val in string.gmatch(list, "(%x+)=(%x+)") do t[#t + 1] = {tonumber(ad, 16), tonumber(val, 16)} end
  pokes[tonumber(fr)] = t
end
local wlo, whi = string.match(os.getenv("WLOG") or "", "(%d+)%-(%d+)")
wlo, whi = tonumber(wlo), tonumber(whi)
local XT = os.getenv("XT") == "1"
-- RAMDUMP "a,b,c" or "every:N:from:to": RAM $0000-$27FF at the end of those frames -> ram_<frame>.bin
local dumps, dev, dfrom, dto = {}, nil, 0, 0
do
  local e, a, b = string.match(os.getenv("RAMDUMP") or "", "every:(%d+):(%d+):(%d+)")
  if e then dev, dfrom, dto = tonumber(e), tonumber(a), tonumber(b)
  else for w in string.gmatch(os.getenv("RAMDUMP") or "", "%d+") do dumps[tonumber(w)] = true end end
end

local fno = 0
local bank = 0
local function key(addr)
  if addr >= 0x8000 and addr <= 0xBFFF then return string.format("b%d:%04X", bank, addr) end
  return string.format("f7:%04X", addr)
end
local function line()
  local lines = scr.frame_period / scr.scan_period
  local left = scr:time_until_pos(0, 0) / scr.scan_period
  return math.floor((lines - left) % lines)
end
local function pc() return cpu.state["PC"].value end

-- bank select
local seen_s = {}
TAP_BANK = mem:install_write_tap(0x8000, 0xBFFF, "banksel", function(off, data)
  local k = string.format("%s %d", key(pc()), data & 7)
  seen_s[k] = (seen_s[k] or 0) + 1
  bank = data & 7
  return data
end)

-- audio
local pcur, plast, tcur, tlast = {}, {}, {}, {}
for i = 1, 9 do pcur[i] = 0; plast[i] = -1 end
for i = 1, 6 do tcur[i] = 0; tlast[i] = -1 end
local who = {}
local wout = wlo and io.open("writes.txt", "w")
local function note(reg, data)
  local k = key(pc()) .. " " .. reg
  local w = who[k]
  if not w then w = {n = 0, first = fno, vals = {}, nv = 0}; who[k] = w end
  w.n = w.n + 1
  if not w.vals[data] and w.nv < 24 then w.vals[data] = true; w.nv = w.nv + 1 end
  if wout and fno >= wlo and fno <= whi then
    wout:write(string.format("%d %d %s %s %02X\n", fno, line(), key(pc()), reg, data))
  end
end
local PNAME = {[0] = "AUDF1", "AUDC1", "AUDF2", "AUDC2", "AUDF3", "AUDC3", "AUDF4", "AUDC4", "AUDCTL",
               "STIMER", "SKREST", "POTGO", "POKEY_C", "SEROUT", "IRQEN", "SKCTL"}
TAP_POKEY = mem:install_write_tap(0x4000, 0x400F, "pokey", function(off, data)
  local r = off - 0x4000
  if r <= 8 then pcur[r + 1] = data & 0xFF end
  note(PNAME[r], data & 0xFF)
  return data
end)
local TNAME = {[0x15] = "AUDC0", [0x16] = "AUDC1t", [0x17] = "AUDF0", [0x18] = "AUDF1t", [0x19] = "AUDV0", [0x1A] = "AUDV1"}
TAP_TIA = mem:install_write_tap(0x0015, 0x001A, "tia", function(off, data)
  tcur[off - 0x15 + 1] = data & 0xFF
  note(TNAME[off], data & 0xFF)
  return data
end)
local preads = {}
TAP_POKEYR = mem:install_read_tap(0x4000, 0x400F, "pokeyr", function(off, data)
  local k = key(pc()) .. " " .. string.format("%04X", off)
  preads[k] = (preads[k] or 0) + 1
  return data
end)

-- timing
local timers = {}
local function parse_pc(s)
  local sp, a = string.match(s, "(%w+):(%x+)")
  return sp, tonumber(a, 16)
end
for name, e, x in string.gmatch(os.getenv("TIME") or "", "([%w_]+)=([%w:]+)%-([%w:]+)") do
  local es, ea = parse_pc(e)
  local xs, xa = parse_pc(x)
  timers[#timers + 1] = {name = name, es = es, ea = ea, xs = xs, xa = xa, t0 = nil}
end
local tout = (#timers > 0) and io.open("time.txt", "w")
local CLK = 1789772.5

-- exec trace + timers + read tap
local seen_x, seen_j = {}, {}
local pending_j = nil
local armed = false
TAP_INPT = mem:install_write_tap(0x0001, 0x0001, "inptctrl", function(off, data)
  if (data & 1) ~= 0 then armed = true end
  return data
end)
local rlo, rhi = string.match(os.getenv("RTAP") or "", "(%x+)%-(%x+)")
rlo, rhi = rlo and tonumber(rlo, 16), rhi and tonumber(rhi, 16)
local rseen = {}
local nfetch = 0
if XT or #timers > 0 or rlo then
  TAP_X = mem:install_read_tap(0x1800, 0xFFFF, "xt", function(off, data)
    local p = pc()
    if p ~= off then
      if rlo and off >= rlo and off <= rhi then
        local k = key(off)
        local r = rseen[k]
        if not r then r = {n = 0, pcs = {}}; rseen[k] = r end
        r.n = r.n + 1
        r.pcs[key(p)] = true
      end
      return data
    end
    nfetch = nfetch + 1
    local k = (p < 0x4000) and string.format("ram:%04X", p) or key(p)
    if XT and armed then
      if pending_j then seen_j[pending_j .. " " .. k] = true; pending_j = nil end
      seen_x[k] = true
      if data == 0x6C then pending_j = k end
    end
    for _, t in ipairs(timers) do
      if p == t.ea and k == t.es .. string.format(":%04X", t.ea) then
        t.t0 = M.time:as_double(); t.l0 = line()
      elseif t.t0 and p == t.xa and k == t.xs .. string.format(":%04X", t.xa) then
        local cyc = (M.time:as_double() - t.t0) * CLK
        tout:write(string.format("%d %s %d %.0f\n", fno, t.name, t.l0, cyc))
        t.t0 = nil
      end
    end
    return data
  end)
end

local pout = io.open("pokey.txt", "w")
pout:write("# chip pokey  base $4000\n# frame  f1 c1  f2 c2  f3 c3  f4 c4  ctl   (hex)\n")
local tiaout = io.open("tia.txt", "w")
tiaout:write("# frame  c0 c1 f0 f1 v0 v1 (hex)\n")
local fout = (#peek > 0) and io.open("frames.txt", "w")

FRAME_CB = emu.register_frame_done(function()
  fno = fno + 1
  local t, cur = fno, nil
  for _, s in ipairs(steps) do
    if t <= s[1] then cur = s break end
    t = t - s[1]
  end
  for k, fl in pairs(stick) do fl:set_value((cur and cur[2]:find(k)) and 1 or 0) end
  local b = cur and cur[3] or 0
  if fire then fire:set_value(b % 2) end
  if fire2 then fire2:set_value(math.floor(b / 2) % 2) end
  if pause then pause:set_value(math.floor(b / 4) % 2) end
  if select then select:set_value(math.floor(b / 8) % 2) end
  if reset then reset:set_value(math.floor(b / 16) % 2) end
  if snaps[fno] then M.video:snapshot() end
  local ch = false
  for i = 1, 9 do if pcur[i] ~= plast[i] then ch = true end end
  if ch then
    local parts = {tostring(fno)}
    for i = 1, 9 do parts[#parts + 1] = string.format("%02X", pcur[i]); plast[i] = pcur[i] end
    pout:write(table.concat(parts, " ") .. "\n")
  end
  ch = false
  for i = 1, 6 do if tcur[i] ~= tlast[i] then ch = true end end
  if ch then
    local parts = {tostring(fno)}
    for i = 1, 6 do parts[#parts + 1] = string.format("%02X", tcur[i]); tlast[i] = tcur[i] end
    tiaout:write(table.concat(parts, " ") .. "\n")
  end
  if fout then
    local v = {tostring(fno)}
    for _, a in ipairs(peek) do v[#v + 1] = string.format("%02X", mem:read_u8(a)) end
    fout:write(table.concat(v, " ") .. "\n")
  end
  if dumps[fno] or (dev and fno >= dfrom and fno <= dto and (fno - dfrom) % dev == 0) then
    local f = io.open(string.format("ram_%05d.bin", fno), "wb")
    local t = {}
    for a = 0, 0x27FF do t[#t + 1] = string.char(mem:read_u8(a)) end
    f:write(table.concat(t)); f:close()
  end
  local p = pokes[fno]
  if p then for _, w in ipairs(p) do mem:write_u8(w[1], w[2]) end end
  if fno >= END then M:exit() end
end)

STOP_CB = emu.add_machine_stop_notifier(function()
  pout:close(); tiaout:close()
  if fout then fout:close() end
  if wout then wout:close() end
  if tout then tout:close() end
  local f = io.open("audiopc.txt", "w")
  local ks = {}
  for k in pairs(who) do ks[#ks + 1] = k end
  table.sort(ks)
  for _, k in ipairs(ks) do
    local w = who[k]
    local vs = {}
    for v in pairs(w.vals) do vs[#vs + 1] = v end
    table.sort(vs)
    local s = {}
    for _, v in ipairs(vs) do s[#s + 1] = string.format("%02X", v) end
    f:write(string.format("%s x%d first %d vals %s%s\n", k, w.n, w.first, table.concat(s, ","), w.nv >= 24 and ",..." or ""))
  end
  ks = {}
  for k in pairs(preads) do ks[#ks + 1] = k end
  table.sort(ks)
  for _, k in ipairs(ks) do f:write(string.format("READ %s x%d\n", k, preads[k])) end
  f:close()
  f = io.open("banks.txt", "w")
  ks = {}
  for k in pairs(seen_s) do ks[#ks + 1] = k end
  table.sort(ks)
  for _, k in ipairs(ks) do f:write(string.format("%s x%d\n", k, seen_s[k])) end
  f:close()
  if XT then
    local lines = {}
    for k in pairs(seen_x) do lines[#lines + 1] = "X " .. k end
    for k in pairs(seen_j) do lines[#lines + 1] = "J " .. k end
    for k, n in pairs(seen_s) do lines[#lines + 1] = string.format("S %s x%d", k, n) end
    table.sort(lines)
    f = io.open("exectrace.log", "w")
    for _, l in ipairs(lines) do f:write(l, "\n") end
    f:close()
  end
  if rlo then
    f = io.open("reads.txt", "w")
    ks = {}
    for k in pairs(rseen) do ks[#ks + 1] = k end
    table.sort(ks)
    for _, k in ipairs(ks) do
      local r = rseen[k]
      local ps = {}
      for p in pairs(r.pcs) do ps[#ps + 1] = p end
      table.sort(ps)
      f:write(string.format("%s x%d %s\n", k, r.n, table.concat(ps, ",")))
    end
    f:close()
  end
  print(string.format("probe: %d frames, %d fetches seen", fno, nfetch))
end)
