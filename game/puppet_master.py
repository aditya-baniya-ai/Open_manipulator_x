"""
PUPPET MASTER: control Robo's arm with your hand and whack the targets.

A camera on a stand watches the player. Robo's gripper follows your hand; make a fist
to whack (Robo taps straight down). Targets are stickers on the table in front of Robo;
the screen lights one up at a time. Whack it before its timer runs out.

    Normal target   50 points, plus up to 50 for being quick
    Gold target     double points, but it doesn't stay long
    Red target      DON'T whack it: -300 and your combo is gone (+50 for leaving it)
    Missed whack    -50 and your combo is gone
    Combo           x2 after 5 hits in a row, x3 after 10
    Max score       9,999 (only near-perfect play gets there)

Run (see README.md, "Puppet Master"):
    python3 puppet_master.py --no-arm     no robot: a pretend arm (try it anywhere)
    python3 puppet_master.py              with Robo's arm (real or simulated) running
    python3 puppet_master.py --setup      place the target stickers (once)

Keys: type your name and press Enter to play, Esc to quit, F for full screen.
"""

import argparse
import json
import math
import random
import threading
import time
from pathlib import Path

import cv2
import numpy as np

import arm_link
from tracker import make_tracker, open_camera

HERE = Path(__file__).resolve().parent
LEADERBOARD = HERE / "leaderboard.json"

# --- The game rules ----------------------------------------------------------------
ROUND_TIME = 60.0        # seconds
LIFE_START = 5.0         # seconds a target stays at the start of the round ...
LIFE_END = 2.5           # ... and at the end
GAP = 0.35               # seconds between targets
GOLD_CHANCE = 0.15
RED_CHANCE = 0.15        # red targets only after the first RED_AFTER seconds
RED_AFTER = 10.0
HIT_RADIUS = 28.0        # mm: how close to a target counts as a hit
POINTS = 50             # for a hit, plus up to the same again for being quick
COMBO_EVERY = 5          # hits in a row for each extra x1 ...
COMBO_MAX = 3            # ... up to x3
MAX_SCORE = 9999
RANKS = [(7500, "S"), (5500, "A"), (3500, "B"), (0, "C")]   # from test rounds
SHOW_HAND_FOR = 1.0      # seconds the hand must be seen before the countdown

# Target stickers on the table: (distance from the base in mm, angle in degrees,
# + = Robo's left = the player's right). "--setup" shows where to put them.
TARGETS = [(145, -32), (145, 0), (145, 32), (200, -38), (200, -13), (200, 13), (200, 38)]

# --- The look ------------------------------------------------------------------------
W, H = 1280, 720
INK = (240, 240, 245)
DIM = (150, 150, 170)
GOLD = (60, 200, 255)          # colours are BGR
CYAN = (255, 220, 60)
PINK = (180, 80, 255)
RED = (70, 70, 255)
GREEN = (120, 230, 120)
PANEL = (40, 28, 30)
CAMERA_BOX = (30, 100, 650, 565)     # left, top, right, bottom
MAP_BOX = (680, 100, 1250, 690)
FOOTER_BOX = (30, 580, 650, 690)

FONT_FILES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",      # Ubuntu (the Jetson)
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",         # Mac
    "/System/Library/Fonts/Helvetica.ttc",
]


class Text:
    """Nice text (TrueType fonts through Pillow). Each piece of text is drawn once into a
    small picture and kept, then pasted where it's needed: much faster than drawing
    all the text on the whole screen every frame."""

    def __init__(self):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.fonts, self.cache, self.queue = {}, {}, []
        self.file = next((f for f in FONT_FILES if Path(f).exists()), None)

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = self.ImageFont.truetype(self.file, size) if self.file \
                else self.ImageFont.load_default()
        return self.fonts[size]

    def add(self, words, x, y, size=24, color=INK, anchor="la"):
        self.queue.append((str(words), int(x), int(y), size, color, anchor))

    def sprite(self, words, size, anchor):
        """The text as a see-through mask (0-1), and where its corner is from (x, y)."""
        key = (words, size, anchor)
        if key not in self.cache:
            if len(self.cache) > 600:
                self.cache.clear()
            font = self.font(size)
            probe = self.ImageDraw.Draw(self.Image.new("L", (1, 1)))
            x0, y0, x1, y1 = probe.textbbox((0, 0), words, font=font, anchor=anchor)
            mask = self.Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 0)
            self.ImageDraw.Draw(mask).text((-x0, -y0), words, font=font, fill=255,
                                            anchor=anchor)
            self.cache[key] = (np.asarray(mask, np.float32)[..., None] / 255, x0, y0)
        return self.cache[key]

    def draw(self, canvas):
        height, width = canvas.shape[:2]
        for words, x, y, size, color, anchor in self.queue:
            mask, dx, dy = self.sprite(words, size, anchor)
            left, top = x + dx, y + dy
            right, bottom = left + mask.shape[1], top + mask.shape[0]
            # Only the part that's on the screen
            cl, ct, cr, cb = max(0, left), max(0, top), min(width, right), min(height, bottom)
            if cl >= cr or ct >= cb:
                continue
            m = mask[ct - top:cb - top, cl - left:cr - left]
            area = canvas[ct:cb, cl:cr]
            area[:] = (area * (1 - m) + np.array(color, np.float32) * m).astype(np.uint8)
        self.queue = []
        return canvas


