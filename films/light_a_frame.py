"""How threepp lights a frame.  Part 6: the Vulkan renderer's hybrid lighting, about 2.5 min.

    python light_a_frame.py                               # the film (1080p60), lesson_out/light_a_frame.mp4
    python light_a_frame.py --stills 20,60,120            # individual frames
    python light_a_frame.py --sheet                       # contact sheet, one frame per 3 s
    python light_a_frame.py --preview --out preview.mp4   # 960x540 @ 30 fps

Every picture of the room is threepp's VulkanRenderer rendering it while the film is made, with
its default lighting settings unless a label says otherwise (probe cache off, TAA off), shown one
lighting view at a time (VulkanRenderer::setLightingView). The renderer's temporal state makes
each frame depend on the ones before it, so each shot runs in a subprocess of its own
(`--stream`) that renders every frame at 60 Hz from the shot's start, with the camera, the rolling
ball and the lamp as the film's clock puts them, and streams the frames to the film; a still
replays its shot from the start. The G-buffer panels, the probe snapshot and the GPU times come
from one capture (`--capture`, cached in lesson_out/light_a_frame_shots). What is on screen:

* the wipes put two lighting views of the same frame side by side: two renderers, one scene, the
  same clock;
* "one frame" is the frame right after resetTemporalHistory(), every frame;
* the probe dots are one slice of the renderer's own probe grid (probe_grid()), each coloured by
  the irradiance its SH-L1 coefficients give towards the camera;
* the light paths in the opening are traced on the CPU, in numpy, against the same boxes and
  spheres, with cosine-weighted bounces; the share that reached the lamp is counted, not assumed;
* the GPU times are the renderer's own per-pass timestamps (frame_timings) at 1920x1080 on the
  machine that made the film; the rays per pixel are the counts the shaders are written with.
"""
from __future__ import annotations

import atexit
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lesson  # noqa: E402
from lesson import (DIM, TEXT, Hud, Keys, Stage, envelope, fade_in_out, remap, run, smooth, tokenize, tp)  # noqa: E402
from lesson import card  # noqa: E402  (the house card)

FPS = 60
STEP = 60                                  # the renderer's frame rate in every shot
CW_, CH_ = 1920, 1080                      # capture size (the G-buffer panels, the timings)
SHOTS = os.path.join("lesson_out", "light_a_frame_shots")
CAPTURE_VERSION = 3                        # bump when the scene or the capture list changes

C_ACCENT = 0x4cc9f0
C_WARM = 0xffb347
C_OK = 0x5ee27a
C_RED = 0xef476f

CPP_KEYWORDS = lesson.KEYWORDS["cpp"] | {"void"}
WORDS = {"G-buffer": "G buffer", "rasterised": "rasterized", "TAA": "T A A"}   # how the narrator says them

# ── the script ────────────────────────────────────────────────────────────────
# The narration sets the pace: each caption lasts as long as its spoken line (Kokoro,
# af_heart, measured) plus the voice's lead-in and tail and a small margin.
CAPTION_TEXT = {
    "o1": "How threepp lights a frame: rasterised visibility, ray-traced light, and three ways to reuse a ray.",
    "p1": "A path tracer lights a pixel by following light backwards, bounce after bounce, until it hits a lamp. "
          "Most random paths never get there.",
    "p2": "So a clean image needs thousands of paths per pixel. threepp's Vulkan renderer spends a few, and reuses "
          "them. Here is how.",
    "g1": "What the camera sees is not traced at all. It is rasterised into a G-buffer: every pixel's normal, "
          "colour, depth and object.",
    "d1": "Light straight from the lamp is summed exactly. Only the shadows need rays: a ray or two per pixel, "
          "aimed at random points on the lamp.",
    "b1": "Bounce light and reflections add a few more. One frame of all of it, with no reuse, boils like this.",
    "t1": "Reuse one: time. Each pixel averages its past frames, found through the motion vectors, so the image "
          "settles even while the camera moves.",
    "t2": "Where the ball uncovers the floor, there is no past to use, and the grain comes back behind it.",
    "s1": "Reuse two: neighbours. Each pixel is blended with nearby pixels on the same surface, reaching further "
          "with every pass.",
    "c1": "Reuse three: a cache. Thousands of probes hold the light that bounces around the room, and a slice of "
          "them is updated every frame.",
    "c2": "Change the lamp, and the bounce light follows in under a second.",
    "r1": "Shiny surfaces add one ray around the mirror direction, blurred more the rougher they are.",
    "k1": "All of it runs in real time on a laptop GPU. A few rays per pixel, and the rest borrowed: from the past, "
          "the neighbours and a cache.",
}
SPEECH = lesson.Speech(CAPTION_TEXT, os.path.join(_HERE, "light_a_frame.speech.json"), words=WORDS,
                       voice_only={"o1"})    # o1 is read aloud over the title card, not drawn
PLAN = [("open", 0.3, ["o1"], 0.6), ("paths", 0.3, ["p1", "p2"], 0.6), ("raster", 0.3, ["g1"], 0.8),
        ("direct", 0.3, ["d1"], 1.4), ("bounce", 0.3, ["b1"], 1.4), ("time", 0.3, ["t1", "t2"], 1.0),
        ("space", 0.3, ["s1"], 1.4), ("cache", 0.3, ["c1", "c2"], 1.2), ("refl", 0.3, ["r1"], 1.2),
        ("cost", 0.3, ["k1"], 1.4), ("outro", 0.0, [], 7.5)]
TL, CAP = SPEECH.layout(PLAN, gap=0.2, slack=lesson.VOICE_LEAD + lesson.VOICE_TAIL + 0.3)


def cap0(k):
    return CAP[k][0]


def cap1(k):
    return CAP[k][1]


