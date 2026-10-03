"""lesson: the house layer of the threepp lesson films, on top of `threepp.lesson`.

The toolkit itself (Timeline, Stage, Hud, Film, Narration, Speech, ...) is the experimental
`threepp.lesson` package; see its docstring for the two-pass model (choreograph once, then
`render(t)` is pure). This module re-exports all of it and adds what makes these films look
and run alike:

`Stage`
    threepp.lesson.Stage with the lessons' defaults: GL, `env` a file name in
    threepp_data/textures/env (the studio HDR unless told otherwise), found by `data_file`,
    and the films' 1920x1080 design space at any render size.

`Hud`
    threepp.lesson.Hud plus the house cards: `title_card` (the opening title) and `summary`
    ("IN SHORT" and the repo link). `card` and `code_card` are the house card and a card of
    code that types itself in.

`THREEPP`, `threepp_file`
    The threepp checkout the films run against ($THREEPP_ROOT, else ../threepp beside this
    repository), whose python/ is put first on sys.path; without one, the installed threepp.

`data_file`
    A threepp_data file from THREEPP_DATA_DIR, a checkout next to threepp's, or the copies CMake
    fetches into the build directories.

`run`
    threepp.lesson's `run`, the command line every lesson shares (the film, a preview, one
    stretch, stills, a contact sheet, the captions as an .srt, `--gate`, `--remeasure`), with
    the captions checked against the house rules first.

`house_rule_warnings`
    The house rules every lesson film follows (a narrated title card, no specific numbers in
    the narration), checked by `run`.
"""
from __future__ import annotations

import atexit
import glob
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)                           # this repository
PROGRAMS = os.path.join(ROOT, "programs")               # the C++ programs the films show and run


def _threepp_checkout():
    """The threepp checkout the films run against: $THREEPP_ROOT, else one next to this
    repository. None when there is neither; then threepp is the installed package."""
    for p in (os.environ.get("THREEPP_ROOT", ""), os.path.join(os.path.dirname(ROOT), "threepp")):
        if p and os.path.isfile(os.path.join(p, "CMakeLists.txt")):
            return os.path.abspath(p)
    return None


THREEPP = _threepp_checkout()
if THREEPP and os.path.isdir(os.path.join(THREEPP, "python", "threepp")):
    if os.path.join(THREEPP, "python") not in sys.path:
        sys.path.insert(0, os.path.join(THREEPP, "python"))
import threepp as tp  # noqa: E402,F401  (the lessons take tp from here)
from threepp.lesson import *  # noqa: E402,F401,F403
from threepp.lesson import Hud as _Hud, Stage as _Stage, run as _run  # noqa: E402


def threepp_file(*parts):
    """Path of a file in the threepp checkout (the gallery's screenshots, a threepp example)."""
    if THREEPP is None:
        raise FileNotFoundError(f"{os.path.join(*parts)} is in the threepp repository: clone it next to "
                                f"this one, or set THREEPP_ROOT to a threepp checkout")
    return os.path.join(THREEPP, *parts)


# ── threepp_data ──────────────────────────────────────────────────────────────
def data_roots():
    """Where threepp_data may be, in search order: THREEPP_DATA_DIR, a checkout next to the
    threepp checkout, the copies CMake fetches into threepp's build directories, then the
    copy this repository's own build fetches for the programs."""
    roots = [os.environ.get("THREEPP_DATA_DIR", "")]
    if THREEPP:
        roots += [os.path.join(os.path.dirname(THREEPP), n) for n in ("threepp-data", "threepp_data")]
        roots += sorted(glob.glob(os.path.join(THREEPP, "cmake-build-*", "_deps", "threepp_data-src")))
    for build in ("build*", "cmake-build-*"):
        roots += sorted(glob.glob(os.path.join(ROOT, build, "_deps", "threepp_data-src")))
    return [r for r in roots if r and os.path.isdir(r)]


