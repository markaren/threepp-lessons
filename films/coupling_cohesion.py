"""Coupling and cohesion.  Why some programs are easy to change.  A little over two minutes.

    python coupling_cohesion.py                               # the film (1080p60), lesson_out/coupling_cohesion.mp4
    python coupling_cohesion.py --stills 30,62,95             # individual frames
    python coupling_cohesion.py --sheet                       # contact sheet, one frame per 3 s
    python coupling_cohesion.py --preview --out preview.mp4   # 960x540 @ 30 fps

A lecture film for AIS1003 (object-oriented programming in C++). A level crossing stands at the
back of the stage: a sensor, a controller, a gate and the lights, and a train that keeps passing.
In front of it lies the program that runs it, taken apart. Every class is a crate; on it lie its
functions (slabs) and the data it keeps (a drum). A colour is a job: sensing, deciding, moving
the gate, switching the lights. A thread runs from a function to each thing it uses.

The program is there twice. programs/coupling/tangled.cpp works, but its functions do several
jobs each (striped slabs) and reach into the data of other classes (threads from crate to
crate). The sensor is replaced by another model, which keeps different data: the threads that
reached for the old data snap, and the build breaks in the other classes. Then the pieces sort
themselves by job, the data goes under glass, and what is left is programs/coupling/tidy.cpp,
where the same replacement touches nothing outside the sensor.

What is on screen was checked against the two programs:

* the crates, slabs, drums and threads are read out of the two sources (`read_program`): a
  slab per member function, a drum per data member, a thread from a function to every data
  member it names and every member function it calls. main(), which only creates the objects
  and calls them in a loop, is not drawn;
* a slab's colours follow one rule: the job of each data member the function names, and green
  where it has an `if`. Which tidy function each stripe of a tangled function flies to (`SPLIT`)
  is the film's own reading, checked to keep its colour;
* the functions that light up red are those that still name the data the new sensor no longer
  has, and their lines are the lines MSVC's errors name (`BUILD_ERRORS`, recorded);
* the code in the cards is read out of the sources between their `// [name]` markers, and the
  terminal's lines are what the programs printed (`PRINTED`: tangled, tidy and tidy with the new
  sensor print the same). When their builds are found they are run again and compared, and a
  compiler on the PATH is asked again which lines break;
* the crossing's gate and lights do what `simulate` computes, a Python copy of tidy.cpp's four
  classes, call for call, whose lines are compared with the programs' own. The train, the radar
  beam and the lit rails are the film's: the programs have no hardware.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lesson  # noqa: E402
from lesson import (DIM, TEXT, Hud, OrbitCamera, Stage, card, clamp01, ease_out, ease_out_back,  # noqa: E402
                    envelope, fade_in_out, remap, run, smooth, standard, tp)
from lesson import VOICE_LEAD  # noqa: E402
from threepp.lesson.scene import disc_texture  # noqa: E402

FPS = 60
SOURCES = os.path.join(lesson.PROGRAMS, "coupling")

C_ACCENT = 0x4cc9f0
C_OUT = 0xa6e3a1             # what a program prints
C_ERR = 0xff5d73             # what no longer compiles
C_GOOD = 0xbff3d2
C_THREAD = 0xfff1d6          # a function reaching for something in another class
JOBS = ("sense", "decide", "gate", "lights")
JOB_COLOUR = {"sense": 0x5b9dff, "decide": 0x5ee27a, "gate": 0xffb347, "lights": 0xb983ff}
JOB_WORD = {"sense": "sensing", "decide": "deciding", "gate": "the gate", "lights": "the lights"}
DATA_JOB = {"distance": "sense", "occupied": "sense", "angle": "gate", "lit": "lights"}   # the job a data member serves
CLASS_JOB = {"Sensor": "sense", "Gate": "gate", "Lights": "lights", "Controller": "decide"}  # what a name promises

CPP_KEYWORDS = lesson.KEYWORDS["cpp"] | {"class", "struct", "public", "private", "void", "bool", "if", "else"}
WORDS = {"C++": "C plus plus"}

# What the programs printed (MSVC 14.44 and g++ 13.3, 2026-10-13): lesson_coupling_tangled,
# lesson_coupling_tidy and lesson_coupling_tidy_new_sensor print the same sixteen lines, one per tick.
PRINTED = (["train far   gate open    lights off"] * 3 + ["train near  gate closed  lights on"] * 7
           + ["train far   gate closed  lights on"] * 2 + ["train far   gate open    lights off"] * 4)
# And what MSVC said to tangled.cpp built with NEW_SENSOR: (line, message), the notes left out. g++ names
# the same two lines.
BUILD_ERRORS = [(70, "error C2039: 'distance': is not a member of 'Sensor'"),
                (82, "error C2039: 'distance': is not a member of 'Sensor'")]

# ── the script ────────────────────────────────────────────────────────────────
# The narration sets the pace: each caption lasts as long as its spoken line (Kokoro, af_heart,
# measured in coupling_cohesion.speech.json) plus the voice's lead-in and tail and a small margin.
CAPTION_TEXT = {
    "title": "Coupling and cohesion. Why some programs are easy to change, and others fight back.",
    "a0": "A level crossing. A sensor spots the train, a controller decides, the gate comes down, and the lights "
          "flash. Four jobs.",
    "a1": "This program runs it. Here it is, taken apart: its classes, their functions, and the data they keep. "
          "Each colour is one of the jobs.",
    "a2": "Look at one function. It reads the sensor, decides, moves the gate, and switches the lights. "
          "Cohesion is how well the things in one class belong together. Here, it is low.",
    "a3": "Now the threads. Each one is a function reaching into the data of another class. "
          "Coupling is how much one class has to know about another. Here, it is high.",
    "b1": "The program works. Then the sensor is replaced by another model, which keeps different data.",
    "b2": "Every function that reached for the old data is left holding nothing. The build breaks, in every "
          "other class.",
    "d1": "So, tidy up. First: one job, one class. Each piece moves to where its job is done, and the deciding "
          "gets a class of its own.",
    "d2": "Second: the data goes under glass. It is private, and each class offers a few functions instead: "
          "its interface.",
    "d3": "Now the controller is the only class that knows the others, and all it knows is those functions.",
    "e1": "Replace the sensor again. The old one lifts out, the new one drops in, and it answers the same "
          "question as before.",
    "e2": "Nothing else had to change. The program builds, and the crossing works.",
    "z1": "High cohesion: each class does one job. Low coupling: classes meet only at a small interface. "
          "Then a change stays where it is made.",
}
SPEECH = lesson.Speech(CAPTION_TEXT, os.path.join(_HERE, "coupling_cohesion.speech.json"), words=WORDS,
                       voice_only={"title"})
PLAN = [("open", 0.4, ["title"], 1.0),
        ("crossing", 0.3, ["a0"], 0.4),
        ("pieces", 0.3, ["a1", "a2", "a3"], 0.7),
        ("change", 0.4, ["b1", "b2"], 1.2),
        ("tidy", 0.5, ["d1", "d2", "d3"], 0.8),
        ("again", 0.4, ["e1", "e2"], 0.6),
        ("end", 0.3, ["z1"], 1.2),
        ("outro", 0.0, [], 5.5)]
TL, CAP = SPEECH.layout(PLAN, slack=0.7)

TITLE = ("A THREEPP LESSON  ·  C++ BASICS", "Coupling and cohesion", "Why some programs are easy to change")
SUMMARY = [(r"$\mathrm{cohesion}$", "Inside a class: everything serves one job."),
           (r"$\mathrm{coupling}$", "Between classes: a small interface, and nothing more."),
           (r"$\mathrm{change}$", "With both, it stays where it is made.")]
FOOTER = "The two programs in this film are programs/coupling/tangled.cpp and tidy.cpp"


def cap0(k):
    return CAP[k][0]


def cap1(k):
    return CAP[k][1]


def say(k, frac):
    """About when the word a fraction `frac` of the way through line k is heard."""
    return CAP[k][0] + VOICE_LEAD + frac * SPEECH.seconds(k)


# ── the two programs, read ────────────────────────────────────────────────────
_TYPES = r"(?:[\w:&<>]+\s+)+"
_IN_CLASS = re.compile(r"\s+" + _TYPES + r"(\w+)\(([^()]*)\)\s*(?:const\s*)?\{")
_OUT_OF_CLASS = re.compile(_TYPES + r"(\w+)::(\w+)\(([^()]*)\)\s*(?:const\s*)?\{")
_FREE = re.compile(_TYPES + r"(\w+)\(([^()]*)\)\s*\{")
_DATA = re.compile(r"\s+([\w:&<>]+(?:\s+[\w:&<>]+)*?)\s+(\w+)\s*(?:=[^;]+)?;")


class Program:
    """One source as the film draws it: `classes` {name: {"data": [...], "functions": [...]}} in
    source order, `data` {member: class}, `funcs` {name: {cls, first, last, body, touches, calls,
    decides}} (line numbers 1-based, as a compiler prints them), and `lines`, the source."""

    def __init__(self, file, defines=()):
        self.file = file
        with open(os.path.join(SOURCES, file), encoding="utf-8") as f:
            self.lines = f.read().split("\n")
        kept = [(i, self.lines[i]) for i in lesson.preprocess(self.lines, 0, tuple(defines))]
        self.classes, self.data, self.funcs = {}, {}, {}
        cls, k = None, 0
        while k < len(kept):
            i, line = kept[k]
            k += 1
            m = re.match(r"(?:struct|class)\s+(\w+)\s*\{", line)
            if m:
                cls = m.group(1)
                self.classes[cls] = {"data": [], "functions": []}
                continue
            if cls and line.startswith("};"):
                cls = None
                continue
            m = (_IN_CLASS.match(line) if cls else None) or _OUT_OF_CLASS.match(line) or \
                (None if cls else _FREE.match(line))
            if m:
                owner, name = (m.group(1), m.group(2)) if m.re is _OUT_OF_CLASS else (cls, m.group(1))
                depth, body, j = 0, [], k - 1
                while True:                      # the body: to the brace that closes the first one
                    text = kept[j][1].split("//")[0]
                    body.append(text)
                    depth += text.count("{") - text.count("}")
                    if depth <= 0:
                        break
                    j += 1
                if name in self.funcs:
                    raise ValueError(f"{file}: two functions named {name}; the film tells them apart by name")
                self.funcs[name] = {"name": name, "cls": owner, "first": i + 1, "last": kept[j][0] + 1,
                                    "body": "\n".join(body).split("{", 1)[1]}
                if owner:
                    self.classes[owner]["functions"].append(name)
                k = j + 1
                continue
            m = _DATA.match(line) if cls and "(" not in line else None
            if m and not m.group(1).endswith("&"):       # a reference to another object is a connection, not data
                if m.group(2) in self.data:
                    raise ValueError(f"{file}: two data members named {m.group(2)}")
                self.data[m.group(2)] = cls
                self.classes[cls]["data"].append(m.group(2))
        for f in self.funcs.values():
            f["touches"] = [d for d in self.data if re.search(rf"\b{d}\b", f["body"])]
            f["calls"] = [g for g, o in self.funcs.items() if o["cls"] and g != f["name"]
                          and re.search(rf"\.{g}\(", f["body"])]
            f["decides"] = bool(re.search(r"\bif\s*\(", f["body"]))

    def members(self):
        """The member functions, in source order of their classes."""
        return [self.funcs[n] for c in self.classes.values() for n in c["functions"]]

    def jobs(self, name):
        """The jobs a function does, by the film's one rule: the job of each data member it
        names, and deciding where it has an `if`."""
        f = self.funcs[name]
        found = {DATA_JOB[d.rstrip("_")] for d in f["touches"]} | ({"decide"} if f["decides"] else set())
        return [j for j in JOBS if j in found]

    def line_jobs(self, line):
        """The same rule for one line of the source."""
        found = {DATA_JOB[d.rstrip("_")] for d in self.data if re.search(rf"\b{d}\b", line)}
        if re.search(r"\bif\s*\(", line):
            found.add("decide")
        return [j for j in JOBS if j in found]

    def region(self, name):
        """The lines between `// [name]` and the next `// [end]`, without their common indent."""
        out, on = [], False
        for line in self.lines:
            s = line.strip()
            if s == f"// [{name}]":
                on = True
            elif on and s == "// [end]":
                break
            elif on:
                out.append(line)
        if not out:
            raise ValueError(f"{self.file} has no region [{name}]")
        ind = min(lesson.indent(l) for l in out if l.strip())
        return [l[ind:] for l in out]


TANGLED, TIDY = Program("tangled.cpp"), Program("tidy.cpp")
TANGLED_NEW, TIDY_NEW = Program("tangled.cpp", ("NEW_SENSOR",)), Program("tidy.cpp", ("NEW_SENSOR",))

# Which tidy function each stripe of a tangled function flies to. The film's own reading of the
# two programs; `check_split` holds it to the colours the rule gives.
SPLIT = {"read": [("sense", "read"), ("decide", "update"), ("lights", "on")],
         "move": [("sense", "trainNear"), ("decide", "update"), ("gate", "lower"), ("gate", "raise"),
                  ("lights", "off")],
         "print": [("sense", "trainNear"), ("gate", "isUp"), ("lights", "isOn")]}


def check_split():
    for f in TANGLED.members():
        if {j for j, _ in SPLIT[f["name"]]} != set(TANGLED.jobs(f["name"])):
            raise RuntimeError(f"tangled {f['name']}() does {TANGLED.jobs(f['name'])}; the film splits it otherwise")
    for f in TIDY.members():
        if len(TIDY.jobs(f["name"])) != 1:
            raise RuntimeError(f"tidy {f['name']}() does {TIDY.jobs(f['name'])}: the film shows it in one colour")
    for pairs in SPLIT.values():
        for job, target in pairs:
            if TIDY.jobs(target) != [job]:
                raise RuntimeError(f"a {job} stripe flies to {target}(), which is {TIDY.jobs(target)}")
    if {t for pairs in SPLIT.values() for _, t in pairs} != {f["name"] for f in TIDY.members()}:
        raise RuntimeError("the stripes do not land on every tidy function")
    for prog in (TANGLED, TIDY, TANGLED_NEW, TIDY_NEW):
        if prog.funcs["main"]["touches"]:
            raise RuntimeError(f"{prog.file}: main() names data; the film leaves main out of the picture")


def broken_by_new_sensor(old, new):
    """{function: [line numbers]}: where the program built with NEW_SENSOR still names a data
    member the new sensor no longer has."""
    gone = [d for d in old.data if d not in new.data]
    out = {}
    for f in new.funcs.values():
        hits = [n for n in range(f["first"], f["last"] + 1)
                if any(re.search(rf"\b{d}\b", new.lines[n - 1].split("//")[0]) for d in gone)]
        if hits:
            out[f["name"]] = hits
    return out


check_split()
BROKEN = broken_by_new_sensor(TANGLED, TANGLED_NEW)                     # {"move": [70], "print": [82]}
if sorted(n for hits in BROKEN.values() for n in hits) != [n for n, _ in BUILD_ERRORS]:
    raise RuntimeError(f"the film finds the old data named on lines {BROKEN}; the recorded errors are {BUILD_ERRORS}")
if broken_by_new_sensor(TIDY, TIDY_NEW):
    raise RuntimeError("tidy.cpp with NEW_SENSOR still names the old data somewhere")
if TIDY.classes["Sensor"]["functions"] != TIDY_NEW.classes["Sensor"]["functions"]:
    raise RuntimeError("the new Sensor of tidy.cpp does not offer the functions the old one does")

MOVE_CODE = TANGLED.region("move")
SENSOR_CODE, NEW_SENSOR_CODE = TIDY.region("sensor"), TIDY.region("new_sensor")
UPDATE_CODE = TIDY.region("update")


# ── the crossing: tidy.cpp's four classes, call for call ──────────────────────
def constants(prog):
    src = "\n".join(prog.lines)
    c = {k: int(v) for k, v in re.findall(r"^const int (\w+) = (-?\d+);", src, re.M)}
    c["ARRIVES"] = int(re.search(r"return \(tick - (\d+)\) \* SPEED;", src).group(1))
    return c


K = constants(TIDY)
if constants(TANGLED) != K:
    raise RuntimeError("tangled.cpp and tidy.cpp no longer describe the same crossing")
TICKS = K["TICKS"]


def train_at(tick):
    return (tick - K["ARRIVES"]) * K["SPEED"]


def simulate():
    """One pass of the train: per tick, (the train is near, the gate's angle, the lights are lit,
    the line main prints)."""
    class Sensor:
        distance_ = K["FAR_AWAY"]

        def read(self, tick):
            self.distance_ = abs(train_at(tick))

        def trainNear(self):
            return self.distance_ < K["SAFE_DISTANCE"]

    class Gate:
        angle_ = K["UP"]

        def lower(self):
            self.angle_ = max(K["DOWN"], self.angle_ - K["STEP"])

        def raise_(self):
            self.angle_ = min(K["UP"], self.angle_ + K["STEP"])

        def isUp(self):
            return self.angle_ == K["UP"]

    class Lights:
        lit_ = False

        def on(self):
            self.lit_ = True

        def off(self):
            self.lit_ = False

        def isOn(self):
            return self.lit_

    sensor, gate, lights, out = Sensor(), Gate(), Lights(), []
    for tick in range(TICKS):
        sensor.read(tick)
        if sensor.trainNear():           # Controller::update
            lights.on()
            gate.lower()
        else:
            gate.raise_()
            if gate.isUp():
                lights.off()
        out.append((sensor.trainNear(), gate.angle_, lights.isOn(),
                    ("train near  " if sensor.trainNear() else "train far   ")
                    + ("gate open    " if gate.isUp() else "gate closed  ")
                    + ("lights on" if lights.isOn() else "lights off")))
    return out


SIM = simulate()
if [s[3] for s in SIM] != PRINTED:
    raise RuntimeError("the film's copy of the crossing does not print what the programs printed")


def check_programs():
    """Run the programs' builds, when they are found, and ask a compiler on the PATH which lines
    of tangled.cpp break with the new sensor; compare both with the record."""
    ran = []
    for name in ("lesson_coupling_tangled", "lesson_coupling_tidy", "lesson_coupling_tidy_new_sensor"):
        try:
            exe = lesson.capture_exe(name)
        except FileNotFoundError:
            continue
        out = subprocess.run([exe], capture_output=True, cwd=os.path.dirname(exe)).stdout.decode().splitlines()
        if out != PRINTED:
            raise RuntimeError(f"{exe} prints {out}; the film shows {PRINTED}")
        ran.append(name)
    print(f"[programs] {', '.join(ran)} print what the terminal shows" if ran else
          "[programs] no build of programs/coupling found here: the terminal shows the recorded output")
    cxx = next((c for c in ("cl", "g++", "clang++") if shutil.which(c)), None)
    if cxx is None:
        print("[build] no compiler on the PATH: the build errors are the recorded ones")
        return
    with tempfile.TemporaryDirectory() as tmp:
        def errors(file):
            src = os.path.join(SOURCES, file)
            cmd = ([cxx, "/nologo", "/EHsc", "/std:c++20", "/Zs", "/DNEW_SENSOR", src] if cxx == "cl" else
                   [cxx, "-std=c++20", "-fsyntax-only", "-DNEW_SENSOR", src])
            r = subprocess.run(cmd, capture_output=True, cwd=tmp)
            text = (r.stdout + r.stderr).decode(errors="replace")
            return sorted({int(m.group(1)) for line in text.splitlines() if "error" in line
                           for m in [re.search(re.escape(file) + r"[(:](\d+)", line)] if m})
        got, want = errors("tangled.cpp"), [n for n, _ in BUILD_ERRORS]
        if got != want:
            raise RuntimeError(f"{cxx} finds errors on lines {got} of tangled.cpp with NEW_SENSOR; the film shows {want}")
        if errors("tidy.cpp"):
            raise RuntimeError(f"{cxx} finds errors in tidy.cpp with NEW_SENSOR")
    print(f"[build] {cxx}: tangled.cpp with the new sensor breaks on lines {want}; tidy.cpp builds")


# ── the stage ─────────────────────────────────────────────────────────────────
ZT, CX = -2.4, 1.5                       # the track's z, and the crossing's x
MS = 0.0095                              # stage metres per metre of the program's world
TICK_S = 0.7                             # seconds of film per tick of the program
TRAIN_LEN = 1.78
ORIGIN = np.array([1.4, 0.0, 0.75])      # the middle of the crates

# crate: where it lies and how large, (x, z, width, depth) from ORIGIN, tangled and tidy
CRATES = {"Sensor": ((-1.05, 0.40, 0.95, 0.86), (-1.33, -0.45, 1.15, 0.86)),
          "Gate": ((1.05, 0.40, 0.95, 0.86), (1.33, -0.45, 1.15, 0.86)),
          "Lights": ((0.0, -0.80, 0.95, 0.86), (0.0, -0.45, 1.15, 0.86)),
          "Controller": (None, (0.0, 0.88, 0.80, 0.50))}
Y_TOP = 0.04                             # the top of a crate's plate
BLOCK_H = 0.07
Z_F, Z_D = 0.06, -0.24                   # on a crate: the row of functions in front, the data behind
Z_LONE = -0.07                           # a function on a crate that keeps no data
SEG = 0.15                               # one stripe of a tangled function
ROW = {1: (0.0, 0.46), 2: (0.47, 0.40), 3: (0.37, 0.31)}   # tidy functions in a row: spacing and width
LIFT_H, LIFT_S, LAND_S = 3.0, 0.9, 0.9   # a crate leaving and arriving


def bump(u, length=0.5):
    """One smooth pulse, 0 -> 1 -> 0 over `length` seconds."""
    return math.sin(math.pi * u / length) ** 2 if 0.0 < u < length else 0.0


def mix(c0, c1, u):
    """Two 0xRRGGBB colours blended, u = 0..1."""
    a = np.array([(c0 >> 16) & 255, (c0 >> 8) & 255, c0 & 255], float)
    b = np.array([(c1 >> 16) & 255, (c1 >> 8) & 255, c1 & 255], float)
    r, g, bl = (int(round(v)) for v in a + (b - a) * min(max(u, 0.0), 1.0))
    return (r << 16) | (g << 8) | bl


def fade_mat(m, o):
    o = clamp01(o)
    m.transparent = o < 0.999
    m.opacity = o
    m.depth_write = o >= 0.999


def box(w, h, d, mat, at=(0.0, 0.0, 0.0), parent=None, shadow=True):
    m = tp.Mesh(tp.BoxGeometry(w, h, d), mat)
    m.position.set(*at)
    m.cast_shadow = shadow
    m.receive_shadow = True
    if parent is not None:
        parent.add(m)
    return m


def glow(color, opacity=1.0):
    """An unlit, additive material: a beam, a halo."""
    m = tp.MeshBasicMaterial()
    m.color = color
    m.transparent = True
    m.blending = tp.Blending.Additive
    m.depth_write = False
    m.opacity = opacity
    return m


# ── when things happen, all from the captions ────────────────────────────────
T_RUN1 = cap0("a0") + 0.9                                    # tick 0 of the pass the opening shows
T_PARTS = [say("a0", f) for f in (0.21, 0.41, 0.55, 0.69)]   # sensor, controller, gate, lights, as each is named
T_CRATES = say("a1", 0.24)                                   # the crates
T_BLOCKS = say("a1", 0.46)                                   # their functions
T_DRUMS = say("a1", 0.58)                                    # and their data
T_LEGEND = say("a1", 0.75)                                   # "each colour"
T_JOB = dict(zip(("sense", "decide", "gate", "lights"), (say("a2", f) for f in (0.16, 0.26, 0.32, 0.41))))
T_COHESION, T_LOW = say("a2", 0.52), say("a2", 0.91)
T_OWN = T_DRUMS + 0.7                                        # each function's thread to its own data
T_THREAD = say("a3", 0.12)                                   # then the threads into other classes, one by one
T_COUPLING, T_HIGH = say("a3", 0.48), say("a3", 0.91)
T_LIFT = say("b1", 0.36)                                     # the old sensor leaves
T_LAND = T_LIFT + LIFT_S + 0.5                               # the new one arrives
T_NOTHING = say("b2", 0.36)                                  # "left holding nothing"
T_BUILD1 = cap0("b2") + 0.3                                  # the build
T_ERRORS = say("b2", 0.60)                                   # "the build breaks"
T_EVERY = say("b2", 0.76)                                    # "in every other class"
T_REW = cap0("d1") - 0.5                                     # back to the old sensor, before tidying up
T_SORT = say("d1", 0.40)                                     # every piece to its job's crate
T_CONTROLLER = say("d1", 0.68)                               # a crate for the deciding
T_SORTED = T_CONTROLLER + 2.3
T_GLASS = say("d2", 0.12)                                    # the data goes under glass
T_PRIVATE, T_PUBLIC = say("d2", 0.34), say("d2", 0.56)
T_CALL = say("d3", 0.10)                                     # the controller's threads, one by one
T_LOOSE = say("d3", 0.88)
T_LIFT2 = say("e1", 0.30)
T_LAND2 = say("e1", 0.47)
T_PLUG = T_LAND2 + LAND_S - 0.15                             # the controller's thread finds the same function
T_ASK = say("e1", 0.66)                                      # and asks it the same question
T_BUILD2 = T_PLUG + 0.5
T_RUN3 = cap0("e2") - 0.6                                    # tick 0 of the pass the ending shows
T_ONE_JOB, T_MEET, T_STAYS = say("z1", 0.14), say("z1", 0.45), say("z1", 0.76)   # the closing line, on the picture
if T_LAND < T_LIFT + LIFT_S or T_LAND2 < T_LIFT2 + LIFT_S:
    raise RuntimeError("a crate arrives before the one it replaces has left")

SWAPS = [(T_LIFT, T_LAND, "new"), (T_REW, T_REW + LIFT_S, "old"), (T_LIFT2, T_LAND2, "new")]


def swap_state(t):
    """The Sensor crate at t: (height, opacity, which sensor it holds)."""
    y, alpha, kind = 0.0, 1.0, "old"
    for t_out, t_in, after in SWAPS:
        if t >= t_in:
            u = remap(t, t_in, t_in + LAND_S)
            y, alpha, kind = LIFT_H * (1.0 - ease_out(u)), smooth(min(u * 2.5, 1.0)), after
        elif t >= t_out:
            u = remap(t, t_out, t_out + LIFT_S)
            y, alpha = LIFT_H * u * u, 1.0 - smooth(remap(u, 0.5, 1.0))
    return y, alpha, kind


def sorted_p(t):
    return smooth(remap(t, T_SORT, T_SORT + 1.8))


# The crossing's clock: the train passes over and over, a pass starting at T_RUN1 and, later, one
# at T_RUN3. Between the two the clock runs a little off the film's, so that both land on tick 0.
_PASS = TICKS * TICK_S
_N = max(1, round((T_RUN3 - cap0("d1")) / _PASS + ((cap0("d1") - T_RUN1) % _PASS) / _PASS))
_L0 = cap0("d1") - T_RUN1
_L1 = (math.floor(_L0 / _PASS) + _N) * _PASS
_CLOCK_T = [T_RUN1 - 1000.0, cap0("d1"), T_RUN3, T_RUN3 + 1000.0]
_CLOCK_L = [-1000.0, _L0, _L1, _L1 + 1000.0]


def tick_at(t):
    """The tick the crossing is in at t, with its fraction: 0 <= tau < TICKS."""
    return (float(np.interp(t, _CLOCK_T, _CLOCK_L)) / TICK_S) % TICKS


# ── the crossing ──────────────────────────────────────────────────────────────
class Crossing:
    """A track, a road across it, and the four parts: the sensor (a radar, later a contact on the
    rail), the controller's cabinet, the gate and the lights. And a train."""
    GAUGE = 0.26

    def __init__(self, parent):
        g = self.group = tp.Group()
        parent.add(g)
        steel = standard(0x9aa6ba, roughness=0.35, metalness=0.8)
        dark = standard(0x2a3140, roughness=0.6, metalness=0.3)
        x0, length = CX + 2.5, 20.0
        box(length, 0.014, 0.56, standard(0x161b24, roughness=0.95), (x0, 0.007, ZT), g, shadow=False)
        sleeper = standard(0x3a2f28, roughness=0.9)
        for k in range(int(length / 0.3)):
            box(0.07, 0.016, 0.42, sleeper, (x0 - length / 2 + 0.15 + 0.3 * k, 0.02, ZT), g, shadow=False)
        for dz in (-self.GAUGE / 2, self.GAUGE / 2):
            box(length, 0.022, 0.024, steel, (x0, 0.037, ZT + dz), g)
        box(0.9, 0.012, 2.1, standard(0x222834, roughness=0.9), (CX, 0.006, ZT + 0.05), g, shadow=False)
        box(0.9, 0.034, 0.5, standard(0x2b3240, roughness=0.9), (CX, 0.017, ZT), g, shadow=False)   # the deck
        for dz in (-0.7, 0.5, 0.85):
            box(0.04, 0.014, 0.22, standard(0xcfd6e2, roughness=0.8), (CX, 0.008, ZT + dz), g, shadow=False)
        zs = ZT + 0.66                                           # the roadside, on the camera's side of the track
        # the gate: a post, and a boom that turns about its top
        c = JOB_COLOUR["gate"]
        box(0.08, 0.36, 0.08, dark, (CX - 0.62, 0.18, zs), g)
        self.boom = tp.Group()
        self.boom.position.set(CX - 0.62, 0.34, zs + 0.065)
        g.add(self.boom)
        stripes = (standard(c, roughness=0.4, emissive=c, emissive_intensity=0.35), standard(0xf2f5fa, roughness=0.5))
        for k in range(7):
            box(0.17, 0.05, 0.05, stripes[k % 2], (-0.02 + 0.17 * k, 0.0, 0.0), self.boom)
        box(0.16, 0.11, 0.07, dark, (-0.2, 0.0, 0.0), self.boom)
        # the lights: two lamps on a board
        c = JOB_COLOUR["lights"]
        box(0.05, 0.62, 0.05, dark, (CX + 0.66, 0.31, zs), g)
        box(0.38, 0.19, 0.035, standard(mix(c, 0x10131a, 0.45), roughness=0.5, emissive=c, emissive_intensity=0.25),
            (CX + 0.66, 0.66, zs + 0.02), g)
        self.lamps = []
        for dx in (-0.095, 0.095):
            m = standard(0x5a0d12, roughness=0.3, emissive=0xff1e1e, emissive_intensity=0.0)
            lamp = tp.Mesh(tp.SphereGeometry(0.058, 24, 16), m)
            lamp.position.set(CX + 0.66 + dx, 0.66, zs + 0.045)
            g.add(lamp)
            self.lamps.append(m)
        # the controller's cabinet
        c = JOB_COLOUR["decide"]
        box(0.27, 0.42, 0.19, standard(mix(c, 0x1a2029, 0.6), roughness=0.5, emissive=c, emissive_intensity=0.18),
            (CX + 1.32, 0.21, zs), g)
        self.cabinet_mat = standard(0xffffff, roughness=0.3, emissive=c, emissive_intensity=1.6)
        lamp = tp.Mesh(tp.SphereGeometry(0.03, 20, 12), self.cabinet_mat)
        lamp.position.set(CX + 1.32, 0.45, zs + 0.02)
        g.add(lamp)
        # the first sensor: a radar on a pole, looking up the track
        c = JOB_COLOUR["sense"]
        blue = standard(mix(c, 0x1a2029, 0.45), roughness=0.45, emissive=c, emissive_intensity=0.3)
        self.eye_mat = standard(0xffffff, roughness=0.3, emissive=c, emissive_intensity=1.6)
        self.radar = tp.Group()
        self.radar.position.set(CX - 1.35, 0.0, zs - 0.12)
        g.add(self.radar)
        box(0.045, 0.5, 0.045, dark, (0.0, 0.25, 0.0), self.radar)
        box(0.2, 0.14, 0.16, blue, (0.0, 0.55, 0.0), self.radar)
        eye = tp.Mesh(tp.SphereGeometry(0.036, 20, 12), self.eye_mat)
        eye.position.set(-0.1, 0.55, 0.0)
        self.radar.add(eye)
        self.eye_at = np.array([CX - 1.45, 0.55, zs - 0.12])
        self.beam_mat = glow(c, 0.0)
        self.beam = tp.Mesh(tp.CylinderGeometry(0.008, 0.008, 1.0, 10), self.beam_mat)
        self.beam.rotation.z = math.pi / 2
        g.add(self.beam)
        # the second: a contact on the rail, and the stretch of track it watches
        reach = K["SAFE_DISTANCE"] * MS
        self.contact = tp.Group()
        self.contact.position.set(CX - reach, 0.0, ZT)
        g.add(self.contact)
        box(0.2, 0.07, 0.12, blue, (0.0, 0.035, 0.34), self.contact)
        eye = tp.Mesh(tp.SphereGeometry(0.03, 20, 12), self.eye_mat)
        eye.position.set(0.0, 0.085, 0.34)
        self.contact.add(eye)
        self.rail_mat = standard(c, roughness=0.4, emissive=c, emissive_intensity=0.0)
        for dz in (-0.07, 0.07):
            box(2 * reach, 0.012, 0.03, self.rail_mat, (reach, 0.034, dz), self.contact, shadow=False)
        # the train: its front is its origin
        self.train = tp.Group()
        self.train.position.set(0.0, 0.0, ZT)
        g.add(self.train)
        body = standard(0xd6dce8, roughness=0.35, metalness=0.3)
        roof = standard(0x39424f, roughness=0.5, metalness=0.5)
        wheel = tp.CylinderGeometry(0.05, 0.05, 0.3, 20)
        for k, (x, length_) in enumerate(((-0.34, 0.68), (-1.0, 0.5), (-1.53, 0.5))):
            box(length_, 0.2, 0.3, body, (x, 0.22, 0.0), self.train)
            box(length_ - 0.04, 0.035, 0.26, roof, (x, 0.337, 0.0), self.train)
            box(length_ - 0.08, 0.05, 0.22, roof, (x, 0.1, 0.0), self.train)
            for dx in (-length_ / 2 + 0.12, length_ / 2 - 0.12):
                w = tp.Mesh(wheel, roof)
                w.rotation.x = math.pi / 2
                w.position.set(x + dx, 0.09, 0.0)
                w.cast_shadow = True
                self.train.add(w)
        box(0.24, 0.1, 0.28, body, (-0.5, 0.37, 0.0), self.train)                    # the cab
        box(0.03, 0.06, 0.2, standard(0x10131a, roughness=0.2), (-0.005, 0.25, 0.0), self.train)
        nose = tp.Mesh(tp.SphereGeometry(0.03, 16, 12), standard(0xfff3d0, emissive=0xffd98a, emissive_intensity=2.5))
        nose.position.set(0.0, 0.17, 0.0)
        self.train.add(nose)
        self.front = 0.0
        self.parts = {"sense": np.array([CX - 1.35, 0.7, zs - 0.12]), "decide": np.array([CX + 1.32, 0.52, zs]),
                      "gate": np.array([CX - 0.3, 0.52, zs]), "lights": np.array([CX + 0.66, 0.82, zs])}

    def set(self, t, new_sensor, lift):
        """The crossing at t. `new_sensor` 0..1: the radar has made way for the rail contact;
        `lift` 0..1..0 while they change places."""
        tau = tick_at(t)
        k, frac = int(tau), tau - int(tau)
        near, angle, lit, _ = SIM[k]
        before = SIM[k - 1][1] if k else K["UP"]
        self.boom.rotation.z = math.radians(before + (angle - before) * smooth(frac))
        self.front = CX + train_at(tau) * MS
        self.train.position.x = self.front
        blink = math.sin(2.0 * math.pi * 1.6 * t)
        for m, phase in zip(self.lamps, (1.0, -1.0)):
            m.emissive_intensity = 1.5 * smooth(clamp01(0.5 + 2.0 * phase * blink)) if lit else 0.0
        self.cabinet_mat.emissive_intensity = 1.2 + 0.5 * math.sin(5.0 * t)
        # the radar looks at whichever end of the train is nearer; the contact lights its rails
        target = self.front if train_at(tau) < 0 else self.front - TRAIN_LEN
        target = min(target, self.eye_at[0] - 0.05) if train_at(tau) < 0 else max(target, self.eye_at[0] + 0.05)
        length = abs(target - self.eye_at[0])
        self.beam.scale.set(1.0, length, 1.0)
        self.beam.position.set((target + self.eye_at[0]) / 2, 0.55 - 0.16 * 0.5, self.eye_at[2] + 0.5 * (ZT - self.eye_at[2]))
        self.beam.rotation.set(0.0, math.atan2(-(ZT - self.eye_at[2]), target - self.eye_at[0]) if length > 1e-3 else 0.0,
                               math.pi / 2)
        self.beam_mat.opacity = 0.55 * (1.0 - new_sensor) * (1.0 if near else 0.0) * (0.75 + 0.25 * math.sin(11.0 * t))
        self.beam.visible = self.beam_mat.opacity > 0.01
        up = 1.6 * lift
        s = max(1.0 - new_sensor, 1e-3)
        self.radar.visible = new_sensor < 0.999
        self.radar.position.y = up
        self.radar.scale.set(s, s, s)
        s = max(new_sensor, 1e-3)
        self.contact.visible = new_sensor > 0.001
        self.contact.position.y = up * (1.0 - new_sensor)
        self.contact.scale.set(1.0, s, 1.0)
        self.rail_mat.emissive_intensity = (1.8 if near else 0.12) * new_sensor


