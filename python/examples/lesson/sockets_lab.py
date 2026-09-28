#!/usr/bin/env python3
"""The measurements behind sockets.py: real sockets over an emulated network link.

Run on Linux as root (WSL2 on Windows works), with only the standard library:

    wsl -u root python3 sockets_lab.py                    # writes sockets.net.json next to this file
    wsl -u root python3 sockets_lab.py --cpp BUILD_DIR    # and runs the C++ programs built in BUILD_DIR

Every experiment runs in a network namespace of its own, and only that namespace's
loopback gets a netem qdisc (a delay, and sometimes losses), so nothing else on the
machine sees the bad link. The namespace is deleted afterwards.

Packets are recorded with an AF_PACKET socket on that loopback. The kernel hands a packet
to the recorder when it is delivered, after the link's delay, so a packet's send time is its
delivery time minus the delay the link gave it. A packet the link drops is never delivered:
it shows up only in the sending program's own log.

Experiments (the film's beats):

    exchange_tcp   a request and its reply over TCP, 20 ms each way: the handshake, the data,
                   the acknowledgements and the teardown, packet by packet
    exchange_udp   the same request and reply as two UDP datagrams
    loss_tcp       six messages, 80 ms apart; the link drops the third and holds the fifth
                   back long enough for the sixth to overtake it (both chosen, so the film can
                   show them); what the receiving program reads, and every packet TCP sends
    loss_udp       the same six messages over UDP, the same link
    stream         a 100 Hz pose stream over UDP and over TCP at the same time, through a link
                   with 20 ms of delay that loses packets at random (netem loss)
    cpp            (with --cpp) the echo pair once and the ping/pong pair twenty times, the film's C++
                   programs as built, each run in a fresh namespace with no delay (a student's loopback)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import select
import socket
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DELAY = 0.020              # one way, seconds
STREAM_HZ = 100
STREAM_SECONDS = 15.0
STREAM_LOSS = 3.0          # percent, every packet on the link (data and acknowledgements)
FRAME = struct.Struct("!Id28x")   # a pose message: sequence number, send time, 7 joint floats' worth of bytes
PORT = 8080


# ── the link ──────────────────────────────────────────────────────────────────
def netem(*args, verb="change"):
    subprocess.run(["tc", "qdisc", verb, "dev", "lo", "root", "netem", *args], check=True)


def base_link(loss=0.0):
    a = ["delay", f"{DELAY * 1000:.0f}ms"]
    if loss > 0:
        a += ["loss", f"{loss}%"]
    return a


class Recorder:
    """Every packet delivered on this namespace's loopback, with its delivery time."""

    def __init__(self):
        self.s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))
        self.s.bind(("lo", 0))
        self.packets = []
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop:
            r, _, _ = select.select([self.s], [], [], 0.05)
            if not r:
                continue
            data, addr = self.s.recvfrom(65535)
            t = time.monotonic()
            if addr[2] == socket.PACKET_OUTGOING:      # loopback shows every packet twice
                continue
            self.packets.append((t, data))

    def stop(self):
        time.sleep(0.15)
        self._stop = True
        self._t.join()
        return [p for p in (parse(t, d) for t, d in self.packets) if p]


def parse(t, d):
    ip = d[14:]
    if len(ip) < 20 or ip[0] >> 4 != 4:
        return None
    ihl, proto = (ip[0] & 15) * 4, ip[9]
    l4 = ip[ihl:]
    sport, dport = struct.unpack("!HH", l4[:4])
    p = {"t": t, "sport": sport, "dport": dport}
    if proto == 6:
        seq, ack = struct.unpack("!II", l4[4:12])
        off, fl = (l4[12] >> 4) * 4, l4[13]
        p.update(proto="tcp", seq=seq, ack=ack,
                 flags=[n for b, n in ((2, "SYN"), (16, "ACK"), (8, "PSH"), (1, "FIN"), (4, "RST")) if fl & b],
                 payload=l4[off:].decode("latin-1"))
        # SACK blocks, if any: they say which later bytes arrived while an earlier one is missing
        opts, i, sack = l4[20:off], 0, []
        while i < len(opts):
            kind = opts[i]
            if kind == 0:
                break
            if kind == 1:
                i += 1
                continue
            ln = opts[i + 1]
            if kind == 5:
                sack = [struct.unpack("!II", opts[j:j + 8]) for j in range(i + 2, i + ln, 8)]
            i += ln
        if sack:
            p["sack"] = sack
    elif proto == 17:
        p.update(proto="udp", payload=l4[8:].decode("latin-1"))
    else:
        return None
    return p


