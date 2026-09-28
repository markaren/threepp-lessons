"""Sockets: how programs on different machines talk to each other.  An AIS2203 lecture film, about 5 min.

    python sockets.py                               # the film (1080p60), lesson_out/sockets.mp4
    python sockets.py --stills 30,60,95             # individual frames
    python sockets.py --sheet                       # contact sheet, one frame per 3 s
    python sockets.py --preview --out preview.mp4   # 960x540 @ 30 fps
    python sockets.py --speech                      # speak every line (Kokoro) and print SPEECH

Part 4 of the AIS2203 e-book (Data Communication), after its pages "Sockets, TCP & UDP" and
"Networking in C++": why machines need sockets, IP address and port, server and client,
TCP and UDP, what each does when the network loses a packet, which one to use for a stream
of poses, why a TCP stream needs framing, and an echo server and client in SimpleSocket.

Nothing on screen is invented:

* every packet, and every read a program makes, comes from sockets_lab.py: real sockets on
  Linux, over a link that netem delays by 20 ms each way (and, where the film says so, drops
  or holds back a packet), recorded packet by packet and cached in sockets.net.json. The
  film only slows them down;
* the TCP and UDP copies of the arm are driven by a real 100 Hz stream, sent over UDP and
  TCP at the same time through a link that loses packets at random: at every moment each
  copy shows the newest pose that had arrived by then;
* the C++ on screen is sockets/*.cpp, built with MSVC and with g++, and what the terminals
  print is what those programs printed when sockets_lab.py ran them.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lesson  # noqa: E402
from lesson import (DIM, TEXT, Hud, OrbitCamera, Ring3D, Stage, Timeline, Tube3D, _quat_y_to, clamp01,  # noqa: E402
                    data_file, ease_out, ease_out_back, envelope, fade_in_out, remap, run, smooth, smoother,
                    standard, tp)
import threepp_intro as intro  # noqa: E402  (the code cards and the syntax colours)
from threepp_intro import card, code_block  # noqa: E402

FPS = 60
NET_FILE = os.path.join(_HERE, "sockets.net.json")
CPP_DIR = os.path.join(_HERE, "sockets")

C_ACCENT = 0x4db6ac      # the e-book's teal, lifted for a dark background
C_TCP = 0x4db6ac         # TCP data
C_CTRL = 0xb39ddb        # TCP's own packets: SYN, ACK, FIN
C_UDP = 0xffb74d         # UDP datagrams
C_LOST = 0xef5350
C_OK = 0x81c784
C_OUT = 0xa6e3a1         # what a program prints
C_PI = 0x7fd08a
C_LAP = 0x90caf9

intro.KW["cpp"] |= {"char", "sizeof", "void", "bool", "true", "false", "nullptr"}

# ── the script ────────────────────────────────────────────────────────────────
# The narration sets the pace: every caption lasts as long as its spoken line (Kokoro,
# af_heart, measured with --speech) plus the voice's lead-in and tail and a small margin,
# and each beat's events hang off its captions. Until a changed line is re-measured, `run`
# holds the picture for any overrun.
CAPTION_TEXT = {
    "t0": "Sockets: how programs on different machines talk to each other.",
    "w1": "Threads inside one program share its memory. But a cyber-physical system is spread across machines: "
          "a controller on a Raspberry Pi, and an operator's laptop.",
    "w2": "They share no memory. The laptop cannot read the Pi's variables. All they can do is send each other bytes, "
          "over a network.",
    "w3": "A program's end of that link is a socket. It writes bytes into the socket and reads bytes out of it, "
          "much like a file.",
    "a1": "A socket is found by two things. The IP address picks the machine, like the street address of a building.",
    "a2": "The port picks one program on that machine, like the apartment number inside the building. "
          "A packet needs both.",
    "a3": "The loopback address, localhost, is this same machine, so a client and a server can be tested on one "
          "computer.",
    "c1": "Networked programs usually take one of two roles. The server starts first: it binds a port, and listens.",
    "c2": "The client knows the server's address and port, and connects. Three packets set up the connection.",
    "c3": "The server accepts, and gets a new socket just for this client. The laptop's question arrives right "
          "behind, and the Pi answers.",
    "c4": "Then both ends close. Every packet here was recorded from a real connection, and slowed down so you can "
          "follow it.",
    "p1": "A socket speaks one of two protocols. TCP is a reliable, ordered stream of bytes, over a connection.",
    "p2": "Those three packets are its handshake: SYN, SYN-ACK, ACK. After that, everything that arrives is "
          "acknowledged.",
    "p3": "UDP has no connection. Each datagram is sent on its own, with no handshake and no acknowledgements.",
    "p4": "The same question and answer over UDP is just two packets. Less work, and nothing is promised.",
    "l1": "The difference shows when the network misbehaves. Six messages cross a link that loses the third one, "
          "and delays the fifth.",
    "l2": "TCP notices the gap and sends the third again. The fourth is held back until the third arrives, so all six "
          "reach the program, in order.",
    "l3": "UDP just carries on. The third is gone for good, and the fifth arrives after the sixth. "
          "The program has to cope with that.",
    "s1": "Which to use depends on the data. Here the Pi sends the arm's pose to the laptop, a hundred times a second.",
    "s2": "The poses go over UDP and TCP at once, through a link that loses packets. The see-through arms show what "
          "the laptop receives, in slow motion.",
    "s3": "The UDP copy misses a sample now and then, but the next one is never far behind, so it stays live.",
    "s4": "The TCP copy gets every sample. But each loss holds up everything behind it, so the copy freezes, "
          "then jumps to catch up.",
    "s5": "So: TCP when every message must arrive, like a command to the robot. UDP when fresh but sometimes lost "
          "beats complete but late.",
    "b1": "One more thing about TCP catches almost everyone out. It carries a stream of bytes, not separate messages.",
    "b2": "Write ping, then pong, and a single read on the other side can return pingpong. The boundary between them "
          "is gone.",
    "b3": "It happened earlier, too: after the lost packet, one read returned the third and fourth messages together.",
    "b4": "So mark the boundaries yourself: end each message with a newline, or send its length first. "
          "UDP keeps them: one send, one receive.",
    "k1": "C++ has no sockets in its standard library. The operating system's own interface is long-winded, "
          "and different on Linux and Windows.",
    "k2": "A small library such as SimpleSocket hides all that. This is a whole echo server: listen on a port, "
          "accept a client, read, and write it back.",
    "k3": "And the client: connect, write hello, and read the reply. Start the server, then the client, and it prints: "
          "server replied, hello.",
    "o1": "In short: an address and a port find the program. TCP delivers every byte, in order. UDP sends datagrams, "
          "and promises nothing.",
}
VOICE_ONLY = {"t0", "o1"}       # spoken over the title card and the closing card, not drawn as captions

# how the narrator says the names on screen
lesson.SPOKEN_WORDS.update({"IP": "I P", "TCP": "T C P", "UDP": "U D P", "SYN": "sin", "ACK": "ack",
                            "C++": "C plus plus", "SimpleSocket": "Simple Socket", "pingpong": "ping pong"})

SPEECH = {"t0": 4.12, "w1": 10.85, "w2": 7.72, "w3": 7.62, "a1": 6.83, "a2": 6.9, "a3": 7.38, "c1": 7.0, "c2": 6.05,
          "c3": 8.28, "c4": 7.42, "p1": 7.33, "p2": 7.05, "p3": 7.28, "p4": 6.62, "l1": 8.1, "l2": 9.55, "l3": 8.28,
          "s1": 7.17, "s2": 10.18, "s3": 7.2, "s4": 8.72, "s5": 9.57, "b1": 7.53, "b2": 7.6, "b3": 6.95, "b4": 8.95,
          "k1": 9.4, "k2": 9.62, "k3": 8.05, "o1": 9.75}     # seconds, af_heart
# beat, lead-in before its first caption, its captions, time after the last one
PLAN = [("open", 1.0, ["t0"], 1.2), ("why", 0.3, ["w1", "w2", "w3"], 0.6), ("addr", 0.4, ["a1", "a2", "a3"], 0.8),
        ("cs", 0.4, ["c1", "c2", "c3", "c4"], 1.0), ("proto", 0.4, ["p1", "p2", "p3", "p4"], 1.4),
        ("loss", 0.4, ["l1", "l2", "l3"], 1.4), ("stream", 0.6, ["s1", "s2", "s3", "s4", "s5"], 1.0),
        ("bytes", 0.4, ["b1", "b2", "b3", "b4"], 1.0), ("code", 0.4, ["k1", "k2", "k3"], 2.2),
        ("outro", 0.4, ["o1"], 2.6)]
SLACK = lesson.VOICE_LEAD + lesson.VOICE_TAIL + 0.3     # a caption outlasts its speech by this much


def _layout():
    tl, cap, t = Timeline(), {}, 0.0
    for name, lead, keys, tail in PLAN:
        c = t + lead
        for k in keys:
            cap[k] = (c, c + SPEECH[k] + SLACK)
            c = cap[k][1] + 0.2
        end = (c - 0.2 if keys else t) + tail
        tl.add(name, t, end)
        t = end
    return tl, cap


TL, CAP = _layout()


def cap0(k):
    """When caption k starts."""
    return CAP[k][0]


def at(k, f):
    """A moment f (0..1) of the way through caption k's spoken line."""
    return cap0(k) + lesson.VOICE_LEAD + f * SPEECH[k]


SUMMARY = [(r"$\mathrm{IP:port}$", "Which machine, and which program on it."),
           (r"$\mathrm{server}$", "Binds a port and listens; the client connects."),
           (r"$\mathrm{TCP}$", "Every byte, in order. Mark your own message boundaries."),
           (r"$\mathrm{UDP}$", "Separate datagrams, no promises. Fresh beats complete.")]


# ── the measurements ──────────────────────────────────────────────────────────
def load_net():
    if not os.path.isfile(NET_FILE):
        raise FileNotFoundError(f"{NET_FILE} is missing: run sockets_lab.py (Linux, as root) to record it")
    with open(NET_FILE, encoding="utf-8") as f:
        return json.load(f)


NET = load_net()
BASE = NET["meta"]["delay_one_way"]      # the link's delay, seconds