# ── the program, taken apart ──────────────────────────────────────────────────
class Crate:
    """A class: a plate, with a bar along its front edge in the colour its name promises."""

    def __init__(self, name, parent):
        self.name, self.colour = name, JOB_COLOUR[CLASS_JOB[name]]
        self.group = tp.Group()
        parent.add(self.group)
        self.plate_mat = standard(0x1b2331, roughness=0.55, metalness=0.15)
        self.plate = tp.Mesh(tp.BoxGeometry(1.0, Y_TOP, 1.0), self.plate_mat)
        self.plate.position.y = Y_TOP / 2
        self.plate.receive_shadow = True
        self.plate.cast_shadow = True
        self.group.add(self.plate)
        self.bar_mat = standard(self.colour, roughness=0.4, emissive=self.colour, emissive_intensity=0.9)
        self.bar = tp.Mesh(tp.BoxGeometry(1.0, 0.016, 0.035), self.bar_mat)
        self.group.add(self.bar)
        self.pose = (0.0, 0.0, 0.0, 1.0, 1.0, 0.0)

    def set(self, x, y, z, w, d, alpha, grow, hot):
        """At (x, y, z), w wide and d deep; `grow` 0..1 as it arrives; `hot` 0..1 red."""
        k = max(ease_out_back(grow), 1e-3)
        alpha = alpha if grow > 1e-3 else 0.0
        self.pose = (x, y, z, w * k, d * k, alpha)
        self.group.visible = alpha > 0.003
        if not self.group.visible:
            return
        self.group.position.set(x, y, z)
        self.plate.scale.set(w * k, 1.0, d * k)
        self.bar.scale.set(w * k, 1.0, 1.0)
        self.bar.position.set(0.0, Y_TOP + 0.008, d * k / 2 - 0.0175)
        fade_mat(self.plate_mat, alpha)
        fade_mat(self.bar_mat, alpha)
        self.plate.cast_shadow = alpha > 0.6 and y < 0.2      # nothing in the air throws a shadow across the stage
        c = mix(self.colour, C_ERR, hot)
        self.bar_mat.color = tp.Color(c)
        self.bar_mat.emissive = tp.Color(c)
        self.bar_mat.emissive_intensity = 0.9 + 1.2 * hot


