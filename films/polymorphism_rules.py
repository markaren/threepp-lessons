"""Polymorphism: one call, many types, and two rules for using it well.  A little over 3 min.

    python polymorphism_rules.py                               # the film (1080p60), lesson_out/polymorphism_rules.mp4
    python polymorphism_rules.py --stills 20,60,120            # individual frames
    python polymorphism_rules.py --sheet                       # contact sheet, one frame per 3 s
    python polymorphism_rules.py --preview --out preview.mp4   # 960x540 @ 30 fps

For students who have just met inheritance and virtual functions. Three parts: one function and
one loop that work for every type in a threepp scene; the promise a derived class makes (the
Liskov substitution principle, with the Square that cannot stand in for a Rectangle); and
composition, in a Thermostat that holds its sensor and in threepp's own Mesh. What is on screen:

* the C++ is read out of programs/polymorphism/scene.cpp, liskov.cpp and thermostat.cpp, between
  their "// [name]" markers; all three are CMake targets of this repository. The two type()
  lines are threepp's headers, without their [[nodiscard]];
* the three objects of the first part are a tp.Mesh, a tp.PointLight and a tp.Group under one
  parent, and the names the loop prints are those children's own class names (the lamp's
  glowing ball is a child of the light, there so the light can be seen);
* the plates of the second part are sized by `Rectangle` and `Square` below, which do what the
  C++ classes do, call for call;
* the mesh of the third part gets its shapes and looks through Mesh.set_geometry and
  Mesh.set_material, and the wall of meshes shares one geometry per column and one material
  per row.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lesson  # noqa: E402
from lesson import (DIM, TEXT, Hud, Keys, OrbitCamera, Stage, ease_out, ease_out_back, envelope,  # noqa: E402
                    fade_in_out, remap, run, smooth, standard, tp)
from lesson import card  # noqa: E402  (the house card)

FPS = 60
SOURCES = os.path.join(lesson.PROGRAMS, "polymorphism")

C_ACCENT = 0x4cc9f0
C_WARM = 0xffb347
C_OK = 0x5ee27a
C_BAD = 0xef476f
C_BOX = 0x4cc9f0
C_TYPE = 0xffcb6b          # a class name, as the code cards colour it
C_OUT = 0xa6e3a1           # what a program prints

CPP_KEYWORDS = lesson.KEYWORDS["cpp"] | {"for", "void", "class", "public", "override", "double", "virtual", "bool"}
WORDS = {"type()": "type"}                 # how the narrator says it

# ── the script ────────────────────────────────────────────────────────────────
# The narration sets the pace: each caption lasts as long as its spoken line (Kokoro,
# af_heart, measured in polymorphism_rules.speech.json) plus the voice's lead-in and tail.
CAPTION_TEXT = {
    "o1": "Polymorphism: one call, many types. And two rules for using it well.",
    "a1": "In threepp, a box, a lamp and a whole group of parts all enter the scene through the same function.",
    "a2": "It takes a pointer to an Object3D, the base class.",
    "a3": "A mesh is an Object3D. So is a light, and so is a group. That is inheritance.",
    "v1": "Now a loop asks every child the same question: what type are you? The loop only knows the base class.",
    "v2": "But type() is a virtual function, and each class overrides it.",
    "v3": "So the object's own type decides which one runs, while the program is running.",
    "v4": "That is polymorphism. Code written for the base class works with every class derived from it, even one "
          "that is written later.",
    "l1": "But inheriting is also a promise. Wherever code expects the base class, your class must work, without "
          "surprises.",
    "l2": "Here is the classic trap. This function sets a rectangle's width, then its height.",
    "l3": "It trusts that one does not change the other.",
    "l4": "In maths, a square is a rectangle. So let Square inherit, and keep its own rule: the sides stay equal.",
    "l5": "Now hand the function a square. It compiles.",
    "l6": "But setting the height also changed the width, and the caller gets the wrong shape.",
    "l7": "The compiler checks that the functions exist. It cannot check the promise.",
    "l8": "This is the Liskov substitution principle: a derived object must be able to stand in for its base.",
    "l9": "A derived class keeps the promise when it accepts what the base accepts, does what the base's function "
          "is meant to do, and keeps what the base guarantees.",
    "l10": "The fix is not a smarter square. Square and Rectangle are siblings: both are shapes, and neither stands "
           "in for the other.",
    "c1": "So ask before you inherit: can my class honestly stand in for the base, everywhere?",
    "c2": "If not, or if you only want to use what another class can do, hold it as a member instead.",
    "c3": "A thermostat uses a temperature sensor. It is not one. Inherit, and the sensor's functions become the "
          "thermostat's too. As a member, the sensor stays private.",
    "c4": "That is composition: has a, not is a. threepp does it too. A mesh is an Object3D, but it has a geometry, "
          "and it has a material.",
    "c5": "So any shape goes with any material, and you can swap either one while the program runs.",
    "c6": "With inheritance, every combination would need a class of its own.",
    "k1": "Polymorphism gives one call many types. Inherit when your class can stand in for its base. When you only "
          "want to reuse, compose.",
}
SPEECH = lesson.Speech(CAPTION_TEXT, os.path.join(_HERE, "polymorphism_rules.speech.json"), words=WORDS,
                       voice_only={"o1"})    # o1 is read aloud over the title card, not drawn
# beat, lead-in before its first caption, its captions, time after the last one
PLAN = [("open", 0.3, ["o1"], 0.9), ("many", 0.7, ["a1", "a2", "a3"], 0.6),
        ("virtual", 0.4, ["v1", "v2", "v3", "v4"], 1.0),
        ("promise", 0.8, ["l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9", "l10"], 1.0),
        ("compose", 0.8, ["c1", "c2", "c3", "c4", "c5", "c6"], 1.2), ("close", 0.3, ["k1"], 0.8),
        ("outro", 0.0, [], 8.0)]
TL, CAP = SPEECH.layout(PLAN, gap=0.45)


def cap0(k):
    return CAP[k][0]


def cap1(k):
    return CAP[k][1]


CUTS = [TL.end("open"), TL.end("virtual"), TL.end("promise")]     # the picture dips to black and changes set

# Each event hangs off the word of the narration it belongs to.
# part one: three objects enter the scene, then the loop visits them
T_NEW = [cap0("a1") + x for x in (1.6, 2.5, 3.3)]                  # the three create() lines
T_ADD = [cap0("a1") + x for x in (4.3, 4.9, 5.5)]                  # the three add() lines, and the objects
T_IS_A = [cap0("a3") + x for x in (0.5, 2.3, 3.3)]                 # a mesh, a light, a group
VISIT = [cap0("v1") + 3.2 + 0.85 * k for k in range(3)]            # the loop's three passes
VISIT_AGAIN = [cap0("v3") + 1.6 + 0.8 * k for k in range(3)]
T_OVERRIDE = cap0("v2") + 2.3

# part two: resize() on a Rectangle, then on a Square
MOVE = 0.9                                                         # how long a plate takes to change size
T_RESIZE = cap0("l2") + 1.9                                        # the function's card
T_RECT = cap0("l2") + 2.3
T_W1, T_H1 = cap0("l2") + 3.5, cap0("l2") + 4.6
T_CLASS, T_SQUARE = cap0("l4") + 2.6, cap0("l4") + 3.0             # the Square's card, and its plate
T_W2, T_H2 = cap0("l5") + 2.6, cap0("l6") + 0.9
T_WRONG = cap0("l6") + 2.7
T_KEEP = [cap0("l9") + x for x in (2.5, 4.3, 6.9)]                 # the three ways to keep the promise

# part three: two Thermostats, then one mesh with new shapes and looks, then every combination
T_LEAK, T_MEMBER, T_PRIVATE = cap0("c3") + 5.2, cap0("c3") + 8.1, cap0("c3") + 9.4
T_THREEPP = cap0("c4") + 2.9
T_HERO = cap0("c4") + 4.7
T_GEO_NOTE, T_MAT_NOTE = cap0("c4") + 7.1, cap0("c4") + 8.4
T_GEO = [cap0("c5") + 0.7, cap0("c5") + 3.2]
T_MAT = [cap0("c5") + 1.8, cap0("c5") + 4.1]
T_WALL = cap1("c5") + 0.1
T_NAMES = cap0("c6") + 1.5
T_COMPOSED = cap0("k1") + 0.4


# ── the code on screen ────────────────────────────────────────────────────────
def region(file, name):
    """The lines of a C++ source between `// [name]` and the next `// [end]`, without their indent."""
    out, on = [], False
    with open(os.path.join(SOURCES, file), encoding="utf-8") as f:
        for line in f.read().splitlines():
            s = line.strip()
            if s == f"// [{name}]":
                on = True
            elif on and s == "// [end]":
                break
            elif on:
                out.append(line)
    if not out:
        raise ValueError(f"{file} has no region [{name}]")
    ind = min(lesson.indent(l) for l in out if l.strip())
    return [l[ind:] for l in out]


ADD = region("scene.cpp", "add")
LOOP = region("scene.cpp", "loop")
SWAP = region("scene.cpp", "swap")
RESIZE = region("liskov.cpp", "resize")
SQUARE = region("liskov.cpp", "square")
IS_A = region("thermostat.cpp", "is_a")
HAS_A = region("thermostat.cpp", "has_a")
ADD_DECL = ["void add(const std::shared_ptr<Object3D>& object);"]
TYPE_DECL = ["// Object3D.hpp",
             "virtual std::string type() const;",
             "",
             "// Mesh.hpp, PointLight.hpp, Group.hpp",
             "std::string type() const override;"]


def line_of(lines, text):
    return next(j for j, l in enumerate(lines) if text in l)


# ── the Rectangle and the Square (programs/polymorphism/liskov.cpp, call for call) ──
class Rectangle:
    def __init__(self):
        self.width, self.height = 1.0, 1.0

    def set_width(self, w):
        self.width = w

    def set_height(self, h):
        self.height = h


class Square(Rectangle):
    def set_width(self, w):
        Rectangle.set_width(self, w)
        Rectangle.set_height(self, w)

    def set_height(self, h):
        Rectangle.set_width(self, h)
        Rectangle.set_height(self, h)


ASKED = (2.0, 0.5)             # liskov.cpp's w and h
UNIT = 0.6                     # metres on stage per unit of width or height


def resize(r, w, h):
    """resize() of liskov.cpp, and the (width, height) before it, between its two calls and after."""
    sizes = [(r.width, r.height)]
    r.set_width(w)
    sizes.append((r.width, r.height))
    r.set_height(h)
    sizes.append((r.width, r.height))
    return sizes


def size_at(t, sizes, t_w, t_h):
    s = np.array(sizes)
    return s[0] + (s[1] - s[0]) * smooth(remap(t, t_w, t_w + MOVE)) + (s[2] - s[1]) * smooth(remap(t, t_h, t_h + MOVE))


# ── the picture ───────────────────────────────────────────────────────────────
LEFT, TOP = 70, 64             # the cards' corner

BOX_AT, LAMP_AT, RIG_AT = np.array([-0.95, 0.3, 0.0]), np.array([0.0, 1.02, 0.15]), np.array([0.9, 0.0, 0.0])
TRIO = [  # where each object's ring, label and printed name go: centre, ring radius (px), under it, over it
    (BOX_AT, 135, BOX_AT + (0, -0.3, 0.55), BOX_AT + (0, 0.55, 0)),
    (LAMP_AT, 70, LAMP_AT + (0, -0.24, 0), LAMP_AT + (0, 0.2, 0)),
    (RIG_AT + (0, 0.36, 0), 150, RIG_AT + (0, 0, 0.6), RIG_AT + (0, 0.98, 0)),
]
STATION_X = (-0.75, 0.75)       # the Rectangle's plate, the Square's
HERO_AT = np.array([0.3, 0.72, 0.0])
WALL_X, WALL_Y = [-0.2, 0.52, 1.24, 1.96], [1.94, 1.12, 0.3]
HERO_SIZE = 1.35              # the one mesh, larger than the wall's
SHAPES, LOOKS = ["Box", "Ball", "Knot", "Cone"], ["Blue", "Shiny", "Wire"]

LOOK_TITLE, LOOK_WALL = (-0.9, 1.1, 0.0), (-0.55, 1.1, 0.0)
LOOK1, LOOK2, LOOK3 = (-1.15, 0.42, 0.0), (-1.25, 0.42, 0.0), (-1.15, 0.6, 0.0)


def _camera():
    e, jump = TL.end, 0.05
    return OrbitCamera([    # (time, azimuth, elevation, distance, look point, fov)
        (0.0, -97, 15, 8.4, LOOK_TITLE, 32), (e("open"), -91, 15, 7.8, LOOK_TITLE, 32),
        (e("open") + jump, -87, 10, 5.4, LOOK1, 32), (e("virtual"), -93, 11, 5.4, LOOK1, 32),
        (e("virtual") + jump, -89, 5, 8.5, LOOK2, 22), (e("promise"), -91, 6, 8.5, LOOK2, 22),
        (e("promise") + jump, -87, 11, 5.0, LOOK3, 32), (T_WALL - 0.2, -92, 12, 5.0, LOOK3, 32),
        (T_WALL + 1.8, -90, 13, 7.6, LOOK_WALL, 32), (TL.duration, -100, 14, 7.8, LOOK_WALL, 32),
    ], frame="yup", drift=((0.8, 0.19), (0.4, 0.15)))


CAMERA = _camera()
SHADOWS = Keys([(0.0, (0.9, 0, 0)), (CUTS[0], (0.9, 0, 0)), (CUTS[0] + 0.05, (0.2, 0, 0)), (CUTS[1], (0.2, 0, 0)),
                (CUTS[1] + 0.05, (0.25, 0, 0)), (CUTS[2], (0.25, 0, 0)), (CUTS[2] + 0.05, (0.5, 0, 0)),
                (T_WALL, (0.5, 0, 0)), (T_WALL + 1.5, (0.9, 0, 0))])

SUMMARY = [(r"$\mathrm{virtual}$", "One call through the base class; each object answers for itself."),
           (r"$\mathrm{is\ a}$", "Inherit only if your class can stand in for its base."),
           (r"$\mathrm{has\ a}$", "To reuse what another class can do, hold it as a member.")]


def hop(t, times, height=0.1, dur=0.5):
    """A small jump at each of `times`."""
    return max(height * math.sin(math.pi * remap(t, t0, t0 + dur)) for t0 in times)


def code_box(ov, x, y, lines, title, a, size=21, lh=31, reveal=None, hl=None, extra=0, min_w=0):
    """A house card of C++ with its corner at (x, y), `extra` px taller than its code; (width, height)."""
    cw = ov.text_width("0", size, "mono")
    w = max(max(len(l) for l in lines) * cw + 60, min_w)
    h = 64 + lh * len(lines) + extra
    if a > 0.003:
        card(ov, x, y, w, h, a, title)
        ov.code(x + 30, y + 50, lines, "cpp", size, lh, a, reveal=reveal, hl=hl, keywords=CPP_KEYWORDS)
    return w, h


def class_box(ov, cx, cy, name, a, color=C_TYPE, size=21, h=44):
    """A class in a diagram, centred on (cx, cy); its (width, height)."""
    w = ov.text_width(name, size, "mono") + 36
    ov.panel(cx - w / 2, cy - h / 2, w, h, radius=8, fill=0x16202f, alpha=0.92 * a, outline=color, outline_alpha=0.5)
    ov.text(cx, cy, name, size=size, color=color, alpha=a, kind="mono", anchor="mm")
    return w, h


def is_a(ov, children, parent, alphas, color=DIM):
    """Inheritance as UML draws it: a hollow triangle under the parent (the middle of its lower
    edge), and a line up to it from each child (the middle of its upper edge)."""
    px, py = parent
    base, bus = py + 16, py + 30
    for (cx, cy), a in zip(children, alphas):
        ov.line([(cx, cy), (px, base)] if abs(cx - px) < 1 else [(cx, cy), (cx, bus), (px, bus), (px, base)],
                color, 2.0, a)
    ov.line([(px, py), (px - 9, base), (px + 9, base), (px, py)], color, 2.0, max(alphas))


def has_a(ov, owner, parts, alphas, color=DIM, stub=28):
    """Composition as UML draws it: a filled diamond at the owner (the middle of its right
    edge), and a line from it to each part (the middle of its left edge)."""
    ox, oy = owner
    d = 11
    turn = ox + 2 * d + stub
    for (px, py), a in zip(parts, alphas):
        ov.line([(ox + 2 * d, oy), (px, py)] if abs(py - oy) < 1 else [(ox + 2 * d, oy), (turn, oy), (turn, py), (px, py)],
                color, 2.0, a)
    ov.arrow2d((ox + d, oy), (ox, oy), color, 2.0, head=d, alpha=max(alphas))
    ov.arrow2d((ox + d, oy), (ox + 2 * d, oy), color, 2.0, head=d, alpha=max(alphas))


def tick(ov, x, y, s, a):
    ov.line([(x - s, y), (x - 0.3 * s, y + 0.7 * s), (x + s, y - 0.8 * s)], C_OK, 5.0, a)


def cross(ov, x, y, s, a):
    ov.line([(x - s, y - s), (x + s, y + s)], C_BAD, 5.0, a)
    ov.line([(x - s, y + s), (x + s, y - s)], C_BAD, 5.0, a)


def para(ov, x, y, text, width, a, size=26, color=TEXT, kind="regular"):
    """Text wrapped to `width`, its first line's top at y; the height it took."""
    lines = ov.wrap(text, size, width, kind)
    for j, l in enumerate(lines):
        ov.text(x, y + j * size * 1.36, l, size=size, color=color, alpha=a, kind=kind)
    return len(lines) * size * 1.36


