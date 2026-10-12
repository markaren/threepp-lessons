"""Throw, and catch.  Exceptions in C++, in about two minutes.

    python exceptions.py                               # the film (1080p60), lesson_out/exceptions.mp4
    python exceptions.py --stills 12,40,62             # individual frames
    python exceptions.py --sheet                       # contact sheet, one frame per 3 s
    python exceptions.py --preview --out preview.mp4   # 960x540 @ 30 fps

A lecture film for AIS1003 (object-oriented programming in C++), made to be watched rather
than read. A tank, a level sensor on top of it and a pump stand on the right; the program that
reads the sensor and runs the pump is a tower of floors beside them, one floor per running
function. The sensor's reading travels into the top floor and is handed down floor by floor.
An exception is thrown instead: the floor it came from is abandoned, every floor it falls
through shatters (that is stack unwinding), each floor's local objects are destroyed as it
goes, and the exception lands in the catch block that matches it. Thrown with nobody catching,
it falls through main too, and the program is terminated. The program is
programs/exceptions.cpp, a console program.

What is on screen was checked against that program:

* the code in the cards is read out of exceptions.cpp, between its `// [name]` markers, so
  every snippet is part of a program that compiles; the sensor's two readings are read out of
  its `sensorText`, and the exception's message is the one the program builds;
* the lines the terminal prints are what that program printed, in its three runs (the good
  day and the bad day; the old way, `exceptions old`; and `exceptions nocatch`, which is
  terminated, and whose destructors never ran). When its build (lesson_exceptions) is found,
  it is run again while the film is made and compared;
* the floors are the program's four functions, in call order. Their colours, sizes and the
  way they fall are the film's own, and so are the tank, the sensor and the pump: the program
  has no hardware, it has a string.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lesson  # noqa: E402
from lesson import (DIM, TEXT, Hud, OrbitCamera, Ring3D, Stage, card, clamp01, ease_out_back,  # noqa: E402
                    envelope, fade_in_out, remap, run, smooth, standard, tp)
from lesson import VOICE_LEAD  # noqa: E402
from threepp.lesson.scene import disc_texture  # noqa: E402

FPS = 60
MAX_SECONDS = 120.0          # the brief: two minutes at most
PROGRAM = os.path.join(lesson.PROGRAMS, "exceptions.cpp")

C_ACCENT = 0x4cc9f0          # the catch, and the sensor's eye
C_OUT = 0xa6e3a1             # what the program prints
C_ERR = 0xff5d73             # the exception, and what the runtime prints when nobody catches it
C_VALUE = 0xe4fff0           # a value on its way down
C_LAMP = 0xffc46b            # a local object, alive
C_WATER = 0x2f8fff
FLOOR_COLOURS = (0x5b9dff, 0x5ee27a, 0xffb347, 0xb983ff)
FLOOR_NAMES = ("main()", "runCycle()", "readLevel()", "parseLevel()")
FLOOR_Y = (0.0, 0.72, 1.44, 2.16)          # the height of each floor's centre
TOWER_X = 0.88                             # the tower stands right of the look point: cards go left
RIG_X, RIG_Z = TOWER_X + 1.72, -0.25       # the tank, right of the tower; the pump beside it
TANK_R, TANK_H = 0.3, 0.86
LAMP_FLOORS = (1, 2)                       # the floors with a Log object on them
LOOK = (0.5, 1.05, 0.0)
LOOK_RIG = (RIG_X + 0.25, 0.5, RIG_Z)

CPP_KEYWORDS = lesson.KEYWORDS["cpp"] | {"struct", "throw", "try", "catch", "if", "void", "explicit"}
WORDS = {"C++": "C plus plus", "ERR": "E R R", "main": "main"}

# What programs/exceptions.cpp printed (g++ 15.2 from MinGW, 2026-10-12): the plain run (a good
# day, then the bad day, caught in main), `exceptions old` (the sentinel, unchecked on one floor)
# and `exceptions nocatch` (stdout, then what the runtime wrote to stderr before terminating).
PRINTED = ["open  runCycle", "open  readLevel", "close readLevel", "pump off", "close runCycle",
           "open  runCycle", "open  readLevel", "close readLevel", "close runCycle", "caught: not a number: ERR"]
PRINTED_OLD = ["pump on"]
PRINTED_NOCATCH = ["open  runCycle", "open  readLevel"]
TERMINATED = ["terminate called after throwing an instance of 'std::invalid_argument'",
              "  what():  not a number: ERR"]

# ── the script ────────────────────────────────────────────────────────────────
# The narration sets the pace: each caption lasts as long as its spoken line (Kokoro, af_heart,
# measured in exceptions.speech.json) plus the voice's lead-in and tail and a small margin.
CAPTION_TEXT = {
    "title": "Throw, and catch. Exceptions, in C++.",
    "a0": "A tank, a level sensor, and a pump. Every cycle, the program reads the level and decides whether the pump should run.",
    "a1": "Inside, the program is a stack of calls: main runs a cycle, the cycle reads the level, and that means parsing the sensor's text.",
    "a2": "Most days the sensor sends a number. It is handed back down, floor by floor. The tank is full enough, so the pump stays off.",
    "a3": "But one day the sensor sends text. There is no number to hand back.",
    "b1": "The old answer is a special value. Minus one, say. And every floor on the way down has to check for it.",
    "b2": "One floor forgets, and the error walks through, dressed as a number. The pump starts, and the tank overflows.",
    "c1": "C++ has another way. The function that finds the problem throws.",
    "c2": "Nothing is returned. The call is abandoned, and its floor is gone.",
    "c3": "The exception falls, and every floor it passes goes the same way, unless that floor catches it. This is unwinding.",
    "c4": "As each floor goes, its local objects are destroyed. The destructors run, just as on a normal return.",
    "d1": "In main, a try block is waiting, with a catch for this type of exception.",
    "d2": "The error lands there, with its message intact. The pump stays off, and the program goes on.",
    "e1": "And if nobody catches it? The exception falls through main as well, and the program is terminated on the spot.",
    "e2": "Nothing was closed: the destructors never ran. So catch the exception where something can be done about it.",
    "z1": "Throw where the problem is found. Catch where it can be handled. The floors in between fall away, and clean up as they go.",
}
SPEECH = lesson.Speech(CAPTION_TEXT, os.path.join(_HERE, "exceptions.speech.json"), words=WORDS,
                       voice_only={"title"})
PLAN = [("open", 0.4, ["title"], 1.4),
        ("rig", 0.3, ["a0"], 0.3),
        ("stack", 0.3, ["a1", "a2", "a3"], 0.6),
        ("old", 0.4, ["b1", "b2"], 0.9),
        ("throw", 0.6, ["c1", "c2", "c3", "c4"], 0.6),
        ("catch", 0.3, ["d1", "d2"], 1.0),
        ("nobody", 0.5, ["e1", "e2"], 0.6),
        ("end", 0.4, ["z1"], 1.0),
        ("outro", 0.0, [], 5.5)]
TL, CAP = SPEECH.layout(PLAN, slack=0.7)      # the lines follow each other a little closer than the default

TITLE = ("A THREEPP LESSON  ·  C++ BASICS", "Throw, and catch", "Exceptions, and what happens to the stack")
SUMMARY = [(r"$\mathrm{throw}$", "Where the problem is found."),
           (r"$\mathrm{unwind}$", "Every floor in between falls, and its destructors run."),
           (r"$\mathrm{catch}$", "Where something can be done about it.")]
FOOTER = "The terminal in this film shows the output of programs/exceptions.cpp"


def cap0(k):
    return CAP[k][0]


def cap1(k):
    return CAP[k][1]


def say(k, frac):
    """About when the word a fraction `frac` of the way through line k is heard."""
    return CAP[k][0] + VOICE_LEAD + frac * SPEECH.seconds(k)


# when things happen, all from the captions
# the rig, then run 1: the good day
T_RIG = cap0("a0") - 0.2                                                         # the tank, the sensor, the pump
T_SENSOR, T_PUMPCHIP = say("a0", 0.12), say("a0", 0.40)                          # each one named
T_BUILD = [say("a1", 0.12), say("a1", 0.30), say("a1", 0.50), say("a1", 0.70)]   # the floors stack up
T_BEAM = say("a1", 0.74)                                                         # the top floor looks at the sensor
T_READ = say("a2", 0.16)                                                         # the reading leaves the sensor
T_VAL = T_READ + 0.8                                                             # and is a number, at the top
T_DESC = [say("a2", 0.42), say("a2", 0.42) + 0.55, say("a2", 0.42) + 1.1]        # it reaches floors 2, 1, main
T_OFF = say("a2", 0.86)                                                          # "the pump stays off"
T_RB2 = say("a3", 0.04)                                                          # the bad day: the tower again
T_ERR = say("a3", 0.36)                                                          # the sensor's text
# run 2: the old way
T_SENT = say("b1", 0.36)                                                         # "minus one"
T_SDESC = [say("b1", 0.68), say("b2", 0.30), say("b2", 0.52)]                    # it reaches floors 2, 1, main
T_FORGOT = say("b2", 0.10)                                                       # the floor that forgets
T_PUMP = say("b2", 0.66)                                                         # the pump starts
T_SPILL = say("b2", 0.88)                                                        # and the tank overflows
# run 3: thrown, and caught
T_RB3 = cap0("c1") - 0.1
T_THROW = say("c1", 0.86)                                                        # "throws"
T_SH = {3: say("c2", 0.48), 2: say("c3", 0.22), 1: say("c4", 0.16)}              # each floor shatters
T_FALL = {3: T_SH[3] + 0.25, 2: T_SH[2] + 0.25, 1: T_SH[1] + 0.25}               # and the exception drops
T_RING = say("d1", 0.62)                                                         # "a catch"
T_CATCH = say("d2", 0.12)                                                        # it lands
# run 4: nobody catches
T_RB4 = cap0("e1") + 0.1
T_X = say("e1", 0.32)
T_SH4 = {3: say("e1", 0.44), 2: say("e1", 0.44) + 0.3, 1: say("e1", 0.44) + 0.6, 0: say("e1", 0.74)}
T_HIT = T_SH4[0] + 0.55                                                          # it hits the ground
# the end: the tower is back while "so catch the exception" is said
T_RB5 = say("e2", 0.40)
T_TAG = [say("z1", 0.42), say("z1", 0.72), say("z1", 0.72) + 0.3, say("z1", 0.08)]  # catch, unwound x2, throw


# ── the program ───────────────────────────────────────────────────────────────
def program_source():
    with open(PROGRAM, encoding="utf-8") as f:
        return f.read().split("\n")


def program_lines(name):
    """The lines of exceptions.cpp between its two `// [name]` markers, without their common indent."""
    src = program_source()
    a, b = [i for i, l in enumerate(src) if l.strip() == f"// [{name}]"]
    lines = src[a + 1:b]
    ind = min(len(l) - len(l.lstrip(" ")) for l in lines if l.strip())
    return [l[ind:] for l in lines]


def sensor_texts():
    """The two strings the program's sensor sends (sensorText): the good day's, then the bad day's."""
    for line in program_source():
        m = re.search(r'return cycle == 0 \? "([^"]*)" : "([^"]*)";', line)
        if m:
            return m.group(1), m.group(2)
    raise RuntimeError("exceptions.cpp no longer has the sensorText line the film reads")