class Slab:
    """A function, or one stripe of one: a slab in the colour of a job."""
    _unit = None

    def __init__(self, job, parent):
        if Slab._unit is None:
            Slab._unit = tp.BoxGeometry(1.0, 1.0, 1.0)
        self.colour = JOB_COLOUR[job]
        self.mat = standard(self.colour, roughness=0.35, emissive=self.colour, emissive_intensity=0.2)
        self.mesh = tp.Mesh(Slab._unit, self.mat)
        self.mesh.cast_shadow = True
        self.mesh.receive_shadow = True
        parent.add(self.mesh)
        self.pos = np.zeros(3)

    def set(self, pos, size, alpha, lit=0.0, hot=0.0):
        """`lit` 0..1 brighter; `hot` 0..1 red."""
        self.pos = np.asarray(pos, float)
        self.mesh.visible = alpha > 0.003 and min(size) > 1e-4
        if not self.mesh.visible:
            return
        self.mesh.position.set(*pos)
        self.mesh.scale.set(*size)
        self.mesh.cast_shadow = alpha > 0.6 and pos[1] < 0.9
        fade_mat(self.mat, alpha)
        c = mix(self.colour, C_ERR, hot)
        self.mat.color = tp.Color(c)
        self.mat.emissive = tp.Color(c)
        self.mat.emissive_intensity = 0.2 + 0.9 * lit + 0.9 * hot