class Painter:
    def __init__(self, st, parts, ov):
        self.st, self.p, self.ov = st, parts, ov
        self.captions = SPEECH.captions(CAP)
        self.shape = self.look = 0            # which geometry and material the hero mesh has now

    # 3D ----------------------------------------------------------------------
    def set3d(self, t):
        st, p = self.st, self.p
        eye, look, fov = CAMERA(t)
        st.look(eye, look, fov)
        st.follow(SHADOWS(t))
        one = CUTS[0] <= t < CUTS[1]
        two = CUTS[1] <= t < CUTS[2]
        three = CUTS[2] <= t

        # part one: the objects arrive with their add() lines, and hop when the loop reaches them
        p["world"].visible = one
        for k, (o, at) in enumerate(zip(p["trio"], (BOX_AT, LAMP_AT, RIG_AT))):
            s = ease_out_back(remap(t, T_ADD[k], T_ADD[k] + 0.5))
            o.visible = s > 0.002
            o.scale.set(max(s, 1e-3), max(s, 1e-3), max(s, 1e-3))
            o.position.set(at[0], at[1] + hop(t, (VISIT[k], VISIT_AGAIN[k])), at[2])
        p["trio"][0].rotation.y = 0.5 + 0.35 * t
        p["trio"][2].rotation.y = 0.6 * t
        p["trio"][1].intensity = p["lamp_power"] * smooth(remap(t, T_ADD[1], T_ADD[1] + 0.6)) if one else 0.0

        # part two: each plate is as wide and as high as its Rectangle or Square is at t
        for plate, x, sizes, t_in, t_w, t_h in zip(p["plates"], STATION_X, p["sizes"], (T_RECT, T_SQUARE),
                                                   (T_W1, T_W2), (T_H1, T_H2)):
            s = ease_out_back(remap(t, t_in, t_in + 0.5))
            w, h = size_at(t, sizes, t_w, t_h) * UNIT * max(s, 1e-3)
            plate.visible = two and s > 0.002
            plate.scale.set(w, h, 1.0)
            plate.position.set(x, h / 2 + 0.003, 0.0)

        # part three: one mesh that changes shape and look, then every combination of them
        s = ease_out_back(remap(t, T_HERO, T_HERO + 0.6)) * (1 - smooth(remap(t, T_WALL, T_WALL + 0.4)))
        hero, wire = p["hero"], p["wire"]
        hero.visible = p["pedestal"].visible = three and s > 0.002
        shape, look_ = sum(t >= x for x in T_GEO), sum(t >= x for x in T_MAT)
        if shape != self.shape:
            hero.set_geometry(p["geometries"][shape])
            wire.set_geometry(p["geometries"][shape])
            self.shape = shape
        if look_ != self.look:
            hero.set_material(p["materials"][look_])
            self.look = look_
        s *= 1 - 0.25 * max(envelope(t, x - 0.15, x + 0.25, 0.15, 0.25) for x in T_GEO + T_MAT)
        s = max(s * HERO_SIZE, 1e-3)
        hero.scale.set(s, s, s)
        hero.rotation.set(0.3, 0.6 * t, 0.0)
        down = 1 - smooth(remap(t, T_WALL, T_WALL + 0.4))
        p["pedestal"].scale.set(max(down, 1e-3), 1.0, max(down, 1e-3))
        wa = envelope(t, T_GEO_NOTE, T_MAT_NOTE + 0.3, 0.4, 0.4)
        wire.visible = wa > 0.003
        wire.material.opacity = 0.9 * wa
        on = t < CUTS[0] or t >= T_WALL
        for k, m in enumerate(p["wall"]):
            s = 1.0 if t < CUTS[0] else ease_out_back(remap(t, T_WALL + 0.3 + 0.07 * k, T_WALL + 0.8 + 0.07 * k))
            m.visible = on and s > 0.002
            m.scale.set(max(s, 1e-3), max(s, 1e-3), max(s, 1e-3))
            m.rotation.set(0.3, 0.5 * t + 0.5 * k, 0.0)

    # 2D ----------------------------------------------------------------------
    def draw2d(self, t):
        ov = self.ov
        a = envelope(t, 0.0, CUTS[0] + 0.3, 0.01, 0.3)
        ov.panel(-20, -20, ov.W + 40, ov.H + 40, radius=0, fill=0x05080d, alpha=0.55 * a)
        ov.title_card(t, "A THREEPP LESSON  ·  C++", "Polymorphism",
                      "One call, many types, and two rules for using it well", C_ACCENT, t_in=0.3,
                      t_out=CUTS[0] - 0.4)
        for first, last, text in (("many", "virtual", "ONE CALL, MANY TYPES"),
                                  ("promise", "promise", "RULE ONE  ·  CAN IT STAND IN FOR ITS BASE?"),
                                  ("compose", "close", "RULE TWO  ·  HAS A, NOT IS A")):
            ov.text(ov.W - LEFT, 44, text, size=18, color=C_ACCENT, kind="semibold", anchor="rm", tracking=3,
                    alpha=envelope(t, TL.start(first) + 0.5, TL.end(last) - 0.3, 0.6, 0.4))
        self.many(t)
        self.virtual(t)
        self.promise(t)
        self.compose(t)
        ov.captions(t, self.captions)
        ov.summary(t, TL.start("outro"), TL.end("outro"), SUMMARY,
                   "Every frame of this film was drawn by threepp's OpenGL renderer", C_ACCENT, C_ACCENT)

    def trio_labels(self, t):
        """Each object's class under it, and from a3 what that makes it."""
        ov, st = self.ov, self.st
        a = envelope(t, TL.start("many"), CUTS[1] - 0.3, 0.3, 0.4)
        if a <= 0.003:
            return
        for k, (name, (_, _, under, _)) in enumerate(zip(self.p["types"], TRIO)):
            q = st.project(under)
            la = a * smooth(remap(t, T_ADD[k] + 0.2, T_ADD[k] + 0.7))
            ov.text(q[0], q[1], name, size=24, color=C_TYPE, alpha=la, kind="mono", anchor="ma")
            ov.text(q[0], q[1] + 34, "is an Object3D", size=19, color=DIM, anchor="ma",
                    alpha=la * smooth(remap(t, T_IS_A[k], T_IS_A[k] + 0.5)))

    def many(self, t):
        ov = self.ov
        self.trio_labels(t)
        a = envelope(t, TL.start("many") + 0.3, TL.end("many") + 0.1, 0.5, 0.5)
        if a <= 0.003:
            return
        times = T_NEW + [0.0] + [x - 0.35 for x in T_ADD]

        def hl(j):
            return envelope(t, T_ADD[j - 4] - 0.1, T_ADD[j - 4] + 0.9, 0.2, 0.4) if j >= 4 else 0.0
        w, h = code_box(ov, LEFT, TOP, ADD, "ONE FUNCTION, THREE TYPES", a, hl=hl,
                        reveal=lambda j: remap(t, times[j], times[j] + 0.4))
        y = TOP + h + 22
        da = a * smooth(remap(t, cap0("a2") + 0.2, cap0("a2") + 0.8))
        _, h = code_box(ov, LEFT, y, ADD_DECL, "IN Object3D.hpp", da, min_w=w)
        # the classes of a3, each under what it inherits from
        y += h + 22
        ha = a * smooth(remap(t, cap0("a3") - 0.2, cap0("a3") + 0.4))
        if ha <= 0.003:
            return
        card(ov, LEFT, y, w, 290, ha, "IS A")
        cx, y0, y1, y2 = LEFT + w / 2, y + 82, y + 162, y + 246
        nodes = [("Mesh", cx - 190, y1, T_IS_A[0]), ("Light", cx, y1, T_IS_A[1]), ("Group", cx + 190, y1, T_IS_A[2]),
                 ("PointLight", cx, y2, T_IS_A[1])]
        shown = [ha * smooth(remap(t, t_in, t_in + 0.5)) for *_, t_in in nodes]
        is_a(ov, [(x, yy - 22) for _, x, yy, _ in nodes[:3]], (cx, y0 + 22), shown[:3])
        is_a(ov, [(cx, y2 - 22)], (cx, y1 + 22), shown[3:])
        for (name, x, yy, _), na in zip(nodes, shown):
            class_box(ov, x, yy, name, na)
        class_box(ov, cx, y0, "Object3D", ha)

    def virtual(self, t):
        ov, st = self.ov, self.st
        a = envelope(t, TL.start("virtual") + 0.2, CUTS[1] - 0.3, 0.5, 0.4)
        if a <= 0.003:
            return
        lh = 31
        w, h = code_box(ov, LEFT, TOP, LOOP, "ONE LOOP, ONE QUESTION", a, extra=lh * 3 + 26, min_w=640,
                        reveal=lambda j: remap(t, cap0("v1") + 0.3 + 0.35 * j, cap0("v1") + 0.9 + 0.35 * j),
                        hl=lambda j: envelope(t, cap0("v4") + 2.0, cap1("v4"), 0.4, 0.4) if j == 0 else 0.0)
        yy = TOP + 50 + lh * len(LOOP) + 10
        ov.panel(LEFT + 12, yy - 4, w - 24, lh * 3 + 12, radius=8, fill=0x070a10, alpha=0.8 * a)
        for k, name in enumerate(self.p["types"]):
            ov.text(LEFT + 30, yy + 2 + lh * k + lh / 2, name, size=21, color=C_OUT, kind="mono", anchor="lm",
                    alpha=a * smooth(remap(t, VISIT[k] + 0.15, VISIT[k] + 0.45)))
        # the loop's pass: a ring on the object it has reached, and what that object answers
        for times, hold in ((VISIT, 0.85), (VISIT_AGAIN, 0.8)):
            for k, (centre, radius, _, over) in enumerate(TRIO):
                ra = a * envelope(t, times[k], times[k] + hold, 0.15, 0.25)
                if ra <= 0.003:
                    continue
                c = st.project(centre + (0, hop(t, (times[k],)), 0))
                ov.circle(c[0], c[1], radius, outline=C_OUT, width=3.0, alpha=0.9 * ra)
                q = st.project(over)
                name = self.p["types"][k]
                bw = ov.text_width(name, 22, "mono") + 32
                ov.panel(q[0] - bw / 2, q[1] - 42, bw, 40, radius=10, fill=0x0d131e, alpha=0.9 * ra, outline=C_OUT,
                         outline_alpha=0.6)
                ov.text(q[0], q[1] - 22, name, size=22, color=C_OUT, alpha=ra, kind="mono", anchor="mm")
        # the two declarations of v2
        y = TOP + h + 22
        da = a * smooth(remap(t, cap0("v2") + 0.2, cap0("v2") + 0.8))

        def hl(j):
            if j == 1:
                return envelope(t, cap0("v2") + 0.9, T_OVERRIDE + 0.2, 0.3, 0.4)
            return envelope(t, T_OVERRIDE, cap1("v3"), 0.3, 0.4) if j == 4 else 0.0
        _, h = code_box(ov, LEFT, y, TYPE_DECL, "DECLARED IN THE BASE, AGAIN IN EACH CLASS", da, hl=hl, min_w=w,
                        reveal=lambda j: 1.0 if j < 3 else remap(t, T_OVERRIDE - 0.4, T_OVERRIDE))
        y += h + 22
        na = a * smooth(remap(t, cap0("v4") + 3.4, cap0("v4") + 4.0))
        if na > 0.003:
            card(ov, LEFT, y, w, 150, na, "WRITTEN FOR THE BASE CLASS")
            para(ov, LEFT + 28, y + 56, "The loop names no Mesh, no PointLight and no Group. A new class "
                 "needs no change to it.", w - 56, na, size=24)

    def station(self, t, k, t_in, t_done, good):
        """What resize() was asked for, as a dashed frame round plate k, and how it went."""
        ov, st = self.ov, self.st
        a = envelope(t, t_in, CUTS[2] - 0.3, 0.5, 0.4)
        if a <= 0.003:
            return
        x, (w, h) = STATION_X[k], np.array(ASKED) * UNIT
        corners = [(x - w / 2, 0.0), (x + w / 2, 0.0), (x + w / 2, h), (x - w / 2, h)]
        px = [st.project((cx, cy, 0.035))[:2] for cx, cy in corners]
        done = smooth(remap(t, t_done, t_done + 0.4))
        colour = 0xdfe8ff if done < 0.5 else (C_OK if good else C_BAD)
        for p0, p1 in zip(px, px[1:] + px[:1]):
            ov.dashed(p0, p1, colour, 2.2, 0.85 * a, dash=9, gap=7)
        ov.panel(px[3][0] - 2, px[3][1] - 40, 104, 30, radius=8, fill=0x0d131e, alpha=0.8 * a * (1 - done))
        ov.text(px[3][0] + 50, px[3][1] - 25, "asked for", size=17, color=DIM, alpha=a * (1 - done), anchor="mm")
        q = st.project((x, 0.0, 0.5))
        ov.text(q[0], q[1], "Rectangle" if k == 0 else "Square", size=24, color=C_TYPE, alpha=a, kind="mono",
                anchor="ma")
        text = "as asked" if good else "not what was asked"
        tw = ov.text_width(text, 22, "semibold")
        va = a * done
        if good:
            tick(ov, q[0] - tw / 2 - 12, q[1] + 52, 9, va)
        else:
            cross(ov, q[0] - tw / 2 - 12, q[1] + 52, 8, va)
        ov.text(q[0] + 12, q[1] + 52, text, size=22, color=C_OK if good else C_BAD, alpha=va, kind="semibold",
                anchor="mm")

    def promise(self, t):
        ov = self.ov
        if not CUTS[1] <= t < CUTS[2]:
            return
        # l1: the promise, in words
        a = envelope(t, cap0("l1") + 0.2, T_RESIZE - 0.2, 0.5, 0.4)
        if a > 0.003:
            card(ov, LEFT, TOP, 760, 214, a, "INHERITANCE IS A PROMISE")
            para(ov, LEFT + 28, TOP + 62, "Wherever code expects the base class, the derived class must work, "
                 "without surprises.", 700, a, size=31)
        # the function, then the class that breaks it
        code = envelope(t, T_RESIZE, cap0("l10") - 0.1, 0.5, 0.4)
        calls = {line_of(RESIZE, "setWidth"): ((T_W1, T_W1 + MOVE + 0.2), (T_W2, T_W2 + MOVE + 0.6)),
                 line_of(RESIZE, "setHeight"): ((T_H1, T_H1 + MOVE + 0.4), (T_H2, T_H2 + MOVE + 0.6))}

        def hl(j):
            return max((envelope(t, t0, t1, 0.2, 0.4) for t0, t1 in calls.get(j, ())), default=0.0)
        w, h = code_box(ov, LEFT, TOP, RESIZE, "WRITTEN FOR A RECTANGLE", code, hl=hl, min_w=700,
                        reveal=lambda j: remap(t, T_RESIZE + 0.2 + 0.3 * j, T_RESIZE + 0.7 + 0.3 * j))
        too = [line_of(SQUARE, "Rectangle::setHeight(w)"), line_of(SQUARE, "Rectangle::setWidth(h)")]

        def hl_square(j):
            if j == too[0]:
                return max(envelope(t, cap0("l4") + 5.0, cap1("l4"), 0.3, 0.4),
                           envelope(t, T_W2, T_W2 + MOVE + 0.6, 0.2, 0.4))
            return envelope(t, T_H2, T_WRONG + 1.6, 0.2, 0.4) if j == too[1] else 0.0
        code_box(ov, LEFT, TOP + h + 22, SQUARE, "A SQUARE THAT INHERITS", code * smooth(remap(t, T_CLASS, T_CLASS + 0.5)),
                 hl=hl_square, min_w=w, reveal=lambda j: remap(t, T_CLASS + 0.2 + 0.2 * j, T_CLASS + 0.7 + 0.2 * j))
        self.station(t, 0, T_RECT, T_H1 + MOVE + 0.2, True)
        self.station(t, 1, T_SQUARE, T_WRONG, False)
        # l5: the call that hands resize() a Square, and compiles
        ca = envelope(t, cap0("l5") + 0.5, cap0("l8") - 0.2, 0.4, 0.4)
        if ca > 0.003:
            x, y, cw = 1420, 150, ov.text_width("0", 21, "mono")
            line = "resize(square, w, h);"
            ov.panel(x, y, len(line) * cw + 44, 48, radius=10, fill=0x0d131e, alpha=0.86 * ca)
            ov.code(x + 22, y + 9, [line], "cpp", 21, 31, ca, keywords=CPP_KEYWORDS)
            oa = ca * smooth(remap(t, cap0("l5") + 2.0, cap0("l5") + 2.4))
            tick(ov, x + 16, y + 76, 8, oa)
            ov.text(x + 36, y + 76, "it compiles", size=21, color=C_OK, alpha=oa, kind="semibold", anchor="lm")
        # l8, l9: the rule's name, and what keeping the promise takes
        x, y = 880, 84
        la = envelope(t, cap0("l8") + 0.6, CUTS[2] - 0.3, 0.5, 0.4)
        if la > 0.003:
            card(ov, x, y, 960, 150, la, "THE LISKOV SUBSTITUTION PRINCIPLE")
            ov.text(x + 28, y + 92, "A derived object must be able to stand in for its base.", size=31, color=TEXT,
                    alpha=la, anchor="lm")
        ka = envelope(t, cap0("l9") + 0.3, CUTS[2] - 0.3, 0.5, 0.4)
        if ka > 0.003:
            y += 172
            card(ov, x, y, 960, 214, ka, "A DERIVED CLASS KEEPS THE PROMISE WHEN IT")
            for k, (t_in, text) in enumerate(zip(T_KEEP, ("accepts what the base accepts",
                                                          "does what the base's function is meant to do",
                                                          "keeps what the base guarantees"))):
                ra = ka * smooth(remap(t, t_in, t_in + 0.5))
                yy = y + 76 + 46 * k
                ov.circle(x + 38, yy, 5, fill=C_ACCENT, alpha=ra)
                ov.text(x + 60, yy, text, size=25, color=TEXT, alpha=ra, anchor="lm")
            xa = ka * smooth(remap(t, T_KEEP[2] + 1.4, T_KEEP[2] + 1.8))
            xx = x + 60 + ov.text_width("keeps what the base guarantees", 25) + 44
            cross(ov, xx, y + 76 + 92, 8, xa)
            ov.text(xx + 22, y + 76 + 92, "the Square did not", size=21, color=C_BAD, alpha=xa, kind="semibold",
                    anchor="lm")
        # l10: siblings, not parent and child
        sa = envelope(t, cap0("l10") + 0.2, CUTS[2] - 0.3, 0.5, 0.4)
        if sa > 0.003:
            x, y = LEFT, TOP
            card(ov, x, y, 760, 400, sa, "SIBLINGS, NOT PARENT AND CHILD")
            c1, c2, y0, y1 = x + 180, x + 540, y + 120, y + 260
            is_a(ov, [(c1, y1 - 22)], (c1, y0 + 22), [sa])
            class_box(ov, c1, y0, "Rectangle", sa)
            class_box(ov, c1, y1, "Square", sa)
            cross(ov, c1, (y0 + y1) / 2 + 8, 16, sa * smooth(remap(t, cap0("l10") + 0.9, cap0("l10") + 1.3)))
            ov.text(c1, y1 + 56, "breaks the promise", size=21, color=C_BAD, alpha=sa, kind="semibold", anchor="mm")
            ra = sa * smooth(remap(t, cap0("l10") + 2.6, cap0("l10") + 3.2))
            is_a(ov, [(c2 - 100, y1 - 22), (c2 + 100, y1 - 22)], (c2, y0 + 22), [ra, ra])
            for cx, name in ((c2 - 100, "Rectangle"), (c2 + 100, "Square")):
                class_box(ov, cx, y1, name, ra)
            class_box(ov, c2, y0, "Shape", ra)
            ov.text(c2, y1 + 56, "each keeps its own", size=21, color=C_OK, alpha=ra, kind="semibold", anchor="mm")

    def offers(self, x, y, names, note, colour, a):
        """Under a class: the functions the rest of the program can call on it."""
        ov = self.ov
        ov.text(x, y, "a Thermostat offers", size=18, color=DIM, alpha=a, anchor="lm")
        x += ov.text_width("a Thermostat offers", 18) + 22
        for k, name in enumerate(names):
            ov.text(x, y, name, size=20, color=TEXT if k == 0 else colour, alpha=a, kind="mono", anchor="lm")
            x += ov.text_width(name, 20, "mono") + 22
        ov.text(x, y, note, size=19, color=colour, alpha=a, kind="semibold", anchor="lm")

    def compose(self, t):
        ov, st, p = self.ov, self.st, self.p
        if t < CUTS[2]:
            return
        right = 900
        # c1, c2: the two questions, and the book's car
        a = envelope(t, cap0("c1") + 0.2, cap0("c5") - 0.1, 0.5, 0.4)
        w = 760
        t_is, t_has = cap0("c1") + 2.0, cap0("c2") + 1.0
        t_inherit, t_member = cap0("c1") + 4.6, cap0("c2") + 3.9
        if a > 0.003:
            card(ov, LEFT, TOP, w, 250, a, "BEFORE YOU INHERIT, ASK")
            rows = [(t_is, t_inherit, "Can my class stand in for the base, everywhere?", "is a", "inherit", C_OK),
                    (t_has, t_member, "Do I only want to use what another class can do?", "has a", "a member",
                     C_ACCENT)]
            for k, (t_in, t_answer, question, kind, answer, colour) in enumerate(rows):
                y = TOP + 78 + 88 * k
                ov.text(LEFT + 28, y, question, size=25, color=TEXT, anchor="lm",
                        alpha=a * smooth(remap(t, t_in, t_in + 0.6)))
                ta = a * smooth(remap(t, t_answer, t_answer + 0.6))
                ov.text(LEFT + 28, y + 36, f"yes:  {kind}", size=22, color=colour, alpha=ta, kind="semibold", anchor="lm")
                x = LEFT + 28 + ov.text_width(f"yes:  {kind}", 22, "semibold") + 18
                ov.arrow2d((x, y + 37), (x + 44, y + 37), colour, 2.2, head=11, alpha=ta)
                ov.text(x + 58, y + 36, answer, size=22, color=colour, alpha=ta, kind="semibold", anchor="lm")
        da = envelope(t, cap0("c1") + 0.8, cap0("c3") - 0.1, 0.5, 0.4)
        if da > 0.003:
            x, y = right, 84
            card(ov, x, y, 900, 330, da, "A CAR IS A VEHICLE, AND HAS AN ENGINE")
            cx, y0, y1, ex = x + 260, y + 100, y + 240, x + 660
            cw, _ = class_box(ov, cx, y1, "Car", da)
            ia = da * smooth(remap(t, t_is, t_is + 0.6))
            is_a(ov, [(cx, y1 - 22)], (cx, y0 + 22), [ia], color=C_OK)
            class_box(ov, cx, y0, "Vehicle", ia)
            ov.text(cx + 18, (y0 + y1) / 2, "is a", size=21, color=C_OK, alpha=ia, kind="semibold", anchor="lm")
            ha = da * smooth(remap(t, t_member, t_member + 0.6))
            ew = ov.text_width("Engine", 21, "mono") + 36
            has_a(ov, (cx + cw / 2, y1), [(ex - ew / 2, y1)], [ha], color=C_ACCENT)
            class_box(ov, ex, y1, "Engine", ha)
            ov.text((cx + ex) / 2, y1 - 20, "has a", size=21, color=C_ACCENT, alpha=ha, kind="semibold", anchor="mm")
        # c3: the same class written both ways
        ta = envelope(t, cap0("c3") + 0.3, T_THREEPP - 0.2, 0.5, 0.4)
        if ta > 0.003:
            x, y, lh = right, 84, 31
            cw_, h = code_box(ov, x, y, IS_A, "INHERITS: A THERMOSTAT IS A SENSOR", ta, extra=52, min_w=680,
                              reveal=lambda j: remap(t, cap0("c3") + 0.5 + 0.2 * j, cap0("c3") + 1.0 + 0.2 * j))
            self.offers(x + 30, y + 50 + lh * len(IS_A) + 26, ["shouldHeat()", "readCelsius()"], "came along", C_BAD,
                        ta * smooth(remap(t, T_LEAK, T_LEAK + 0.6)))
            y += h + 22
            ma = ta * smooth(remap(t, T_MEMBER - 0.3, T_MEMBER + 0.3))
            member = line_of(HAS_A, "sensor_;")
            code_box(ov, x, y, HAS_A, "HOLDS: A THERMOSTAT HAS A SENSOR", ma, extra=52, min_w=cw_,
                     hl=lambda j: envelope(t, T_PRIVATE - 0.4, T_THREEPP, 0.3, 0.4) if j == member else 0.0,
                     reveal=lambda j: remap(t, T_MEMBER + 0.1 * j, T_MEMBER + 0.5 + 0.1 * j))
            self.offers(x + 30, y + 50 + lh * len(HAS_A) + 26, ["shouldHeat()"], "only what you chose", C_OK,
                        ma * smooth(remap(t, T_PRIVATE + 0.5, T_PRIVATE + 1.1)))
        # c4: threepp's Mesh is one thing and has two
        ua = envelope(t, T_THREEPP + 0.1, T_WALL - 0.2, 0.5, 0.4)
        if ua > 0.003:
            x, y = LEFT, 336
            card(ov, x, y, w, 300, ua, "WHAT A Mesh IS, AND WHAT IT HAS")
            mx, my = x + 170, y + 216
            ia = ua * smooth(remap(t, cap0("c4") + 5.5, cap0("c4") + 6.1))
            is_a(ov, [(mx, my - 22)], (mx, y + 110), [ia])
            class_box(ov, mx, y + 88, "Object3D", ia)
            ov.text(mx + 16, (y + 110 + my - 22) / 2, "is a", size=19, color=DIM, alpha=ia, anchor="lm")
            mw, _ = class_box(ov, mx, my, "Mesh", ua)
            has = [("BufferGeometry", my - 44, T_GEO_NOTE, 0xdfe8ff), ("Material", my + 44, T_MAT_NOTE, C_ACCENT)]
            shown = [ua * smooth(remap(t, t_in, t_in + 0.5)) for *_, t_in, _ in has]
            bx = x + 580
            has_a(ov, (mx + mw / 2, my), [(bx - (ov.text_width(name, 21, "mono") + 36) / 2, yy) for name, yy, *_ in has],
                  shown, stub=96)
            for (name, yy, _, colour), ha in zip(has, shown):
                class_box(ov, bx, yy, name, ha, color=colour)
            ov.text(mx + mw / 2 + 70, my - 12, "has a", size=19, color=DIM, alpha=shown[0], anchor="md")
        # the mesh itself: what it has now
        ha = envelope(t, T_HERO + 0.3, T_WALL + 0.1, 0.4, 0.3)
        if ha > 0.003:
            q = st.project(HERO_AT)
            ga = ha * envelope(t, T_GEO_NOTE, T_MAT_NOTE + 0.2, 0.4, 0.4)
            ov.callout(q[:2] + np.array([-60, -50]), (q[0] - 190, q[1] - 170), "its geometry: the shape", 0xffffff, ga,
                       grow=ease_out(remap(t, T_GEO_NOTE, T_GEO_NOTE + 0.5)))
            ma = ha * envelope(t, T_MAT_NOTE + 0.2, cap1("c4") + 0.2, 0.4, 0.4)
            ov.callout(q[:2] + np.array([-60, -50]), (q[0] - 190, q[1] - 170), "its material: the look", C_ACCENT, ma,
                       grow=ease_out(remap(t, T_MAT_NOTE + 0.2, T_MAT_NOTE + 0.7)))
            sa = ha * smooth(remap(t, cap0("c5") + 0.2, cap0("c5") + 0.6))
            x, y = q[0] - 250, 96
            card(ov, x, y, 500, 150, sa, "THE MESH HAS, RIGHT NOW")
            for j, (label, name, when) in enumerate((("a geometry", p["geometry_names"][self.shape], T_GEO),
                                                     ("a material", p["material_names"][self.look], T_MAT))):
                flash = max(envelope(t, x_, x_ + 0.9, 0.1, 0.6) for x_ in when)
                ov.text(x + 28, y + 74 + 40 * j, label, size=20, color=DIM, alpha=sa, anchor="lm")
                ov.text(x + 160, y + 74 + 40 * j, name, size=22, color=C_TYPE if flash < 0.3 else 0xffffff, alpha=sa,
                        kind="mono", anchor="lm")
        # c5: swapping either part
        ca = envelope(t, cap0("c5") + 0.1, T_WALL + 0.2, 0.4, 0.4)
        shape_line, look_line = line_of(SWAP, "setGeometry"), line_of(SWAP, "setMaterial")

        def hl(j):
            times = (T_GEO[0],) if j == shape_line else (T_MAT[0],) if j == look_line else ()
            return max((envelope(t, x - 0.2, x + 1.0, 0.2, 0.3) for x in times), default=0.0)
        code_box(ov, LEFT, TOP, SWAP, "ONE MESH, ANY SHAPE, ANY LOOK", ca, hl=hl, min_w=w)
        # c6: what inheritance would cost, then what composition needs
        wa = envelope(t, T_WALL + 0.9, TL.start("outro") + 0.6, 0.5, 0.5)
        if wa <= 0.003:
            return
        comp = smooth(remap(t, T_COMPOSED, T_COMPOSED + 0.7))
        card(ov, LEFT, TOP, 700, 236, wa, "THE SAME WALL, TWO WAYS")
        for k, (name, text, colour, ra) in enumerate((
                ("inheritance", "a new class for every combination", C_BAD,
                 smooth(remap(t, cap0("c6") + 0.3, cap0("c6") + 0.9))),
                ("composition", "one Mesh, any geometry, any material", C_OK, comp))):
            y = TOP + 82 + 78 * k
            ov.text(LEFT + 28, y, name, size=25, color=colour, alpha=wa * ra, kind="semibold", anchor="lm")
            ov.text(LEFT + 28, y + 34, text, size=22, color=TEXT, alpha=wa * ra, anchor="lm")
        for k in range(len(p["wall"])):
            col, row = k % len(WALL_X), k // len(WALL_X)
            q = st.project((WALL_X[col], WALL_Y[row] - 0.35, 0.0))
            na = wa * smooth(remap(t, T_NAMES + 0.11 * k, T_NAMES + 0.11 * k + 0.3)) * (1 - comp)
            ov.text(q[0], q[1], f"class {LOOKS[row]}{SHAPES[col]}", size=17, color=C_BAD, alpha=na, kind="mono",
                    anchor="ma")
        for col, name in enumerate(p["geometry_names"]):
            q = st.project((WALL_X[col], WALL_Y[0] + 0.4, 0.0))
            ov.text(q[0], q[1], name, size=16, color=0xdfe8ff, alpha=wa * comp, kind="mono", anchor="md")
        rows = [st.project((WALL_X[-1] + 0.4, y, 0.0)) for y in WALL_Y]
        for q, name in zip(rows, p["material_names"]):
            ov.text(max(r[0] for r in rows), q[1], name, size=16, color=C_ACCENT, alpha=wa * comp, kind="mono",
                    anchor="lm")