def data_file(*parts):
    """Path of a threepp_data file in the first root that has it. Roots are checked
    per file, so an older checkout that lacks it does not hide a newer copy."""
    rel = os.path.join(*parts)
    roots = data_roots()
    for r in roots:
        p = os.path.join(r, rel)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f"threepp_data file '{rel}' not found in {roots or 'any data directory'}; "
                            f"set THREEPP_DATA_DIR to a threepp_data checkout that has it")


# ── the house stage and cards ─────────────────────────────────────────────────
class Stage(_Stage):
    """threepp.lesson.Stage with the lessons' defaults: GL, `env` a file name in
    threepp_data/textures/env, found by `data_file`, and the films' 1920x1080 design space
    whatever the render size (their Hud is built at that size). A missing HDR is reported and
    the stage renders without image-based lighting."""

    def __init__(self, width=1920, height=1080, renderer="gl", env="empty_warehouse_01_2k.hdr",
                 design=(1920, 1080), **kw):
        if renderer != "gl":
            raise ValueError(f"the lessons render with GL, not {renderer!r}")
        path = None
        if env:
            try:
                path = data_file("textures", "env", env)
            except FileNotFoundError as e:
                print(f"[stage] rendering without image-based lighting: {e}", file=sys.stderr)
        super().__init__(width, height, env=path, design=design, **kw)


class Hud(_Hud):
    """threepp.lesson.Hud plus the house cards: the opening title and the closing summary."""

    def title_card(self, t, kicker, title, subtitle, accent, t_in=0.9, t_out=6.4, size=96, sub_dy=118):
        """Opening title, left-aligned: a small tracked kicker, the title rising into place,
        and a subtitle `sub_dy` below it that fades in after it."""
        a = envelope(t, t_in, t_out, 0.9, 0.8)
        if a <= 0:
            return
        y = 360 + 14 * (1 - ease_out(remap(t, t_in, t_in + 1.3)))
        self.text(128, y - 58, kicker, size=22, color=accent, alpha=a, kind="semibold", tracking=4)
        self.text(122, y, title, size=size, color=TEXT, alpha=a, kind="semibold")
        sub = a * smooth(remap(t, t_in + 0.7, t_in + 1.7))
        self.text(128, y + sub_dy, subtitle, size=38, color=DIM, alpha=sub, kind="light")

    def summary(self, t, t0, t1, rows, footer, accent, link_color, text_dx=260, link="github.com/markaren/threepp"):
        """Closing card over the darkened frame, from t0 to past t1: "IN SHORT", rows of
        (tex, sentence) that appear one after another, then a footer and a link."""
        a = envelope(t, t0 + 0.2, t1 + 1, 0.8, 0.1)
        if a <= 0:
            return
        self.panel(-20, -20, self.W + 40, self.H + 40, radius=0, fill=0x070a10, alpha=0.8 * a)
        x = 250
        self.text(x, 250, "IN SHORT", size=22, color=accent, alpha=a, kind="semibold", tracking=4)
        for k, (tex, txt) in enumerate(rows):
            al = a * smooth(remap(t, t0 + 0.6 + 0.5 * k, t0 + 1.3 + 0.5 * k))
            yy = 350 + k * 110
            self.math(x, yy, tex, size=46, color=TEXT, alpha=al, anchor="lm")
            self.text(x + text_dx, yy, txt, size=38, color=TEXT, alpha=al, anchor="lm")
        al = a * smooth(remap(t, t0 + 2.4, t0 + 3.2))
        self.text(x, 780, footer, size=28, color=DIM, alpha=al, kind="semibold")
        self.text(x, 824, link, size=26, color=link_color, alpha=al)


# ── the house rules ───────────────────────────────────────────────────────────
TITLE_VOICE_BY = 2.0                     # the first spoken line starts this early: the title card is narrated
_NUMBER_RE = re.compile(r"\d(?![dD]\b)")   # a digit, except the one in "2D" / "3D"