GOOD_TEXT, BAD_TEXT = sensor_texts()
MESSAGE = "not a number: " + BAD_TEXT          # what parseLevel puts in the exception
if PRINTED[-1] != "caught: " + MESSAGE or TERMINATED[-1].strip() != "what():  " + MESSAGE:
    raise RuntimeError("the recorded output does not carry the message the film shows")


def check_program():
    """Run the program's build, when there is one, in its three ways, and compare with the record."""
    try:
        exe = lesson.capture_exe("lesson_exceptions")
    except FileNotFoundError:
        print("[program] lesson_exceptions is not built here: the terminal shows the recorded output")
        return
    cwd = os.path.dirname(exe)
    for args, want_out, want_err in (([], PRINTED, []), (["old"], PRINTED_OLD, []),
                                     (["nocatch"], PRINTED_NOCATCH, TERMINATED)):
        r = subprocess.run([exe] + args, capture_output=True, cwd=cwd)
        out, err = r.stdout.decode().splitlines(), r.stderr.decode().splitlines()
        if out != want_out or err != want_err:
            raise RuntimeError(f"{exe} {' '.join(args)} prints {out} / {err}; the film shows {want_out} / {want_err}")
    print(f"[program] {os.path.basename(exe)} prints what the terminal shows, in all three runs")


# ── helpers ───────────────────────────────────────────────────────────────────
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


def ease_in(u):
    return u * u


def path(t, keys):
    """Position at t along keys [(time, (x, y, z), ease)]: each segment eased by the ease of
    the key it ends at. Before the first key, the first point; after the last, the last."""
    if t <= keys[0][0]:
        return np.array(keys[0][1], float)
    for (t0, p0, _), (t1, p1, ease) in zip(keys, keys[1:]):
        if t <= t1:
            u = ease(remap(t, t0, t1)) if t1 > t0 else 1.0
            return np.array(p0, float) + (np.array(p1, float) - np.array(p0, float)) * u
    return np.array(keys[-1][1], float)