class Drum:
    """A data member: a drum (and, for the new sensor's, a cube)."""

    def __init__(self, job, parent):
        c = JOB_COLOUR[job]
        self.mat = standard(c, roughness=0.3, metalness=0.2, emissive=c, emissive_intensity=0.3)
        self.drum = tp.Mesh(tp.CylinderGeometry(0.085, 0.085, 0.09, 40), self.mat)
        self.cube = tp.Mesh(tp.BoxGeometry(0.14, 0.11, 0.14), self.mat)
        for m in (self.drum, self.cube):
            m.cast_shadow = True
            parent.add(m)
        self.pos = np.zeros(3)

    def set(self, pos, alpha, grow, kind="old", lit=0.0):
        self.pos = np.asarray(pos, float)
        vis = alpha > 0.003 and grow > 1e-3
        self.drum.visible = vis and kind == "old"
        self.cube.visible = vis and kind == "new"
        if not vis:
            return
        k = max(ease_out_back(grow), 1e-3)
        for m, h in ((self.drum, 0.045), (self.cube, 0.055)):
            m.position.set(pos[0], pos[1] + h * k, pos[2])
            m.scale.set(k, k, k)
            m.cast_shadow = alpha > 0.6 and pos[1] < 0.2
        fade_mat(self.mat, alpha)
        self.mat.emissive_intensity = 0.3 + 1.0 * lit