def house_rule_warnings(captions):
    """The house rules every lesson film follows, as warnings: no specific numbers in the
    narration, and a narrated title card (a caption from the first seconds, spoken-only if the
    title card should stay clean). The picture is the lesson's own to check."""
    out = []
    if not captions or min(c[0] for c in captions) > TITLE_VOICE_BY:
        out.append(f"the title card is not narrated: no caption starts in the first {TITLE_VOICE_BY:.0f} s")
    for a, _, txt, *_ in captions:
        if _NUMBER_RE.search(txt):
            out.append(f"the caption at {a:.1f} s has a number in it: {txt[:70]!r}")
    return out


def card(ov, x, y, w, h, alpha, title=None):
    """The house card: a rounded panel with a small spaced-out title."""
    ov.panel(x, y, w, h, radius=16, alpha=0.74 * alpha, outline=0x8aa0c0, outline_alpha=0.16)
    if title:
        ov.text(x + 26, y + 22, title, size=16, color=DIM, alpha=alpha, kind="semibold", tracking=2.2)


def code_card(ov, t, t_in, t_out, x, y, lines, lang, title, size=20, lh=27, stagger=0.35, min_w=0, out=None,
              out_t=None, keywords=None, out_color=0xa6e3a1):
    """A titled card of code whose lines type in one after another from t_in. `out`: lines
    the program prints, shown under the code from `out_t` (default: once the code is in)."""
    a = envelope(t, t_in, t_out, 0.6, 0.6)
    if a <= 0.003:
        return
    cw = ov.text_width("0", size, "mono")
    w = max(max(len(l) for l in lines + (out or [])) * cw + 60, min_w)
    h = 64 + lh * len(lines) + (lh * len(out) + 26 if out else 0)
    card(ov, x, y, w, h, a, title)
    ov.code(x + 30, y + 50, lines, lang, size, lh, a,
            reveal=lambda j: remap(t, t_in + 0.3 + stagger * j, t_in + 0.9 + stagger * j), keywords=keywords)
    if out:
        oa = a * smooth(remap(t, out_t if out_t is not None else t_in + 0.9 + stagger * len(lines),
                              (out_t if out_t is not None else t_in + 0.9 + stagger * len(lines)) + 0.4))
        yy = y + 50 + lh * len(lines) + 10
        ov.panel(x + 12, yy - 4, w - 24, lh * len(out) + 12, radius=8, fill=0x070a10, alpha=0.8 * oa)
        for j, line in enumerate(out):
            ov.text(x + 30, yy + 2 + lh * j + lh / 2, line, size=size, color=out_color, alpha=oa, kind="mono",
                    anchor="lm")



# ── C++ programs on screen: steps of a source, and capture builds ──────────────
# A lesson program grows in steps marked `#if STEP >= n` (programs/app.cpp, programs/snake/main.cpp),
# and each step is built as a capture program (programs/capture.hpp): headless, on a fixed
# 1/60 s clock, with the input replayed from a script. The film shows what a step adds, read
# out of the source, and the window is that program's own output, streamed in as it runs.
def _cond(directive, step, defines):
    """The value of one #if / #ifdef / #ifndef line (STEP >= k and STEP < k are all the lessons use)."""
    d = directive.strip()
    m = re.match(r"#(?:el)?if\s+STEP\s*(>=|<)\s*(\d+)$", d)
    if m:
        k = int(m.group(2))
        return step >= k if m.group(1) == ">=" else step < k
    m = re.match(r"#if(n?)def\s+(\w+)$", d)
    if m:
        on = m.group(2) in defines
        return not on if m.group(1) else on
    raise ValueError(f"a directive the film cannot read: {d}")


def preprocess(lines, step, defines=("STEP",)):
    """Indices of the source lines the preprocessor keeps for STEP = step (directives dropped)."""
    keep, stack, active = [], [], True
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("#if ", "#ifdef ", "#ifndef ")):
            c = _cond(s, step, defines)
            stack.append([active, c])
            active = active and c
        elif s.startswith("#elif"):
            parent, taken = stack[-1]
            c = _cond(s, step, defines)
            active = parent and not taken and c
            stack[-1][1] = taken or c
        elif s.startswith("#else"):
            parent, taken = stack[-1]
            active = parent and not taken
            stack[-1][1] = True
        elif s.startswith("#endif"):
            active = stack.pop()[0]
        elif active:
            keep.append(i)
    return keep