# ── the room: one description for the renderer and for the CPU path tracer ────
W, H, D, T = 4.0, 4.0, 4.0, 0.1
WHITE, RED, GREEN = 0xdcdcdc, 0xd1483f, 0x69b354          # Cornell box albedos (0.73; red, green), sRGB
BALL_R, BALL_Z, BALL_X0 = 0.42, 1.5, -0.3
ROOM = [  # (kind, size or radius, centre, yaw, colour, roughness, metalness)
    ("box", (W + 2 * T, T, D), (0, -T / 2, 0), 0.0, WHITE, 0.9, 0.0),                 # floor
    ("box", (W + 2 * T, T, D), (0, H + T / 2, 0), 0.0, WHITE, 0.9, 0.0),              # ceiling
    ("box", (W + 2 * T, H + 2 * T, T), (0, H / 2, -D / 2 - T / 2), 0.0, WHITE, 0.9, 0.0),   # back
    ("box", (T, H, D), (-W / 2 - T / 2, H / 2, 0), 0.0, RED, 0.9, 0.0),               # left
    ("box", (T, H, D), (W / 2 + T / 2, H / 2, 0), 0.0, GREEN, 0.9, 0.0),              # right
    ("box", (1.2, 2.4, 1.2), (-0.75, 1.2, -0.6), 0.3, WHITE, 0.9, 0.0),               # tall block
    ("box", (1.2, 1.2, 1.2), (0.85, 0.6, 0.3), -0.3, WHITE, 0.9, 0.0),                # short block
    ("sphere", 0.5, (0.85, 1.7, 0.3), 0.0, 0xeeeeee, 0.02, 1.0),                       # mirror
    ("sphere", BALL_R, (BALL_X0, BALL_R, BALL_Z), 0.0, 0xffffff, 0.3, 0.0),            # the ball (parked)
]
LAMP_Y, LAMP_R = H - 0.04, 0.45            # the lamp's glowing disc, just under the ceiling
LIGHT_POS, LIGHT_RADIUS, LIGHT_INTENSITY = (0.0, H - 0.35, 0.0), 0.25, 30.0
WARM, COOL = (1.0, 0.945, 0.867), (0.45, 0.62, 1.0)          # the lamp's colour, linear


# ── what moves: the camera, the ball, the lamp (film clock) ───────────────────
FRONT = ((0.0, 2.0, 9.6), (0.0, 2.0, 0.0), 30.0)


def _camera_keys():
    s, e = TL.start, TL.end
    k = [(0.0, ((0.0, 2.5, 15.5), (0.0, 2.0, 0.0), 30.0)),
         (s("paths"), FRONT), (e("raster"), FRONT),
         (e("direct") - 0.4, ((1.3, 2.4, 8.0), (-0.3, 1.2, 0.0), 32.0)),
         (e("bounce") - 0.4, ((-1.5, 2.3, 7.8), (0.2, 1.5, 0.0), 32.0)),
         (cap1("t1"), ((1.9, 1.7, 7.2), (0.0, 1.3, 0.0), 32.0)),
         (cap0("t2") + 1.0, ((0.9, 1.9, 4.4), (-0.2, 0.35, 0.9), 42.0)),
         (e("time"), ((0.7, 1.85, 4.3), (-0.2, 0.35, 0.9), 42.0)),
         (s("space") + 2.0, ((0.9, 2.0, 8.4), (0.0, 1.6, 0.0), 32.0)),
         (e("space"), ((0.3, 2.0, 8.6), (0.0, 1.8, 0.0), 32.0)),
         (s("cache") + 1.0, FRONT), (cap0("c2"), FRONT),
         (e("cache"), ((0.0, 2.1, 8.2), (0.0, 1.9, 0.0), 32.0)),
         (s("refl") + 1.4, ((2.3, 2.3, 5.2), (0.85, 1.6, 0.3), 34.0)),
         (e("refl"), ((1.0, 2.6, 4.7), (0.8, 1.6, 0.3), 34.0)),
         (s("cost") + 1.2, ((-1.2, 2.2, 10.2), (0.0, 1.9, 0.0), 30.0)),
         (e("cost") + 8.0, ((1.2, 2.0, 10.2), (0.0, 1.9, 0.0), 30.0))]
    return (Keys([(t, v[0]) for t, v in k]), Keys([(t, v[1]) for t, v in k]), Keys([(t, [v[2]]) for t, v in k]))


EYE_K, LOOK_K, FOV_K = _camera_keys()
ROLL_T0 = TL.start("direct")


def camera_at(t):
    return tuple(EYE_K(t)), tuple(LOOK_K(t)), float(FOV_K(t)[0])


def ball_at(t):
    """The ball's centre x and its roll angle about z: it rolls back and forth in front of the blocks."""
    if t < ROLL_T0:
        return BALL_X0, 0.0
    u = t - ROLL_T0
    ramp = smooth(remap(u, 0.0, 1.5))
    x = BALL_X0 + 1.3 * math.sin(0.62 * u) * ramp
    return x, -(x - BALL_X0) / BALL_R


def lamp_at(t):
    """The lamp's colour: warm, cool for a few seconds in the cache beat, then warm again."""
    return COOL if cap0("c2") + 0.9 <= t < cap0("c2") + 3.6 else WARM


def _hex(c):
    r, g, b = (int(round(255 * (min(max(v, 0.0), 1.0) ** (1 / 2.2)))) for v in c)
    return r << 16 | g << 8 | b


def ball_texture():
    """Eight segments round the ball, alternating orange and white, so its roll shows."""
    h, w = 64, 256
    u = (np.arange(w) + 0.5) / w
    seg = (np.floor(u * 8) % 2).astype(bool)
    img = np.empty((h, w, 3), np.uint8)
    img[:, seg] = (240, 240, 236)
    img[:, ~seg] = (232, 116, 38)
    img[:4] = img[-4:] = (240, 240, 236)
    return tp.data_texture(img, True)


def build_scene():
    scene = tp.Scene()
    scene.background = tp.Background(Stage.BG)
    parts = {}
    for kind, size, pos, yaw, col, rough, metal in ROOM:
        geo = tp.BoxGeometry(*size) if kind == "box" else tp.SphereGeometry(size, 96, 48)
        mat = lesson.standard(col, rough, metal)
        m = tp.Mesh(geo, mat)
        m.position.set(*pos)
        m.rotation.y = yaw
        scene.add(m)
        if kind == "sphere" and size == BALL_R:
            mat.map = ball_texture()
            parts["ball"] = m
    lamp_mat = tp.MeshBasicMaterial()
    lamp_mat.color = _hex(WARM)
    lamp = tp.Mesh(tp.CylinderGeometry(LAMP_R, LAMP_R, 0.04, 64), lamp_mat)
    lamp.position.set(0, H - 0.02, 0)
    scene.add(lamp)
    light = tp.PointLight(tp.Color(*WARM), LIGHT_INTENSITY, 0.0, 2.0)
    light.position.set(*LIGHT_POS)
    light.radius = LIGHT_RADIUS
    scene.add(light)
    parts.update(lamp=lamp, light=light)
    return scene, parts