class Case:
    """Glass over a class's data: private."""
    W, H, D = 0.42, 0.24, 0.34

    def __init__(self, parent):
        self.group = tp.Group()
        parent.add(self.group)
        self.glass = standard(0xdfeaff, roughness=0.1, emissive=0x9fc0ff, emissive_intensity=0.25)
        self.glass.side = tp.Side.Double
        self.frame = standard(0xdfeaff, roughness=0.3, emissive=0xbfd4ff, emissive_intensity=0.9)
        shell = tp.Mesh(tp.BoxGeometry(self.W, self.H, self.D), self.glass)
        shell.position.y = self.H / 2
        self.group.add(shell)
        t = 0.012
        for sx in (-1, 1):
            for sz in (-1, 1):
                box(t, self.H, t, self.frame, (sx * self.W / 2, self.H / 2, sz * self.D / 2), self.group, shadow=False)
            box(t, t, self.D, self.frame, (sx * self.W / 2, self.H, 0.0), self.group, shadow=False)
        for sz in (-1, 1):
            box(self.W, t, t, self.frame, (0.0, self.H, sz * self.D / 2), self.group, shadow=False)

    def set(self, pos, down, alpha):
        """`down` 0..1 as it is lowered over the data."""
        a = alpha * smooth(min(down * 2.0, 1.0))
        self.group.visible = a > 0.003
        if not self.group.visible:
            return
        self.group.position.set(pos[0], pos[1] + 1.1 * (1.0 - ease_out(down)), pos[2])
        self.glass.transparent = True
        self.glass.depth_write = False
        self.glass.opacity = 0.2 * a
        fade_mat(self.frame, a)


class Thread:
    """A function using something: an arc from the function to the thing, drawn up to `grow`."""
    N, SIDES = 30, 8

    def __init__(self, parent, radius):
        self.radius = radius
        self.mat = standard(C_THREAD, roughness=0.4, emissive=C_THREAD, emissive_intensity=1.0)
        n = self.N * self.SIDES
        self.geom = tp.BufferGeometry()
        self.geom.set_attribute("position", np.zeros((n, 3), np.float32))
        self.geom.set_attribute("normal", np.zeros((n, 3), np.float32))
        i, j = np.arange(self.N - 1)[:, None], np.arange(self.SIDES)[None, :]
        a, b = i * self.SIDES + j, i * self.SIDES + (j + 1) % self.SIDES
        c, d = a + self.SIDES, b + self.SIDES
        self.geom.set_index(np.stack([a, c, b, b, c, d], axis=-1).reshape(-1).astype(np.uint32))
        self.mesh = tp.Mesh(self.geom, self.mat)
        self.mesh.frustum_culled = False
        self.mesh.visible = False
        parent.add(self.mesh)
        ang = np.linspace(0.0, 2.0 * np.pi, self.SIDES, endpoint=False)
        self._ca, self._sa = np.cos(ang), np.sin(ang)
        self.a = self.b = self.c = np.zeros(3)
        self.alpha = 0.0

    def point(self, s):
        return (1 - s) ** 2 * self.a + 2 * (1 - s) * s * self.c + s ** 2 * self.b

    def set(self, a, b, rise, grow=1.0, alpha=1.0, colour=C_THREAD, power=1.0):
        """From a to b, its middle pulled up by `rise`."""
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.c = (self.a + self.b) / 2 + np.array([0.0, rise, 0.0])
        self.alpha = alpha if grow > 0.02 else 0.0
        self.mesh.visible = self.alpha > 0.003
        if not self.mesh.visible:
            return
        s = np.linspace(0.0, grow, self.N)[:, None]
        pts = (1 - s) ** 2 * self.a + 2 * (1 - s) * s * self.c + s ** 2 * self.b
        tan = 2 * (1 - s) * (self.c - self.a) + 2 * s * (self.b - self.c)
        tan /= np.linalg.norm(tan, axis=1, keepdims=True) + 1e-9
        flat = self.b - self.a
        side = np.cross([flat[0], 0.0, flat[2]], [0.0, 1.0, 0.0])
        side = side / np.linalg.norm(side) if np.linalg.norm(side) > 1e-6 else np.array([1.0, 0.0, 0.0])
        n1 = np.broadcast_to(side, tan.shape)
        n2 = np.cross(tan, n1)
        nrm = self._ca[None, :, None] * n1[:, None, :] + self._sa[None, :, None] * n2[:, None, :]
        pos = pts[:, None, :] + self.radius * nrm
        self.geom.update_attribute("position", np.ascontiguousarray(pos.reshape(-1, 3), np.float32))
        self.geom.update_attribute("normal", np.ascontiguousarray(nrm.reshape(-1, 3), np.float32))
        fade_mat(self.mat, self.alpha)
        self.mat.color = tp.Color(colour)
        self.mat.emissive = tp.Color(colour)
        self.mat.emissive_intensity = power


class Spark:
    """Something travelling a thread: a call."""
    _disc = None

    def __init__(self, parent, r=0.032):
        if Spark._disc is None:
            Spark._disc = disc_texture(96, soft=0.9)
        self.mat = standard(0xffffff, roughness=0.3, emissive=0xffffff, emissive_intensity=2.0)
        self.ball = tp.Mesh(tp.SphereGeometry(r, 20, 14), self.mat)
        parent.add(self.ball)
        self.halo_mat = tp.SpriteMaterial()
        self.halo_mat.map = Spark._disc
        self.halo_mat.transparent = True
        self.halo_mat.blending = tp.Blending.Additive
        self.halo_mat.depth_write = False
        self.halo = tp.Sprite(self.halo_mat)
        self.halo.scale.set(r * 7.0, r * 7.0, 1.0)
        parent.add(self.halo)

    def set(self, pos, alpha, colour=0xffffff):
        vis = alpha > 0.003
        self.ball.visible = self.halo.visible = vis
        if not vis:
            return
        self.ball.position.set(*pos)
        self.halo.position.set(*pos)
        fade_mat(self.mat, alpha)
        self.mat.emissive = tp.Color(colour)
        self.halo_mat.color = tp.Color(colour)
        self.halo_mat.opacity = 0.6 * alpha


# ── the terminal: (time, kind, text); a 'prompt' starts a new screen ───────────
def _status_lines(t0):
    return [(t0 + (k + 0.15) * TICK_S, "out", line) for k, line in enumerate(PRINTED)]


def _error_rows(t0):
    rows = []
    for k, (n, message) in enumerate(BUILD_ERRORS):
        f = next(f for f in TANGLED_NEW.funcs.values() if f["first"] <= n <= f["last"])
        rows.append((t0 + 0.45 * k, "where", f"tangled.cpp, in {f['cls']}::{f['name']}"))
        rows.append((t0 + 0.45 * k + 0.01, "err", "  " + re.sub(r"error C\d+", "error", message)))
    return rows


TERM = ([(T_RUN1 - 0.3, "prompt", "tangled")] + _status_lines(T_RUN1)
        + [(T_BUILD1, "prompt", "build tangled.cpp, with the new sensor")] + _error_rows(T_ERRORS)
        + [(T_BUILD2, "prompt", "build tidy.cpp, with the new sensor"), (T_RUN3 - 0.3, "then", "tidy")]
        + _status_lines(T_RUN3))
TERM.sort(key=lambda e: e[0])
TERM_ON = [(T_RUN1 - 0.8, cap0("a2") - 0.3), (T_BUILD1, T_REW - 0.1),      # each from its first prompt on
           (T_BUILD2, T_RUN3 + (TICKS + 1.5) * TICK_S)]

LEFT, TOP = 70, 64             # the cards' corner
COL_W = 715                    # and their width
CODE_Y = 262