def timeline(packets, t0, server_port, delays=None):
    """Packets as the film uses them: who sent it, when it left, when it arrived, what it said.
    `delays`: [(t_from, t_to, seconds)] windows in which the link's delay was changed; a packet
    whose delivery minus that delay falls inside the window left then."""
    out = []
    isn0 = {}
    for p in packets:
        side = "server" if p["sport"] == server_port else "client"
        d = DELAY
        for a, b, dd in delays or ():
            if a - 0.002 <= p["t"] - t0 - dd <= b + 0.002:
                d = dd
        e = {"from": side, "t_arrived": round(p["t"] - t0, 6), "t_sent": round(p["t"] - d - t0, 6),
             "proto": p["proto"], "payload": p["payload"]}
        if p["proto"] == "tcp":
            if "SYN" in p["flags"]:
                isn0[side] = p["seq"]
            other = "client" if side == "server" else "server"
            e["flags"] = p["flags"]
            e["seq"] = (p["seq"] - isn0.get(side, p["seq"])) & 0xFFFFFFFF      # relative, as Wireshark shows it
            e["ack"] = (p["ack"] - isn0.get(other, p["ack"])) & 0xFFFFFFFF if "ACK" in p["flags"] else None
            if "sack" in p:
                e["sack"] = [[(a - isn0.get(other, a)) & 0xFFFFFFFF, (b - isn0.get(other, b)) & 0xFFFFFFFF]
                             for a, b in p["sack"]]
        out.append(e)
    out.sort(key=lambda e: e["t_arrived"])
    return out


# ── experiments (run inside the namespace) ────────────────────────────────────
def exchange_tcp():
    netem(*base_link(), verb="add")
    rec = Recorder()
    time.sleep(0.1)
    ev = {}
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", PORT))
    srv.listen(1)
    t0 = time.monotonic()
    ev["listen"] = 0.0

    def serve():
        c, _ = srv.accept()
        ev["accept"] = time.monotonic() - t0
        req = c.recv(1024)
        ev["server_read"] = (time.monotonic() - t0, req.decode())
        c.sendall(b"battery=82%")
        ev["server_write"] = time.monotonic() - t0
        c.close()
        ev["server_close"] = time.monotonic() - t0
    th = threading.Thread(target=serve)
    th.start()
    time.sleep(0.05)
    cl = socket.socket()
    ev["connect_call"] = time.monotonic() - t0
    cl.connect(("127.0.0.1", PORT))
    ev["connected"] = time.monotonic() - t0
    cl.sendall(b"GET STATUS")
    ev["client_write"] = time.monotonic() - t0
    rep = cl.recv(1024)
    ev["client_read"] = (time.monotonic() - t0, rep.decode())
    cl.close()
    ev["client_close"] = time.monotonic() - t0
    th.join()
    pk = rec.stop()
    return {"link": {"delay": DELAY}, "events": ev, "packets": timeline(pk, t0, PORT)}


def exchange_udp():
    netem(*base_link(), verb="add")
    rec = Recorder()
    time.sleep(0.1)
    ev = {}
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", PORT))
    t0 = time.monotonic()

    def serve():
        data, addr = srv.recvfrom(1024)
        ev["server_read"] = (time.monotonic() - t0, data.decode())
        srv.sendto(b"battery=82%", addr)
        ev["server_write"] = time.monotonic() - t0
    th = threading.Thread(target=serve)
    th.start()
    time.sleep(0.05)
    cl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ev["client_write"] = time.monotonic() - t0
    cl.sendto(b"GET STATUS", ("127.0.0.1", PORT))
    data, _ = cl.recvfrom(1024)
    ev["client_read"] = (time.monotonic() - t0, data.decode())
    th.join()
    pk = rec.stop()
    return {"link": {"delay": DELAY}, "events": ev, "packets": timeline(pk, t0, PORT)}