def apply_state(t, cam, parts, aspect):
    eye, look, fov = camera_at(t)
    cam.fov = fov
    cam.aspect = aspect
    cam.update_projection_matrix()
    cam.position.set(*eye)
    cam.look_at(*look)
    cam.update_matrix_world()
    x, roll = ball_at(t)
    parts["ball"].position.set(x, BALL_R, BALL_Z)
    parts["ball"].rotation.z = roll
    c = lamp_at(t)
    parts["light"].color = tp.Color(*c)
    parts["lamp"].material.color = _hex(c)


# ── the renderer, in subprocesses ─────────────────────────────────────────────
def need_lighting_views():
    """The room's pictures need a threepp module that binds the renderer's lighting views."""
    r = getattr(tp, "VulkanRenderer", None)
    if r is None or not (hasattr(r, "lighting_view") and hasattr(r, "probe_grid")):
        raise RuntimeError(f"this film needs a threepp module with VulkanRenderer.lighting_view and probe_grid(); "
                           f"the one at {os.path.dirname(tp.__file__)} has neither")


def _renderer(w, h):
    canvas = tp.Canvas("light_a_frame", width=w, height=h, vsync=False, headless=True)
    r = tp.VulkanRenderer(canvas)
    r.tone_mapping = tp.ToneMapping.ACESFilmic
    r.tone_mapping_exposure = 1.0
    return canvas, r


def stream_main(spec):
    """Render one shot frame by frame at STEP Hz and write the frames (h x w x 3 uint8) to stdout."""
    # frames go to the real stdout; everything the renderer prints goes to stderr
    fd = os.dup(1)
    os.dup2(2, 1)
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(fd, os.O_BINARY)
    out = os.fdopen(fd, "wb")
    w, h = spec["w"], spec["h"]
    canvas, r = _renderer(w, h)
    scene, parts = build_scene()
    cam = tp.PerspectiveCamera(30, w / h, 0.1, 100.0)
    r.probe_gi = spec["probes"]
    r.set_view_taa(0, spec["taa"])
    r.lighting_view = spec["view"]
    t0, t1 = spec["t0"], spec["t1"]
    pre = int(round(spec["preroll"] * STEP))
    for k in range(pre):
        t = t0 - (pre - k) / STEP
        apply_state(t, cam, parts, w / h)
        r.sim_time = t
        r.render(scene, cam)
    if spec["reset"] == "start":
        r.reset_temporal_history()
    n = int(round((t1 - t0) * STEP)) + 1
    out.write(f"LESSON_FRAMES {n}\n".encode())
    out.flush()
    for k in range(n):
        t = t0 + k / STEP
        apply_state(t, cam, parts, w / h)
        if spec["reset"] == "every":
            r.reset_temporal_history()
        r.sim_time = t
        r.render(scene, cam)
        out.write(np.ascontiguousarray(r.read_pixels()).tobytes())
        out.flush()
    out.close()


def capture(outdir):
    """The stills (G-buffer panels, the lit frame, a probe snapshot) and the GPU times, at 1920x1080."""
    import shutil
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    canvas, r = _renderer(CW_, CH_)
    scene, parts = build_scene()
    cam = tp.PerspectiveCamera(30, CW_ / CH_, 0.1, 100.0)
    t_still = TL.start("raster") + 0.5
    apply_state(t_still, cam, parts, CW_ / CH_)
    t0 = time.time()

    def save(name, img):
        np.save(os.path.join(outdir, name + ".npy"), np.ascontiguousarray(img))

    for _ in range(120):
        r.render(scene, cam)
    tim, throttle = [], set()
    for k in range(90):
        r.render(scene, cam)
        tim.append(dict(r.frame_timings))
        if k in (30, 60):
            throttle.add(gpu_query("clocks_throttle_reasons.active"))
    save("final", r.read_pixels())
    timings = {key: float(np.median([t[key] for t in tim])) for key in tim[0]}
    grid = r.probe_grid()
    np.savez(os.path.join(outdir, "probes.npz"), origin=np.array(grid["origin"]), spacing=np.array(grid["spacing"]),
             dims=np.array(grid["dims"]), sh=grid["sh"])
    for aov in ("normals", "albedo", "segmentation"):
        save("gbuf_" + aov, r.render_aov(scene, cam, aov))
    np.save(os.path.join(outdir, "gbuf_depth.npy"), r.read_depth(scene, cam))
    numbers = dict(version=CAPTURE_VERSION, timings=timings, gpu=gpu_query("name"),
                   throttle=sorted(throttle), power_limit=gpu_query("power.limit"), seconds=time.time() - t0)
    with open(os.path.join(outdir, "numbers.json"), "w") as f:
        json.dump(numbers, f, indent=1)
    print(f"[capture] {len(os.listdir(outdir))} files in {time.time() - t0:.0f}s", flush=True)


def gpu_query(field):
    try:
        return subprocess.run(["nvidia-smi", f"--query-gpu={field}", "--format=csv,noheader"], capture_output=True,
                              text=True, timeout=10).stdout.strip().split("\n")[0]
    except Exception:
        return ""


def ensure_shots():
    p = os.path.join(SHOTS, "numbers.json")
    ok = False
    if os.path.isfile(p) and not os.environ.get("LESSON_RECAPTURE"):
        with open(p) as f:
            ok = json.load(f).get("version") == CAPTURE_VERSION
    if not ok:
        need_lighting_views()
        print("[capture] rendering the stills and timing the renderer ...", flush=True)
        subprocess.run([sys.executable, os.path.abspath(__file__), "--capture", SHOTS], check=True)
    with open(p) as f:
        return json.load(f)