class Painter:
    """Everything a frame needs: the stage's pose at t, then the 2D layer over it."""

    def __init__(self, st, ov):
        self.st, self.ov = st, ov
        self.captions = SPEECH.captions(CAP)
        world = tp.Group()
        st.scene.add(world)
        self.crossing = Crossing(world)
        self.crates = {name: Crate(name, world) for name in CRATES}
        # a slab for every stripe of every tangled function; each flies to a tidy function
        self.slabs, landed = [], set()
        for f in TANGLED.members():
            pairs = SPLIT[f["name"]]
            for k, (job, target) in enumerate(pairs):
                cls = TIDY.funcs[target]["cls"]
                row = TIDY.classes[cls]["functions"]
                spacing, width = ROW[len(row)]
                s = Slab(job, world)
                s.src, s.dst, s.of, s.target, s.job = f["cls"], cls, f["name"], target, job
                s.xa = (k - (len(pairs) - 1) / 2) * SEG
                s.xb = (row.index(target) - (len(row) - 1) / 2) * spacing
                s.zb = Z_F if TIDY.classes[cls]["data"] else Z_LONE
                s.width = width
                s.order = len(self.slabs)
                s.extra = target in landed            # a second stripe landing on the same function
                landed.add(target)
                self.slabs.append(s)
        self.drums = {cls: Drum(CLASS_JOB[cls], world) for cls, c in TIDY.classes.items() if c["data"]}
        self.cases = {cls: Case(world) for cls in self.drums}
        # threads, as the two sources have them
        self.t_threads, self.d_threads = [], []
        for f in TANGLED.members():
            for d in f["touches"]:
                own = TANGLED.data[d] == f["cls"]
                th = Thread(world, 0.0055 if own else 0.009)
                th.f, th.cls, th.to, th.own = f["name"], f["cls"], TANGLED.data[d], own
                self.t_threads.append(th)
        for f in TIDY.members():
            for d in f["touches"]:
                th = Thread(world, 0.0055)
                th.f, th.cls, th.to, th.own = f["name"], f["cls"], TIDY.data[d], True
                self.d_threads.append(th)
            for g in f["calls"]:
                th = Thread(world, 0.009)
                th.f, th.cls, th.to, th.own = f["name"], f["cls"], g, False
                self.d_threads.append(th)
        self.reach = [th for th in self.t_threads if not th.own]          # into another class's data
        self.calls = [th for th in self.d_threads if not th.own]          # the controller's
        self.sparks = [Spark(world) for _ in range(len(self.reach) + len(self.calls) + 2)]
        front = -90.0
        ox, oz = ORIGIN[0], ORIGIN[2]
        v_road = (CX - 0.75, 0.3, ZT + 0.55)
        v_title = (CX - 2.0, 0.55, ZT + 0.55)
        v_all = (ox - 1.45, 0.1, oz - 0.45)
        v_gate = (ox - 0.15, 0.1, oz + 0.25)
        v_tidy = (ox - 1.6, 0.1, oz - 0.15)
        v_sensor = (ox - 1.95, 0.1, oz + 0.45)
        v_works = (CX - 0.75, 0.25, ZT + 0.15)
        v_end = (ox - 0.95, 0.2, oz - 0.7)
        self.cam = OrbitCamera([    # (time, azimuth, elevation, distance, look point, fov)
            (0.0, front + 14, 12.0, 7.8, v_title, 32),
            (cap0("a0") - 0.6, front + 12, 12.0, 7.4, v_title, 32),
            (cap0("a0") + 1.2, front + 10, 13.0, 5.9, v_road, 32),
            (cap1("a0") - 0.4, front + 6, 14.0, 5.6, v_road, 32),
            (T_CRATES + 0.7, front + 2, 34.0, 7.5, v_all, 32),
            (cap0("a2") - 0.2, front, 34.0, 7.5, v_all, 32),
            (cap0("a2") + 1.3, front - 5, 47.0, 4.7, v_gate, 32),
            (cap1("a2") - 0.5, front - 7, 47.0, 4.7, v_gate, 32),
            (cap0("a3") + 1.1, front, 35.0, 7.5, v_all, 32),
            (T_REW, front + 3, 35.0, 7.5, v_all, 32),
            (T_SORT + 1.2, front, 38.0, 7.6, v_tidy, 32),
            (cap0("d2") - 0.2, front, 38.0, 7.6, v_tidy, 32),
            (cap0("d2") + 1.4, front + 3, 50.0, 6.2, v_sensor, 32),
            (cap1("d2") - 0.4, front + 5, 50.0, 6.2, v_sensor, 32),
            (cap0("d3") + 1.2, front, 38.0, 7.6, v_tidy, 32),
            (cap1("e1") - 0.6, front - 3, 38.0, 7.6, v_tidy, 32),
            (cap0("e2") + 1.0, front + 6, 33.0, 5.2, v_works, 32),
            (cap1("e2") - 0.2, front + 3, 33.0, 5.1, v_works, 32),
            (cap0("z1") + 1.6, front, 31.0, 8.2, v_end, 32),
            (TL.duration, front - 5, 31.0, 8.5, v_end, 32),
        ], frame="yup")
        self.xy = {}

    # where things are --------------------------------------------------------
    def crate_pose(self, name, t):
        """(x, y, z, width, depth, opacity, 0..1 as it arrives) of a crate at t."""
        a, b = CRATES[name]
        if a is None:
            x, z, w, d = b
            grow = remap(t, T_CONTROLLER, T_CONTROLLER + 0.6)
        else:
            x, z, w, d = np.array(a) + (np.array(b) - np.array(a)) * sorted_p(t)
            k = list(CRATES).index(name)
            grow = remap(t, T_CRATES + 0.22 * k, T_CRATES + 0.22 * k + 0.6)
        y, alpha = (swap_state(t)[:2] if name == "Sensor" else (0.0, 1.0))
        if name != "Gate":                       # while one function of Gate is read, the rest stands back
            alpha *= 1.0 - 0.85 * envelope(t, cap0("a2") + 0.5, cap1("a2") - 0.2, 0.7, 0.7)
        return ORIGIN[0] + x, y, ORIGIN[2] + z, w, d, alpha, grow

    def tangled_at(self, cls, t, dx=0.0):
        """The top of a tangled class's function, dx along it."""
        x, y, z, *_ = self.crate_pose(cls, t)
        return np.array([x + dx, y + Y_TOP + BLOCK_H, z + Z_F])

    def tidy_at(self, name, t):
        """The top of a tidy function."""
        cls = TIDY.funcs[name]["cls"]
        row = TIDY.classes[cls]["functions"]
        x, y, z, *_ = self.crate_pose(cls, t)
        return np.array([x + (row.index(name) - (len(row) - 1) / 2) * ROW[len(row)][0], y + Y_TOP + BLOCK_H,
                         z + (Z_F if TIDY.classes[cls]["data"] else Z_LONE)])

    def data_at(self, cls, t, top=True):
        x, y, z, *_ = self.crate_pose(cls, t)
        return np.array([x, y + Y_TOP + (0.09 if top else 0.0), z + Z_D])

    def flown(self, s, t):
        """How far slab s is on its way from its tangled function to its tidy one, 0..1."""
        if s.dst == "Controller":             # the deciding leaves last, as its crate arrives
            t0 = T_CONTROLLER - 0.1 + 0.03 * s.order
        else:
            t0 = T_SORT + 0.13 * s.order
        return smooth(remap(t, t0, t0 + 1.9))

    def broken(self, name, t):
        """0..1: a function left naming data that is gone."""
        if name not in BROKEN:
            return 0.0
        k = list(BROKEN).index(name)
        return envelope(t, T_LIFT + 0.55 + 0.25 * k, T_REW + LIFT_S + 0.5, 0.25, 0.5)

    # 3D ----------------------------------------------------------------------
    def pose(self, t):
        st = self.st
        new2 = smooth(remap(t, T_LIFT2 + 0.2, T_LAND2 + 0.5))
        self.crossing.set(t, new2, math.sin(math.pi * new2))
        poses = {name: self.crate_pose(name, t) for name in CRATES}
        kind = swap_state(t)[2]
        for name, c in self.crates.items():
            x, y, z, w, d, alpha, grow = poses[name]
            hot = envelope(t, T_EVERY, T_REW + LIFT_S + 0.5, 0.3, 0.5) if any(
                TANGLED.funcs[f]["cls"] == name for f in BROKEN) else 0.0
            c.set(x, y, z, w, d, alpha, grow, hot)
        # the functions
        for s in self.slabs:
            u = self.flown(s, t)
            ax, ay, az, _, _, a_alpha, _ = poses[s.src]
            bx, by, bz, _, _, b_alpha, _ = poses[s.dst]
            pa = np.array([ax + s.xa, ay + Y_TOP + BLOCK_H / 2, az + Z_F])
            pb = np.array([bx + s.xb, by + Y_TOP + BLOCK_H / 2, bz + s.zb])
            pos = pa + (pb - pa) * u + np.array([0.0, 0.6 * math.sin(math.pi * u), 0.0])
            size = np.array([SEG, BLOCK_H, 0.17]) + (np.array([s.width, BLOCK_H, 0.15]) - [SEG, BLOCK_H, 0.17]) * u
            k = list(TANGLED.classes).index(s.src)
            grow = ease_out_back(remap(t, T_BLOCKS + 0.25 * k, T_BLOCKS + 0.25 * k + 0.5))
            alpha = (a_alpha + (b_alpha - a_alpha) * u) * (0.0 if s.extra and u > 0.999 else 1.0)
            lit = 0.0
            if s.of == "move":                       # the one function the film reads aloud
                lit = envelope(t, T_JOB[s.job], T_JOB[s.job] + 1.5, 0.15, 0.6)
                pos[1] += 0.06 * lit * (1.0 - u)
            lit = max(lit, bump(t - T_PUBLIC - 0.07 * s.order, 0.9), self.called(s.target, t) * u,
                      0.7 * bump(t - T_ONE_JOB - 0.3 * list(CRATES).index(s.dst), 0.9),
                      0.8 * bump(t - T_STAYS, 1.4) * (s.dst == "Sensor"))
            s.set(pos, size * max(grow, 1e-3), alpha, lit=lit, hot=self.broken(s.of, t) * (1.0 - u))
        # the data, and the glass over it
        for k, (cls, drum) in enumerate(self.drums.items()):
            x, y, z, _, _, alpha, _ = poses[cls]
            at = np.array([x, y + Y_TOP, z + Z_D])
            touched = max((bump(t - self.reach_t(th) - 0.55, 0.7) for th in self.reach if th.to == cls), default=0.0)
            drum.set(at, alpha, remap(t, T_DRUMS + 0.2 * k, T_DRUMS + 0.2 * k + 0.5),
                     kind if cls == "Sensor" else "old", lit=touched)
            self.cases[cls].set(at, remap(t, T_GLASS + 0.3 * k, T_GLASS + 0.3 * k + 0.9), alpha)
        self.threads(t)
        eye, look, fov = self.cam(t)
        st.look(eye, look, fov)
        st.follow((1.2, 0.0, -0.7))
        # where the labels go
        P = lambda p: tuple(st.project(p)[:2])  # noqa: E731
        xy = self.xy = {}
        for name in CRATES:
            x, y, z, w, d, alpha, grow = poses[name]
            xy["crate", name] = P((x, y + Y_TOP, z + d / 2 + 0.03))
        for cls in TANGLED.classes:
            xy["tangled", cls] = P(self.tangled_at(cls, t) + (0.0, -BLOCK_H, 0.19))
            xy["data", cls] = P(self.data_at(cls, t) + (0.15, -0.03, 0.0))
            xy["case", cls] = P(self.data_at(cls, t) + (-Case.W / 2, Case.H - 0.09, 0.0))
        for f in TIDY.members():
            xy["tidy", f["name"]] = P(self.tidy_at(f["name"], t) + (0.0, -BLOCK_H, 0.2))
        for job, p in self.crossing.parts.items():
            xy["part", job] = P(p)
        for th in self.reach:
            if th.to == "Sensor":                    # the loose end of a thread that reached for the old data
                xy["stub", th.f] = P(th.b)

    def reach_t(self, th):
        """When a thread into another class's data starts to grow."""
        return T_THREAD + 0.75 * self.reach.index(th)

    def call_t(self, th):
        return T_CALL + 0.55 * self.calls.index(th)

    def called(self, name, t):
        """0..1: a tidy function as a call reaches it."""
        out = 0.0
        for th in self.calls:
            if th.to == name:
                out = max(out, bump(t - self.call_t(th) - 0.5, 0.8))
        if name == "trainNear":
            out = max(out, bump(t - T_ASK - 0.45, 0.8))
        return out

    def threads(self, t):
        sparks = iter(self.sparks)
        y_s, a_s, _ = swap_state(t)
        tangled = 1.0 - smooth(remap(t, T_SORT - 0.5, T_SORT + 0.1))
        # tangled.cpp: each function to its own data, and into the data of other classes
        fan = {}
        for th in self.t_threads:
            n = sum(1 for o in self.t_threads if o.f == th.f)
            k = fan[th.f] = fan.get(th.f, -1) + 1
            a = self.tangled_at(th.cls, t, (k - (n - 1) / 2) * 0.13)
            b = self.data_at(th.to, t)
            alpha = tangled * (a_s if "Sensor" in (th.cls, th.to) else 1.0)
            if th.own:
                th.set(a, b, 0.22, smooth(remap(t, T_OWN, T_OWN + 0.6)), 0.85 * alpha,
                       JOB_COLOUR[CLASS_JOB[th.cls]], power=0.7)
                continue
            t0 = self.reach_t(th)
            grow = ease_out(remap(t, t0, t0 + 0.7))
            i = self.reach.index(th)
            b = b + np.array([0.04 * math.cos(2.1 * i), 0.0, 0.04 * math.sin(2.1 * i)])
            snapped = 0.0
            if th.to == "Sensor":                    # it reaches for the data the new sensor no longer has
                t1 = T_LIFT + 0.5 + 0.25 * list(BROKEN).index(th.f)
                snapped = smooth(remap(t, t1, t1 + 0.3)) * (1.0 - smooth(remap(t, T_REW + LIFT_S + 0.3, T_REW + LIFT_S + 0.8)))
                away = self.data_at("Sensor", t) - a            # it is left pointing at where the data was
                away[1] = 0.0
                away /= np.linalg.norm(away)
                loose = a + 0.6 * away + np.array([0.05 * math.sin(2.6 * t + i), 0.3 + 0.03 * math.sin(3.7 * t + i),
                                                   0.05 * math.cos(2.1 * t + i)])
                b = b + (loose - b) * snapped
                alpha = tangled * max(a_s, snapped)
            dist = float(np.linalg.norm(b - a))
            th.set(a, b, (0.5 + 0.3 * dist) * (1.0 - 0.75 * snapped), grow, alpha,
                   mix(C_THREAD, C_ERR, snapped), power=1.0 + 0.6 * snapped)
            u = remap(t, t0, t0 + 0.7)
            next(sparks).set(th.point(ease_out(u)), envelope(t, t0, t0 + 0.9, 0.1, 0.25) * alpha, C_THREAD)
        # tidy.cpp: each function to its own data, and the controller to the others' functions
        tidy = smooth(remap(t, T_SORTED - 0.5, T_SORTED + 0.3))
        for k, th in enumerate(self.d_threads):
            a = self.tidy_at(th.f, t)
            if th.own:
                alpha = tidy * (a_s if th.cls == "Sensor" else 1.0)
                th.set(a, self.data_at(th.to, t), 0.2, smooth(remap(t, T_SORTED - 0.5 + 0.06 * k, T_SORTED + 0.2 + 0.06 * k)),
                       0.85 * alpha, JOB_COLOUR[CLASS_JOB[th.cls]], power=0.7)
                continue
            t0 = self.call_t(th)
            b = self.tidy_at(th.to, t)
            out = 0.0
            if th.to == "trainNear":                 # the sensor leaves; the thread waits where its function was
                out = smooth(remap(t, T_LIFT2, T_LIFT2 + 0.25)) * (1.0 - smooth(remap(t, T_PLUG, T_PLUG + 0.3)))
                rest = b.copy()
                rest[1] += 0.14 + 0.02 * math.sin(4.0 * t) - y_s
                b = b + (rest - b) * out
            dist = float(np.linalg.norm(b - a))
            th.set(a, b, 0.35 + 0.25 * dist, ease_out(remap(t, t0, t0 + 0.6)), 1.0 - 0.45 * out, C_THREAD,
                   power=1.0 + 0.8 * bump(t - T_PLUG, 0.6) * (th.to == "trainNear") + 1.2 * bump(t - T_MEET, 1.2))
            u = remap(t, t0, t0 + 0.6)
            next(sparks).set(th.point(ease_out(u)), envelope(t, t0, t0 + 0.8, 0.1, 0.25), C_THREAD)
            if th.to == "trainNear":                 # the same question, and its answer
                go, back = remap(t, T_ASK, T_ASK + 0.5), remap(t, T_ASK + 0.75, T_ASK + 1.25)
                next(sparks).set(th.point(smooth(go)), envelope(t, T_ASK, T_ASK + 0.6, 0.1, 0.15), C_THREAD)
                next(sparks).set(th.point(1.0 - smooth(back)), envelope(t, T_ASK + 0.75, T_ASK + 1.4, 0.1, 0.2),
                                 JOB_COLOUR["sense"])
        for s in sparks:
            s.set((0, 0, 0), 0.0)

    # 2D ----------------------------------------------------------------------
    def draw2d(self, t):
        ov = self.ov
        ov.title_card(t, *TITLE, C_ACCENT, t_in=0.6, t_out=TL.end("open") - 0.4, size=84)
        self.parts(t)
        self.names(t)
        self.legend(t)
        self.score(t)
        self.cards(t)
        self.terminal(t)
        ov.captions(t, self.captions)
        ov.summary(t, TL.start("outro"), TL.end("outro"), SUMMARY, FOOTER, C_ACCENT, C_ACCENT, text_dx=300)

    def chip(self, x, y, text, alpha, color, size=20, anchor="mm", glow_=0.6, text_color=None, kind="mono"):
        """A small labelled panel at (x, y)."""
        if alpha <= 0.003:
            return
        ov = self.ov
        w, h = ov.text_width(text, size, kind) + 26, size + 16
        x0 = x - w / 2 if anchor[0] == "m" else x if anchor[0] == "l" else x - w
        ov.panel(x0, y - h / 2, w, h, radius=9, alpha=0.84 * alpha, outline=mix(0x8aa0c0, color, glow_),
                 outline_alpha=0.3 + 0.7 * glow_, width=1.5)
        ov.text(x0 + w / 2, y, text, size=size, color=text_color or mix(TEXT, color, glow_), alpha=alpha, kind=kind,
                anchor="mm")

    def name(self, x, y, text, alpha, color, size=18):
        """A function's name, on a dark backing so a thread behind it does not strike it out."""
        if alpha <= 0.003:
            return
        ov = self.ov
        w = ov.text_width(text, size, "mono") + 12
        ov.panel(x - w / 2, y - size / 2 - 3, w, size + 6, radius=6, fill=0x0d131e, alpha=0.8 * alpha)
        ov.text(x, y, text, size=size, color=color, alpha=alpha, kind="mono", anchor="mm")

    def parts(self, t):
        """The crossing's four parts, named as the narrator names them."""
        words = {"sense": "sensor", "decide": "controller", "gate": "gate", "lights": "lights"}
        for job, t_in in zip(JOBS, T_PARTS):
            a = envelope(t, t_in, T_CRATES - 0.6, 0.3, 0.5)
            x, y = self.xy["part", job]
            self.chip(x, y - 22, words[job], a, JOB_COLOUR[job], size=22, kind="semibold", glow_=0.8)

    def names(self, t):
        """Each crate's class, each function and each data member, where it lies."""
        ov = self.ov
        gone = 1.0 - smooth(remap(t, TL.start("outro") - 0.2, TL.start("outro") + 0.5))
        s = sorted_p(t)
        kind = swap_state(t)[2]
        for name, c in self.crates.items():
            x, y = self.xy["crate", name]
            a = c.pose[5] * smooth(remap(t, T_CRATES + 0.6, T_CRATES + 1.1)) * gone if CRATES[name][0] else \
                c.pose[5] * smooth(remap(t, T_CONTROLLER + 0.3, T_CONTROLLER + 0.8)) * gone
            self.chip(x, y + 20, name, a, c.colour, size=21, glow_=0.75)
        for cls in TANGLED.classes:
            pose_a = self.crates[cls].pose[5]
            f = TANGLED.classes[cls]["functions"][0]
            x, y = self.xy["tangled", cls]
            hot = self.broken(f, t)
            a = pose_a * envelope(t, T_BLOCKS + 0.5, T_SORT + 0.2, 0.4, 0.4)
            self.name(x, y, f + "()", a, mix(TEXT, C_ERR, hot), size=19)
            x, y = self.xy["data", cls]
            a = pose_a * smooth(remap(t, T_DRUMS + 0.5, T_DRUMS + 0.9)) * gone
            old, new = (TANGLED, TANGLED_NEW) if s < 0.5 else (TIDY, TIDY_NEW)
            member = (new if cls == "Sensor" and kind == "new" else old).classes[cls]["data"][0]
            ov.text(x, y, member, size=18, color=mix(JOB_COLOUR[CLASS_JOB[cls]], TEXT, 0.45), kind="mono", anchor="lm",
                    alpha=a * (1.0 - 4.0 * s * (1.0 - s)))
            # private, once it is under glass
            x, y = self.xy["case", cls]
            ov.text(x - 8, y, "private", size=17, color=DIM, alpha=pose_a * envelope(t, T_PRIVATE, cap1("d2") + 0.4, 0.3, 0.5),
                    kind="semibold", anchor="rm")
        for f in TIDY.members():
            first = next(sl for sl in self.slabs if sl.target == f["name"])
            a = self.crates[f["cls"]].pose[5] * smooth(remap(self.flown(first, t), 0.85, 1.0)) * gone
            x, y = self.xy["tidy", f["name"]]
            lit = self.called(f["name"], t)
            self.name(x, y, f["name"] + "()", a, mix(TEXT, 0xffffff, lit), size=18)
        # what a function is left holding when the data it reached for is gone
        for name in BROKEN:
            x, y = self.xy["stub", name]
            gone_name = next(d for d in TANGLED.data if d not in TANGLED_NEW.data)
            self.chip(x, y - 24, f"{gone_name} ?", self.broken(name, t) * smooth(remap(t, T_NOTHING, T_NOTHING + 0.4)),
                      C_ERR, size=18, glow_=1.0)

    def legend(self, t):
        """The four jobs and their colours, top right."""
        ov = self.ov
        a = envelope(t, T_LEGEND, TL.start("outro") + 0.3, 0.5, 0.5)
        if a <= 0.003:
            return
        x = ov.W - LEFT
        w = sum(ov.text_width(JOB_WORD[job], 19) + 58 for job in JOBS)
        ov.panel(x - w - 2, 24, w + 24, 44, radius=22, alpha=0.62 * a)
        for job in reversed(JOBS):
            w = ov.text_width(JOB_WORD[job], 19)
            ov.text(x, 46, JOB_WORD[job], size=19, color=TEXT, alpha=a, anchor="rm")
            ov.circle(x - w - 16, 46, 7, fill=JOB_COLOUR[job], alpha=a)
            x -= w + 58

    def score(self, t):
        """The two words, what each asks, and how this program answers."""
        ov = self.ov
        a = envelope(t, T_COHESION - 0.2, TL.start("outro") + 0.3, 0.5, 0.5)
        if a <= 0.003:
            return
        rows = [("COHESION", "Do the things inside one class belong together?", T_COHESION, T_LOW, "low", "high",
                 T_SORTED + 0.6),
                ("COUPLING", "How much does one class have to know about another?", T_COUPLING, T_HIGH, "high",
                 "low", T_LOOSE)]
        h = 86 * sum(1 for r in rows if t >= r[2] - 0.2) + 14
        ov.panel(LEFT, TOP, COL_W, h, radius=16, alpha=0.74 * a, outline=0x8aa0c0, outline_alpha=0.16)
        for k, (word, asks, t_in, t_bad, bad, good, t_good) in enumerate(rows):
            ra = a * smooth(remap(t, t_in, t_in + 0.5))
            y = TOP + 14 + 86 * k
            ov.text(LEFT + 26, y + 26, word, size=21, color=TEXT, alpha=ra, kind="semibold", tracking=2.6, anchor="lm")
            ov.text(LEFT + 26, y + 58, asks, size=19, color=DIM, alpha=ra, anchor="lm")
            turned = smooth(remap(t, t_good, t_good + 0.5))
            for text, colour, sa in ((bad, C_ERR, (1.0 - turned) * smooth(remap(t, t_bad, t_bad + 0.4))),
                                     (good, C_GOOD, turned)):
                self.chip(LEFT + COL_W - 26, y + 26, text, ra * sa, colour, size=20, anchor="rm", glow_=1.0,
                          kind="semibold")

    def code_card(self, t, t_in, t_out, lines, title, hl=None, marks=None, size=18, lh=26, stagger=0.12, red=None):
        """A house card of C++ under the two words. `marks(j)`: [(colour, 0..1)] squares beside
        line j; `red(j)`: 0..1, the line no longer compiles."""
        ov = self.ov
        a = envelope(t, t_in, t_out, 0.5, 0.5)
        if a <= 0.003:
            return
        h = 64 + lh * len(lines)
        card(ov, LEFT, CODE_Y, COL_W, h, a, title)
        x = LEFT + (64 if marks else 30)
        cw = ov.text_width("0", size, "mono")
        for j, line in enumerate(lines):
            yy = CODE_Y + 50 + j * lh
            r = red(j) if red else 0.0
            if r > 0.003:
                ov.panel(x - 12, yy - 2, len(line) * cw + 24, lh + 2, radius=5, fill=0x4a1a24, alpha=0.85 * r * a)
            for k, (colour, on) in enumerate(marks(j) if marks else ()):
                ov.circle(LEFT + 25 + 15 * k, yy + lh / 2, 5.5, fill=colour, alpha=a * (0.25 + 0.75 * on))
        ov.code(x, CODE_Y + 50, lines, "cpp", size, lh, a, hl=hl, keywords=CPP_KEYWORDS,
                reveal=lambda j: remap(t, t_in + 0.2 + stagger * j, t_in + 0.6 + stagger * j))

    def cards(self, t):
        # one function of tangled.cpp, each line marked with the jobs it does
        def marks(j):
            return [(JOB_COLOUR[job], envelope(t, T_JOB[job], cap1("a2") + 0.5, 0.2, 0.4))
                    for job in TANGLED.line_jobs(MOVE_CODE[j])]
        self.code_card(t, cap0("a2") + 0.2, cap0("a3") + 0.4, MOVE_CODE, "TANGLED.CPP  ·  ONE FUNCTION", marks=marks)
        # the same function when the sensor's data is gone
        first = TANGLED.funcs["move"]["first"]
        bad = [n - first for n in BROKEN["move"]]
        self.code_card(t, T_BUILD1 - 0.2, T_REW - 0.1, MOVE_CODE, "TANGLED.CPP  ·  WITH THE NEW SENSOR", stagger=0.0,
                       red=lambda j: smooth(remap(t, T_ERRORS, T_ERRORS + 0.4)) if j in bad else 0.0)
        # a class of tidy.cpp: what is private, and what it offers
        private = [j for j, l in enumerate(SENSOR_CODE) if l.strip() == "private:"][0]
        public = [j for j, l in enumerate(SENSOR_CODE) if l.strip() == "public:"][0]

        def hl(j):
            if private <= j < len(SENSOR_CODE) - 1:
                return envelope(t, T_PRIVATE - 0.1, T_PUBLIC - 0.2, 0.3, 0.3)
            return envelope(t, T_PUBLIC - 0.1, cap1("d2") + 0.2, 0.3, 0.4) if public <= j < private - 1 else 0.0
        self.code_card(t, cap0("d2") + 0.3, cap0("d3") + 0.1, SENSOR_CODE, "TIDY.CPP  ·  ONE CLASS", hl=hl)
        # the one place that decides
        self.code_card(t, cap0("d3") + 0.5, T_LIFT2 - 0.1, UPDATE_CODE, "TIDY.CPP  ·  THE CONTROLLER DECIDES")
        # the new sensor: other data, the same functions
        kept = TIDY_NEW.classes["Sensor"]["data"][0]
        data = [j for j, l in enumerate(NEW_SENSOR_CODE) if re.match(rf"\s*\w+ {kept}\b", l)][0]
        asked = [j for j, l in enumerate(NEW_SENSOR_CODE) if "trainNear()" in l][0]

        def hl_new(j):
            if j == data:
                return envelope(t, T_LAND2 + 0.9, T_ASK - 0.2, 0.3, 0.4)
            return envelope(t, T_ASK - 0.1, cap1("e1") + 0.4, 0.3, 0.4) if j == asked else 0.0
        self.code_card(t, T_LAND2 - 0.1, cap0("z1") - 0.2, NEW_SENSOR_CODE, "TIDY.CPP  ·  THE NEW SENSOR", hl=hl_new,
                       stagger=0.06)

    def terminal(self, t):
        """What the programs print, and what the compiler says, bottom left."""
        ov = self.ov
        x, y, w, h = LEFT, 612, COL_W, 262
        a = max(envelope(t, a0, a1, 0.5, 0.5) for a0, a1 in TERM_ON)
        if a <= 0.003:
            return
        ov.panel(x, y, w, h, radius=16, alpha=0.78 * a, outline=0x8aa0c0, outline_alpha=0.16)
        ov.text(x + 26, y + 22, "TERMINAL", size=16, color=DIM, alpha=a, kind="semibold", tracking=2.2)
        seen = [e for e in TERM if e[0] <= t]
        if not seen:
            return
        start = max(i for i, e in enumerate(seen) if e[1] == "prompt")
        head = [e for e in seen[start:] if e[1] in ("prompt", "then")]
        rows = head + [e for e in seen[start:] if e[1] not in ("prompt", "then")][-(7 - len(head)):]
        lh, size = 29, 18
        for j, (t0, kind, text) in enumerate(rows):
            al = a * smooth(remap(t, t0, t0 + 0.25))
            yy = y + 54 + lh * j + lh / 2
            if kind in ("prompt", "then"):
                ov.text(x + 30, yy, "> " + text, size=size, color=DIM, alpha=al, kind="mono", anchor="lm")
            else:
                col = {"out": C_OUT, "err": C_ERR, "where": mix(C_ERR, TEXT, 0.55)}[kind]
                ov.text(x + 30, yy, text, size=size, color=col, alpha=al, kind="mono", anchor="lm")