def read_cpp(name):
    with open(os.path.join(CPP_DIR, name), encoding="utf-8") as f:
        return f.read().rstrip("\n").split("\n")


class Warp:
    """Piecewise-linear map from lab time to film time (s), extended linearly past its ends."""

    def __init__(self, keys):
        self.k = sorted((float(a), float(b)) for a, b in keys)

    def _map(self, x, k):
        if x <= k[0][0]:
            (x0, y0), (x1, y1) = k[0], k[1]
        elif x >= k[-1][0]:
            (x0, y0), (x1, y1) = k[-2], k[-1]
        else:
            for (x0, y0), (x1, y1) in zip(k, k[1:]):
                if x <= x1:
                    break
        return y0 + (y1 - y0) * (x - x0) / max(x1 - x0, 1e-12)

    def __call__(self, x):
        return self._map(x, self.k)

    def inv(self, y):
        return self._map(y, [(b, a) for a, b in self.k])


# ── the set (Y-up world, metres) ──────────────────────────────────────────────
ARM = np.array([-1.35, 0.0, 0.0])            # the FR3's base
PED = np.array([-0.30, 0.0, 0.55])           # the Pi's pedestal (centre of its footprint)
PED_H = 0.55
PI_TOP = PED + np.array([0.0, PED_H, 0.0])
PI_PORT = PI_TOP + np.array([0.17, 0.035, -0.04])     # its Ethernet jack
DESK = np.array([1.45, 0.0, 0.35])
DESK_H = 0.74
LAPTOP = DESK + np.array([-0.05, DESK_H, 0.05])
LAP_PORT = LAPTOP + np.array([-0.185, 0.02, 0.02])
CLOUD = np.array([0.55, 1.62, 0.05])
WIDE = np.array([0.05, 0.82, 0.2])


def catmull(points, n=700):
    """Points along a Catmull-Rom curve through `points`, evenly spaced by arc length."""
    P = np.asarray(points, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for u in np.linspace(0, 1, 60, endpoint=False):
            u2, u3 = u * u, u * u * u
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u3))
    out.append(P[-2])
    out = np.array(out)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(out, axis=0), axis=1))]
    s = np.linspace(0, L[-1], n)
    return np.stack([np.interp(s, L, out[:, k]) for k in range(3)], axis=1)


class Path:
    """A route for packets, from end A (s = 0) to end B (s = 1), with where it enters and
    leaves the network cloud."""

    def __init__(self, points, cloud=None, r=0.30):
        self.P = catmull(points)
        self.T = np.gradient(self.P, axis=0)
        self.T /= np.linalg.norm(self.T, axis=1, keepdims=True)
        n = len(self.P)
        if cloud is not None:
            inside = np.linalg.norm(self.P - cloud, axis=1) < r
            idx = np.where(inside)[0]
            self.s_in, self.s_out = idx[0] / (n - 1), idx[-1] / (n - 1)
        else:
            self.s_in, self.s_out = 0.45, 0.55

    def at(self, s, lane=0.0):
        s = clamp01(s)
        f = s * (len(self.P) - 1)
        i = min(int(f), len(self.P) - 2)
        u = f - i
        p = self.P[i] * (1 - u) + self.P[i + 1] * u
        return p + np.array([0.0, 0.0, lane]), self.T[i]


LINK = Path([PI_PORT, PI_PORT + (0.10, 0.32, 0.0), CLOUD + (-0.55, -0.02, 0.0), CLOUD, CLOUD + (0.55, -0.02, 0.0),
             LAP_PORT + (-0.12, 0.32, 0.0), LAP_PORT], cloud=CLOUD)
LOOP = Path([LAP_PORT, LAP_PORT + (-0.16, 0.20, 0.0), LAP_PORT + (-0.05, 0.42, 0.0), LAP_PORT + (0.14, 0.40, 0.0),
             LAP_PORT + (0.18, 0.20, 0.0), LAP_PORT + (0.07, 0.03, 0.0)])


class Flight:
    """One packet's trip, in lab seconds. It leaves `src` ('pi' or 'laptop') at ts and arrives
    at ta; ta None means the network lost it. The time a trip takes beyond the link's own delay
    is spent inside the cloud, where the network holds it."""

    def __init__(self, src, ts, ta, label="", kind="data", lane=0.0, path=LINK, warp=None, bundle=0, note=None):
        self.src, self.ts, self.ta, self.label, self.kind, self.lane = src, ts, ta, label, kind, lane
        self.path, self.warp, self.bundle, self.note = path, warp, bundle, note
        # LINK runs from the Pi to the laptop; the loopback path runs one way only
        self.forward = src == "pi" or path is not LINK

    def cloud_span(self):
        p = self.path
        return (p.s_in, p.s_out) if self.forward else (1 - p.s_out, 1 - p.s_in)

    @property
    def lost(self):
        return self.ta is None

    def s_lab(self, tau):
        """How far along the path (0..1 from its sender) at lab time tau; None when not on the wire."""
        s_in, s_out = self.cloud_span()
        a, b = BASE * s_in, BASE * (1 - s_out)
        if tau < self.ts:
            return None
        if self.lost:
            u = (tau - self.ts) / a
            return s_in * u if u <= 1.0 else None
        if tau > self.ta:
            return None
        if tau < self.ts + a:
            return s_in * (tau - self.ts) / a
        if tau > self.ta - b:
            return s_out + (1 - s_out) * (tau - (self.ta - b)) / b
        return s_in + (s_out - s_in) * (tau - self.ts - a) / max(self.ta - b - self.ts - a, 1e-9)

    def t_sent(self):
        return self.warp(self.ts)

    def t_arrived(self):
        return self.warp(self.ta) if not self.lost else None

    def t_lost(self):
        return self.warp(self.ts + BASE * self.cloud_span()[0])


def bundle(flights, window=0.002):
    """Packets that leave one end within `window` of each other: number them 0, 1, 2.. so they
    can be drawn side by side instead of on top of each other."""
    fl = sorted(flights, key=lambda f: f.ts)
    for i, f in enumerate(fl):
        k = 0
        for g in fl[:i]:
            if g.src == f.src and abs(g.ts - f.ts) < window:
                k = max(k, g.bundle + 1)
        f.bundle = k
    return fl


def tcp_label(p, msg_len=6, show_ack=False):
    """A packet of the recorded connection as the film names it."""
    fl = p.get("flags", [])
    if "SYN" in fl:
        return "SYN-ACK" if "ACK" in fl else "SYN", "ctrl"
    if "FIN" in fl:
        return "FIN", "ctrl"
    if p["payload"]:
        return p["payload"], "data"
    if p.get("sack"):
        missing = (p["ack"] - 1) // msg_len + 1
        return f"ack: missing {missing}", "ctrl"
    return "ack", "ctrl"


def flights_of(packets, side_of, warp, lane=0.0, label=tcp_label):
    out = []
    for p in packets:
        lab, kind = label(p) if p["proto"] == "tcp" else (p["payload"], "udp")
        out.append(Flight(side_of[p["from"]], p["t_sent"], p["t_arrived"], lab, kind, lane, warp=warp))
    return bundle(out)


# ── the choreography: every beat's packets, on the film's clock ───────────────
def choreograph():
    rec = {}
    ex = NET["exchange_tcp"]
    ev = ex["events"]
    # the recorded exchange: the laptop is the client, the Pi the server
    w_ex = Warp([(-0.02, at("c1", 0.55)), (ev["connect_call"], at("c2", 0.52)), (ev["connected"], at("c2", 1.0)),
                 (ev["accept"], at("c3", 0.12)), (ev["client_read"][0], at("c3", 0.92)),
                 (ev["client_close"] + 0.020, at("c4", 0.30)), (0.172, at("c4", 0.62))])
    rec["ex_tcp"] = flights_of(ex["packets"], {"client": "laptop", "server": "pi"}, w_ex)
    rec["ex_tcp_warp"] = w_ex
    rec["ex_events"] = [("pi", -0.012, "bind · listen"), ("laptop", ev["connect_call"], "connect"),
                        ("laptop", ev["connected"], "write"), ("pi", ev["accept"], "accept · read"),
                        ("pi", ev["server_write"] + 0.0006, "write · close"),
                        ("laptop", ev["client_read"][0], "read · close")]
    ux = NET["exchange_udp"]
    u0 = ux["events"]["client_write"]
    w_ux = Warp([(u0, at("p3", 0.35)), (u0 + 0.042, at("p3", 0.95))])
    rec["ex_udp"] = flights_of(ux["packets"], {"client": "laptop", "server": "pi"}, w_ux)
    rec["ex_udp_warp"] = w_ux
    rec["ex_udp_events"] = [("pi", u0 - 0.002, "bind"), ("laptop", u0, "send"), ("pi", u0 + 0.0205, "receive · send"),
                            ("laptop", u0 + 0.041, "receive")]

    # one lost packet: the Pi sends, the laptop reads
    lt = NET["loss_tcp"]
    sent = {s["msg"]: s["t"] for s in lt["sent"]}
    w_lt = Warp([(0.03, at("l1", 0.45)), (sent["pose 3"], CAP["l1"][1] - 0.2), (0.330, at("l2", 0.22)),
                 (0.351, at("l2", 0.45)), (0.503, at("l2", 0.93)), (0.53, CAP["l2"][1] + 0.1)])
    fl = flights_of([p for p in lt["packets"] if p["t_sent"] < 0.56], {"client": "pi", "server": "laptop"}, w_lt)
    fl.append(Flight("pi", sent["pose 3"], None, "pose 3", "data", warp=w_lt))
    for f in fl:
        if f.label == "pose 3" and not f.lost:
            f.note = "sent again"
    rec["loss_tcp"] = bundle(fl)
    rec["loss_tcp_reads"] = [(r["t"], r["data"]) for r in lt["reads"]]
    rec["loss_tcp_warp"] = w_lt
    lu = NET["loss_udp"]
    sent_u = {s["msg"]: s["t"] for s in lu["sent"]}
    w_lu = Warp([(0.03, cap0("l3") - 0.3), (sent_u["pose 3"], at("l3", 0.22)), (0.4705, at("l3", 0.52)),
                 (0.5235, at("l3", 0.70)), (0.56, CAP["l3"][1])])
    fu = flights_of(lu["packets"], {"client": "pi"}, w_lu)
    fu.append(Flight("pi", sent_u["pose 3"], None, "pose 3", "udp", warp=w_lu))
    rec["loss_udp"] = bundle(fu)
    rec["loss_udp_reads"] = [(r["t"], r["data"]) for r in lu["received"]]
    rec["loss_udp_warp"] = w_lu

    # the pose stream: lab time runs at a quarter of film speed from the start of its beat
    s = NET["stream"]
    rec["st_sent"] = np.asarray(s["sent"], float)
    for k in ("udp", "tcp"):
        arr = np.array([np.nan if v is None else v for v in s[k]], float)
        rec[f"st_{k}"] = arr
        ok = np.where(~np.isnan(arr))[0]
        order = ok[np.argsort(arr[ok], kind="stable")]
        rec[f"st_{k}_t"] = arr[order]                        # arrival times, sorted
        rec[f"st_{k}_seq"] = np.maximum.accumulate(order)    # newest sample delivered by then
    lat_t = (rec["st_tcp"] - rec["st_sent"]) * 1000
    lat_u = (rec["st_udp"] - rec["st_sent"]) * 1000
    rec["meta"] = dict(tcp_packets=len(ex["packets"]), udp_packets=len(ux["packets"]),
                       stream_lost_udp=int(np.isnan(rec["st_udp"]).sum()), stream_n=len(rec["st_sent"]),
                       lat_tcp_p50=float(np.nanmedian(lat_t)), lat_tcp_max=float(np.nanmax(lat_t)),
                       lat_udp_max=float(np.nanmax(lat_u)))
    return rec