class Stream:
    """One shot, rendered by its own renderer process and streamed in. Frames come in order;
    asking for an earlier one restarts the shot (a still replays it from the start)."""

    def __init__(self, name, spec, w, h):
        self.name = name
        self.spec = dict(spec, w=w, h=h)
        self.w, self.h = w, h
        self.proc, self.k, self.cur, self.n = None, -1, None, 0
        atexit.register(self.close)

    @property
    def t0(self):
        return self.spec["t0"]

    @property
    def t1(self):
        return self.spec["t1"]

    def _start(self):
        self.close()
        need_lighting_views()
        self.proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--stream", json.dumps(self.spec)],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        line = b""
        while not line.endswith(b"\n"):
            ch = self.proc.stdout.read(1)
            if not ch:
                raise RuntimeError(f"stream {self.name} ended before its first frame")
            line += ch
        self.n = int(line.split()[1])
        self.k = -1

    def _read_one(self):
        size = self.w * self.h * 3
        data = bytearray()
        while len(data) < size:
            chunk = self.proc.stdout.read(size - len(data))
            if not chunk:
                raise RuntimeError(f"stream {self.name} ended at frame {self.k + 1}")
            data += chunk
        self.k += 1
        return data

    def at(self, t):
        """The shot's frame at film time t, (h, w, 3) uint8."""
        k = max(int(round((t - self.t0) * STEP)), 0)
        if self.proc is None or k < self.k:
            self._start()
        k = min(k, self.n - 1)
        data = None
        while self.k < k:
            data = self._read_one()
        if data is not None:
            self.cur = np.frombuffer(bytes(data), np.uint8).reshape(self.h, self.w, 3)
        return self.cur

    def close(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:
                pass
            self.proc = None


# ── light paths on the CPU, against the same room ─────────────────────────────
def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def hit(o, d):
    """Nearest hit of the ray o + t d: (t, point, normal, index into ROOM or 'lamp'), or None."""
    best = None
    for i, (kind, size, pos, yaw, *_rest) in enumerate(ROOM):
        c = np.array(pos, float)
        if kind == "sphere":
            oc = o - c
            b = oc @ d
            q = b * b - (oc @ oc - size * size)
            if q < 0:
                continue
            t = -b - math.sqrt(q)
            if t < 1e-4:
                continue
            p = o + t * d
            n = (p - c) / size
        else:
            R = _rot_y(yaw)
            lo, ld = R.T @ (o - c), R.T @ d
            half = np.array(size) / 2
            with np.errstate(divide="ignore", invalid="ignore"):
                t1, t2 = (-half - lo) / ld, (half - lo) / ld
            tn, tf = np.nanmax(np.minimum(t1, t2)), np.nanmin(np.maximum(t1, t2))
            if tn > tf or tf < 1e-4:
                continue
            t = tn if tn > 1e-4 else tf
            lp = lo + t * ld
            ax = int(np.argmax(np.abs(lp) / half))
            ln = np.zeros(3)
            ln[ax] = np.sign(lp[ax])
            n = R @ ln
            p = o + t * d
        if best is None or t < best[0]:
            best = (t, p, n, i)
    if d[1] > 0:                                          # the lamp's disc, facing down
        t = (LAMP_Y - o[1]) / d[1]
        p = o + t * d
        if t > 1e-4 and p[0] ** 2 + p[2] ** 2 < LAMP_R ** 2 and (best is None or t < best[0]):
            best = (t, p, np.array([0, -1.0, 0]), "lamp")
    return best


def cosine_dir(n, rng):
    u1, u2 = rng.random(), rng.random()
    r, phi = math.sqrt(u1), 2 * math.pi * u2
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    tx = np.cross(n, a)
    tx /= np.linalg.norm(tx)
    ty = np.cross(n, tx)
    return r * math.cos(phi) * tx + r * math.sin(phi) * ty + math.sqrt(1 - u1) * n


PIXEL = (1040, 380)          # the pixel the opening follows (1920x1080, the FRONT camera): on the back wall
N_PATHS, MAX_BOUNCES = 1000, 4


def trace_paths(seed=7):
    """N_PATHS random paths through PIXEL: each a list of points, and whether it reached the lamp."""
    rng = np.random.default_rng(seed)
    cam = CameraBasis(*FRONT)
    d0 = cam.ray(PIXEL[0] + 0.5, PIXEL[1] + 0.5)
    out = []
    for _ in range(N_PATHS):
        o, d, pts, lit = cam.eye.copy(), d0.copy(), [cam.eye.copy()], False
        for _b in range(MAX_BOUNCES + 1):
            h = hit(o, d)
            if h is None:
                break
            _, p, n, idx = h
            pts.append(p)
            if idx == "lamp":
                lit = True
                break
            d = d - 2 * (d @ n) * n if ROOM[idx][6] > 0.5 else cosine_dir(n, rng)   # metal: mirror bounce
            o = p + n * 1e-4
        out.append((pts, lit))
    return out


class CameraBasis:
    """A camera as numpy: world point -> pixel of a CW_ x CH_ frame, and pixel -> ray."""

    def __init__(self, eye, look, fov):
        self.eye = np.array(eye, float)
        f = np.array(look, float) - self.eye
        self.f = f / np.linalg.norm(f)
        self.r = np.cross(self.f, [0, 1.0, 0])
        self.r /= np.linalg.norm(self.r)
        self.u = np.cross(self.r, self.f)
        self.th = math.tan(math.radians(fov) / 2)
        self.a = CW_ / CH_

    def project(self, p):
        p = np.atleast_2d(np.asarray(p, float)) - self.eye
        z = p @ self.f
        x = (p @ self.r) / (z * self.th * self.a)
        y = (p @ self.u) / (z * self.th)
        return np.c_[(x * 0.5 + 0.5) * CW_, (0.5 - y * 0.5) * CH_]

    def ray(self, px, py):
        x = (px / CW_ * 2 - 1) * self.th * self.a
        y = (1 - py / CH_ * 2) * self.th
        d = self.f + x * self.r + y * self.u
        return d / np.linalg.norm(d)


# ── the shots ─────────────────────────────────────────────────────────────────
# (beat, view, probe cache, TAA, history reset, preroll s). A and B of a beat are the two sides of a wipe.
def _shots():
    s, e = TL.start, TL.end

    def win(a, b):
        return dict(t0=max(a - 0.6, 0.0), t1=b + 0.8)
    out = {
        "open":     dict(win(0.0, e("paths")), view="final", probes=True, taa=True, reset="none", preroll=2.0),
        "direct_a": dict(win(s("direct"), e("direct")), view="direct_unshadowed", probes=True, taa=True,
                         reset="none", preroll=0.5),
        "direct_b": dict(win(s("direct"), e("direct")), view="direct_temporal", probes=False, taa=False,
                         reset="every", preroll=0.0),
        "bounce":   dict(win(s("bounce"), e("bounce")), view="final_temporal", probes=False, taa=False,
                         reset="every", preroll=0.0),
        "time_a":   dict(win(s("time"), cap1("t1")), view="final_temporal", probes=False, taa=False,
                         reset="every", preroll=0.0),
        "time_b":   dict(win(s("time"), e("space")), view="final_temporal", probes=False, taa=True,
                         reset="start", preroll=0.0),
        "time_c":   dict(win(cap0("t2") - 1.0, e("time")), view="final_temporal", probes=True, taa=False,
                         reset="none", preroll=2.0),
        "space_b":  dict(win(s("space"), e("space")), view="final", probes=False, taa=True, reset="none",
                         preroll=1.0),
        "cache":    dict(win(s("cache"), e("cache")), view="final", probes=True, taa=True, reset="none", preroll=2.0),
        "refl_a":   dict(win(s("refl"), e("refl")), view="reflections", probes=True, taa=True, reset="none",
                         preroll=1.5),
        "refl_b":   dict(win(s("refl"), e("refl")), view="final", probes=True, taa=True, reset="none", preroll=1.5),
        "cost":     dict(win(s("cost"), e("cost") + 8.0), view="final", probes=True, taa=True, reset="none",
                         preroll=1.5),
    }
    return out


SUMMARY = [(r"$\mathrm{raster}$", "What the camera sees is rasterised, not traced."),
           (r"$\mathrm{rays}$", "Shadows, bounces, reflections: a few rays per pixel."),
           (r"$\mathrm{reuse}$", "Over past frames, across neighbours, through a probe cache."),
           (r"$\mathrm{cost}$", "Real time, on a laptop GPU.")]

CODE = ["renderer.setLightingView(",
        "    VulkanRenderer::LightingView::IndirectTemporal);"]

PASS_ROWS = [("tlas_refit_ms", "ray-tracing structure", "refit for this frame"),
             ("raster_gbuf_ms", "G-buffer", "rasterised"), ("rtao_ms", "ambient occlusion", "rays, half resolution"),
             ("probe_gi_ms", "probe cache", "a slice of the probes, each frame"),
             ("shade_ms", "shade", "shadow, bounce and reflection rays"),
             ("denoise_ms", "denoise", "edge-aware filter and reflection blur"), ("taa_ms", "TAA", "temporal anti-aliasing")]

# ── the picture ───────────────────────────────────────────────────────────────
BIG = (160, 18, 1600, 900)                 # the room, large: x, y, w, h (16:9)


def turbo_depth(depth):
    """Metric depth as a turbo-coloured image (near = red), the background in the film's colour."""
    d = np.asarray(depth, float)
    fg = d < 50
    lo, hi = np.percentile(d[fg], 1), np.percentile(d[fg], 99)
    img = (lesson.turbo(1 - np.clip((d - lo) / (hi - lo), 0, 1)) * 255).astype(np.uint8)
    img[~fg] = lesson.hex_rgb(Stage.BG)
    return img


def resize(img, w, h):
    """Nearest-neighbour resize (the stills are 1920x1080; the room is shown smaller)."""
    ys = (np.arange(h) * img.shape[0] / h).astype(int)
    xs = (np.arange(w) * img.shape[1] / w).astype(int)
    return img[ys][:, xs]


class Slot:
    """A texture that shows a new numpy image every frame."""

    def __init__(self):
        self.tex, self.shape = None, None

    def texture(self, img):
        img = np.ascontiguousarray(img[::-1])            # textures take their rows bottom first
        if self.tex is None or self.shape != img.shape:
            self.tex, self.shape = tp.data_texture(img, True), img.shape
        else:
            self.tex.update_data(img)
        return self.tex


class Painter:
    def __init__(self, ov, streams, stills, rec, sw, sh):
        self.ov, self.streams, self.stills, self.rec = ov, streams, stills, rec
        self.sw, self.sh = sw, sh
        self.slots = {}
        self.captions = SPEECH.captions(CAP)

    # helpers ------------------------------------------------------------------
    def show(self, slot, img, rect, a):
        if a <= 0.003 or img is None:
            return
        x, y, w, h = rect
        self.ov.image(x, y, w, h, self.slots.setdefault(slot, Slot()).texture(img), alpha=a)

    def frame(self, name, t):
        return self.streams[name].at(t)

    def wipe(self, t, a_name, b_name, u):
        """Stream A with stream B from the fraction u of the width onwards (u in 0..1)."""
        A, B = self.frame(a_name, t), self.frame(b_name, t)
        x = int(round(u * self.sw))
        if x <= 0:
            return B
        if x >= self.sw:
            return A
        out = A.copy()
        out[:, x:] = B[:, x:]
        return out

    def wipe_line(self, u, a, rect=BIG):
        x, y, w, h = rect
        if a <= 0.003 or not 0.0 < u < 1.0:
            return
        px = x + u * w
        self.ov.line([(px, y), (px, y + h)], 0xffffff, 3.0, 0.9 * a)

    def to_rect(self, pts, rect):
        x, y, w, h = rect
        p = np.atleast_2d(pts)
        return np.c_[x + p[:, 0] * w / CW_, y + p[:, 1] * h / CH_]

    def pill(self, rect, text, a, color=TEXT, sub=None, corner="tl"):
        if a <= 0.003:
            return
        ov = self.ov
        x, y, w, h = rect
        tw = ov.text_width(text, 20, "semibold") + 36
        if sub:
            tw = max(tw, ov.text_width(sub, 17) + 36)
        ph = 40 if not sub else 66
        px = x + 18 if corner == "tl" else x + w - 18 - tw
        ov.panel(px, y + 16, tw, ph, radius=12, fill=0x0d131e, alpha=0.82 * a)
        ov.text(px + 18, y + 16 + 20, text, size=20, color=color, alpha=a, kind="semibold", anchor="lm")
        if sub:
            ov.text(px + 18, y + 16 + 48, sub, size=17, color=DIM, alpha=a, anchor="lm")

    # beats ----------------------------------------------------------------------
    def draw2d(self, t):
        ov = self.ov
        for beat in (self.opening, self.raster, self.direct, self.bounce, self.time_beat, self.space, self.cache,
                     self.refl, self.cost):
            beat(t)
        ov.captions(t, self.captions)
        ov.summary(t, TL.start("outro"), TL.end("outro"),
                   SUMMARY,
                   "Every picture of the room is threepp's own Vulkan output, one lighting view at a time",
                   C_ACCENT, C_ACCENT, text_dx=300)

    def opening(self, t):
        a = envelope(t, 0.0, TL.end("paths") + 0.3, 0.6, 0.6)
        if a <= 0.003:
            return
        ov = self.ov
        self.show("open", self.frame("open", t), BIG, a)
        dim = envelope(t, 0.0, TL.end("open"), 0.3, 0.9)
        ov.panel(BIG[0], BIG[1], BIG[2], BIG[3], radius=0, fill=0x05080d, alpha=0.6 * dim)
        ov.title_card(t, "A THREEPP LESSON  ·  PART 6", "How threepp lights a frame",
                      "Rasterised visibility, ray-traced light, and three ways to reuse a ray", C_ACCENT,
                      t_in=0.3, t_out=TL.end("open") - 0.3, size=88)
        # the paths: they draw on one after another, then the misses fill in as a haze
        pa = a * envelope(t, TL.start("paths"), TL.end("paths") + 0.3, 0.4, 0.5)
        if pa <= 0.003:
            return
        rec = self.rec
        px = self.to_rect([PIXEL], BIG)[0]
        ov.circle(px[0], px[1], 9, outline=0xffffff, width=2.5, alpha=pa)
        ov.text(px[0] + 16, px[1] - 18, "one pixel", size=18, color=TEXT, alpha=pa, anchor="lm")
        u = smooth(remap(t, cap0("p1") + 0.5, cap0("p1") + 3.2))
        for k, q in enumerate(rec["reached_px"]):
            f = min(max(u * 3.0 - k, 0.0), 1.0)
            if f <= 0:
                continue
            seg = self._partial(self.to_rect(q, BIG), f)
            ov.line(seg, C_WARM, 2.6, pa)
            for p in seg[1:]:
                ov.circle(p[0], p[1], 4.5, fill=C_WARM, alpha=pa)
        ma = pa * smooth(remap(t, cap0("p1") + 3.4, cap0("p1") + 4.6))
        if ma > 0.003:
            for q in rec["missed_px"]:
                ov.line(self.to_rect(q, BIG), 0x8aa0c0, 1.2, 0.35 * ma)
            self.pill(BIG, "Random paths from one pixel", ma, corner="tr",
                      sub="orange: three that reached the lamp · grey: some that did not")

    @staticmethod
    def _partial(q, f):
        n = len(q) - 1
        s = f * n
        k = int(math.floor(s))
        if k >= n:
            return q
        return np.vstack([q[:k + 1], q[k] + (q[k + 1] - q[k]) * (s - k)])

    def raster(self, t):
        """The lit frame peels back, strip by strip, into its G-buffer."""
        a = envelope(t, TL.start("raster") - 0.1, TL.end("raster") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        layers = self.rec["peel"]                       # final, normals, albedo, depth, objects (resized)
        labels = ["normal", "colour (albedo)", "depth", "object"]
        img = layers[0].copy()
        edges = []
        L, R = self.rec["room_x"]                          # the room's front opening, as fractions of the width
        for k in range(4):
            # strip k (a quarter of the room) wipes in from its right edge, one after another
            u = smooth(remap(t, TL.start("raster") + 0.6 + 0.55 * k, TL.start("raster") + 1.3 + 0.55 * k))
            xk = int(self.sw * (L + (R - L) * k / 4))
            x1 = int(self.sw * (L + (R - L) * (k + 1) / 4))
            x0 = int(round(x1 - (x1 - xk) * u))
            if x0 < x1:
                img[:, x0:x1] = layers[k + 1][:, x0:x1]
            edges.append((x0, u))
        self.show("raster", img, BIG, a)
        x, y, w, h = BIG
        for k, (x0, u) in enumerate(edges):
            la = a * smooth(remap(u, 0.6, 1.0))
            if la > 0.003:
                cx = x + w * (L + (R - L) * (k + 0.5) / 4)
                tw = self.ov.text_width(labels[k], 20, "semibold") + 32
                self.ov.panel(cx - tw / 2, y + h - 60, tw, 40, radius=12, fill=0x0d131e, alpha=0.82 * la)
                self.ov.text(cx, y + h - 40, labels[k], size=20, color=TEXT, alpha=la, kind="semibold", anchor="mm")
        self.pill(BIG, "The G-buffer", a * smooth(remap(t, TL.start("raster") + 2.8, TL.start("raster") + 3.4)),
                  sub="rasterised, no rays")

    def direct(self, t):
        a = envelope(t, TL.start("direct"), TL.end("direct") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        u = 1.0 - 0.55 * smooth(remap(t, cap0("d1") + 2.6, cap0("d1") + 4.0))
        self.show("direct", self.wipe(t, "direct_a", "direct_b", u), BIG, a)
        self.wipe_line(u, a)
        self.pill(BIG, "Direct light, no shadows", a, sub="summed exactly · no rays")
        self.pill(BIG, "× shadow rays, one frame", a * (1 - smooth(remap(u, 0.7, 0.95))), corner="tr",
                  sub="a ray or two per pixel · TAA off")

    def bounce(self, t):
        a = envelope(t, TL.start("bounce"), TL.end("bounce") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        self.show("bounce", self.frame("bounce", t), BIG, a)
        self.pill(BIG, "Everything, one frame", a, sub="no reuse · probe cache off · TAA off")

    def time_beat(self, t):
        a = envelope(t, TL.start("time"), TL.end("time") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        # raw | averaged over time, the wipe opening while the camera moves; then the time side alone
        u = 0.5 * smooth(remap(t, cap0("t1") + 0.6, cap0("t1") + 1.8))
        solo = smooth(remap(t, cap1("t1") - 0.6, cap1("t1") + 0.2))
        u = u * (1 - solo)
        close = envelope(t, cap0("t2") - 0.5, TL.end("time") + 1.0, 0.6, 0.1)
        if close < 1.0:
            img = self.wipe(t, "time_a", "time_b", u) if solo < 1.0 else self.frame("time_b", t)
            self.show("time", img, BIG, a)
        if close > 0.003:
            self.show("time_close", self.frame("time_c", t), BIG, a * close)
        self.wipe_line(u, a * (1 - solo))
        self.pill(BIG, "One frame", a * (1 - solo) * smooth(remap(u, 0.05, 0.3)), sub="no reuse")
        self.pill(BIG, "Averaged over time", a * (1 - close), corner="tr",
                  sub="pixel histories and TAA · probe cache off")
        self.pill(BIG, "Averaged over time, close up", a * close, corner="tr",
                  sub="probe cache on · TAA off · no spatial filter")

    def space(self, t):
        a = envelope(t, TL.start("space"), TL.end("space") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        ov = self.ov
        u = 1.0 - 0.5 * smooth(remap(t, cap0("s1") + 0.8, cap0("s1") + 2.2))
        self.show("space", self.wipe(t, "time_b", "space_b", u), BIG, a)
        self.wipe_line(u, a)
        self.pill(BIG, "Over time", a, sub="pixel histories and TAA · probe cache off")
        self.pill(BIG, "Over time and across neighbours", a * (1 - smooth(remap(u, 0.7, 0.95))), corner="tr",
                  sub="an edge-aware filter · probe cache off")
        # the filter's reach: 5x5 taps, twice as far apart each pass
        da = a * smooth(remap(t, cap0("s1") + 3.5, cap0("s1") + 4.1))
        if da <= 0.003:
            return
        x0, y0 = BIG[0] + BIG[2] - 420, BIG[1] + BIG[3] - 250
        ov.panel(x0, y0, 400, 230, radius=14, alpha=0.8 * da, outline=0x8aa0c0, outline_alpha=0.16)
        ov.text(x0 + 20, y0 + 22, "ONE PIXEL'S NEIGHBOURS, PASS BY PASS", size=15, color=DIM, alpha=da,
                kind="semibold", tracking=2.0)
        cx, cy = x0 + 200, y0 + 135
        for k, (step, col) in enumerate(((1, 0xffffff), (2, C_WARM), (4, C_ACCENT), (8, C_OK))):
            pa = da * smooth(remap(t, cap0("s1") + 4.0 + 0.5 * k, cap0("s1") + 4.4 + 0.5 * k))
            g = 3.1 * step
            for i in range(-2, 3):
                for j in range(-2, 3):
                    if (i, j) != (0, 0):
                        ov.circle(cx + i * g, cy + j * g, 2.6, fill=col, alpha=pa)
        ov.circle(cx, cy, 3.5, fill=0xffffff, alpha=da)

    def cache(self, t):
        a = envelope(t, TL.start("cache"), TL.end("cache") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        ov = self.ov
        self.show("cache", self.frame("cache", t), BIG, a)
        # one slice of the probe grid over the room (a snapshot, projected with the camera at t)
        ga = a * envelope(t, cap0("c1") + 0.8, cap1("c1") - 0.2, 0.8, 0.6)
        if ga > 0.003:
            ov.panel(BIG[0], BIG[1], BIG[2], BIG[3], radius=0, fill=0x05080d, alpha=0.5 * ga)
            dots = self.rec["probe_dots"]
            q = self.to_rect(CameraBasis(*camera_at(t)).project(dots["pos"]), BIG)
            reveal = remap(t, cap0("c1") + 1.0, cap0("c1") + 3.2)
            for (x, y), col, order in zip(q, dots["col"], dots["order"]):
                da = ga * smooth(min(max(reveal * 1.4 - order, 0.0), 1.0))
                if da > 0.003:
                    ov.circle(x, y, 5.0, fill=col, alpha=da)
            self.pill(BIG, "The probe cache, one slice", ga, sub="each dot a probe, coloured by the light it holds")
        la = a * smooth(remap(t, cap0("c2") + 0.4, cap0("c2") + 0.8))
        self.pill(BIG, "The lamp turns blue" if lamp_at(t) == COOL else "The lamp, warm", la,
                  sub="default settings · probe cache on", corner="tr")

    def refl(self, t):
        a = envelope(t, TL.start("refl"), TL.end("refl") + 0.2, 0.5, 0.5)
        if a <= 0.003:
            return
        u = 0.15 + 0.4 * smooth(remap(t, cap0("r1") + 0.8, cap0("r1") + 4.5))
        self.show("refl", self.wipe(t, "refl_a", "refl_b", u), BIG, a)
        self.wipe_line(u, a)
        self.pill(BIG, "Reflections only", a, sub="a ray per pixel on shiny surfaces")
        self.pill(BIG, "Everything", a, corner="tr", sub="the lit frame, default settings")

    def cost(self, t):
        a = envelope(t, TL.start("cost"), TL.end("cost") + 0.6, 0.5, 0.6)
        if a <= 0.003:
            return
        ov = self.ov
        rec = self.rec
        self.show("cost", self.frame("cost", t), (40, 60, 1000, 563), a)
        # where one frame's GPU time goes: the renderer's own per-pass timestamps, as shares
        x, y, w = 1080, 60, 800
        rows = rec["passes"]
        card(ov, x, y, w, 80 + 46 * len(rows), a, "WHERE ONE FRAME'S GPU TIME GOES")
        total = sum(v for _, v, _ in rows)
        for k, (label, ms, note) in enumerate(rows):
            ka = a * smooth(remap(t, cap0("k1") + 0.4 + 0.2 * k, cap0("k1") + 0.9 + 0.2 * k))
            yy = y + 70 + 46 * k
            ov.text(x + 26, yy + 12, label, size=19, color=TEXT, alpha=ka, anchor="lm")
            ov.text(x + 26, yy + 33, note, size=15, color=DIM, alpha=ka, anchor="lm")
            bx, bw = x + 330, w - 330 - 30
            grow = smooth(remap(t, cap0("k1") + 0.4 + 0.2 * k, cap0("k1") + 1.4 + 0.2 * k))
            ov.bar(bx, yy + 8, bw * ms / total * grow, 14, 1.0, C_ACCENT, alpha=ka, radius=4)
        ca = a * smooth(remap(t, cap0("k1") + 3.0, cap0("k1") + 3.6))
        cw = ov.text_width("0", 19, "mono")
        card(ov, 40, 680, 1000, 64 + 30 * len(CODE), ca, "EVERY PICTURE OF THE ROOM IN THIS FILM, IN C++")
        for j, line in enumerate(CODE):
            for col, s_, c in tokenize(line, "cpp", CPP_KEYWORDS):
                ov.text(70 + col * cw, 680 + 50 + 30 * j + 15, s_, size=19, color=c, alpha=ca, kind="mono",
                        anchor="lm")


# ── the stage ─────────────────────────────────────────────────────────────────
def probe_dots(probes):
    """One x-y slice of the probe grid (the middle z layer), coloured by irradiance towards
    the front camera (SH-L1: L00 · 0.886 + L1 · n · 1.023)."""
    o, s, dims, sh = probes["origin"], probes["spacing"], probes["dims"], probes["sh"]
    nx, ny, nz = (int(v) for v in dims)
    k = nz // 2
    n = np.array(FRONT[0]) - np.array(FRONT[1])
    n /= np.linalg.norm(n)
    pos, col, order = [], [], []
    for j in range(ny):
        for i in range(nx):
            idx = i + nx * (j + ny * k)
            if sh[idx, 0, 3] < 0.5:                       # a probe inside geometry
                continue
            e = np.maximum(sh[idx, 0, :3] * 0.8862269 + (sh[idx, 1, :3] * n[0] + sh[idx, 2, :3] * n[1]
                                                          + sh[idx, 3, :3] * n[2]) * 1.0233267, 0)
            pos.append(o + np.array([i, j, k]) * s)
            col.append(e)
            order.append((i + j) / (nx + ny))
    col = np.array(col)
    c = np.clip(col / np.percentile(col.max(axis=1), 98), 0, 1) ** (1 / 2.2)
    hexes = [int(r * 255) << 16 | int(g * 255) << 8 | int(b * 255) for r, g, b in c]
    return dict(pos=np.array(pos), col=hexes, order=np.array(order) * 1.4)


def setup(width, height):
    t0 = time.time()
    numbers = ensure_shots()
    sw, sh = int(round(BIG[2] * width / 1920 / 2)) * 2, int(round(BIG[3] * height / 1080 / 2)) * 2
    streams = {name: Stream(name, spec, sw, sh) for name, spec in _shots().items()}
    st = Stage(width, height, renderer="gl", floor=False, fog=None)
    stills = {name: np.load(os.path.join(SHOTS, name + ".npy")) for name in
              ("final", "gbuf_normals", "gbuf_albedo", "gbuf_segmentation")}
    depth = np.load(os.path.join(SHOTS, "gbuf_depth.npy"))
    stills["gbuf_depth"] = turbo_depth(depth)
    for k in ("gbuf_normals", "gbuf_albedo", "gbuf_segmentation"):
        stills[k] = stills[k].copy()
        stills[k][depth >= 50] = lesson.hex_rgb(Stage.BG)            # the background, as the lit frame has it
    peel = [resize(stills[k], sw, sh) for k in ("final", "gbuf_normals", "gbuf_albedo", "gbuf_depth",
                                                "gbuf_segmentation")]
    cam = CameraBasis(*FRONT)
    room_x = tuple(cam.project(np.array([[-W / 2, 0.0, D / 2], [W / 2, 0.0, D / 2]]))[:, 0] / CW_)
    paths = trace_paths()
    reached = [p for p, lit in paths if lit]
    shown = []
    for n in (4, 5, 6):                                   # after one, two and three bounces
        shown += [p for p in reached if len(p) == n][:1]

    def to_px(pts):                                       # a path leaves the camera through PIXEL
        return np.vstack([np.array(PIXEL, float), cam.project(np.array(pts[1:]))])
    missed = [to_px(p) for p, lit in paths if not lit][:40]
    probes = dict(np.load(os.path.join(SHOTS, "probes.npz")))
    tim = numbers["timings"]
    passes = [(label, tim[key], note) for key, label, note in PASS_ROWS if key in tim and tim[key] > 0.005]
    gpu_total = tim["gpu_total_ms"]
    gpu = numbers["gpu"].replace("NVIDIA ", "").replace("GeForce ", "")
    nums = dict(reached=f"{len(reached)}", tried=f"{N_PATHS:,}", ms=f"{gpu_total:.1f}", probes="16,384")
    print(f"[paths] {len(reached)} of {N_PATHS} paths from pixel {PIXEL} reached the lamp in <= {MAX_BOUNCES} bounces")
    print(f"[gpu] {gpu}: " + ", ".join(f"{label} {ms:.2f}" for label, ms, _ in passes) + f"; total {gpu_total:.2f} ms"
          f" (throttle reasons under load {numbers.get('throttle')}, power limit {numbers.get('power_limit')})")
    rec = dict(numbers=nums, reached_px=[to_px(p) for p in shown], missed_px=missed, n_reached=len(reached),
               probe_dots=probe_dots(probes), passes=passes, gpu_total=gpu_total, gpu=gpu, peel=peel,
               room_x=room_x)
    ov = Hud(1920, 1080, math_cache=os.path.join(_HERE, "light_a_frame.math.json"))
    painter = Painter(ov, streams, stills, rec, sw, sh)
    print(f"[setup] {time.time() - t0:.1f}s, film {TL.duration:.1f} s on the script clock, shots {sw}x{sh}")

    def render(t):
        ov.begin()
        painter.draw2d(t)
        ov.fade(fade_in_out(t, TL.duration))
        ov.end()
        for s in streams.values():                         # a shot whose part of the film is over can go
            if s.proc is not None and t > s.t1 + 0.5:
                s.close()
        return st.frame(t, hud=ov)
    return render, painter.captions


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--capture":
        capture(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--stream":
        stream_main(json.loads(sys.argv[2]))
    else:
        run("light_a_frame", TL.duration, setup, fps=FPS, speech=SPEECH)
