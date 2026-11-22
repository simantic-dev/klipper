#!/usr/bin/env python3
"""Klipper identify handshake over a sim --uart-tcp socket. Usage: identify_peer.py PORT [dict.json]"""
import json, socket, sys, time, zlib
from klipper_host_peer import crc16, vlq, unvlq, frame

class Link:
    """Framed Klipper link over a TCP socket from sim --uart-tcp."""
    def __init__(self, port):
        self.s = None; self.buf = b''; self.seq = 0
        for _ in range(100):
            try: self.s = socket.create_connection(("127.0.0.1", port)); break
            except OSError: time.sleep(0.1)
        self.s.settimeout(5)
    def send(self, payload):
        self.s.sendall(frame(self.seq, payload)); self.seq += 1
    def get_frame(self):
        while True:
            b = self.buf
            if b and not 5 <= b[0] <= 64: self.buf = b[1:]; continue
            if b and len(b) >= b[0]:
                f, self.buf = b[:b[0]], b[b[0]:]
                if f[-1] == 0x7e and crc16(f[:-3]) == int.from_bytes(f[-3:-1], 'big'): return f
                continue
            self.buf += self.s.recv(256)
    def wait_msg(self, msgid):
        while True:
            p = self.get_frame()[2:-3]
            if p.startswith(vlq(msgid)): return p
    def identify(self):
        data = b''
        while True:
            self.send(vlq(1) + vlq(len(data)) + vlq(40))
            p = self.wait_msg(0)
            _, i = unvlq(p, 0); off, i = unvlq(p, i); n, i = unvlq(p, i)
            chunk = p[i:i + n]
            if off == len(data): data += chunk
            if not chunk: return json.loads(zlib.decompress(data))

if __name__ == "__main__":
    d = Link(int(sys.argv[1])).identify()
    print("identify OK: version=%s commands=%d responses=%d MCU=%s CLOCK_FREQ=%s" % (
        d["version"], len(d["commands"]), len(d["responses"]), d["config"]["MCU"], d["config"]["CLOCK_FREQ"]))
    if len(sys.argv) > 2: json.dump(d, open(sys.argv[2], "w"))