def background():
    """Dark blue-purple gradient with a faint grid (made once)."""
    top, bottom = np.array([30, 15, 10], float), np.array([45, 15, 30], float)
    rows = np.linspace(0, 1, H)[:, None]
    canvas = (top + (bottom - top) * rows[..., None]).repeat(W, axis=1).astype(np.uint8)
    for x in range(0, W, 40):
        cv2.line(canvas, (x, 0), (x, H), (50, 30, 35), 1)
    for y in range(0, H, 40):
        cv2.line(canvas, (0, y), (W, y), (50, 30, 35), 1)
    return canvas


def panel(canvas, box, color=PANEL, border=(90, 60, 70)):
    left, top, right, bottom = box
    overlay = canvas.copy()
    cv2.rectangle(overlay, (left, top), (right, bottom), color, -1)
    cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)
    cv2.rectangle(canvas, (left, top), (right, bottom), border, 2, cv2.LINE_AA)


def glow_circle(canvas, center, radius, color, thickness=-1):
    """A circle with a soft glow around it (only the area around it is touched)."""
    glow = int(radius * 1.6) + 2
    x, y = center
    left, top = max(0, x - glow), max(0, y - glow)
    right, bottom = min(canvas.shape[1], x + glow), min(canvas.shape[0], y + glow)
    if left < right and top < bottom:
        area = canvas[top:bottom, left:right]
        overlay = area.copy()
        cv2.circle(overlay, (x - left, y - top), glow - 2, color, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.25, area, 0.75, 0, area)
    cv2.circle(canvas, center, int(radius), color, thickness, cv2.LINE_AA)


# --- The camera ----------------------------------------------------------------------

class Camera:
    """Reads the camera in the background and keeps only the newest picture (so the
    game never shows an old one), mirrored like a mirror (mirror=False: as it is)."""

    def __init__(self, device, mirror=True):
        self.mirror = mirror
        self.capture = open_camera(device)
        self.frame, self.count, self.running = None, 0, True
        if not self.capture.isOpened():
            raise RuntimeError(f"Can't open the camera {device}. Is another program "
                               "(like usb_cam or detect.py) using it?")
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        while self.running:
            ok, frame = self.capture.read()
            if ok:
                self.frame = cv2.flip(frame, 1) if self.mirror else frame
                self.count += 1

    def close(self):
        self.running = False
        time.sleep(0.05)
        self.capture.release()


class Tracking:
    """Tracks the hand in the background, always on the newest camera picture, so
    drawing the screen never waits for it."""

    def __init__(self, tracker, camera):
        self.tracker, self.camera = tracker, camera
        self.hand, self.frame, self.ms, self.running = None, None, 0.0, True
        self.failed = False
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        last = None
        while self.running:
            frame = self.camera.frame
            if frame is None or frame is last:
                time.sleep(0.002)
                continue
            last = frame
            started = time.perf_counter()
            try:
                hand = self.tracker.track(frame)
            except Exception as error:  # a bad picture must not stop the tracking
                if not self.failed:
                    print(f"Hand tracking error (still trying): {error}")
                self.failed, hand = True, None
            self.ms = 0.9 * self.ms + 0.1 * (time.perf_counter() - started) * 1000
            # The picture and the hand found in it, together (so the drawing lines up)
            self.hand, self.frame = hand, frame

    def close(self):
        self.running = False


