"""Scripted UART peer that plays Klipper's host: identify handshake, then a stepper move.
Runs inside a sim scenario (UART.ScriptedUartPeer). Prints results with ctx.info."""
import json, zlib
def crc16(buf):
    c = 0xffff
    for d in buf:
        d ^= c & 0xff; d ^= (d << 4) & 0xff
        c = ((d << 8) | (c >> 8)) ^ (d >> 4) ^ (d << 3)
        c &= 0xffff
    return c
def vlq(v):
    v &= 0xffffffff
    if v >= 0x80000000: v -= 1 << 32  # signed
    out = []; 
    while True:
        out.append(v & 0x7f); v >>= 7
        if (v == 0 and not out[-1] & 0x40) or (v == -1 and out[-1] & 0x40): break
    return bytes(b | 0x80 for b in reversed(out[1:])) + bytes([out[0]]) if False else \
        bytes([(b | 0x80) for b in reversed(out[1:])] + [out[0]])
def unvlq(b, i):
    c = b[i]; i += 1; v = c & 0x7f
    if (c & 0x60) == 0x60: v |= -0x20
    while c & 0x80:
        c = b[i]; i += 1; v = (v << 7) | (c & 0x7f)
    return v & 0xffffffff, i
def frame(seq, payload):
    m = bytes([5 + len(payload), 0x10 | (seq & 15)]) + payload
    return m + crc16(m).to_bytes(2, 'big') + b'\x7e'

STEP, DIR = "PB0", "PB1"
PULSES, INTERVAL_US = 100, 100            # queue_step: 100 steps, one per 100 us
SEND_GAP_US = 1000

class Peer:
    def __init__(self, ctx):
        self.ctx = ctx; self.buf = bytearray(); self.seq = 0
        self.ident = b""; self.d = None; self.queue = []; self.clock = None
        self.t_first_ack = None
        ctx.schedule_periodic_ns(SEND_GAP_US * 1000)
        self.want_ident = True; self.waiting = False
        self.idle_ticks = 0

    def tx(self, payload):
        self.ctx.send(frame(self.seq, payload)); self.seq += 1

    def on_timer(self):
        if self.waiting and self.idle_ticks < 20:      # a request is outstanding
            self.idle_ticks += 1; return
        self.idle_ticks = 0; self.waiting = False
        if self.want_ident:
            self.tx(vlq(1) + vlq(len(self.ident)) + vlq(40)); self.waiting = True
        elif self.queue:
            self.tx(self.queue.pop(0)); 
            if not self.queue and self.clock is None: pass

    def cmd(self, name_prefix, *args):
        for k, v in self.d["commands"].items():
            if k.split()[0] == name_prefix:
                return vlq(v) + b"".join(vlq(a) for a in args)
        raise KeyError(name_prefix)

    def on_byte(self, b):
        self.buf.append(b)
        while self.buf and not 5 <= self.buf[0] <= 64: del self.buf[0]
        if self.buf and len(self.buf) >= self.buf[0]:
            f = bytes(self.buf[:self.buf[0]]); del self.buf[:f[0]]
            if f[-1] == 0x7e and crc16(f[:-3]) == int.from_bytes(f[-3:-1], "big"):
                self.on_msg(f[2:-3])

    def on_msg(self, p):
        if self.want_ident and p.startswith(vlq(0)):
            _, i = unvlq(p, 0); off, i = unvlq(p, i); n, i = unvlq(p, i)
            if off == len(self.ident): self.ident += p[i:i + n]
            self.waiting = False
            if n:
                self.tx(vlq(1) + vlq(len(self.ident)) + vlq(40)); self.waiting = True
            if n == 0:
                self.d = json.loads(zlib.decompress(self.ident)); self.want_ident = False
                self.ctx.info("identify OK: %s, %d commands" % (self.d["version"], len(self.d["commands"])))
                self.queue.append(self.cmd("get_clock"))
        elif self.d and p.startswith(vlq(self.d["responses"]["clock clock=%u"])):
            self.waiting = False
            if self.clock is None:
                self.clock, _ = unvlq(p, len(vlq(self.d["responses"]["clock clock=%u"])))
                pin = {n: self.d["enumerations"]["pin"][n[:2] + "0"][0] + int(n[2:]) for n in (STEP, DIR)}
                self.queue += [self.cmd("allocate_oids", 1),
                    self.cmd("config_stepper", 0, pin[STEP], pin[DIR], 0, 20),
                    self.cmd("finalize_config", 0),
                    self.cmd("set_next_step_dir", 0, 1),
                    self.cmd("reset_step_clock", 0, self.clock + 180000 * 20),
                    self.cmd("queue_step", 0, INTERVAL_US * 180, PULSES, 0)]
                self.ctx.info("MCU clock %d at host t=%d us; move scheduled +20 ms" % (self.clock, self.ctx.now_us))
        elif self.d and p:
            self.waiting = False