# ── the stage: the rig, a tower of floors, the orbs that travel it, and the ring that catches ──
class Rig:
    """The tank, its level sensor and the pump: what the program is for."""

    def __init__(self, parent):
        self.group = tp.Group()
        self.group.position.set(RIG_X, 0.0, RIG_Z)
        parent.add(self.group)
        base = tp.Mesh(tp.CylinderGeometry(TANK_R + 0.06, TANK_R + 0.09, 0.05, 48),
                       standard(0x39424f, roughness=0.5, metalness=0.6))
        base.position.y = 0.025
        base.receive_shadow = True
        self.group.add(base)
        shell_mat = standard(0xe6eef8, roughness=0.15, emissive=0x8fb4d8, emissive_intensity=0.2)
        shell_mat.transparent = True
        shell_mat.opacity = 0.16
        shell_mat.side = tp.Side.Double
        shell_mat.depth_write = False
        shell = tp.Mesh(tp.CylinderGeometry(TANK_R, TANK_R, TANK_H, 48, 1, True), shell_mat)
        shell.position.y = 0.05 + TANK_H / 2
        self.group.add(shell)
        rim = tp.Mesh(tp.TorusGeometry(TANK_R, 0.012, 12, 64), standard(0x8aa0c0, roughness=0.4, metalness=0.5))
        rim.rotation.x = math.pi / 2
        rim.position.y = 0.05 + TANK_H
        self.group.add(rim)
        self.water_mat = standard(C_WATER, roughness=0.25)
        self.water = tp.Mesh(tp.CylinderGeometry(TANK_R - 0.015, TANK_R - 0.015, 1.0, 48), self.water_mat)
        self.water.cast_shadow = True
        self.group.add(self.water)
        self.spill = tp.Mesh(tp.CylinderGeometry(1.0, 1.0, 0.012, 64), self.water_mat)
        self.spill.position.y = 0.006
        self.group.add(self.spill)
        # the sensor, on the lid: a small box with an eye that shows what it is sending
        lid = tp.Mesh(tp.CylinderGeometry(TANK_R + 0.02, TANK_R + 0.02, 0.03, 48),
                      standard(0x39424f, roughness=0.5, metalness=0.6))
        lid.position.y = 0.05 + TANK_H + 0.015
        self.group.add(lid)
        self.sensor = tp.Group()
        self.sensor.position.set(0.0, 0.05 + TANK_H + 0.03, 0.0)
        self.group.add(self.sensor)
        box = tp.Mesh(tp.BoxGeometry(0.24, 0.13, 0.18), standard(0x2a3140, roughness=0.45, metalness=0.3))
        box.position.y = 0.065
        box.cast_shadow = True
        self.sensor.add(box)
        self.eye_mat = standard(0xffffff, roughness=0.3, emissive=C_ACCENT, emissive_intensity=1.6)
        eye = tp.Mesh(tp.SphereGeometry(0.03, 24, 16), self.eye_mat)
        eye.position.set(0.0, 0.075, 0.1)
        self.sensor.add(eye)
        # the pump, beside the tank, with a pipe up to the rim
        self.pump = tp.Group()
        self.pump.position.set(0.62, 0.0, 0.0)
        self.group.add(self.pump)
        self.pump_mat = standard(0x39424f, roughness=0.45, metalness=0.5, emissive=C_ERR, emissive_intensity=0.0)
        body = tp.Mesh(tp.BoxGeometry(0.3, 0.22, 0.26), self.pump_mat)
        body.position.y = 0.11
        body.cast_shadow = True
        self.pump.add(body)
        motor = tp.Mesh(tp.CylinderGeometry(0.09, 0.09, 0.16, 32), self.pump_mat)
        motor.position.y = 0.3
        motor.cast_shadow = True
        self.pump.add(motor)
        self.pipe_mat = standard(0x8aa0c0, roughness=0.4, metalness=0.5, emissive=C_WATER, emissive_intensity=0.0)
        pipe = tp.Mesh(tp.CylinderGeometry(0.02, 0.02, TANK_H + 0.1, 16), self.pipe_mat)
        pipe.position.set(-0.2, 0.05 + (TANK_H + 0.1) / 2, 0.0)
        self.pump.add(pipe)
        elbow = tp.Mesh(tp.CylinderGeometry(0.02, 0.02, 0.4, 16), self.pipe_mat)
        elbow.rotation.z = math.pi / 2
        elbow.position.set(-0.4, 0.05 + TANK_H + 0.1, 0.0)
        self.pump.add(elbow)
        self.level = 0.0

    def set(self, build, level, pump_on, spill, eye):
        """`build` 0..1 as it arrives; `level` 0..1 of the tank; `pump_on` 0..1; `spill` 0..1 the
        puddle's size; `eye` the sensor's colour (0xRRGGBB)."""
        vis = build > 1e-3
        self.group.visible = vis
        if not vis:
            return
        k = max(ease_out_back(build), 1e-4)
        self.group.scale.set(k, k, k)
        h = max(level * TANK_H, 1e-3)
        self.water.scale.set(1.0, h, 1.0)
        self.water.position.y = 0.05 + h / 2
        self.spill.visible = spill > 1e-3
        self.spill.scale.set(max(spill, 1e-3) * 0.78, 1.0, max(spill, 1e-3) * 0.78)
        self.pump_mat.emissive_intensity = 1.4 * pump_on
        self.pipe_mat.emissive_intensity = 0.8 * pump_on
        self.eye_mat.emissive = tp.Color(eye)