# --- The game ------------------------------------------------------------------------

def target_xy(target):
    reach, angle = target
    return (arm_link.arm.BASE_X + reach * math.cos(math.radians(angle)),
            reach * math.sin(math.radians(angle)))


def rank_for(score):
    return next(rank for floor, rank in RANKS if score >= floor)


def load_board():
    try:
        return json.loads(LEADERBOARD.read_text())
    except (OSError, ValueError):
        return []


def save_board(board):
    LEADERBOARD.write_text(json.dumps(board[:10], indent=1) + "\n")


class Round:
    """One 60-second round: targets, score, combo and stats."""

    def __init__(self):
        self.started = time.monotonic()
        self.score, self.streak, self.best_streak = 0, 0, 0
        self.hits, self.whacks, self.reactions = 0, 0, []
        self.target = None          # (index, kind, appeared, life)
        self.next_at = self.started + 1.0
        self.popups = []            # (text, x, y, color, time)
        self.last_index = None

    def left(self):
        return max(0.0, ROUND_TIME - (time.monotonic() - self.started))

    def multiplier(self):
        return min(COMBO_MAX, 1 + self.streak // COMBO_EVERY)

    def add(self, points, where, color):
        self.score = max(0, min(MAX_SCORE, self.score + points))
        self.popups.append((f"{points:+d}", where[0], where[1], color, time.monotonic()))

    def update(self):
        """New targets appear, old ones run out."""
        now = time.monotonic()
        if self.target:
            index, kind, appeared, life = self.target
            if now - appeared > life:
                self.target = None
                self.next_at = now + GAP
                if kind == "red":
                    self.add(50, TARGETS[index], GREEN)   # well done for leaving it
                else:
                    self.streak = 0
        elif now >= self.next_at and self.left() > 0.5:
            progress = 1 - self.left() / ROUND_TIME
            life = LIFE_START + (LIFE_END - LIFE_START) * progress
            roll = random.random()
            kind = "gold" if roll < GOLD_CHANCE else \
                "red" if roll < GOLD_CHANCE + RED_CHANCE and now - self.started > RED_AFTER \
                else "normal"
            if kind == "gold":
                life *= 0.7
            index = random.choice([i for i in range(len(TARGETS)) if i != self.last_index])
            self.last_index = index
            self.target = (index, kind, now, life)

    def whacked(self, spot):
        """The gripper reached the table at spot (x, y mm): score it."""
        now = time.monotonic()
        self.whacks += 1
        hit = None
        for i, target in enumerate(TARGETS):
            if math.dist(spot, target_xy(target)) <= HIT_RADIUS:
                hit = i
        where = TARGETS[hit] if hit is not None else None
        if self.target and hit == self.target[0]:
            index, kind, appeared, life = self.target
            self.target, self.next_at = None, now + GAP
            if kind == "red":
                self.streak = 0
                self.add(-300, where, RED)
                return "red"
            quick = max(0.0, 1 - (now - appeared) / life)
            points = int(POINTS * (1 + quick) * self.multiplier() * (2 if kind == "gold" else 1))
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            self.hits += 1
            self.reactions.append(now - appeared)
            self.add(points, where, GOLD if kind == "gold" else CYAN)
            return kind
        self.streak = 0
        self.add(-50, where or spot_to_target(spot), DIM)
        return "miss"


def spot_to_target(spot):
    """A (distance, angle) for a spot, so popups can be drawn there."""
    x, y = spot
    return (math.hypot(x - arm_link.arm.BASE_X, y),
            math.degrees(math.atan2(y, x - arm_link.arm.BASE_X)))


class Game:
    def __init__(self, args):
        self.args = args
        self.text = Text()
        self.background = background()
        for box in (CAMERA_BOX, MAP_BOX, FOOTER_BOX):     # the panels never change
            panel(self.background, box)
        self.tracker = make_tracker(args.tracker)
        self.camera = Camera(args.camera)
        self.tracking = Tracking(self.tracker, self.camera)
        self.robot = arm_link.VirtualArm(args.touch_height) if args.no_arm \
            else arm_link.RealArm(args.touch_height, args.ros_args)
        self.state, self.name, self.round = "title", "", None
        self.hand, self.hand_since, self.hand_seen = None, None, 0.0
        self.was_fist = False
        self.board = load_board()
        self.track_ms, self.fps, self.frames, self.fps_since = 0.0, 0.0, 0, time.monotonic()
        self.result_at = 0.0
        self.countdown_at = 0.0
        self.fullscreen = args.fullscreen

    # -- each frame ---------------------------------------------------------------
    def step(self):
        frame, self.hand = self.tracking.frame, self.tracking.hand
        self.track_ms = self.tracking.ms
        now = time.monotonic()
        if self.hand:
            self.hand_seen = now
            self.hand_since = self.hand_since or now
        elif now - self.hand_seen > 0.3:
            self.hand_since = None
        self.robot.update()

        if self.state == "ready" and self.hand_since and now - self.hand_since > SHOW_HAND_FOR:
            self.state, self.countdown_at = "countdown", now
        elif self.state == "countdown":
            # Practice: Robo already follows the hand (no whacking yet)
            if self.hand:
                self.robot.follow(self.hand.x, self.hand.y)
            if now - self.countdown_at > 3.0:
                self.state, self.round = "play", Round()
                self.was_fist = bool(self.hand and self.hand.whack)
        elif self.state == "play":
            self.play(now)
        elif self.state == "results" and now - self.result_at > 12.0:
            self.state = "title"

        self.frames += 1
        if now - self.fps_since >= 1.0:
            self.fps, self.frames, self.fps_since = self.frames / (now - self.fps_since), 0, now
        return self.draw(frame)

    def play(self, now):
        game = self.round
        # The arm follows the hand (and holds still if the hand is lost)
        if self.hand:
            self.robot.follow(self.hand.x, self.hand.y)
            fist = self.hand.whack
            if fist and not self.was_fist:
                self.robot.whack()
            self.was_fist = fist
        if self.robot.bottom_of_whack():
            x, y, _, _ = arm_link.arm.forward(self.robot.joints())
            game.whacked((x, y))
        game.update()
        if game.left() <= 0 and not self.robot.whacking():
            self.finish()

    def finish(self):
        game = self.round
        self.board.append({"name": self.name or "PLAYER", "score": game.score,
                           "rank": rank_for(game.score), "date": time.strftime("%Y-%m-%d")})
        self.board.sort(key=lambda entry: -entry["score"])
        save_board(self.board)
        self.state, self.result_at = "results", time.monotonic()

    def key(self, key):
        """Returns False to quit."""
        if key == 27:                                   # Esc
            return False
        if key in (ord("f"), ord("F")) and self.state != "title":
            self.fullscreen = not self.fullscreen
            cv2.setWindowProperty("Puppet Master", cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL)
        elif self.state == "title":
            if key in (13, 10):                          # Enter
                self.state = "ready"
            elif key in (8, 127):                        # Backspace
                self.name = self.name[:-1]
            elif 32 <= key < 127 and len(self.name) < 12:
                self.name += chr(key).upper()
        elif self.state == "results" and key in (13, 10, 32):
            self.state, self.name = "title", ""
        return True

    # -- drawing -------------------------------------------------------------------
    def draw(self, frame):
        canvas = self.background.copy()
        self.draw_header(canvas)
        self.draw_camera(canvas, frame)
        self.draw_map(canvas)
        self.draw_footer(canvas)
        if self.state in ("title", "ready", "countdown", "results"):
            # The game's text first, so the dark overlay covers it too
            canvas = self.text.draw(canvas)
            self.draw_overlay(canvas)
        return self.text.draw(canvas)

    def draw_header(self, canvas):
        t = self.text
        t.add("PUPPET", 30, 22, 38, GOLD)
        t.add("MASTER", 205, 22, 38, CYAN)
        t.add("control Robo with your hand", 32, 66, 15, DIM)
        game = self.round if self.state in ("play", "results") else None
        score = game.score if game else 0
        t.add(f"{score:,}", W // 2, 42, 54, INK, "mm")
        t.add(f"/ {MAX_SCORE:,}", W // 2, 82, 14, DIM, "mm")
        best = self.board[0]["score"] if self.board else 0
        t.add("HIGH SCORE", W - 30, 20, 14, DIM, "ra")
        t.add(f"{best:,}", W - 30, 38, 28, GOLD, "ra")
        if game:
            left = game.left()
            share = left / ROUND_TIME
            cv2.rectangle(canvas, (870, 76), (1250, 86), (70, 50, 60), -1)
            cv2.rectangle(canvas, (870, 76), (870 + int(380 * share), 86),
                          RED if left < 10 else CYAN, -1)
            t.add(f"{left:4.1f}s", 860, 81, 18, RED if left < 10 else INK, "rm")
            if game.multiplier() > 1 and self.state == "play":
                t.add(f"COMBO x{game.multiplier()}", W // 2 + 150, 42, 26, PINK, "lm")

    def draw_camera(self, canvas, frame):
        left, top, right, bottom = CAMERA_BOX
        if frame is None:
            self.text.add("Waiting for the camera ...", (left + right) // 2,
                          (top + bottom) // 2, 22, DIM, "mm")
            return
        width, height = right - left - 10, bottom - top - 10
        view = cv2.resize(frame, (width, height))
        view = (view * 0.75).astype(np.uint8)          # darker, so the drawing stands out
        sx, sy = width / frame.shape[1], height / frame.shape[0]
        # The play area: the hand moves inside this box
        a = self.tracker_area()
        cv2.rectangle(view, (int(a[0] * width), int(a[1] * height)),
                      (int(a[2] * width), int(a[3] * height)), (120, 90, 100), 1, cv2.LINE_AA)
        hand = self.hand
        if hand:
            points = [(int(x * sx), int(y * sy)) for x, y in hand.points]
            for i, j in hand.lines:
                if i < len(points) and j < len(points):
                    cv2.line(view, points[i], points[j], CYAN, 2, cv2.LINE_AA)
            for p in points:
                cv2.circle(view, p, 3, INK, -1, cv2.LINE_AA)
            cx = int((a[0] + hand.x * (a[2] - a[0])) * width)
            cy = int((a[1] + hand.y * (a[3] - a[1])) * height)
            glow_circle(view, (cx, cy), 14, PINK if hand.whack else GOLD, 3)
        canvas[top + 5:bottom - 5, left + 5:right - 5] = view
        self.text.add("FIST = WHACK" if not (hand and hand.whack) else "WHACK!",
                      left + 15, bottom - 32, 18, PINK if hand and hand.whack else DIM)

    def tracker_area(self):
        from tracker import PLAY_AREA
        return PLAY_AREA

    def to_map(self, u, v):
        left, top, right, bottom = MAP_BOX
        cx = (left + right) // 2
        # The map shows the table from the player's side: Robo at the top
        base_y = top + 70
        scale = min((right - left - 60) / (2 * arm_link.FAR * math.sin(arm_link.SIDE)),
                    (bottom - top - 130) / arm_link.FAR)
        reach = arm_link.NEAR + v * (arm_link.FAR - arm_link.NEAR)
        angle = (u - 0.5) * 2 * arm_link.SIDE
        return (int(cx + reach * math.sin(angle) * scale),
                int(base_y + reach * math.cos(angle) * scale)), scale

    def target_on_map(self, target):
        reach, angle = target
        u = 0.5 + math.radians(angle) / (2 * arm_link.SIDE)
        v = (reach - arm_link.NEAR) / (arm_link.FAR - arm_link.NEAR)
        return self.to_map(u, v)[0]

    def draw_map(self, canvas):
        left, top, right, bottom = MAP_BOX
        t = self.text
        t.add("THE TABLE", left + 15, top + 12, 16, DIM)
        # The area the gripper can reach
        points = [self.to_map(u / 20, 0)[0] for u in range(21)] + \
                 [self.to_map(u / 20, 1)[0] for u in range(20, -1, -1)]
        cv2.fillPoly(canvas, [np.array(points)], (60, 40, 45), cv2.LINE_AA)
        cv2.polylines(canvas, [np.array(points)], True, (110, 80, 90), 1, cv2.LINE_AA)
        # Robo
        base = ((left + right) // 2, top + 70)
        cv2.circle(canvas, base, 22, (90, 70, 80), -1, cv2.LINE_AA)
        t.add("ROBO", base[0], base[1], 13, INK, "mm")
        t.add("you are here", base[0], bottom - 18, 14, DIM, "mm")

        game = self.round if self.state == "play" else None
        lit = game.target if game else None
        _, scale = self.to_map(0.5, 0.5)
        radius = int(HIT_RADIUS * scale)
        for i, target in enumerate(TARGETS):
            spot = self.target_on_map(target)
            if lit and lit[0] == i:
                index, kind, appeared, life = lit
                color = GOLD if kind == "gold" else RED if kind == "red" else CYAN
                pulse = 1 + 0.12 * math.sin(time.monotonic() * 12)
                glow_circle(canvas, spot, radius * pulse, color)
                share = max(0.0, 1 - (time.monotonic() - appeared) / life)
                cv2.ellipse(canvas, spot, (radius + 9, radius + 9), -90, 0, 360 * share,
                            INK, 3, cv2.LINE_AA)
                t.add("DON'T!" if kind == "red" else str(i + 1), spot[0], spot[1], 20,
                      (20, 20, 20), "mm")
            else:
                cv2.circle(canvas, spot, radius, (110, 85, 95), 2, cv2.LINE_AA)
                t.add(str(i + 1), spot[0], spot[1], 16, DIM, "mm")

        # Where the gripper really is (and whether it's down)
        if self.robot.command is not None:
            u, v, z = self.robot.gripper_area()
            spot, _ = self.to_map(u, v)
            down = z < arm_link.HOVER_HEIGHT - 15
            cv2.circle(canvas, spot, 9 if down else 13, PINK if down else INK, 3, cv2.LINE_AA)
            cv2.circle(canvas, spot, 3, PINK if down else INK, -1, cv2.LINE_AA)

        # Points flying up from where they were scored
        if self.round and self.state == "play":
            now = time.monotonic()
            self.round.popups = [p for p in self.round.popups if now - p[4] < 1.0]
            for words, reach, angle, color, when in self.round.popups:
                x, y = self.target_on_map((reach, angle))
                rise = int(50 * (now - when))
                t.add(words, x, y - 30 - rise, 26, color, "mm")

    def draw_footer(self, canvas):
        left, top, right, bottom = CAMERA_BOX
        t = self.text
        game = self.round if self.state in ("play", "results") else None
        stats = [("HITS", game.hits if game else 0),
                 ("BEST COMBO", game.best_streak if game else 0),
                 ("ACCURACY", f"{100 * game.hits / game.whacks:.0f}%" if game and game.whacks
                  else "-"),
                 ("REACTION", f"{sum(game.reactions) / len(game.reactions):.2f}s"
                  if game and game.reactions else "-")]
        for i, (label, value) in enumerate(stats):
            x = left + 20 + i * 155
            t.add(label, x, bottom + 30, 13, DIM)
            t.add(value, x, bottom + 50, 26, INK)
        t.add(f"{self.tracker.name} {self.track_ms:.0f} ms  ·  {self.fps:.0f} fps  ·  "
              f"{self.robot.name}", left + 20, 672, 12, DIM)

    def draw_overlay(self, canvas):
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (W, H), (15, 8, 10), -1)
        dark = 0.5 if self.state == "countdown" else 0.88   # see your hand while counting
        cv2.addWeighted(overlay, dark, canvas, 1 - dark, 0, canvas)
        t = self.text
        mid = W // 2
        if self.state == "title":
            t.add("PUPPET MASTER", mid, 130, 72, GOLD, "mm")
            t.add("Your hand controls Robo's arm. Make a fist to whack the lit target.",
                  mid, 195, 20, INK, "mm")
            t.add("Gold = double points  ·  Red = don't touch  ·  hits in a row = combo",
                  mid, 225, 17, DIM, "mm")
            t.add("TYPE YOUR NAME", mid, 300, 16, DIM, "mm")
            cursor = "_" if int(time.monotonic() * 2) % 2 else " "
            t.add((self.name or "") + cursor, mid, 345, 46, CYAN, "mm")
            t.add("press ENTER to play", mid, 400, 18, INK, "mm")
            t.add("TOP 10", mid, 460, 18, GOLD, "mm")
            for i, entry in enumerate(self.board[:10]):
                column, row = i // 5, i % 5
                x = mid - 300 + column * 320
                y = 495 + row * 32
                t.add(f"{i + 1:>2}. {entry['name'][:12]}", x, y, 20, INK)
                t.add(f"{entry['score']:,}  {entry['rank']}", x + 270, y, 20, GOLD, "ra")
            if not self.board:
                t.add("Be the first on the board!", mid, 500, 20, DIM, "mm")
        elif self.state == "ready":
            t.add(f"Get ready, {self.name or 'player'}!", mid, 260, 44, INK, "mm")
            t.add("Hold your hand up in front of the camera", mid, 320, 24, CYAN, "mm")
            seen = (time.monotonic() - self.hand_since) / SHOW_HAND_FOR if self.hand_since else 0
            cv2.rectangle(canvas, (mid - 200, 360), (mid + 200, 372), (70, 50, 60), -1)
            cv2.rectangle(canvas, (mid - 200, 360), (mid - 200 + int(400 * min(1, seen)), 372),
                          GOLD, -1)
        elif self.state == "countdown":
            number = 3 - int(time.monotonic() - self.countdown_at)
            t.add(str(max(1, number)), mid, H // 2, 160, GOLD, "mm")
            t.add("Move your hand: Robo follows. Fist = whack!", mid, H // 2 + 120, 22,
                  INK, "mm")
        elif self.state == "results":
            game = self.round
            rank = rank_for(game.score)
            place = next((i for i, e in enumerate(self.board)
                          if e["score"] == game.score and e["name"] == (self.name or "PLAYER")), 99)
            t.add("TIME!", mid, 110, 40, DIM, "mm")
            t.add(f"{game.score:,}", mid, 200, 96, GOLD, "mm")
            t.add(f"RANK {rank}", mid, 285, 44,
                  {"S": PINK, "A": GOLD, "B": CYAN}.get(rank, INK), "mm")
            if place == 0:
                t.add("NEW HIGH SCORE!", mid, 345, 30, PINK, "mm")
            elif place < 10:
                t.add(f"#{place + 1} on the leaderboard", mid, 345, 26, CYAN, "mm")
            reaction = (f"{sum(game.reactions) / len(game.reactions):.2f}s"
                        if game.reactions else "-")
            t.add(f"Hits {game.hits}   ·   Best combo {game.best_streak}   ·   "
                  f"Average reaction {reaction}", mid, 410, 20, INK, "mm")
            t.add("press ENTER", mid, 470, 18, DIM, "mm")


def setup_targets(args):
    """Move the gripper over each target spot so a sticker can be put under it."""
    robot = arm_link.RealArm(args.touch_height, args.ros_args)
    why = robot.start()
    if why:
        print(f"Can't start: {why}")
        robot.stop()
        return
    try:
        for i, target in enumerate(TARGETS):
            x, y = target_xy(target)
            why = arm_link.arm.move_to(robot.node, x, y, arm_link.HOVER_HEIGHT)
            why = why or arm_link.arm.move_to(robot.node, x, y, args.touch_height + 10,
                                              straight=True)
            if why:
                print(f"Can't reach target {i + 1}: {why}")
                continue
            input(f"Put sticker {i + 1} on the table right under the gripper, "
                  "then press Enter ...")
            arm_link.arm.move_to(robot.node, x, y, arm_link.HOVER_HEIGHT, straight=True)
        print("All targets placed. Have fun!")
    finally:
        robot.stop()


def main():
    parser = argparse.ArgumentParser(description="Puppet Master: whack targets with Robo.")
    parser.add_argument("--no-arm", action="store_true",
                        help="no robot: play with a pretend arm (for trying it anywhere)")
    parser.add_argument("--setup", action="store_true",
                        help="move the gripper over each target to place the stickers")
    parser.add_argument("--tracker", default="auto", choices=["auto", "mediapipe", "yolo"],
                        help="hand tracker (default: MediaPipe if installed)")
    parser.add_argument("--camera", default="/dev/video0",
                        help="the camera watching the player (default /dev/video0)")
    parser.add_argument("--touch-height", type=float, default=arm_link.TOUCH_HEIGHT,
                        help="fingertip height at the bottom of a whack, mm (default 20)")
    parser.add_argument("--fullscreen", action="store_true", help="start in full screen")
    args, args.ros_args = parser.parse_known_args()

    if args.setup:
        setup_targets(args)
        return

    try:
        game = Game(args)
    except RuntimeError as error:      # no camera
        print(error)
        return
    why = game.robot.start()
    if why:
        print(f"Can't start the arm: {why}")
        game.camera.close()
        game.robot.stop()
        return
    cv2.namedWindow("Puppet Master", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Puppet Master", W, H)
    if args.fullscreen:
        cv2.setWindowProperty("Puppet Master", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow("Puppet Master", game.step())
            key = cv2.waitKey(1)
            if key != -1 and not game.key(key & 0xFF):
                break
            if cv2.getWindowProperty("Puppet Master", cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        game.tracking.close()
        game.camera.close()
        game.robot.stop()


if __name__ == "__main__":
    main()
