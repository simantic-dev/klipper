#!/usr/bin/env python3
"""After identify, poll get_clock every 0.5 s wall; print MCU clock so it can be compared with the sim's virtual-time stamps. Usage: clock_check.py PORT N"""
import sys, time
from identify_peer import Link, vlq, unvlq
l = Link(int(sys.argv[1])); d = l.identify()
gc, clk = d["commands"]["get_clock"], d["responses"]["clock clock=%u"]
for _ in range(int(sys.argv[2])):
    l.send(vlq(gc)); p = l.wait_msg(clk); v, _ = unvlq(p, len(vlq(clk)))
    print(time.time(), "clock", v, "= %.4f s at 180 MHz" % (v / 180e6), flush=True); time.sleep(0.5)