LOSS_MSGS = [f"pose {k}" for k in range(1, 7)]
LOSS_GAP = 0.080
LOSS_DROP = 3                  # the link drops this message's packet (its first copy)
LOSS_HOLD, LOSS_HOLD_DELAY = 5, 0.130    # and holds this one back, so the next overtakes it


def _send_over_bad_link(send, t0, log):
    """Send the six messages 80 ms apart; the link drops one and holds one back."""
    windows = []
    for k, msg in enumerate(LOSS_MSGS, 1):
        target = t0 + 0.05 + (k - 1) * LOSS_GAP
        time.sleep(max(0.0, target - time.monotonic()))
        if k == LOSS_DROP:
            netem(*base_link(), "loss", "100%")
        elif k == LOSS_HOLD:
            netem("delay", f"{LOSS_HOLD_DELAY * 1000:.0f}ms")
        a = time.monotonic()
        send(msg.encode())
        log.append({"t": round(a - t0, 6), "msg": msg, "dropped": k == LOSS_DROP,
                    "held": k == LOSS_HOLD})
        if k in (LOSS_DROP, LOSS_HOLD):
            netem(*base_link())
            if k == LOSS_HOLD:
                windows.append((a - t0 - 0.004, time.monotonic() - t0, LOSS_HOLD_DELAY))
    return windows


def loss_tcp():
    netem(*base_link(), verb="add")
    rec = Recorder()
    time.sleep(0.1)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", PORT))
    srv.listen(1)
    reads, sent = [], []
    t0 = [None]

    def serve():
        c, _ = srv.accept()
        got = b""
        while True:
            d = c.recv(1024)
            if not d:
                break
            reads.append({"t": round(time.monotonic() - t0[0], 6), "data": d.decode()})
            got += d
        c.close()
    cl = socket.socket()
    cl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    th = threading.Thread(target=serve)
    th.start()
    cl.connect(("127.0.0.1", PORT))
    time.sleep(0.2)                                      # the handshake is over and acknowledged
    t0[0] = time.monotonic()
    windows = _send_over_bad_link(cl.sendall, t0[0], sent)
    time.sleep(1.2)                                      # let TCP finish its recovery
    cl.close()
    th.join()
    tl = [e for e in timeline(rec.stop(), t0[0], PORT, windows) if e["t_arrived"] >= 0]
    return {"link": {"delay": DELAY, "gap": LOSS_GAP, "dropped": LOSS_DROP, "held": LOSS_HOLD,
                     "held_delay": LOSS_HOLD_DELAY},
            "sent": sent, "reads": reads, "packets": tl}


def loss_udp():
    netem(*base_link(), verb="add")
    rec = Recorder()
    time.sleep(0.1)
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", PORT))
    srv.settimeout(0.6)
    got, sent = [], []
    t0 = time.monotonic()

    def serve():
        while True:
            try:
                d, _ = srv.recvfrom(1024)
            except socket.timeout:
                break
            got.append({"t": round(time.monotonic() - t0, 6), "data": d.decode()})
    th = threading.Thread(target=serve)
    th.start()
    cl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    windows = _send_over_bad_link(lambda b: cl.sendto(b, ("127.0.0.1", PORT)), t0, sent)
    th.join()
    pk = rec.stop()
    return {"link": {"delay": DELAY, "gap": LOSS_GAP, "dropped": LOSS_DROP, "held": LOSS_HOLD,
                     "held_delay": LOSS_HOLD_DELAY},
            "sent": sent, "received": got, "packets": timeline(pk, t0, PORT, windows)}