class Floor:
    """One running function: a slab of strips, so it can shatter. `set(build, kind, gone)`:
    build 0..1 as it arrives; then it leaves by `kind` ('return': it sinks and fades;
    'shatter': the strips drop away, the middle first) with `gone` 0..1."""
    N = 6
    W, D, H = 1.7, 1.1, 0.1
    GAP = 0.03

    def __init__(self, i, color, parent):
        self.i, self.color = i, color
        self.group = tp.Group()
        self.group.position.set(TOWER_X, FLOOR_Y[i], 0.0)
        parent.add(self.group)
        self.strips, self.mats = [], []
        sw = (self.W - self.GAP * (self.N - 1)) / self.N
        for k in range(self.N):
            m = standard(color, roughness=0.35, emissive=color, emissive_intensity=0.16)
            s = tp.Mesh(tp.BoxGeometry(sw, self.H, self.D), m)
            s.cast_shadow = True
            s.receive_shadow = True
            s.position.x = -self.W / 2 + sw / 2 + k * (sw + self.GAP)
            self.group.add(s)
            self.strips.append(s)
            self.mats.append(m)
        self.x0 = [s.position.x for s in self.strips]
        self.lamp = None
        if i in LAMP_FLOORS:
            self.lamp_mat = standard(0xfff0d0, roughness=0.4, emissive=C_LAMP, emissive_intensity=2.0)
            self.lamp = tp.Mesh(tp.SphereGeometry(0.055, 32, 24), self.lamp_mat)
            self.lamp.position.set(-0.62, self.H / 2 + 0.07, 0.36)
            self.lamp.cast_shadow = True
            self.group.add(self.lamp)
        self.present = 0.0          # how much of the floor is there, for the labels
        self.rise = 0.0

    def set(self, build, kind, gone, lamp_on=1.0, lamp_alpha=1.0):
        vis = build > 1e-3 and gone < 0.999
        self.group.visible = vis
        self.present = 0.0 if not vis else smooth(min(build * 2.5, 1.0)) * (1.0 - smooth(gone))
        if not vis:
            return
        rise = -0.35 * (1.0 - ease_out_back(build))
        self.rise = rise
        a_in = smooth(min(build * 2.5, 1.0))
        for k, (s, m) in enumerate(zip(self.strips, self.mats)):
            x, y, rz, o = self.x0[k], rise, 0.0, a_in
            if kind == "return" and gone > 0:
                u = smooth(gone)
                y -= 0.3 * u
                o *= 1.0 - u
            elif kind == "shatter" and gone > 0:
                d = 0.06 * abs(k - 2.5)
                u = clamp01((gone * 0.9 - d) / 0.72)
                sign = -1.0 if k < 3 else 1.0
                y -= 1.5 * u * u
                x += sign * 0.28 * u
                rz = -sign * 1.1 * u
                o *= 1.0 - smooth(u)
            s.position.set(x, y, 0.0)
            s.rotation.z = rz
            fade_mat(m, o)
            s.visible = o > 0.003
        if self.lamp is not None:       # the lamp outlasts the strips a little: its destructor is seen to run
            o = a_in * (1.0 - smooth(remap(gone, 0.55, 1.0))) * lamp_alpha
            self.lamp.position.y = self.H / 2 + 0.07 + rise
            self.lamp_mat.emissive_intensity = 2.0 * lamp_on
            self.lamp_mat.color = tp.Color(mix(0x2a2f38, 0xfff0d0, lamp_on))
            fade_mat(self.lamp_mat, o)
            self.lamp.visible = o > 0.003


class Orb:
    """A thing that travels the tower: a value, or an exception. A glowing ball with a halo
    and a small light, so the floors it passes are lit by it."""

    def __init__(self, color, parent, r=0.085, core=None):
        self.group = tp.Group()
        parent.add(self.group)
        self.mat = standard(color, roughness=0.3, emissive=color, emissive_intensity=1.5)
        self.ball = tp.Mesh(tp.SphereGeometry(r, 32, 24), self.mat)
        self.ball.cast_shadow = True
        self.group.add(self.ball)
        # the halo: a soft additive disc that always faces the camera
        self.halo_mat = tp.SpriteMaterial()
        self.halo_mat.map = disc_texture(96, soft=0.9)
        self.halo_mat.color = tp.Color(color)
        self.halo_mat.transparent = True
        self.halo_mat.blending = tp.Blending.Additive
        self.halo_mat.depth_write = False
        self.halo = tp.Sprite(self.halo_mat)
        self.halo.scale.set(r * 6.0, r * 6.0, 1.0)
        self.group.add(self.halo)
        self.r = r
        self.core = None
        self.shell = 1.0
        if core is not None:                # a value with something wrong inside: the shell is see-through
            self.core_mat = standard(core, roughness=0.3, emissive=core, emissive_intensity=2.2)
            self.core = tp.Mesh(tp.SphereGeometry(r * 0.55, 24, 16), self.core_mat)
            self.group.add(self.core)
            self.shell = 0.55
        self.light = tp.PointLight(color, 0.0, 3.5, 2.0)
        self.group.add(self.light)
        self.power = 5.0
        self.pos = np.zeros(3)
        self.alpha = 0.0

    def set(self, pos, opacity, scale=1.0, halo=1.0):
        vis = opacity > 0.003 and scale > 0.003
        self.group.visible = vis
        self.pos, self.alpha = np.asarray(pos, float), opacity if vis else 0.0
        self.light.intensity = self.power * opacity * min(scale, 1.0) if vis else 0.0
        if not vis:
            return
        self.group.position.set(*pos)
        self.ball.scale.set(scale, scale, scale)
        fade_mat(self.mat, opacity * self.shell)
        hs = self.r * 6.0 * scale * halo
        self.halo.scale.set(hs, hs, 1.0)
        self.halo_mat.opacity = 0.55 * opacity * min(1.0, 1.0 / max(halo, 1.0))
        if self.core is not None:
            self.core.scale.set(scale, scale, scale)
            fade_mat(self.core_mat, opacity)


def build_world(st):
    world = tp.Group()
    st.scene.add(world)
    rig = Rig(world)
    floors = [Floor(i, FLOOR_COLOURS[i], world) for i in range(4)]
    # the ring on main's floor: the catch block
    ring = Ring3D(C_ACCENT, radius=0.34, tube=0.014, parent=floors[0].group, emissive=1.4)
    ring.mesh.rotation.x = -math.pi / 2
    ring.mesh.position.y = Floor.H / 2 + 0.02
    # the ground, where an uncaught exception ends: a shock ring
    shock = Ring3D(C_ERR, radius=0.5, tube=0.02, parent=world, emissive=1.6)
    shock.mesh.rotation.x = -math.pi / 2
    shock.mesh.position.set(TOWER_X, 0.02, 0.0)
    value = Orb(C_VALUE, world)
    sentinel = Orb(0xbfffd0, world, core=C_ERR)
    exc = Orb(C_ERR, world)
    exc.power = 7.0
    return world, rig, floors, ring, shock, value, sentinel, exc