# the stream beat's clocks
SLOWMO = 4.0
T_STREAM = TL.start("stream") + 0.4          # the arm starts to move
TAU0 = 1.6                                    # lab time at T_STREAM
T_GHOST = at("s2", 0.55)                      # the copies appear ("the see-through arms")


def tau_of(t):
    return TAU0 + (t - T_STREAM) / SLOWMO


def ghost_alpha(k, t):
    """The copies one at a time, as the narration takes them: both where s2 names them,
    UDP's through s3, TCP's through s4, and both again for the verdict."""
    end = TL.end("stream") - 0.3
    both = max(envelope(t, T_GHOST, cap0("s3") + 0.6, 0.6, 0.6), envelope(t, cap0("s5") - 0.2, end, 0.6, 0.8))
    if k == "udp":
        own = envelope(t, cap0("s3"), CAP["s3"][1] + 0.3, 0.6, 0.6)
    else:
        own = envelope(t, cap0("s4") - 0.2, CAP["s4"][1] + 0.3, 0.6, 0.6)
    return max(both, own)


# ── the arm ───────────────────────────────────────────────────────────────────
DOF = 7
Q_READY = np.array([0.0, -math.pi / 4, 0.0, -3 * math.pi / 4, 0.0, math.pi / 2, math.pi / 4])
AMP = np.array([0.55, 0.32, 0.30, 0.38, 0.45, 0.40, 0.7])
OMEGA = np.array([2.7, 3.4, 2.9, 3.6, 3.1, 3.8, 2.6])
PHASE = np.array([0.0, 0.9, 2.1, 0.4, 1.7, 2.6, 1.1])


def q_stream(tau):
    """The arm's joints at lab time tau: still before the stream, then a steady dance."""
    ramp = smoother((tau - TAU0) / 1.2)
    return Q_READY + ramp * AMP * np.sin(OMEGA * (tau - TAU0) + PHASE) * np.array([1, 1, 1, 1, 1, 1, 1])


def q_idle(t):
    return Q_READY + np.array([0.18, 0.06, 0.1, 0.08, 0.12, 0.08, 0.2]) * np.sin(0.35 * t + PHASE)


def full(q7):
    return list(map(float, q7[:DOF])) + [0.035, 0.035]


# ── the picture ───────────────────────────────────────────────────────────────
LOOK_CS = np.array([0.95, 0.82, 0.12])
LOOK_LOSS = np.array([1.20, 0.86, 0.12])
LOOK_ARM = np.array([-0.95, 0.55, 0.05])
CAMERA = OrbitCamera([    # (time, azimuth, elevation, distance, look point, fov)
    (0.0, -93, 13, 7.4, WIDE + (-0.95, 0.42, 0.0), 32),
    (TL.end("open") - 0.6, -90, 12, 6.8, WIDE + (-0.8, 0.36, 0.0), 32),
    (at("w1", 0.6), -90, 12, 5.6, WIDE + (0, 0.02, 0), 32),
    (TL.end("why") - 0.6, -91, 12, 5.4, WIDE + (0, 0.02, 0), 32),
    (at("a1", 0.3), -86, 13, 4.3, np.array([-0.05, 0.85, 0.3]), 32),
    (at("a2", 1.0), -88, 13, 4.6, np.array([0.10, 0.85, 0.3]), 32),
    (at("a3", 0.15), -74, 17, 2.3, LAPTOP + (0.0, 0.2, 0.0), 32),
    (TL.end("addr") - 0.5, -78, 17, 2.4, LAPTOP + (0.0, 0.2, 0.0), 32),
    (TL.start("cs") + 1.6, -90, 11, 6.0, LOOK_CS, 32),
    (TL.end("proto") - 1.0, -91, 11, 6.0, LOOK_CS, 32),
    (TL.start("loss") + 1.4, -90, 11, 6.6, LOOK_LOSS, 32),
    (TL.end("loss") - 0.8, -91, 11, 6.6, LOOK_LOSS, 32),
    (TL.start("stream") + 2.2, -64, 13, 3.1, LOOK_ARM, 32),
    (TL.end("stream") - 1.0, -70, 14, 3.0, LOOK_ARM, 32),
    (TL.start("bytes") + 1.6, -90, 13, 6.6, WIDE, 32),
    (TL.end("code"), -94, 13, 6.6, WIDE, 32),
    (TL.end("outro"), -97, 13, 6.9, WIDE, 32),
], frame="yup", drift=((0.8, 0.19), (0.4, 0.15)))