def stream():
    """A 100 Hz pose stream, once over UDP and once over TCP, at the same time on one link."""
    netem(*base_link(STREAM_LOSS), verb="add")
    n = int(STREAM_SECONDS * STREAM_HZ)
    t0 = time.monotonic() + 0.3
    udp_recv, tcp_recv = {}, {}
    udp_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_rx.bind(("127.0.0.1", PORT + 1))
    udp_rx.settimeout(1.0)
    lst = socket.socket()
    lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lst.bind(("127.0.0.1", PORT))
    lst.listen(1)

    def udp_reader():
        while True:
            try:
                d, _ = udp_rx.recvfrom(1024)
            except socket.timeout:
                return
            t = time.monotonic()
            seq, ts = FRAME.unpack(d)[:2]
            udp_recv.setdefault(seq, t - t0)

    def tcp_reader(c):
        buf = b""
        while True:
            d = c.recv(65536)
            if not d:
                return
            t = time.monotonic()
            buf += d
            while len(buf) >= FRAME.size:
                seq, ts = FRAME.unpack(buf[:FRAME.size])[:2]
                buf = buf[FRAME.size:]
                tcp_recv[seq] = t - t0

    # the laptop connects to the Pi; the Pi then streams on the accepted connection
    cl = socket.socket()
    cl.connect(("127.0.0.1", PORT))
    pi_tcp, _ = lst.accept()
    pi_tcp.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    pi_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    readers = [threading.Thread(target=udp_reader), threading.Thread(target=tcp_reader, args=(cl,))]
    for r in readers:
        r.start()
    sent = []
    for k in range(n):
        target = t0 + k / STREAM_HZ
        time.sleep(max(0.0, target - time.monotonic()))
        ts = time.monotonic() - t0
        msg = FRAME.pack(k, ts)
        pi_udp.sendto(msg, ("127.0.0.1", PORT + 1))
        pi_tcp.sendall(msg)
        sent.append(round(ts, 6))
    time.sleep(3.0)
    pi_tcp.close()
    for r in readers:
        r.join()
    stats = subprocess.run(["tc", "-s", "qdisc", "show", "dev", "lo"], capture_output=True, text=True).stdout
    return {"link": {"delay": DELAY, "loss_percent": STREAM_LOSS, "rate_hz": STREAM_HZ, "frame_bytes": FRAME.size,
                     "tc": stats.strip()},
            "sent": sent,
            "udp": [round(udp_recv[k], 6) if k in udp_recv else None for k in range(n)],
            "tcp": [round(tcp_recv[k], 6) if k in tcp_recv else None for k in range(n)]}