# ── what each floor does when ─────────────────────────────────────────────────
INF = 1e9
# per floor: [(arrive, leave, how)], in film order
EPISODES = {
    0: [(T_BUILD[0], T_SH4[0], "shatter"), (T_RB5, INF, None)],
    1: [(T_BUILD[1], T_DESC[2] + 0.1, "return"), (T_RB2, T_SDESC[2] + 0.1, "return"),
        (T_RB3, T_SH[1], "shatter"), (T_RB4, T_SH4[1], "shatter"), (T_RB5 + 0.25, INF, None)],
    2: [(T_BUILD[2], T_DESC[1] + 0.1, "return"), (T_RB2 + 0.25, T_SDESC[1] + 0.1, "return"),
        (T_RB3 + 0.25, T_SH[2], "shatter"), (T_RB4 + 0.2, T_SH4[2], "shatter"), (T_RB5 + 0.5, INF, None)],
    3: [(T_BUILD[3], T_DESC[0] + 0.1, "return"), (T_RB2 + 0.5, T_SDESC[0] + 0.1, "return"),
        (T_RB3 + 0.5, T_SH[3], "shatter"), (T_RB4 + 0.4, T_SH4[3], "shatter"), (T_RB5 + 0.75, INF, None)],
}
LEAVE_SECONDS = {"return": 0.55, "shatter": 0.9, None: 1.0}


def floor_state(i, t):
    """(build 0..1, how it leaves, gone 0..1, the episode) for floor i at t."""
    ep = None
    for e in EPISODES[i]:
        if e[0] <= t:
            ep = e
    if ep is None:
        return 0.0, None, 0.0, None
    a, b, how = ep
    build = remap(t, a, a + 0.55)
    gone = remap(t, b, b + LEAVE_SECONDS[how]) if how else 0.0
    return build, how, gone, ep


# the terminal: (time, kind, text); a 'prompt' starts a new run
TERM = []


def _run_lines(t_prompt, cmd, lines):
    """One run of the program: its prompt, then its lines, each (time, kind, text)."""
    TERM.append((t_prompt, "prompt", cmd))
    TERM.extend(lines)


_run_lines(T_BUILD[0] - 0.3, "exceptions", [
    (T_BUILD[1] + 0.35, "out", PRINTED[0]), (T_BUILD[2] + 0.35, "out", PRINTED[1]),
    (T_DESC[1] + 0.15, "out", PRINTED[2]), (T_DESC[2] + 0.2, "out", PRINTED[3]), (T_DESC[2] + 0.55, "out", PRINTED[4]),
    (T_RB2 + 0.35, "out", PRINTED[5]), (T_RB2 + 0.75, "out", PRINTED[6])])
_run_lines(cap0("b1") + 0.1, "exceptions old", [(T_PUMP, "out", PRINTED_OLD[0])])
# the third run shows the plain run again: the good day's lines are already there, dimmed
_run_lines(T_RB3 - 0.1, "exceptions", [(T_RB3 - 0.09 + 0.001 * j, "old", l) for j, l in enumerate(PRINTED[:5])] + [
    (T_RB3 + 0.35, "out", PRINTED[5]), (T_RB3 + 0.75, "out", PRINTED[6]),
    (T_SH[2] + 0.4, "out", PRINTED[7]), (T_SH[1] + 0.4, "out", PRINTED[8]), (T_CATCH + 0.35, "out", PRINTED[9])])
_run_lines(T_RB4 - 0.1, "exceptions nocatch", [
    (T_RB4 + 0.3, "out", PRINTED_NOCATCH[0]), (T_RB4 + 0.5, "out", PRINTED_NOCATCH[1]),
    (T_HIT + 0.25, "err", TERMINATED[0]), (T_HIT + 0.6, "err", TERMINATED[1])])
TERM.sort(key=lambda e: e[0])