def setup(width, height):
    t0 = time.time()
    check_programs()
    st = Stage(width, height, fog=(7.5, 17.0), shadow_extent=4.6, far=60.0)
    ov = Hud(1920, 1080, math_cache=os.path.join(_HERE, "coupling_cohesion.math.json"))
    painter = Painter(st, ov)
    reach = [(th.f, th.to) for th in painter.reach]
    print(f"[film] {TL.duration:.1f} s")
    print("[cohesion] jobs per function, tangled: "
          + ", ".join(f"{f['cls']}::{f['name']} {len(TANGLED.jobs(f['name']))}" for f in TANGLED.members())
          + f"; tidy: {max(len(TIDY.jobs(f['name'])) for f in TIDY.members())} in each of {len(TIDY.members())}")
    print(f"[coupling] tangled: {len(reach)} functions-into-foreign-data {reach}; tidy: "
          f"{sum(1 for th in painter.d_threads if not th.own and th.to in TIDY.data)}, and "
          f"{len(painter.calls)} calls, all from {sorted({th.cls for th in painter.calls})}")
    print(f"[new sensor] tangled.cpp no longer compiles in {sorted(BROKEN)} (lines {sorted(sum(BROKEN.values(), []))}); "
          f"tidy.cpp changes inside Sensor only")
    print(f"[setup] {time.time() - t0:.1f}s")

    def render(t):
        painter.pose(t)
        ov.begin()
        painter.draw2d(t)
        ov.fade(fade_in_out(t, TL.duration))
        ov.end()
        return st.frame(t, hud=ov)
    return render, painter.captions


if __name__ == "__main__":
    run("coupling_cohesion", TL.duration, setup, fps=FPS, speech=SPEECH)