class Painter:
    def __init__(self, st, parts, rec, ov):
        self.st, self.p, self.rec, self.ov = st, parts, rec, ov
        cpp = NET.get("cpp", {})
        self.echo_out = cpp.get("echo", {"server": ["listening on port 8080..."], "client": ["server replied: hello"]})
        pp = [l for l in cpp.get("pingpong", []) if l.endswith("pingpong")]
        self.pingpong_out = pp[0] if pp else "read 8 bytes: pingpong"
        self.captions = [(a, b, CAPTION_TEXT[k]) + ((False,) if k in VOICE_ONLY else ()) for k, (a, b) in CAP.items()]
        self.code = {n: read_cpp(n) for n in ("echo_server.cpp", "echo_client.cpp", "posix_echo_server.cpp")}

    # 3D ----------------------------------------------------------------------
    def set3d(self, t):
        st, p, rec = self.st, self.p, self.rec
        eye, look, fov = CAMERA(t)
        st.look(eye, look, fov)

        # the arm: idling, then the stream's dance; its copies from the recorded stream
        tau = tau_of(t)
        w = smoother((tau - TAU0) / 1.2) if t >= T_STREAM else 0.0
        q = q_stream(tau) + (1 - w) * (q_idle(t) - Q_READY)
        p["robot"].set_joint_values(full(q))
        for k, key in (("udp", "ghost_udp"), ("tcp", "ghost_tcp")):
            ga = ghost_alpha(k, t)
            g, m = p[key]
            g.visible = ga > 0.003
            if g.visible:
                i = np.searchsorted(rec[f"st_{k}_t"], tau, side="right") - 1
                seq = int(rec[f"st_{k}_seq"][i]) if i >= 0 else 0
                g.set_joint_values(full(q_stream(rec["st_sent"][seq])))
                m.opacity = 0.5 * ga
        st.follow([0.0, 0.0, 0.25])

        # the network cloud turns stormy while the link loses packets
        storm = max(envelope(t, TL.start("loss") + 0.6, TL.end("loss"), 1.2, 1.0),
                    envelope(t, at("s2", 0.0), TL.end("stream"), 1.2, 1.2))
        c0, c1 = np.array(lesson.hex_rgb(0xd9e1ee)), np.array(lesson.hex_rgb(0x5b6472))
        r_, g_, b_ = (int(round(v)) for v in c0 * (1 - storm) + c1 * storm)
        p["cloud_mat"].color = (r_ << 16) | (g_ << 8) | b_
        p["cloud"].rotation.y = 0.04 * t
        # the link itself: a faint tube
        la = max(envelope(t, at("w3", 0.1), TL.end("loss") + 0.8, 0.8, 0.8), 0.0)
        p["link_mat"].opacity = 0.30 * la
        p["link"].visible = la > 0.003

        # the laptop's screen: the battery reading appears when the reply has arrived
        got = t >= self.rec["ex_tcp_warp"](NET["exchange_tcp"]["events"]["client_read"][0])
        p["screen"].material.map = p["screen_after"] if got else p["screen_before"]

        # sockets: rings at the ports
        self.rings(t)
        self.packets(t)

    def rings(self, t):
        p = self.p
        pulse = 0.5 + 0.5 * math.sin(5.0 * t)
        ev = NET["exchange_tcp"]["events"]
        w = self.rec["ex_tcp_warp"]
        # the socket ends, once they are introduced
        on = envelope(t, at("w3", 0.05), TL.end("loss") + 0.5, 0.6, 0.8)
        listen = envelope(t, at("c1", 0.75), TL.end("loss") + 0.5, 0.4, 0.8)
        pi_a = max(on * (1.0 if t < TL.start("cs") else 0.0), listen)
        p["ring_pi"].set_opacity(pi_a * (0.65 + 0.35 * pulse if TL.start("cs") <= t < w(ev["accept"]) else 1.0))
        acc = envelope(t, w(ev["accept"]), TL.end("loss") + 0.5, 0.3, 0.8)
        p["ring_pi2"].set_opacity(acc)
        s = 1.0 + 0.5 * (1 - smooth(remap(t, w(ev["accept"]), w(ev["accept"]) + 0.6)))
        p["ring_pi2"].mesh.scale.set(s, s, s)
        lap = max(on * (1.0 if t < TL.start("cs") else 0.0), envelope(t, w(ev["connect_call"]), TL.end("loss") + 0.5,
                                                                        0.4, 0.8))
        p["ring_lap"].set_opacity(lap)
        # loopback: a second socket on the laptop
        lb = envelope(t, at("a3", 0.2), TL.end("addr") - 0.2, 0.5, 0.5)
        p["ring_lap2"].set_opacity(lb)

    def active_flights(self, t):
        """Every packet on the wire at film time t: (flight, s along its path, opacity)."""
        rec = self.rec
        groups = [("ex_tcp", TL.start("cs"), TL.end("cs") + 0.5), ("ex_udp", at("p3", 0.0), TL.end("proto")),
                  ("loss_tcp", TL.start("loss"), CAP["l2"][1] + 0.5), ("loss_udp", cap0("l3") - 0.6, TL.end("loss"))]
        out = []
        for key, a, b in groups:
            if not (a <= t <= b):
                continue
            for f in rec[key]:
                tau = f.warp.inv(t)
                s = f.s_lab(tau)
                if s is None:
                    continue
                out.append((f, s))
        out += self.scripted_flights(t)
        return out

    def scripted_flights(self, t):
        """The packets that illustrate an idea (not a recording): bytes on their way in the
        opening beats, the addressed packet and the loopback one."""
        out = []
        # w2/w3: a trickle of bytes each way once the socket is named
        a, b = at("w3", 0.35), TL.end("why") + 0.4
        if a <= t <= b:
            for k in range(14):
                t0 = a + 0.42 * k
                s = (t - t0) / 1.6
                if 0 <= s <= 1:
                    out.append((Flight("pi" if k % 2 == 0 else "laptop", 0, 1, "", "byte"), s))
        # a2: one packet addressed to 192.168.1.42:8080, from the laptop to the Pi
        t0, t1 = at("a2", 0.35), at("a2", 0.85)
        if t0 <= t <= t1:
            out.append((Flight("laptop", 0, 1, "to 192.168.1.42 : 8080", "data"), (t - t0) / (t1 - t0)))
        # a3: the loopback: out of the laptop, and straight back in
        t0, t1 = at("a3", 0.35), at("a3", 0.9)
        if t0 <= t <= t1:
            out.append((Flight("laptop", 0, 1, "to 127.0.0.1 : 8080", "data", path=LOOP), (t - t0) / (t1 - t0)))
        return out

    def packets(self, t):
        p = self.p
        used = 0
        self.labels = []
        for f, s in self.active_flights(t):
            if used >= len(p["pk"]):
                break
            m, mat = p["pk"][used]
            used += 1
            along = s if f.forward else 1.0 - s
            along = clamp01(along - 0.035 * f.bundle * (1 if f.forward else -1))
            pos, tan = f.path.at(along, f.lane)
            m.visible = True
            m.position.set(*pos)
            m.quaternion.set(*_quat_y_to(tan))
            col = {"data": C_TCP, "ctrl": C_CTRL, "udp": C_UDP, "byte": 0xdfe8ff}[f.kind]
            size = {"data": 1.0, "ctrl": 0.72, "udp": 1.0, "byte": 0.45}[f.kind]
            if f.note == "sent again":
                col = 0x9ff5e8
            mat.color = col
            mat.emissive = col
            m.scale.set(size, size, size)
            if f.label and (f.kind != "ctrl" or f.label in ("SYN", "SYN-ACK")):
                self.labels.append((pos, f.label, col, f.bundle))
        for m, _ in p["pk"][used:]:
            m.visible = False
        # a lost packet bursts where it enters the cloud
        used = 0
        for key in ("loss_tcp", "loss_udp"):
            for f in self.rec[key]:
                if not f.lost:
                    continue
                tl_ = f.t_lost()
                u = (t - tl_) / 0.8
                if 0 <= u <= 1 and used < len(p["burst"]):
                    m, mat = p["burst"][used]
                    used += 1
                    pos, _ = LINK.at(LINK.s_in, f.lane)
                    m.visible = True
                    m.position.set(*pos)
                    r = 0.05 + 0.22 * ease_out(u)
                    m.scale.set(r, r, r)
                    mat.opacity = 0.85 * (1 - u) ** 1.5
        for m, _ in p["burst"][used:]:
            m.visible = False

    # 2D ----------------------------------------------------------------------
    def draw2d(self, t):
        ov = self.ov
        ov.title_card(t, "AIS2203  ·  PART 4  ·  DATA COMMUNICATION", "Sockets",
                      "How programs on different machines talk to each other", C_ACCENT, t_in=0.6,
                      t_out=TL.end("open") - 0.3)
        self.why_hud(t)
        self.addr_hud(t)
        self.packet_labels(t)
        self.cs_hud(t)
        self.proto_hud(t)
        self.loss_hud(t)
        self.stream_hud(t)
        self.bytes_hud(t)
        self.code_hud(t)
        ov.captions(t, self.captions)
        ov.summary(t, TL.start("outro"), TL.end("outro"), SUMMARY,
                   "Read more in the e-book: Sockets, TCP & UDP, and Networking in C++", C_ACCENT, C_ACCENT,
                   text_dx=300, link="markaren.github.io/E-book_cps")

    def P(self, p):
        return self.st.project(np.asarray(p, float))

    def packet_labels(self, t):
        ov = self.ov
        for pos, label, col, k in self.labels:
            q = self.P(pos + np.array([0.0, 0.07, 0.0]))
            if q[2] <= 0:
                continue
            ov.text(q[0], q[1] - 6 - 24 * k, label, size=19, color=col, alpha=0.95, kind="semibold", anchor="md")

    def machine_tags(self, t, a):
        """Names over the two machines."""
        ov = self.ov
        q = self.P(PI_TOP + (0.0, 0.14, 0.0))
        ov.text(q[0], q[1] - 30, "Raspberry Pi", size=22, color=C_PI, alpha=a, kind="semibold", anchor="ms")
        ov.text(q[0], q[1] - 6, "controller", size=17, color=DIM, alpha=a, anchor="ms")
        q = self.P(LAPTOP + (0.0, 0.34, -0.1))
        ov.text(q[0], q[1] - 30, "laptop", size=22, color=C_LAP, alpha=a, kind="semibold", anchor="ms")
        ov.text(q[0], q[1] - 6, "operator", size=17, color=DIM, alpha=a, anchor="ms")

    def why_hud(self, t):
        ov = self.ov
        a = envelope(t, TL.start("why") + 0.3, TL.end("why") - 0.1, 0.6, 0.5)
        if a <= 0.003:
            return
        self.machine_tags(t, a * smooth(remap(t, at("w1", 0.55), at("w1", 0.75))))
        # each machine's memory: what it knows
        ma = a * envelope(t, at("w1", 0.1), at("w3", 0.25), 0.6, 0.6)
        rows_pi = [("battery", "82", TEXT), ("mode", "RUN", TEXT), ("pose", "{0.12, -0.81, ...}", TEXT)]
        rows_lap = [("battery", "?", C_LOST), ("mode", "?", C_LOST), ("pose", "?", C_LOST)]
        for (anchor, title, rows, col, dx) in ((PI_TOP, "THE PI'S MEMORY", rows_pi, C_PI, -380),
                                             (LAPTOP, "THE LAPTOP'S MEMORY", rows_lap, C_LAP, -150)):
            q = self.P(anchor + (0.0, 0.62, 0.0))
            x, y = q[0] + dx, q[1] - 200
            card(ov, x, y, 420, 60 + 36 * len(rows), ma, title)
            for j, (k, v, c) in enumerate(rows):
                la = ma * (smooth(remap(t, at("w2", 0.25), at("w2", 0.45))) if c == C_LOST else 1.0)
                ov.text(x + 26, y + 70 + 36 * j, k, size=21, color=DIM, alpha=ma, kind="mono", anchor="lm")
                ov.text(x + 150, y + 70 + 36 * j, "= " + v, size=21, color=c, alpha=la, kind="mono", anchor="lm")
        # no shared memory: a dashed line between them, crossed out
        xa = envelope(t, at("w2", 0.05), at("w3", 0.25), 0.5, 0.5) * a
        if xa > 0.003:
            q0 = self.P(PI_TOP + (0.25, 0.75, 0.0))
            q1 = self.P(LAPTOP + (-0.25, 0.75, 0.0))
            ov.dashed(q0[:2], q1[:2], C_LOST, 2.5, xa, dash=12, gap=9)
            mx, my = (q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2
            for d in (1, -1):
                ov.line([(mx - 16, my - 16 * d), (mx + 16, my + 16 * d)], C_LOST, 4.0, xa)
            ov.text(mx, my + 30, "no shared memory", size=22, color=C_LOST, alpha=xa, kind="semibold", anchor="ma")
        # the socket: where each program's end of the link is
        sa = a * smooth(remap(t, at("w3", 0.05), at("w3", 0.3)))
        if sa > 0.003:
            for anchor, lx, ly in ((PI_PORT, -150, 80), (LAP_PORT, 150, 80)):
                q = self.P(anchor)
                ov.callout(q[:2], (q[0] + lx, q[1] + ly), "socket", C_ACCENT, sa, size=22,
                           grow=ease_out(remap(t, at("w3", 0.05), at("w3", 0.3))))

    def addr_hud(self, t):
        ov = self.ov
        a = envelope(t, TL.start("addr") + 0.2, TL.end("addr") - 0.1, 0.5, 0.5)
        if a <= 0.003:
            return
        # a1: which machine
        ia = a * envelope(t, at("a1", 0.3), at("a3", 0.1), 0.5, 0.5)
        for anchor, ip, col, dy in ((PI_TOP, "192.168.1.42", C_PI, 0.36), (LAPTOP, "192.168.1.17", C_LAP, 0.55)):
            q = self.P(anchor + (0.0, dy, 0.0))
            ov.text(q[0], q[1], ip, size=34, color=col, alpha=ia, kind="mono", anchor="ms")
            ov.text(q[0], q[1] + 28, "IP address: the machine", size=18, color=DIM, alpha=ia, anchor="ms")
        # a2: which program on it: the ports
        pa = a * envelope(t, at("a2", 0.05), at("a3", 0.1), 0.5, 0.5)
        if pa > 0.003:
            q = self.P(PI_TOP + (0.0, 0.1, 0.0))
            x, y = q[0] - 440, q[1] - 120
            rows = [("22", "ssh"), ("80", "web server"), ("8080", "telemetry service")]
            card(ov, x, y, 330, 60 + 44 * len(rows), pa, "PORTS ON THE PI")
            hit = t >= at("a2", 0.85)
            for j, (port, name) in enumerate(rows):
                ra = pa * smooth(remap(t, at("a2", 0.08 + 0.07 * j), at("a2", 0.16 + 0.07 * j)))
                yy = y + 74 + 44 * j
                glow = port == "8080" and hit
                if glow:
                    ov.panel(x + 12, yy - 20, 306, 40, radius=8, fill=0x1d4d47, alpha=0.9 * ra)
                ov.text(x + 30, yy, port, size=24, color=C_ACCENT if port == "8080" else TEXT, alpha=ra, kind="mono",
                        anchor="lm")
                ov.text(x + 130, yy, name, size=21, color=TEXT if glow else DIM, alpha=ra, anchor="lm")
        # a3: this same machine
        la = a * envelope(t, at("a3", 0.1), TL.end("addr"), 0.5, 0.4)
        if la > 0.003:
            q = self.P(LAPTOP + (0.0, 0.62, 0.0))
            ov.text(q[0], q[1] - 40, "127.0.0.1", size=40, color=C_ACCENT, alpha=la, kind="mono", anchor="ms")
            ov.text(q[0], q[1] - 6, "localhost: this same machine", size=21, color=DIM, alpha=la, anchor="ms")
            for anchor, lx, name in ((LAP_PORT, -200, "client"), (LAP_PORT + (0.07, 0.03, 0.0), 200, "server")):
                qq = self.P(anchor)
                ov.callout(qq[:2], (qq[0] + lx, qq[1] + 110), name, C_ACCENT, la, size=21,
                           grow=ease_out(remap(t, at("a3", 0.15), at("a3", 0.35))))

    # the sequence diagram ------------------------------------------------------
    def diagram(self, t, flights, warp, x, y, w, lab0, lab1, px_ms, title, alpha, events=(), hl=None,
                names=(("Pi", "server", C_PI), ("laptop", "client", C_LAP)), reads=None, xl=None, xr=None):
        """A sequence diagram drawn as the packets fly: time runs down (lab time, to scale), each
        packet an arrow from its sender's line to its receiver's. Lost packets end in a cross."""
        ov = self.ov
        if alpha <= 0.003:
            return
        h_body = (lab1 - lab0) * 1000 * px_ms
        top = y + 132
        h = 132 + h_body + 30
        card(ov, x, y, w, h, alpha, title)
        xl = x + 70 if xl is None else x + xl
        xr = x + w - 70 if xr is None else x + xr
        for xx, (name, sub, col) in ((xl, names[0]), (xr, names[1])):
            ov.text(xx, y + 76, name, size=22, color=col, alpha=alpha, kind="semibold", anchor="ms")
            ov.text(xx, y + 98, sub, size=16, color=DIM, alpha=alpha, anchor="ms")
            ov.dashed((xx, top - 6), (xx, top + h_body + 8), 0x56637a, 1.6, alpha, dash=6, gap=6)

        def Y(tau):
            return top + (tau - lab0) * 1000 * px_ms

        X = {"pi": xl, "laptop": xr}
        for f in flights:
            t_s = warp(f.ts)
            if t < t_s:
                continue
            x0, y0 = X[f.src], Y(f.ts) + 30 * f.bundle
            x1 = X["laptop" if f.src == "pi" else "pi"]
            col = {"data": C_TCP, "ctrl": C_CTRL, "udp": C_UDP}.get(f.kind, TEXT)
            if f.note == "sent again":
                col = 0x9ff5e8
            hla = hl(f) if hl else 0.0
            if f.lost:
                y1 = Y(f.ts + BASE * 0.5) + 30 * f.bundle
                u = remap(t, t_s, f.t_lost())
                xe, ye = x0 + (x1 - x0) * 0.5 * u, y0 + (y1 - y0) * u
                ov.line([(x0, y0), (xe, ye)], col, 2.4, alpha)
                if u >= 1.0:
                    ov.line([(xe - 9, ye - 9), (xe + 9, ye + 9)], C_LOST, 3.4, alpha)
                    ov.line([(xe - 9, ye + 9), (xe + 9, ye - 9)], C_LOST, 3.4, alpha)
                    ov.text(xe + 14, ye, "lost", size=16, color=C_LOST, alpha=alpha, kind="semibold", anchor="lm")
            else:
                y1 = Y(f.ta) + 30 * f.bundle
                u = remap(t, t_s, warp(f.ta))
                xe, ye = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
                if hla > 0.003:
                    ov.line([(x0, y0), (x1, y1)], col, 9.0, alpha * 0.28 * hla)
                ov.arrow2d((x0, y0), (xe, ye), col, width=2.4, head=10 if u > 0.1 else 0.1, alpha=alpha)
            lab = f.label if f.note is None else f"{f.label} ({f.note})"
            if f.lost:
                la = alpha * smooth(remap(t, t_s + 0.05, t_s + 0.4))
                lx, ly, anc = x0 + (14 if x1 > x0 else -14), y0 - 10, "lm" if x1 > x0 else "rm"
            else:
                # along the arrow, packets sent together spread out; the label shows once the arrow is past it
                fr = 0.5 if f.bundle == 0 else 0.3 + 0.24 * f.bundle
                la = alpha * smooth(remap(u, fr - 0.1, fr + 0.1))
                lx, ly, anc = x0 + (x1 - x0) * fr, y0 + (y1 - y0) * fr - 11, "mm"
            if la > 0.003:
                tw = ov.text_width(lab, 16, "semibold")
                bx = lx - tw / 2 if anc == "mm" else lx if anc == "lm" else lx - tw
                ov.panel(bx - 6, ly - 11, tw + 12, 22, radius=6, fill=0x0d131e, alpha=0.88 * la)
                ov.text(lx, ly, lab, size=16, color=col, alpha=la, kind="semibold", anchor=anc)
        # what the programs call, on their own lines (pushed apart where they would overlap)
        last = {}
        for side, tau, text in sorted(events, key=lambda e: e[1]):
            yy = max(Y(max(tau, lab0 - 0.004)), last.get(side, -1e9) + 30)
            last[side] = yy
            ta_ = warp(tau)
            ea = alpha * smooth(remap(t, ta_, ta_ + 0.3))
            if ea <= 0.003:
                continue
            xx = X[side]
            tw = ov.text_width(text, 15, "semibold") + 20
            ov.panel(xx - tw / 2, yy - 13, tw, 26, radius=13, fill=0x243245, alpha=0.96 * ea)
            ov.text(xx, yy, text, size=15, color=TEXT, alpha=ea, kind="semibold", anchor="mm")
        # what the receiving program reads, beside its line
        if reads:
            for tau, data, col in reads:
                ta_ = warp(tau)
                ea = alpha * smooth(remap(t, ta_, ta_ + 0.3))
                if ea <= 0.003:
                    continue
                xx = X["laptop"] + 18
                yy = Y(tau)
                tw = ov.text_width(data, 17, "mono") + 22
                ov.panel(xx, yy - 14, tw, 28, radius=7, fill=0x0a2a26 if col == C_OK else 0x2a2320, alpha=0.95 * ea,
                         outline=col, outline_alpha=0.5)
                ov.text(xx + 11, yy, data, size=17, color=col, alpha=ea, kind="mono", anchor="lm")
        return (xl, xr, Y)

    def cs_hud(self, t):
        ov, rec = self.ov, self.rec
        a = envelope(t, TL.start("cs") + 0.3, TL.end("proto") - 0.2, 0.6, 0.6)
        if a <= 0.003:
            return
        # the packets' labels in the 3D view are enough before the diagram: the diagram is the record
        hl = None
        if TL.start("proto") <= t:
            def hl(f):
                hs = f.label in ("SYN", "SYN-ACK") or (f.label == "ack" and f.ts < 0.1 and f.src == "laptop"
                                                      and f.bundle == 0)
                acks = f.label == "ack" and not hs
                return (envelope(t, at("p2", 0.05), at("p2", 0.55), 0.3, 0.3) * hs
                        + envelope(t, at("p2", 0.55), at("p2", 1.0) + 0.3, 0.3, 0.3) * acks)
        self.diagram(t, rec["ex_tcp"], rec["ex_tcp_warp"], 1320, 64, 540, 0.046, 0.176, 4.0,
                     "TCP  ·  ONE QUESTION, ONE ANSWER", a, events=rec["ex_events"], hl=hl)
        # the roles, on the machines
        ra = a * envelope(t, at("c1", 0.35), TL.end("cs"), 0.5, 0.6)
        if ra > 0.003:
            q = self.P(np.array([PED[0], 0.30, PED[2] + 0.24]))
            ov.text(q[0], q[1], "server", size=26, color=C_PI, alpha=ra, kind="semibold", anchor="ms")
            ov.text(q[0], q[1] + 26, "waits on port 8080", size=18, color=DIM, alpha=ra, anchor="ms")
            ca = a * envelope(t, at("c2", 0.1), TL.end("cs"), 0.5, 0.6)
            q = self.P(np.array([DESK[0], DESK_H - 0.22, DESK[2] + 0.33]))
            ov.text(q[0], q[1], "client", size=26, color=C_LAP, alpha=ca, kind="semibold", anchor="ms")
            ov.text(q[0], q[1] + 26, "connects to 192.168.1.42 : 8080", size=18, color=DIM, alpha=ca, anchor="ms")
            aa = a * envelope(t, at("c3", 0.1), at("c3", 0.6), 0.4, 0.5)
            q = self.P(PI_PORT)
            ov.callout(q[:2], (q[0] - 230, q[1] - 110), "a new socket, for this client", C_ACCENT, aa, size=20,
                       grow=ease_out(remap(t, at("c3", 0.1), at("c3", 0.3))))

    def proto_hud(self, t):
        ov, rec = self.ov, self.rec
        a = envelope(t, at("p3", 0.2), TL.end("proto") - 0.2, 0.6, 0.6)
        if a > 0.003:
            self.diagram(t, rec["ex_udp"], rec["ex_udp_warp"], 70, 64, 460, 0.046, 0.176, 4.0,
                         "UDP  ·  THE SAME QUESTION", a, events=rec["ex_udp_events"])
        # TCP and UDP side by side, as the e-book's table has them
        ta = envelope(t, at("p4", 0.55), TL.end("proto") + 0.1, 0.5, 0.5)
        if ta > 0.003:
            rows = [("connection", "handshake first", "none: just send"),
                    ("delivery", "guaranteed", "may be lost"),
                    ("order", "kept", "may change"),
                    ("shape", "a stream of bytes", "separate datagrams")]
            x, y, w = 560, 250, 740
            ov.panel(x, y, w, 70 + 50 * len(rows), radius=16, alpha=0.9 * ta, outline=0x8aa0c0, outline_alpha=0.2)
            ov.text(x + 250, y + 36, "TCP", size=26, color=C_TCP, alpha=ta, kind="semibold", anchor="lm")
            ov.text(x + 500, y + 36, "UDP", size=26, color=C_UDP, alpha=ta, kind="semibold", anchor="lm")
            for j, (k, a_, b_) in enumerate(rows):
                ra = ta * smooth(remap(t, at("p4", 0.6 + 0.07 * j), at("p4", 0.7 + 0.07 * j)))
                yy = y + 90 + 50 * j
                ov.text(x + 30, yy, k, size=20, color=DIM, alpha=ra, kind="semibold", anchor="lm")
                ov.text(x + 250, yy, a_, size=21, color=TEXT, alpha=ra, anchor="lm")
                ov.text(x + 500, yy, b_, size=21, color=TEXT, alpha=ra, anchor="lm")

    def loss_hud(self, t):
        ov, rec = self.ov, self.rec
        a = envelope(t, TL.start("loss") + 0.3, TL.end("loss") - 0.1, 0.6, 0.6)
        if a <= 0.003:
            return
        # the bad link, named
        la = a * envelope(t, at("l1", 0.35), TL.end("loss"), 0.5, 0.6)
        q = self.P(CLOUD + (0.0, 0.42, 0.0))
        ov.text(q[0], q[1], "a bad link", size=24, color=0xffa39e, alpha=la, kind="semibold", anchor="ms")
        ov.text(q[0], q[1] + 26, "drops the 3rd, holds back the 5th", size=17, color=DIM, alpha=la, anchor="ms")
        names = (("Pi", "sends", C_PI), ("laptop", "reads", C_LAP))
        tcp_reads = [(tau, d, C_OK) for tau, d in rec["loss_tcp_reads"]]
        self.diagram(t, rec["loss_tcp"], rec["loss_tcp_warp"], 970, 64, 450, 0.030, 0.540, 1.12,
                     "TCP", a * smooth(remap(t, at("l1", 0.3), at("l1", 0.5))), names=names, reads=tcp_reads,
                     xl=54, xr=250)
        order = [d for _, d in rec["loss_udp_reads"]]
        udp_reads = []
        for tau, d in rec["loss_udp_reads"]:
            k = int(d.split()[-1])
            late = any(int(e.split()[-1]) > k for e in order[:order.index(d)])
            udp_reads.append((tau, d + ("  late" if late else ""), C_UDP if not late else 0xffa39e))
        ua = a * smooth(remap(t, cap0("l3") - 0.4, cap0("l3") + 0.2))
        self.diagram(t, rec["loss_udp"], rec["loss_udp_warp"], 1436, 64, 450, 0.030, 0.540, 1.12,
                     "UDP", ua, names=names, reads=udp_reads, xl=54, xr=250)
        if ua > 0.003:
            ma = ua * smooth(remap(t, at("l3", 0.3), at("l3", 0.45)))
            ov.text(1436 + 250 + 18, 64 + 104 + (0.2125 + 0.020 - 0.030) * 1000 * 1.12, "pose 3: never", size=17,
                    color=C_LOST, alpha=ma, kind="mono", anchor="lm")

    def stream_hud(self, t):
        ov, rec = self.ov, self.rec
        a = envelope(t, TL.start("stream") + 0.3, TL.end("stream") - 0.1, 0.6, 0.6)
        if a <= 0.003:
            return
        tau = tau_of(t)
        # the copies, named
        ga = a * envelope(t, T_GHOST, TL.end("stream"), 0.6, 0.6)
        ov.text(70, 90, "the arm", size=24, color=TEXT, alpha=ga, kind="semibold", anchor="ls")
        xx = 70 + ov.text_width("the arm", 24, "semibold") + 34
        for k, name, col in (("udp", "its UDP copy", C_UDP), ("tcp", "its TCP copy", C_TCP)):
            ka = ga * (0.3 + 0.7 * ghost_alpha(k, t))
            ov.text(xx, 90, name, size=24, color=col, alpha=ka, kind="semibold", anchor="ls")
            xx += ov.text_width(name, 24, "semibold") + 34
        ov.text(70, 124, "the copies are what the laptop has received, in slow motion", size=19, color=DIM, alpha=ga,
                anchor="ls")
        # how late each sample arrives, as it arrives
        pa = a * smooth(remap(t, T_GHOST + 0.4, T_GHOST + 1.2))
        if pa > 0.003:
            t_first = tau_of(T_GHOST)
            win = 3.2                                       # lab seconds shown
            x0 = max(t_first, tau - win)
            sent = rec["st_sent"]
            sel = (sent >= x0) & (sent <= tau)
            series = []
            for k, col, name in (("tcp", C_TCP, "TCP"), ("udp", C_UDP, "UDP")):     # UDP drawn on top
                arr = rec[f"st_{k}"]
                ok = sel & ~np.isnan(arr) & (arr <= tau)
                xs = sent[ok]
                ys = (arr[ok] - sent[ok]) * 1000
                series.append((xs, ys, col, name))
            lost = np.where(sel & np.isnan(rec["st_udp"]) & (sent + BASE <= tau))[0]
            ymax = 140.0
            X0, Y0, W, H = 1240, 64, 620, 330
            ov.plot(X0, Y0, W, H, series, (x0, x0 + win), (0.0, ymax), alpha=pa,
                    title="HOW LATE EACH SAMPLE ARRIVES", yticks=(), xticks=(), legend=True,
                    markers=[(sent[k], 4.0, C_LOST) for k in lost], width=2.6)
            # the link's own delay, and the scale's meaning, in words
            px, py, pw, ph = X0 + 70, Y0 + 52, W - 94, H - 52 - 46
            yb = py + ph * (1 - BASE * 1000 / ymax)
            ov.dashed((px, yb), (px + pw, yb), 0x9fb2cc, 1.4, pa * 0.8, dash=6, gap=6)
            ov.text(px - 10, yb, "on time", size=15, color=DIM, alpha=pa, anchor="rm")
            ov.text(px - 10, py + 6, "late", size=15, color=DIM, alpha=pa, anchor="rm")
            ov.circle(px + pw - 138, py + 4 + 44 + 9, 5.0, fill=C_LOST, alpha=pa)
            ov.text(px + pw - 118, py + 4 + 44 + 9, "lost (UDP)", size=15, color=TEXT, alpha=pa, anchor="lm")
            ov.text(px + pw, py + ph + 14, "time", size=15, color=DIM, alpha=pa, anchor="ra")

    def bytes_hud(self, t):
        ov = self.ov
        a = envelope(t, TL.start("bytes") + 0.1, TL.end("bytes") - 0.1, 0.6, 0.6)
        if a <= 0.003:
            return
        ov.panel(-20, -20, ov.W + 40, ov.H + 40, radius=0, fill=0x070a10, alpha=0.88 * a)
        cw, gap = 54, 8
        # the stream: a pipe from the sender's writes to the receiver's reads
        X0, X1, YP = 380, 1240, 260
        pa = a * smooth(remap(t, at("b1", 0.3), at("b1", 0.6)))
        ov.text(X0, YP - 70, "TCP: ONE STREAM OF BYTES", size=20, color=C_TCP, alpha=pa, kind="semibold", tracking=3)
        ov.outline(X0, YP - 44, X1 - X0, 88, 0x6b7a90, 0.7 * pa, width=2.0, radius=44)
        # the writes
        w1, w2 = at("b2", 0.08), at("b2", 0.16)
        for k, (tw, word) in enumerate(((w1, "ping"), (w2, "pong"))):
            wa = a * smooth(remap(t, tw - 0.2, tw + 0.2))
            ov.text(X0 - 30, YP - 20 + 44 * k, f'write("{word}")', size=22, color=TEXT, alpha=wa, kind="mono",
                    anchor="rm")
        # the bytes move right as one train and close up at the far end, where they wait to be read
        letters = list("pingpong")
        t_read = at("b2", 0.5)
        v = 4 * (cw + gap) / max(w2 - w1, 1e-3)          # the first word is clear of the entry when the second comes
        for j, ch in enumerate(letters):
            tw = w1 if j < 4 else w2
            start = X0 + 24 + (j % 4) * (cw + gap)
            end = X1 - 24 - (8 - j) * (cw + gap)
            xx = min(start + v * max(t - tw, 0.0), end)
            ca = a * smooth(remap(t, tw, tw + 0.25))
            if t >= t_read:                               # the read takes all of it
                u = smoother(remap(t, t_read, t_read + 0.7))
                xx = xx + (X1 + 80 + j * (cw + gap) - xx) * u
            if ca > 0.003:
                ov.panel(xx, YP - cw / 2, cw, cw, radius=8, fill=0x1d4d47, alpha=0.95 * ca, outline=C_TCP,
                         outline_alpha=0.5)
                ov.text(xx + cw / 2, YP, ch, size=28, color=TEXT, alpha=ca, kind="mono", anchor="mm")
        ra = a * smooth(remap(t, t_read - 0.3, t_read + 0.2))
        ov.text(X1 + 80, YP - 60, "one read()", size=22, color=TEXT, alpha=ra, kind="mono", anchor="ls")
        oa = a * smooth(remap(t, t_read + 0.8, t_read + 1.2))
        card(ov, X1 + 60, YP + 60, 420, 110, oa, "WHAT pingpong_server PRINTS")
        ov.text(X1 + 84, YP + 60 + 72, self.pingpong_out, size=22, color=C_OUT, alpha=oa, kind="mono", anchor="lm")
        # b3: the earlier read
        ea = a * envelope(t, at("b3", 0.05), TL.end("bytes"), 0.5, 0.5)
        if ea > 0.003:
            x, y = X0, 420
            card(ov, x, y, 620, 120, ea, "EARLIER, TCP AFTER THE LOST PACKET")
            reads = [d for _, d in self.rec["loss_tcp_reads"]]
            xx = x + 26
            for d in reads:
                w_ = ov.text_width(d, 20, "mono") + 22
                hi = len(d) > 6
                ov.panel(xx, y + 58, w_, 34, radius=7, fill=0x1d4d47 if hi else 0x1a2230, alpha=0.95 * ea,
                         outline=C_OK if hi else 0x6b7a90, outline_alpha=0.6)
                ov.text(xx + 11, y + 75, d, size=20, color=C_OK if hi else DIM, alpha=ea, kind="mono", anchor="lm")
                xx += w_ + 10
        # b4: the boundaries, marked by the program
        fa = a * envelope(t, at("b4", 0.02), TL.end("bytes"), 0.5, 0.5)
        if fa > 0.003:
            y = 630
            rows = [("a newline after each", list("ping") + ["\\n"] + list("pong") + ["\\n"], {4, 9}),
                    ("its length first", ["4"] + list("ping") + ["4"] + list("pong"), {0, 5})]
            for r, (name, cells, marks) in enumerate(rows):
                ra = fa * smooth(remap(t, at("b4", 0.05 + 0.25 * r), at("b4", 0.15 + 0.25 * r)))
                yy = y + 84 * r
                ov.text(X0 - 30, yy, name, size=21, color=DIM, alpha=ra, anchor="rm")
                for j, ch in enumerate(cells):
                    xx = X0 + j * (cw + gap)
                    mk = j in marks
                    ov.panel(xx, yy - cw / 2, cw, cw, radius=8, fill=0x3a2e14 if mk else 0x1d4d47, alpha=0.95 * ra,
                             outline=C_UDP if mk else C_TCP, outline_alpha=0.5)
                    ov.text(xx + cw / 2, yy, ch, size=24 if len(ch) == 1 else 20, color=C_UDP if mk else TEXT,
                            alpha=ra, kind="mono", anchor="mm")
            # UDP: two datagrams, two reads
            ua = fa * smooth(remap(t, at("b4", 0.62), at("b4", 0.75)))
            yy = y + 84 * 2 + 10
            ov.text(X0 - 30, yy, "UDP", size=21, color=C_UDP, alpha=ua, kind="semibold", anchor="rm")
            for k, word in enumerate(("ping", "pong")):
                xx = X0 + k * 5 * (cw + gap)
                ov.panel(xx - 8, yy - cw / 2 - 8, 4 * (cw + gap) + 8, cw + 16, radius=12, fill=0x2a2010,
                         alpha=0.9 * ua, outline=C_UDP, outline_alpha=0.6)
                for j, ch in enumerate(word):
                    ov.text(xx + j * (cw + gap) + cw / 2, yy, ch, size=24, color=TEXT, alpha=ua, kind="mono",
                            anchor="mm")
                ov.text(xx + 4 * (cw + gap) / 2, yy + cw / 2 + 26, "one datagram, one read", size=16, color=DIM,
                        alpha=ua, anchor="ma")

    def code_hud(self, t):
        ov = self.ov
        a = envelope(t, TL.start("code") + 0.1, TL.end("code") + 0.3, 0.6, 0.6)
        if a <= 0.003:
            return
        ov.panel(-20, -20, ov.W + 40, ov.H + 40, radius=0, fill=0x070a10, alpha=0.88 * a)
        # k1: the operating system's own interface, as the e-book shows it (Linux)
        pa = a * envelope(t, at("k1", 0.05), at("k2", 0.1), 0.6, 0.6)
        if pa > 0.003:
            lines = self.code["posix_echo_server.cpp"]
            size, lh = 16, 21
            cw = ov.text_width("0", size, "mono")
            w = max(len(l) for l in lines) * cw + 60
            card(ov, 70, 50, w, 76 + lh * len(lines), pa, "posix_echo_server.cpp  ·  THE OS's OWN API, LINUX ONLY")
            bad = {j for j, l in enumerate(lines) if any(s in l for s in ("reinterpret_cast", "htons", "arpa/inet",
                                                                           "unistd", "close(", "SO_REUSEADDR"))}
            code_block(ov, 100, 108, lines, "cpp", size, lh, pa,
                       hl=lambda j: envelope(t, at("k1", 0.5), at("k2", 0.1), 0.4, 0.4) if j in bad else 0.0,
                       reveal=lambda j: remap(t, at("k1", 0.08) + 0.05 * j, at("k1", 0.2) + 0.05 * j))
            wa = pa * smooth(remap(t, at("k1", 0.6), at("k1", 0.75)))
            card(ov, 70 + w + 40, 200, 600, 150, wa, "ON WINDOWS")
            for j, s in enumerate(("Winsock2: WSAStartup first,", "a SOCKET handle instead of an int,",
                                   "closesocket() instead of close()")):
                ov.text(70 + w + 66, 200 + 70 + 30 * j, s, size=20, color=TEXT, alpha=wa, anchor="lm")
        # k2, k3: the same with SimpleSocket, and what it prints
        sa = a * envelope(t, at("k2", 0.02), TL.end("code") + 0.3, 0.6, 0.6)
        if sa > 0.003:
            size, lh = 18, 25
            srv = self.code["echo_server.cpp"]
            cli = self.code["echo_client.cpp"]
            cw = ov.text_width("0", size, "mono")
            ws = max(len(l) for l in srv) * cw + 60
            card(ov, 70, 50, ws, 76 + lh * len(srv), sa, "echo_server.cpp  ·  SIMPLESOCKET")
            code_block(ov, 100, 108, srv, "cpp", size, lh, sa,
                       reveal=lambda j: remap(t, at("k2", 0.3) + 0.12 * j, at("k2", 0.36) + 0.12 * j))
            ca = a * envelope(t, at("k3", 0.0), TL.end("code") + 0.3, 0.6, 0.6)
            wc = max(len(l) for l in cli) * cw + 60
            xc = 1850 - wc
            card(ov, xc, 50, wc, 76 + lh * len(cli), ca, "echo_client.cpp  ·  SIMPLESOCKET")
            code_block(ov, xc + 30, 108, cli, "cpp", size, lh, ca,
                       reveal=lambda j: remap(t, at("k3", 0.02) + 0.09 * j, at("k3", 0.08) + 0.09 * j))
            # the two terminals: what the programs printed
            ta = a * envelope(t, at("k3", 0.55), TL.end("code") + 0.3, 0.5, 0.6)
            yT = 76 + lh * max(len(srv), len(cli)) + 90
            for k, (name, lines_, x) in enumerate((("server", self.echo_out["server"], 70),
                                                  ("client", self.echo_out["client"], xc))):
                la = ta * smooth(remap(t, at("k3", 0.55 + 0.2 * k), at("k3", 0.65 + 0.2 * k)))
                w_ = 560
                ov.panel(x, yT, w_, 110, radius=10, fill=0x05070b, alpha=0.95 * la, outline=0x6b7a90,
                         outline_alpha=0.5)
                ov.panel(x + 2, yT + 2, w_ - 4, 30, radius=8, fill=0x1a2233, alpha=0.95 * la)
                ov.text(x + 16, yT + 17, f"> echo_{name}", size=16, color=DIM, alpha=la, kind="mono", anchor="lm")
                for j, line in enumerate(lines_):
                    ov.text(x + 18, yT + 58 + 28 * j, line, size=21, color=C_OUT, alpha=la, kind="mono", anchor="lm")


# ── the stage ─────────────────────────────────────────────────────────────────
def screen_texture(battery=None):
    """The laptop's dashboard (rows bottom-first, as data_texture wants them)."""
    h, w = 200, 320
    img = np.zeros((h, w, 4), np.uint8)
    img[..., 3] = 255
    img[..., :3] = (14, 22, 36)
    img[:22, :, :3] = (28, 44, 68)
    img[6:16, 10:80, :3] = (80, 110, 150)
    # a panel with a trace
    img[40:120, 14:190, :3] = (20, 32, 50)
    xs = np.arange(20, 184)
    ys = (80 + 22 * np.sin(xs * 0.07) + 8 * np.sin(xs * 0.23)).astype(int)
    for x, y in zip(xs, ys):
        img[y - 1:y + 2, x, :3] = (77, 182, 172)
    # the battery
    img[40:120, 204:306, :3] = (20, 32, 50)
    img[62:98, 220:282, :3] = (150, 170, 200)
    img[66:94, 224:278, :3] = (20, 32, 50)
    img[72:88, 282:288, :3] = (150, 170, 200)
    if battery is not None:
        n = int(round(50 * battery))
        img[68:92, 226:226 + n, :3] = (129, 199, 132)
    else:
        for k in range(3):
            img[78:82, 240 + 10 * k:244 + 10 * k, :3] = (150, 170, 200)
    img[140:186, 14:306, :3] = (20, 32, 50)
    return tp.data_texture(np.ascontiguousarray(img[::-1]), True)


def box(parent, size, pos, color, rough=0.6, metal=0.0, emissive=None, ei=1.0, shadow=True):
    m = tp.Mesh(tp.BoxGeometry(*size), standard(color, roughness=rough, metalness=metal, emissive=emissive,
                                                emissive_intensity=ei))
    m.position.set(*pos)
    m.cast_shadow = shadow
    m.receive_shadow = True
    parent.add(m)
    return m


def build(width, height):
    st = Stage(width, height, renderer="gl", fog=(7.5, 18.0), shadow_extent=2.8, far=40.0)
    parts = {}

    # the arm, and its two copies on the laptop's side of the link
    root = tp.Group()
    root.position.set(ARM[0], -ARM[2], ARM[1])       # robot frame: world (x, y, z) -> (x, -z, y)
    st.zup.add(root)
    robot = tp.URDFLoader().load(data_file("urdf", "franka", "fr3.urdf"))
    robot.show_colliders(False)
    robot.traverse(lambda o: setattr(o, "cast_shadow", True))
    robot.set_end_effector("fr3_hand_tcp")
    robot.set_joint_values(full(Q_READY))
    root.add(robot)
    parts["robot"] = robot
    for key, col in (("ghost_udp", C_UDP), ("ghost_tcp", C_TCP)):
        g = tp.URDFLoader().load(data_file("urdf", "franka", "fr3.urdf"))
        g.show_colliders(False)
        mat = standard(col, roughness=0.4, emissive=col, emissive_intensity=0.55)
        mat.transparent = True
        mat.depth_write = False
        mat.opacity = 0.0

        def f(o, mat=mat):
            if type(o).__name__ == "Mesh" and o.visible:
                o.set_material(mat)
                o.cast_shadow = False
        g.traverse(f)
        g.visible = False
        root.add(g)
        parts[key] = (g, mat)

    # the Raspberry Pi on its pedestal, twice real size so it reads on screen
    set_ = tp.Group()
    st.scene.add(set_)
    box(set_, (0.46, PED_H, 0.46), (PED[0], PED_H / 2, PED[2]), 0x222833, rough=0.8)
    board = tp.Group()
    board.position.set(*PI_TOP)
    set_.add(board)
    box(board, (0.34, 0.012, 0.224), (0, 0.006, 0), 0x1c6b3a, rough=0.55)
    box(board, (0.056, 0.012, 0.056), (-0.02, 0.018, 0.0), 0xb8bec8, rough=0.3, metal=0.8)       # the SoC
    box(board, (0.05, 0.008, 0.034), (-0.02, 0.016, 0.07), 0x111317, rough=0.4)                 # memory
    box(board, (0.042, 0.03, 0.05), (0.145, 0.027, 0.07), 0xc9ced6, rough=0.35, metal=0.9)       # USB
    box(board, (0.042, 0.03, 0.05), (0.145, 0.027, 0.005), 0xc9ced6, rough=0.35, metal=0.9)      # USB
    box(board, (0.044, 0.028, 0.044), (0.148, 0.026, -0.06), 0xc9ced6, rough=0.35, metal=0.9)    # Ethernet
    box(board, (0.2, 0.014, 0.012), (-0.02, 0.019, -0.098), 0x15171b, rough=0.5)                  # GPIO header
    box(board, (0.2, 0.006, 0.006), (-0.02, 0.029, -0.098), 0xd4af37, rough=0.3, metal=1.0)
    parts["led"] = box(board, (0.01, 0.006, 0.01), (-0.14, 0.015, 0.09), 0x5ee27a, emissive=0x5ee27a, ei=2.5,
                       shadow=False)
    box(board, (0.01, 0.006, 0.01), (-0.125, 0.015, 0.09), 0xff4040, emissive=0xff4040, ei=2.5, shadow=False)
    # a cable from the Pi down to the arm's base
    cable = Tube3D(0x1a1d22, radius=0.012, parent=set_, emissive=0.0)
    cable.mat.emissive_intensity = 0.0
    cable.set_points(catmull([PI_TOP + (-0.17, 0.01, 0.02), PI_TOP + (-0.28, -0.1, 0.02), (PED[0] - 0.3, 0.02, 0.3),
                              (ARM[0] + 0.25, 0.02, 0.18), (ARM[0] + 0.1, 0.05, 0.08)], n=80))

    # the operator's desk and laptop
    for dx in (-0.5, 0.5):
        for dz in (-0.28, 0.28):
            box(set_, (0.04, DESK_H - 0.04, 0.04), (DESK[0] + dx, (DESK_H - 0.04) / 2, DESK[2] + dz), 0x2b313c)
    box(set_, (1.1, 0.04, 0.64), (DESK[0], DESK_H - 0.02, DESK[2]), 0x39414e, rough=0.7)
    lap = tp.Group()
    lap.position.set(*LAPTOP)
    set_.add(lap)
    box(lap, (0.36, 0.02, 0.25), (0, 0.01, 0), 0x3b4452, rough=0.4, metal=0.6)
    box(lap, (0.3, 0.002, 0.1), (0, 0.021, 0.035), 0x20242c, rough=0.8)
    hinge = tp.Group()
    hinge.position.set(0, 0.02, -0.125)
    hinge.rotation.x = -0.22
    lap.add(hinge)
    box(hinge, (0.36, 0.24, 0.012), (0, 0.12, 0.0), 0x3b4452, rough=0.4, metal=0.6)
    sm = tp.MeshBasicMaterial()
    sm.tone_mapped = False
    parts["screen_before"] = screen_texture(None)
    parts["screen_after"] = screen_texture(0.82)
    sm.map = parts["screen_before"]
    screen = tp.Mesh(tp.PlaneGeometry(0.33, 0.21), sm)
    screen.position.set(0, 0.125, 0.0065)
    hinge.add(screen)
    parts["screen"] = screen

    # the network: a cloud the packets cross
    cloud = tp.Group()
    cloud.position.set(*CLOUD)
    st.scene.add(cloud)
    cm = standard(0xd9e1ee, roughness=0.95, emissive=0x1a2233, emissive_intensity=0.6)
    for (x, y, z, r) in ((0, 0, 0, 0.26), (-0.26, -0.06, 0.02, 0.19), (0.27, -0.05, -0.02, 0.2),
                         (-0.12, 0.13, -0.05, 0.18), (0.13, 0.12, 0.06, 0.17), (0.0, -0.1, 0.12, 0.17),
                         (0.4, -0.1, 0.05, 0.12), (-0.42, -0.1, -0.03, 0.12)):
        s = tp.Mesh(tp.SphereGeometry(r, 36, 20), cm)
        s.position.set(x, y, z)
        s.cast_shadow = False
        cloud.add(s)
    parts["cloud"], parts["cloud_mat"] = cloud, cm
    link = Tube3D(0x8fb4d8, radius=0.006, parent=st.scene, emissive=0.8)
    link.set_points(LINK.P[::6], opacity=0.3)
    link.mat.transparent = True
    link.mat.depth_write = False
    parts["link"], parts["link_mat"] = link.mesh, link.mat

    # sockets: rings at the two ports (and a second one on each side when needed)
    def ring(pos, col, normal):
        r = Ring3D(col, radius=0.045, tube=0.006, parent=st.scene, emissive=1.4)
        r.mesh.position.set(*pos)
        r.mesh.quaternion.set(*_quat_z_to(normal))
        return r
    parts["ring_pi"] = ring(PI_PORT + (0.012, 0.0, 0.02), C_ACCENT, (0.3, 0.2, 1))
    parts["ring_pi2"] = ring(PI_PORT + (0.02, 0.0, 0.09), C_TCP, (0.3, 0.2, 1))
    parts["ring_lap"] = ring(LAP_PORT + (0.0, 0.0, 0.02), C_ACCENT, (-0.3, 0.2, 1))
    parts["ring_lap2"] = ring(LAP_PORT + (0.07, 0.03, 0.02), C_ACCENT, (-0.3, 0.2, 1))

    # packets and the flashes of lost ones, pooled
    parts["pk"] = []
    for _ in range(48):
        mat = standard(C_TCP, roughness=0.3, emissive=C_TCP, emissive_intensity=0.75)
        m = tp.Mesh(tp.BoxGeometry(0.05, 0.085, 0.05), mat)
        m.cast_shadow = False
        m.visible = False
        st.scene.add(m)
        parts["pk"].append((m, mat))
    parts["burst"] = []
    for _ in range(4):
        mat = tp.MeshBasicMaterial()
        mat.color = C_LOST
        mat.transparent = True
        mat.depth_write = False
        mat.blending = tp.Blending.Additive
        m = tp.Mesh(tp.SphereGeometry(1.0, 32, 16), mat)
        m.visible = False
        st.scene.add(m)
        parts["burst"].append((m, mat))
    return st, parts


def _quat_z_to(d):
    """Quaternion (x, y, z, w) rotating +Z onto the direction d (a ring faces along its axis)."""
    z = np.array([0.0, 0.0, 1.0])
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    c = float(np.dot(z, d))
    if c < -0.999999:
        return (1.0, 0.0, 0.0, 0.0)
    axis = np.cross(z, d)
    s = math.sqrt((1.0 + c) * 2.0)
    return (axis[0] / s, axis[1] / s, axis[2] / s, s / 2.0)


def setup(width, height):
    t0 = time.time()
    st, parts = build(width, height)
    rec = choreograph()
    m = rec["meta"]
    print(f"[exchange] TCP {m['tcp_packets']} packets, UDP {m['udp_packets']} (one question, one answer)")
    print(f"[loss] TCP reads {[d for _, d in rec['loss_tcp_reads']]}; UDP receives {[d for _, d in rec['loss_udp_reads']]}")
    print(f"[stream] UDP lost {m['stream_lost_udp']} of {m['stream_n']}; TCP latency median {m['lat_tcp_p50']:.1f} ms, "
          f"max {m['lat_tcp_max']:.1f} ms; UDP max {m['lat_udp_max']:.1f} ms")
    ov = Hud(1920, 1080, math_cache=os.path.join(_HERE, "sockets.math.json"))
    painter = Painter(st, parts, rec, ov)
    print(f"[setup] {time.time() - t0:.1f}s, film {TL.duration:.1f}s")

    def render(t):
        painter.set3d(t)
        ov.begin()
        painter.draw2d(t)
        ov.fade(fade_in_out(t, TL.duration))
        ov.end()
        return st.frame(t, hud=ov)
    return render, painter.captions


def measure_speech(voice="af_heart", cache=os.path.join("lesson_out", "voice_cache")):
    """Speak every line and print how long each takes: the SPEECH table above."""
    narr = lesson.Narration(voice, cache_dir=cache)
    out = {}
    for k, text in CAPTION_TEXT.items():
        out[k] = round(len(narr.clip(text)) / lesson.Narration.RATE, 2)
        print(f"{k}: {out[k]:5.2f} s  {lesson.spoken(text)}", flush=True)
    print("SPEECH =", out)


if __name__ == "__main__":
    if "--speech" in sys.argv:
        i = sys.argv.index("--speech")
        measure_speech(cache=sys.argv[i + 1] if len(sys.argv) > i + 1 else os.path.join("lesson_out", "voice_cache"))
    else:
        run("sockets", TL.duration, setup, fps=FPS)