def cpp_pair(build, server, client):
    """One of the film's C++ programs and its client, as built, on a student's loopback (no delay).
    Each run gets a namespace of its own: a fresh port 8080 even for a server without SO_REUSEADDR."""
    exe = lambda n: os.path.join(build, n)     # noqa: E731
    s = subprocess.Popen([exe(server)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.2)
    c = subprocess.run([exe(client)], capture_output=True, text=True, timeout=10)
    out, err = s.communicate(timeout=10)
    return {"server": out.splitlines(), "client": c.stdout.splitlines(), "errors": (err + c.stderr).strip()}


PINGPONG_RUNS = 20


EXPERIMENTS = {"exchange_tcp": exchange_tcp, "exchange_udp": exchange_udp, "loss_tcp": loss_tcp,
               "loss_udp": loss_udp, "stream": stream}


# ── the outer process: one namespace per experiment ───────────────────────────
def in_namespace(name, extra=()):
    """Run experiment `name` in a fresh network namespace (its own loopback, its own ports)."""
    ns = f"sockets_lab_{os.getpid()}"
    subprocess.run(["ip", "netns", "add", ns], check=True)
    try:
        subprocess.run(["ip", "-n", ns, "link", "set", "lo", "up"], check=True)
        r = subprocess.run(["ip", "netns", "exec", ns, sys.executable, os.path.abspath(__file__), "--inner", name,
                            *extra], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{name} failed:\n{r.stderr}")
        return json.loads(r.stdout)
    finally:
        subprocess.run(["ip", "netns", "del", ns])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "sockets.net.json"))
    ap.add_argument("--cpp", default=None, help="a build directory with the echo and ping/pong programs")
    ap.add_argument("--only", default=None, help="comma-separated experiments to (re)run; the rest are kept")
    ap.add_argument("--inner", default=None, help=argparse.SUPPRESS)
    ap.add_argument("inner_args", nargs="*", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.inner:
        if a.inner == "cpp_pair":
            res = cpp_pair(*a.inner_args)
        else:
            res = EXPERIMENTS[a.inner]()
        json.dump(res, sys.stdout)
        return
    if os.geteuid() != 0:
        sys.exit("run as root (network namespaces and netem): wsl -u root python3 sockets_lab.py")
    out = {}
    if os.path.isfile(a.out):
        with open(a.out, encoding="utf-8") as f:
            out = json.load(f)
    names = a.only.split(",") if a.only else list(EXPERIMENTS) + (["cpp"] if a.cpp else [])
    for name in names:
        t = time.time()
        if name == "cpp":
            b = os.path.abspath(a.cpp)
            echo = in_namespace("cpp_pair", [b, "echo_server", "echo_client"])
            pp = [in_namespace("cpp_pair", [b, "pingpong_server", "pingpong_client"]) for _ in range(PINGPONG_RUNS)]
            out[name] = {"echo": {"server": echo["server"], "client": echo["client"]},
                         "pingpong": [r["server"][0] if r["server"] else "" for r in pp],
                         "errors": sorted({r["errors"] for r in pp + [echo] if r["errors"]})}
        else:
            out[name] = in_namespace(name)
        print(f"[lab] {name} in {time.time() - t:.1f}s")
    out["meta"] = {"kernel": platform.release(), "python": platform.python_version(),
                   "made": time.strftime("%Y-%m-%d"), "delay_one_way": DELAY}
    tmp = a.out + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, a.out)
    report(out)
    print("saved", a.out)


def report(o):
    """What the film shows, as numbers (the README's honest numbers)."""
    if "exchange_tcp" in o:
        ps = o["exchange_tcp"]["packets"]
        print(f"[exchange] TCP: {len(ps)} packets for one request and its reply; "
              f"UDP: {len(o.get('exchange_udp', {}).get('packets', []))}")
    if "loss_tcp" in o:
        r = o["loss_tcp"]["reads"]
        print("[loss] TCP reads: " + ", ".join(f"{x['t'] * 1000:.0f} ms '{x['data']}'" for x in r))
        rx = [p for p in o["loss_tcp"]["packets"] if LOSS_MSGS[LOSS_DROP - 1] in p["payload"]]
        if rx:
            print(f"[loss] TCP resent '{LOSS_MSGS[LOSS_DROP - 1]}' at {rx[0]['t_sent'] * 1000:.0f} ms")
    if "loss_udp" in o:
        print("[loss] UDP received: " + ", ".join(f"'{x['data']}'" for x in o["loss_udp"]["received"]))
    if "stream" in o:
        s = o["stream"]
        for k in ("udp", "tcp"):
            lat = [r - t for t, r in zip(s["sent"], s[k]) if r is not None]
            lost = sum(r is None for r in s[k])
            lat.sort()
            print(f"[stream] {k}: {len(lat)} of {len(s['sent'])} arrived ({lost} lost); latency median "
                  f"{lat[len(lat) // 2] * 1000:.1f} ms, p99 {lat[int(len(lat) * 0.99)] * 1000:.1f} ms, "
                  f"max {lat[-1] * 1000:.1f} ms")
    if "cpp" in o:
        pp = o["cpp"]["pingpong"]
        print(f"[cpp] echo client: {o['cpp']['echo']['client']}; ping/pong: one read returned 'pingpong' "
              f"in {sum(p.endswith('pingpong') for p in pp)} of {len(pp)} runs")


if __name__ == "__main__":
    main()