def indent(s):
    return len(s) - len(s.lstrip(" "))

def step_rows(lines, step, defines=("STEP",), base=None):
    """What step `step` changes, as display rows [(kind, text)]: 'add' and 'del' lines, and
    dim 'ctx' lines (the block they sit in) and 'gap's between separate places."""
    now = set(preprocess(lines, step, defines))
    before = set(preprocess(lines, step - 1, ("STEP",))) if base is None else set(base)
    changed = sorted((now - before) | (before - now))
    rows, last, ctx_open = [], None, None
    for i in changed:
        if not lines[i].strip() and (last is None or i != last + 1):
            continue
        if last is not None and any(lines[j].strip() and (j in now or j in before) for j in range(last + 1, i)):
            # an unchanged line sits between: a new place in the file
            ind = indent(lines[i])
            ctx = None
            if ind > 4:
                for j in range(i - 1, -1, -1):
                    if j in now and lines[j].strip() and indent(lines[j]) < ind:
                        ctx = j
                        break
            if ctx is not None and ctx == ctx_open:
                rows.append(("gap", ""))
            else:
                if ctx_open is not None:
                    rows.append(("ctx", "});"))
                rows.append(("gap", ""))
                if ctx is not None:
                    rows.append(("ctx", lines[ctx][4:]))
                ctx_open = ctx
        elif last is None:
            ind = indent(lines[i])
            if ind > 4:
                for j in range(i - 1, -1, -1):
                    if j in now and lines[j].strip() and indent(lines[j]) < ind:
                        rows.append(("ctx", lines[j][4:]))
                        ctx_open = j
                        break
        kind = "add" if i in now else "del"
        rows.append((kind, lines[i][4:] if lines[i].startswith("    ") else lines[i]))
        last = i
    while rows and not rows[-1][1].strip() and rows[-1][0] != "gap":
        rows.pop()
    if ctx_open is not None:
        rows.append(("ctx", "});"))
    # blank rows inside a run stay (they are part of the code); strip them at the ends
    while rows and rows[0][0] == "gap":
        rows.pop(0)
    return rows


def capture_exe(name, env="LESSON_APP_BIN"):
    """The capture build `name` (a CMake target beside the lesson's program), from the
    directory in $`env` or the bin/ of a build*/ or cmake-build-*/ directory of this repository."""
    exe = f"{name}.exe" if os.name == "nt" else name
    roots = [os.environ.get(env, "")]
    for build in ("build*", "cmake-build-*"):
        roots += sorted(glob.glob(os.path.join(ROOT, build, "bin")))
    for r in roots:
        p = os.path.join(r, exe)
        if r and os.path.isfile(p):
            return p
    raise FileNotFoundError(f"{exe}: build the CMake target {name} (or point {env} at its directory)")