# ── the stage ─────────────────────────────────────────────────────────────────
def build(width, height):
    st = Stage(width, height, renderer="gl", fog=(8.0, 17.0), shadow_extent=2.6, far=40.0)
    p = {}

    def mesh(geometry, material, at=(0, 0, 0), parent=None):
        m = tp.Mesh(geometry, material)
        m.position.set(*at)
        m.cast_shadow = True
        if parent is not None:
            parent.add(m)
        return m

    # part one: a Mesh, a PointLight and a Group, the children of one parent
    world = tp.Group()
    st.scene.add(world)
    box = mesh(tp.BoxGeometry(0.6, 0.6, 0.6), standard(C_BOX, roughness=0.42, metalness=0.05))
    lamp = tp.PointLight(tp.Color(0xffd9a0), 0.0, 5.0, 2.0)
    bulb = tp.Mesh(tp.SphereGeometry(0.07, 32, 16), standard(0xffe2b0, emissive=0xffb347, emissive_intensity=1.4))
    lamp.add(bulb)
    rig = tp.Group()
    mesh(tp.CylinderGeometry(0.34, 0.34, 0.06, 48), standard(0x3a4150, 0.5, 0.6), (0, 0.03, 0), rig)
    mesh(tp.CylinderGeometry(0.2, 0.2, 0.46, 48), standard(0x2a9d8f, 0.4), (-0.08, 0.29, 0), rig)
    mesh(tp.SphereGeometry(0.1, 32, 16), standard(0xf4a259, 0.4), (-0.08, 0.62, 0), rig)
    mesh(tp.BoxGeometry(0.16, 0.16, 0.16), standard(0xef476f, 0.4), (0.2, 0.14, 0.08), rig)
    for o in (box, lamp, rig):
        world.add(o)
    p.update(world=world, trio=[box, lamp, rig], lamp_power=7.0, types=[type(c).__name__ for c in world.children])

    # part two: a plate for the Rectangle and one for the Square
    plate = tp.BoxGeometry(1.0, 1.0, 0.06)
    p["plates"] = [mesh(plate, standard(c, roughness=0.45, metalness=0.05), parent=st.scene) for c in (C_BOX, C_WARM)]
    p["sizes"] = [resize(Rectangle(), *ASKED), resize(Square(), *ASKED)]

    # part three: four geometries and three materials, on one mesh and then on a wall of them
    geometries = [tp.BoxGeometry(0.36, 0.36, 0.36), tp.SphereGeometry(0.24, 48, 24),
                  tp.TorusKnotGeometry(0.16, 0.055, 160, 24), tp.ConeGeometry(0.23, 0.44, 48)]
    shiny = tp.MeshPhongMaterial()
    shiny.color = C_WARM
    shiny.shininess = 120
    shiny.specular = 0xaaaaaa
    wires = tp.MeshBasicMaterial()
    wires.color = 0xdfe8ff
    wires.wireframe = True
    materials = [standard(C_BOX, roughness=0.42, metalness=0.05), shiny, wires]
    p.update(geometries=geometries, materials=materials,
             geometry_names=[type(g).__name__ for g in geometries],
             material_names=[type(m).__name__ for m in materials])
    p["pedestal"] = mesh(tp.CylinderGeometry(0.34, 0.38, 0.1, 64), standard(0x3a4150, 0.5, 0.6),
                         (HERO_AT[0], 0.05, 0), st.scene)
    hero = mesh(geometries[0], materials[0], HERO_AT, st.scene)
    overlay = tp.MeshBasicMaterial()
    overlay.wireframe = True
    overlay.color = 0xffffff
    overlay.transparent = True
    overlay.depth_write = False
    wire = tp.Mesh(geometries[0], overlay)
    wire.scale.set(1.01, 1.01, 1.01)
    hero.add(wire)
    p.update(hero=hero, wire=wire)
    p["wall"] = [mesh(g, m, (x, y, 0.0), st.scene) for y, m in zip(WALL_Y, materials) for x, g in zip(WALL_X, geometries)]
    return st, p


def setup(width, height):
    st, p = build(width, height)
    print("[types] the children of the scene:", ", ".join(p["types"]))
    for name, sizes in zip(("Rectangle", "Square"), p["sizes"]):
        print(f"[resize] {name}: asked for {ASKED[0]:g} x {ASKED[1]:g}, got {sizes[-1][0]:g} x {sizes[-1][1]:g}")
    print(f"[wall] {len(p['wall'])} meshes from {len(p['geometries'])} geometries and {len(p['materials'])} materials")
    ov = Hud(1920, 1080, math_cache=os.path.join(_HERE, "polymorphism_rules.math.json"))
    painter = Painter(st, p, ov)
    print(f"[setup] film {TL.duration:.1f} s on the script clock")

    def render(t):
        painter.set3d(t)
        ov.begin()
        painter.draw2d(t)
        ov.fade(max(fade_in_out(t, TL.duration), max(envelope(t, c - 0.45, c + 0.45, 0.4, 0.4) for c in CUTS)))
        ov.end()
        return st.frame(t, hud=ov)
    return render, painter.captions


if __name__ == "__main__":
    run("polymorphism_rules", TL.duration, setup, fps=FPS, speech=SPEECH)