class Painter:
    """Everything a frame needs: the stage's pose at t, then the 2D layer over it."""

    def __init__(self, st, ov, parts):
        self.st, self.ov = st, ov
        self.world, self.rig, self.floors, self.ring, self.shock, self.value, self.sentinel, self.exc = parts
        self.captions = SPEECH.captions(CAP)
        self.code = {k: program_lines(k) for k in ("sentinel", "parse", "dtor", "main")}
        self.lights = (st.key.intensity, st.hemi.intensity, st.rim.intensity)
        front = -90.0
        self.cam = OrbitCamera([
            (0.0, front + 22, 13.0, 4.2, LOOK_RIG, 32),
            (cap0("a0") + 1.0, front + 16, 12.0, 4.0, LOOK_RIG, 32),
            (cap0("a1") - 0.4, front + 16, 12.0, 4.0, LOOK_RIG, 32),
            (T_BUILD[1] + 0.3, front + 5, 12.0, 7.0, LOOK, 32),
            (cap0("b1"), front + 2, 11.0, 6.9, LOOK, 32),
            (cap0("c1"), front - 5, 10.0, 6.8, (0.5, 1.15, 0.0), 32),
            (T_CATCH, front - 12, 7.0, 6.2, (0.5, 0.85, 0.0), 32),
            (cap0("e1"), front - 5, 13.0, 7.0, (0.5, 1.0, 0.0), 32),
            (T_HIT + 1.2, front + 3, 19.0, 7.8, (0.5, 0.8, 0.0), 32),
            (T_RB5 + 1.0, front + 10, 13.0, 7.0, LOOK, 32),
            (TL.duration, front + 20, 12.0, 7.3, LOOK, 32),
        ], frame="yup")
        # the orbs' paths
        top = (TOWER_X, FLOOR_Y[3] + 0.33, 0.0)
        at = lambda i, dy=0.33: (TOWER_X, FLOOR_Y[i] + dy, 0.0)  # noqa: E731
        self.value_path = [(T_VAL, top, smooth), (T_DESC[0] - 0.5, top, smooth), (T_DESC[0], at(2), smooth),
                           (T_DESC[1], at(1), smooth), (T_DESC[2], at(0), smooth)]
        self.sent_path = [(T_SENT, top, smooth), (T_SDESC[0] - 0.5, top, smooth), (T_SDESC[0], at(2), smooth),
                          (T_SDESC[1] - 0.5, at(2), smooth), (T_SDESC[1], at(1), smooth),
                          (T_SDESC[2] - 0.5, at(1), smooth), (T_SDESC[2], at(0), smooth)]
        self.exc_path = [(T_THROW, top, smooth), (T_FALL[3], top, smooth), (T_FALL[3] + 0.7, at(2), ease_in),
                         (T_FALL[2], at(2), smooth), (T_FALL[2] + 0.7, at(1), ease_in),
                         (T_FALL[1], at(1), smooth), (T_FALL[1] + 0.7, at(0, 0.55), ease_in),
                         (T_CATCH, at(0, 0.55), smooth), (T_CATCH + 0.3, at(0, 0.12), ease_in)]
        self.exc4_path = [(T_X, top, smooth), (T_SH4[3] + 0.2, top, smooth), (T_SH4[2] + 0.2, at(2), ease_in),
                          (T_SH4[1] + 0.2, at(1), ease_in), (T_SH4[0] + 0.2, at(0), ease_in),
                          (T_HIT, (TOWER_X, 0.09, 0.0), ease_in)]
        self.plate = [(0.0, 0.0)] * 4          # each floor's nameplate, on the slab
        self.state = [(0.0, 0.0)] * 4          # and the spot beside it for a chip
        self.lamp_xy = {i: (0.0, 0.0) for i in LAMP_FLOORS}
        self.top_xy = (0.0, 0.0)
        self.sensor_xy = (0.0, 0.0)
        self.pump_xy = (0.0, 0.0)
        self.left_xy = (0.0, 0.0)

    # 3D ----------------------------------------------------------------------
    def dimmed(self, t):
        """How far the lights are down after the crash: 0 (normal) .. 1 (dark)."""
        return smooth(remap(t, T_HIT, T_HIT + 0.5)) * (1.0 - smooth(remap(t, T_RB5 - 0.4, T_RB5 + 0.4)))

    def water_level(self, t):
        """The tank, as a fraction: the good reading, then the old way fills it over the rim."""
        full = smooth(remap(t, T_PUMP + 0.3, T_SPILL + 0.4))
        reset = smooth(remap(t, T_RB3 - 0.3, T_RB3 + 0.6))
        return int(GOOD_TEXT) / 100.0 * (1.0 - full * (1.0 - reset)) + full * (1.0 - reset)

    def pose(self, t):
        in_old = cap0("b1") - 0.2 <= t < T_RB3 - 0.3
        pump_on = envelope(t, T_PUMP, T_RB3, 0.3, 0.5) * (0.8 + 0.2 * math.sin(9.0 * t))
        spill = smooth(remap(t, T_SPILL, T_SPILL + 2.2)) * (1.0 - smooth(remap(t, T_RB3 - 0.3, T_RB3 + 0.6)))
        err = max(envelope(t, T_ERR - 0.2, T_SENT + 0.2, 0.2, 0.3), envelope(t, T_RB3 + 0.9, T_THROW + 0.2, 0.2, 0.3),
                  envelope(t, T_RB4 + 0.8, T_X + 0.2, 0.2, 0.3))
        blink = 0.5 + 0.5 * math.sin(7.0 * t)
        self.rig.set(remap(t, T_RIG, T_RIG + 0.7), self.water_level(t), pump_on, spill,
                     mix(C_ACCENT, C_ERR, err * (0.6 + 0.4 * blink)))
        for i, fl in enumerate(self.floors):
            build, how, gone, ep = floor_state(i, t)
            on, al = 1.0, 1.0
            if i in LAMP_FLOORS and ep is not None:
                a, b, _ = ep
                if in_old:
                    al = 0.0                   # the old way's functions have no Log on them
                elif how == "shatter" and t > b + 0.35:
                    on = 1.0 - smooth(remap(t, b + 0.35, b + 0.6))   # the destructor runs as the floor goes
                if ep == EPISODES[i][3]:       # the run nobody catches: the lamp dies with the lights
                    on = 1.0 - self.dimmed(t)
            fl.set(build, how, gone, lamp_on=on, lamp_alpha=al)
        # the catch ring: lit from "catch" until the run nobody catches, and again at the end
        ra = max(envelope(t, T_RING, T_RB4 - 0.3, 0.6, 0.5), envelope(t, T_RB5 + 0.9, TL.end("end"), 0.6, 0.5))
        pulse = bump(t - T_CATCH - 0.3, 0.8)
        self.ring.set_opacity(ra * (0.55 + 0.45 * pulse))
        k = 1.0 + 0.35 * pulse
        self.ring.mesh.scale.set(k, k, 1.0)
        # the shock ring on the ground
        u = remap(t, T_HIT, T_HIT + 1.2)
        self.shock.set_opacity(0.9 * (1.0 - smooth(u)) if 0.0 < u < 1.0 else 0.0)
        k = 0.2 + 2.2 * (1.0 - (1.0 - u) ** 2)
        self.shock.mesh.scale.set(k, k, 1.0)
        # the orbs
        self.value.set(path(t, self.value_path), envelope(t, T_VAL, T_DESC[2] + 0.45, 0.4, 0.35),
                       scale=1.0 + 0.6 * bump(t - T_VAL, 0.5))
        self.sentinel.set(path(t, self.sent_path), envelope(t, T_SENT, T_SDESC[2] + 0.5, 0.4, 0.35),
                          scale=1.0 + 0.6 * bump(t - T_SENT, 0.5))
        landed = smooth(remap(t, T_CATCH + 0.3, T_CATCH + 0.75))
        self.exc.set(path(t, self.exc_path) if t < T_RB4 - 0.5 else path(t, self.exc4_path),
                     envelope(t, T_THROW, T_CATCH + 0.9, 0.15, 0.3) if t < T_RB4 - 0.5
                     else envelope(t, T_X, T_HIT + 0.25, 0.15, 0.2),
                     scale=(1.0 + 1.2 * bump(t - T_THROW, 0.45)) * (1.0 - landed) if t < T_RB4 - 0.5
                     else 1.0 + 1.2 * bump(t - T_X, 0.45),
                     halo=1.0 + 2.5 * bump(t - T_CATCH - 0.3, 0.8) + 2.0 * bump(t - T_HIT, 0.5))
        # the lights go down with the program
        d = 1.0 - 0.82 * self.dimmed(t)
        self.st.key.intensity, self.st.hemi.intensity, self.st.rim.intensity = (v * d for v in self.lights)
        eye, look, fov = self.cam(t)
        self.st.look(eye, look, fov)
        P = lambda p: tuple(self.st.project(p)[:2])  # noqa: E731
        for i in range(4):
            y = FLOOR_Y[i] + Floor.H / 2 + self.floors[i].rise
            self.plate[i] = P((TOWER_X - Floor.W / 2 + 0.04, y, -0.4))
            self.state[i] = P((TOWER_X + 0.18, y, -0.4))
        for i in LAMP_FLOORS:
            lamp = self.floors[i].lamp
            self.lamp_xy[i] = P((TOWER_X + lamp.position.x, FLOOR_Y[i] + lamp.position.y + 0.1, lamp.position.z))
        self.top_xy = P((TOWER_X, FLOOR_Y[3] + 0.33, 0.0))
        self.sensor_xy = P((RIG_X, 0.05 + TANK_H + 0.11, RIG_Z + 0.1))
        self.pump_xy = P((RIG_X + 0.62, 0.42, RIG_Z))
        self.left_xy = P((TOWER_X - Floor.W / 2 - 0.1, (FLOOR_Y[1] + FLOOR_Y[2]) / 2, 0.0))

    # 2D ----------------------------------------------------------------------
    def draw2d(self, t):
        ov = self.ov
        ov.title_card(t, *TITLE, C_ACCENT, t_in=0.6, t_out=TL.end("open") - 0.4, size=84)
        self.rig_beat(t)
        self.names(t)
        self.terminal(t)
        self.read_beat(t)
        self.old_beat(t)
        self.throw_beat(t)
        self.catch_beat(t)
        self.nobody_beat(t)
        self.end_beat(t)
        ov.captions(t, self.captions)
        ov.summary(t, TL.start("outro"), TL.end("outro"), SUMMARY, FOOTER, C_ACCENT, C_ACCENT, text_dx=300)

    def code_card(self, t, t_in, t_out, y, lines, title, hl=None, x=70, size=20, lh=28, stagger=0.25):
        """A house card of C++ that types itself in. Returns the card's height."""
        ov = self.ov
        cw = ov.text_width("0", size, "mono")
        w = max(len(l) for l in lines) * cw + 60
        h = 64 + lh * len(lines)
        a = envelope(t, t_in, t_out, 0.5, 0.5)
        if a <= 0.003:
            return h
        card(ov, x, y, w, h, a, title)
        ov.code(x + 30, y + 50, lines, "cpp", size, lh, a, hl=hl, keywords=CPP_KEYWORDS,
                reveal=lambda j: remap(t, t_in + 0.3 + stagger * j, t_in + 0.8 + stagger * j))
        return h

    def chip(self, x, y, text, alpha, color, size=22, anchor="mm", glow=1.0, text_color=None):
        """A small labelled panel at (x, y)."""
        if alpha <= 0.003:
            return
        ov = self.ov
        w, h = ov.text_width(text, size, "mono") + 34, size + 22
        x0 = x - w / 2 if anchor[0] == "m" else x if anchor[0] == "l" else x - w
        ov.panel(x0, y - h / 2, w, h, radius=10, alpha=0.82 * alpha, outline=mix(0x8aa0c0, color, glow),
                 outline_alpha=0.3 + 0.7 * glow, width=1.5 + 1.0 * glow)
        ov.text(x0 + w / 2, y, text, size=size, color=text_color or mix(TEXT, color, glow), alpha=alpha, kind="mono",
                anchor="mm")

    def names(self, t):
        """Each floor's function, on a nameplate at the back of the slab, while the floor is there."""
        gone = 1.0 - smooth(remap(t, TL.start("outro") - 0.2, TL.start("outro") + 0.6))
        for i, name in enumerate(FLOOR_NAMES):
            a = self.floors[i].present * gone
            x, y = self.plate[i]
            self.chip(x, y - 4, name, a, FLOOR_COLOURS[i], size=22, anchor="lm", glow=0.55)

    def rig_beat(self, t):
        """The tank, the sensor and the pump, named as they are introduced; the pump's state later."""
        gone = 1.0 - smooth(remap(t, TL.start("outro") - 0.2, TL.start("outro") + 0.6))
        sx, sy = self.sensor_xy
        a = envelope(t, T_SENSOR, cap0("a1") + 1.0, 0.3, 0.5)
        self.ov.text(sx, sy - 46, "level sensor", size=24, color=C_ACCENT, alpha=a, kind="semibold", anchor="mm")
        px, py = self.pump_xy
        a = envelope(t, T_PUMPCHIP, cap0("a1") + 1.0, 0.3, 0.5)
        self.ov.text(px, py - 40, "pump", size=24, color=DIM, alpha=a, kind="semibold", anchor="mm")
        self.chip(px, py - 40, "pump off", envelope(t, T_OFF, T_RB2 + 0.5, 0.3, 0.4) * gone, DIM, size=20)
        self.chip(px, py - 40, "pump on", envelope(t, T_PUMP, T_RB3 - 0.3, 0.3, 0.4) * gone, C_ERR, size=20)
        self.chip(px, py - 40, "pump off", envelope(t, T_CATCH + 0.9, cap1("d2") + 0.6, 0.3, 0.4) * gone, DIM, size=20)

    def terminal(self, t):
        """What the program prints, run by run, bottom left."""
        ov = self.ov
        x, y, w, h = 70, 596, 715, 276
        a = envelope(t, T_BUILD[0] - 0.5, TL.start("outro") + 0.3, 0.5, 0.5)
        if a <= 0.003:
            return
        hot = envelope(t, say("e2", 0.02), T_RB5 + 0.6, 0.3, 0.6)
        ov.panel(x, y, w, h, radius=16, alpha=0.78 * a, outline=mix(0x8aa0c0, C_ERR, hot),
                 outline_alpha=0.16 + 0.6 * hot, width=1.5 + 1.2 * hot)
        ov.text(x + 26, y + 22, "TERMINAL", size=16, color=DIM, alpha=a, kind="semibold", tracking=2.2)
        seen = [e for e in TERM if e[0] <= t]
        if not seen:
            return
        start = max(i for i, e in enumerate(seen) if e[1] == "prompt")
        rows = seen[start:][-7:]
        lh, size = 30, 18
        for j, (t0, kind, text) in enumerate(rows):
            al = a * smooth(remap(t, t0, t0 + 0.25))
            yy = y + 56 + lh * j + lh / 2
            if kind == "prompt":
                ov.text(x + 30, yy, "> " + text, size=size, color=DIM, alpha=al, kind="mono", anchor="lm")
            else:
                col = {"out": C_OUT, "old": mix(C_OUT, 0x0d131e, 0.55), "err": C_ERR}[kind]
                ov.text(x + 30, yy, text, size=size, color=col, alpha=al, kind="mono", anchor="lm")

    def beam(self, t, t_in, t_out):
        """The top floor asking the sensor: a dashed line from the sensor to the top of the tower."""
        a = envelope(t, t_in, t_out, 0.3, 0.4)
        if a <= 0.003:
            return
        self.ov.dashed(self.sensor_xy, self.top_xy, C_ACCENT, 2.0, 0.7 * a, dash=12, gap=9, phase=-140.0 * t)

    def reading(self, t, t0, text, color, t_out=None):
        """The sensor's text, travelling from the sensor to the top floor from t0, then waiting there."""
        u = smooth(remap(t, t0, t0 + 0.8))
        a = envelope(t, t0, t_out if t_out is not None else t0 + 0.8, 0.2, 0.2)
        (sx, sy), (tx, ty) = self.sensor_xy, self.top_xy
        x, y = sx + (tx - sx) * u, sy - 46 + (ty - 46 - (sy - 46)) * u - 60 * math.sin(math.pi * u)
        self.chip(x, y, f'"{text}"', a, color, size=24)

    def orb_label(self, orb, text, color, alpha=None, text_color=None):
        """A chip riding with an orb: what it carries."""
        a = orb.alpha if alpha is None else alpha
        if a <= 0.003:
            return
        x, y = self.st.project(orb.pos)[:2]
        self.chip(x + 64, y - 34, text, a, color, size=22, anchor="lm", text_color=text_color)

    def read_beat(self, t):
        """The good day: the top floor asks the sensor, and the number is handed down."""
        self.beam(t, T_BEAM, T_VAL + 0.1)
        self.reading(t, T_READ, GOOD_TEXT, C_VALUE)
        self.orb_label(self.value, GOOD_TEXT, C_VALUE)
        # the bad day: the sensor's text, over the top floor, until the old way takes it
        self.reading(t, T_ERR, BAD_TEXT, C_ERR, t_out=T_SENT + 0.2)

    def old_beat(self, t):
        """A special value: the floors that check, and the one that forgets."""
        self.code_card(t, cap0("b1") + 0.1, T_RB3 - 0.3, 64, self.code["sentinel"], "EXCEPTIONS.CPP",
                       hl=lambda j: envelope(t, T_SENT - 0.1, T_SDESC[0] + 0.3, 0.3, 0.5) if j == 2 else 0.0)
        self.orb_label(self.sentinel, "-1", C_VALUE)
        # floor 2 checks as the value arrives; floor 1 never does
        x2, y2 = self.state[2]
        self.chip(x2, y2 - 4, "checked", self.floors[2].present * envelope(t, T_SDESC[0] + 0.1, T_SDESC[1] + 0.3, 0.3, 0.3),
                  C_ACCENT, size=20, anchor="lm")
        x1, y1 = self.state[1]
        self.chip(x1, y1 - 4, "not checked", self.floors[1].present * envelope(t, T_FORGOT, T_SDESC[2] + 0.4, 0.3, 0.3),
                  C_ERR, size=20, anchor="lm")

    def throw_beat(self, t):
        """The function that found the problem throws; the floors between fall; the destructors run."""
        self.reading(t, T_RB3 + 1.0, BAD_TEXT, C_ERR, t_out=T_THROW + 0.1)
        t_out = cap0("d1") - 0.1
        h = self.code_card(t, cap0("c1") + 0.25, t_out, 64, self.code["parse"], "EXCEPTIONS.CPP",
                           hl=lambda j: envelope(t, T_THROW - 0.15, T_SH[2], 0.3, 0.5) if j == 2 else 0.0)
        lines = ["struct Log {", "    // ..."] + ["    " + l for l in self.code["dtor"]] + ["};"]
        self.code_card(t, cap0("c4") + 0.1, t_out, 64 + h + 22, lines, "A LOCAL OBJECT",
                       hl=lambda j: envelope(t, T_SH[1] + 0.3, t_out, 0.3, 0.5) if j == 3 else 0.0)
        if t < T_RB4 - 0.5:
            self.orb_label(self.exc, MESSAGE, C_ERR, text_color=C_ERR)
        # each Log's destructor, at the lamp, as its floor goes
        for i in LAMP_FLOORS:
            t0 = T_SH[i] + 0.35
            x, y = self.lamp_xy[i]
            a = envelope(t, t0, t0 + 1.6, 0.2, 0.4)
            pop = 8.0 * (1.0 - smooth(remap(t, t0, t0 + 0.35)))
            self.chip(x, y - 34 + pop, "~Log()", a, C_LAMP, size=20)
        # "unwinding", once it is named
        a = envelope(t, say("c3", 0.86), cap0("d1") - 0.2, 0.4, 0.5)
        x, y = self.left_xy
        self.ov.text(x, y, "unwinding", size=24, color=DIM, alpha=a, kind="light", anchor="rm")

    def catch_beat(self, t):
        """A try block and a catch, in main."""
        t_out = cap1("d2") + 0.6
        self.code_card(t, cap0("d1") + 0.1, t_out, 64, self.code["main"], "EXCEPTIONS.CPP",
                       hl=lambda j: (envelope(t, say("d1", 0.25), T_RING, 0.3, 0.3) if j == 0 else
                                     envelope(t, T_RING - 0.1, t_out, 0.3, 0.5) if j == 2 else
                                     envelope(t, T_CATCH + 0.3, t_out, 0.3, 0.5) if j == 3 else 0.0))

    def nobody_beat(self, t):
        """Nobody catches: a chip where the catch used to be."""
        self.reading(t, T_RB4 + 0.9, BAD_TEXT, C_ERR, t_out=T_X + 0.1)
        if t >= T_RB4 - 0.5:
            self.orb_label(self.exc, MESSAGE, C_ERR, text_color=C_ERR)
        x, y = self.state[0]
        self.chip(x, y - 4, "no catch", self.floors[0].present * envelope(t, T_RB4 + 0.6, T_SH4[0], 0.3, 0.3),
                  C_ERR, size=20, anchor="lm")
        a = envelope(t, T_HIT + 0.4, T_RB5 + 0.2, 0.3, 0.5)
        self.ov.text(960, 430, "terminated", size=44, color=C_ERR, alpha=a, kind="semibold", anchor="mm",
                     tracking=3)

    def end_beat(self, t):
        """The tower once more, each floor with its part."""
        t_out = TL.start("outro") + 0.3
        tags = [("catch", C_ACCENT), ("unwound", DIM), ("unwound", DIM), ("throw", C_ERR)]
        for i, (text, col) in enumerate(tags):
            a = self.floors[i].present * envelope(t, T_TAG[i], t_out, 0.3, 0.5)
            x, y = self.state[i]
            self.chip(x, y - 4, text, a, col, size=22, anchor="lm")


def setup(width, height):
    t0 = time.time()
    check_program()
    st = Stage(width, height, fog=(8.0, 20.0), shadow_extent=3.4)
    parts = build_world(st)
    ov = Hud(1920, 1080, math_cache=os.path.join(_HERE, "exceptions.math.json"))
    painter = Painter(st, ov, parts)
    over = TL.duration - MAX_SECONDS
    print(f"[film] {TL.duration:.1f} s" + (f": {over:.1f} s over the two minutes it may take" if over > 0 else ""))
    print(f"[program] the sensor sends {GOOD_TEXT!r}, then {BAD_TEXT!r}; the exception says {MESSAGE!r}")
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
    run("exceptions", TL.duration, setup, fps=FPS, speech=SPEECH)