class Stream:
    """One capture build, running headless and streaming its frames into a texture. Frames
    come in order; asking for an earlier one restarts the program (it is deterministic).
    `script` has .text() (the LESSON_SCRIPT file), .frames, .frame(t) and .t1. `stats`: run it
    through once first, for the renderer's counts per frame (`stat`); `log`: the same, for what
    the program prints in each frame (`printed`). `args` go on the program's command line."""
    W, H = 1280, 720

    def __init__(self, name, script, stats=False, log=False, args=()):
        self.name, self.script, self.args = name, script, list(args)
        self.exe = capture_exe(name)
        fd, self.script_path = tempfile.mkstemp(prefix=f"{name}_", suffix=".txt")
        with os.fdopen(fd, "w") as f:
            f.write(script.text() + "\n")
        self.stats_path = self.script_path[:-4] + ".stats"
        self.proc, self.k, self.cur = None, -1, None
        self.texture = None
        self.calls = None
        self.log = None
        atexit.register(self.close)
        if stats or log:
            self._prepass(log)

    def _start(self):
        self.close_proc()
        env = dict(os.environ, LESSON_SCRIPT=self.script_path, LESSON_OUT="-", LESSON_STATS=self.stats_path)
        self.proc = subprocess.Popen([self.exe] + self.args, env=env, cwd=os.path.dirname(self.exe),
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        # anything the program printed before its first frame comes first; the marker line ends it
        buf = b""
        while b"LESSON_FRAMES" not in buf or not buf[buf.index(b"LESSON_FRAMES"):].count(b"\n"):
            ch = self.proc.stdout.read(1)
            if not ch:
                raise RuntimeError(f"{self.exe} ended before its first frame")
            buf += ch
        self.k = -1

    def _read_one(self):
        n = self.W * self.H * 3
        data = bytearray()
        while len(data) < n:
            chunk = self.proc.stdout.read(n - len(data))
            if not chunk:
                raise RuntimeError(f"{self.exe} ended at frame {self.k + 1}")
            data += chunk
        self.k += 1
        return data

    def frame(self, k):
        """Frame k (0-based, clamped to the script) as (H, W, 3) uint8."""
        k = min(max(int(k), 0), self.script.frames - 1)
        if self.proc is None or k < self.k:
            self._start()
        data = None
        while self.k < k:
            data = self._read_one()
        if data is not None:
            self.cur = np.frombuffer(bytes(data), np.uint8).reshape(self.H, self.W, 3)
        return self.cur

    def at(self, t):
        return self.frame(self.script.frame(t))

    def tex(self, t):
        img = self.at(t)[::-1]            # textures take their rows bottom first
        if self.texture is None:
            self.texture = tp.data_texture(np.ascontiguousarray(img), True)
            self._shown = self.k
        elif self._shown != self.k:
            self.texture.update_data(np.ascontiguousarray(img))
            self._shown = self.k
        return self.texture

    def _prepass(self, log):
        """Run the program once through, for the renderer's counts on every frame and, with
        `log`, what it printed in each (capture.hpp marks the frames: LESSON_MARK_FRAMES)."""
        if not log:     # as the stats were always read: streamed, then the program stopped
            self.frame(self.script.frames - 1)
            self.close_proc()
            self.calls = np.loadtxt(self.stats_path).reshape(-1, 2)
            return
        env = dict(os.environ, LESSON_SCRIPT=self.script_path, LESSON_OUT=os.devnull,
                   LESSON_STATS=self.stats_path, LESSON_MARK_FRAMES="1")
        out = subprocess.run([self.exe] + self.args, env=env, cwd=os.path.dirname(self.exe), capture_output=True,
                             check=True).stdout.decode("utf-8", "replace")
        self.calls = np.loadtxt(self.stats_path).reshape(-1, 2)
        self.log, k = {}, -1
        for line in out.splitlines():
            if line.startswith("LESSON_FRAME "):
                k = int(line.split()[1])
            else:
                self.log.setdefault(k, []).append(line)

    def printed(self, t):
        """Every line the program printed up to the frame shown at t."""
        k = self.script.frame(t)
        return [line for f in sorted(self.log) if f <= k for line in self.log[f]]

    def stat(self, t):
        k = min(self.script.frame(t), len(self.calls) - 1)
        return int(self.calls[k, 0]), int(self.calls[k, 1])

    def close_proc(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:
                pass
            self.proc = None

    def close(self):
        self.close_proc()
        for p in (self.script_path, self.stats_path):
            try:
                os.remove(p)
            except OSError:
                pass


# ── the command line ──────────────────────────────────────────────────────────
def run(name, duration, setup, fps=60, speech=None):
    """threepp.lesson's `run` (the film, --preview, --from/--to, --stills, --sheet, --srt,
    --gate, --remeasure; the captions read aloud unless --no-voice), with the captions checked
    against the house rules first: each break is printed as a [captions] line."""
    return _run(name, duration, setup, fps=fps, speech=speech, warn=house_rule_warnings)
