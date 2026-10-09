"""
Robo's control panel, in two tabs:

  Robo                  gestures and the gripper, the camera view with YOLO's boxes and
                        the camera greeting, and talking with Robo (once, or live)
  Build your own move   a step-by-step builder: pose the arm, add poses, test the move,
                        save it with a name, and play, edit or delete saved moves.
                        Camera greetings pause while this tab is open, so the arm stays
                        where you put it.

Run it while the arm (or the simulation) is launched (see README.md):
    python3 gui.py
Or start everything together (arm, camera, detection and this window):
    ../launch/robo.sh            (add --sim for the simulated arm)

Talking needs Ollama, Whisper, Piper, the mic and the speaker (README, setup steps
10-12). Greeting needs the camera and perception/detect.py running.

Options:
    --model NAME     Ollama model for Robo (default llama3.2:3b)
    --whisper SIZE   Whisper model (default small)
"""

import argparse
import math
import queue
import signal
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import rclpy
from control_msgs.action import FollowJointTrajectory, GripperCommand
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool

try:  # for showing the camera video (installed with YOLO)
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

from gestures import (
    BUILT_IN, GESTURES, GRIPPER, GRIPPER_TIME, JOINTS, Gesturer, catch_up, connect,
    delete_saved, jog, load_saved, move_gripper, name_problem, plan_gesture, record_pose,
    save_recording, saved_key,
)
from greet import GreetDecider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
from robo_voice import GREETING, RoboVoice, choose_gesture, is_goodbye  # noqa: E402

JOINT_NAMES = ["Base", "Shoulder", "Elbow", "Wrist"]
VIDEO_SIZE = (480, 360)  # the camera view, in pixels
NO_VIDEO_AFTER = 2.0     # seconds without video before saying "Camera not connected"
CAMERA_START_TIME = 20.0 # at startup, wait this long for detection to load first
ONCE_TIMEOUT = 10        # seconds "Talk once" waits for you to start speaking

# ---------- Look: Texas State maroon and gold ----------
MAROON, MAROON_DARK = "#501214", "#3a0d0f"
GOLD, GOLD_LIGHT = "#8D734A", "#E9DCC0"
PAGE, CARD, LINE = "#F4F1EC", "#FFFFFF", "#E3DDD3"
TEXT, MUTED = "#1F2328", "#6E6A64"
GREEN, RED, BLUE = "#1a7f37", "#cf222e", "#0969da"
FAMILY = "DejaVu Sans"   # installed on Ubuntu; other systems fall back to their default
FONT = (FAMILY, 12)
BOLD = (FAMILY, 12, "bold")
SMALL = (FAMILY, 10)
TITLE = (FAMILY, 14, "bold")
BUTTONS = {  # kind: (background, text, background when the mouse is over it)
    "primary": (MAROON, "white", MAROON_DARK),
    "gold": (GOLD, "white", "#76603c"),
    "light": (GOLD_LIGHT, TEXT, "#dccaa2"),
    "danger": ("#f6dcdc", RED, "#efc4c4"),
}


def button(parent, text, command, kind="light", width=None, repeat=False):
    """A flat, coloured button that darkens when the mouse is over it."""
    bg, fg, hover = BUTTONS[kind]
    b = tk.Button(parent, text=text, command=command, font=BOLD, bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=7, cursor="hand2")
    if width:
        b.config(width=width)
    if repeat:  # hold to keep repeating
        b.config(repeatdelay=300, repeatinterval=100)
    b.bind("<Enter>", lambda e: b.config(bg=hover) if str(b["state"]) != "disabled" else None)
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def card(parent, title, help_text=None):
    """A white box with a title and an optional line of help; returns its inside."""
    outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
    outer.pack(fill="x", padx=8, pady=8)
    tk.Label(outer, text=title, font=TITLE, bg=CARD, fg=MAROON).pack(
        anchor="w", padx=14, pady=(12, 0))
    if help_text:
        tk.Label(outer, text=help_text, font=SMALL, bg=CARD, fg=MUTED, justify="left",
                 wraplength=440).pack(anchor="w", padx=14, pady=(2, 0))
    inside = tk.Frame(outer, bg=CARD)
    inside.pack(fill="both", expand=True, padx=14, pady=(8, 14))
    return inside


def text(parent, words, muted=False, bold=False, **options):
    return tk.Label(parent, text=words, bg=CARD, fg=MUTED if muted else TEXT,
                    font=SMALL if muted else (BOLD if bold else FONT), **options)


def describe_pose(number, pose):
    """One line for the list of poses, e.g. 1.  base +19°  shoulder +14° ... · 1.0 s"""
    turn, j2, j3, j4, seconds, *grip = pose
    angles = "  ".join(f"{name.lower()} {math.degrees(v):+.0f}°"
                       for name, v in zip(JOINT_NAMES, (turn, j2, j3, j4)))
    gripper = f" · gripper {grip[0]}" if grip else ""
    return f"{number:>2}.  {angles}{gripper} · {seconds:.1f} s"


class App:
    def __init__(self, root, node, robo):
        self.root, self.node, self.robo = root, node, robo
        root.title("Robo · Ingram Hall Makerspace")
        root.configure(bg=PAGE)
        root.resizable(False, False)

        self.jobs = queue.Queue()      # work for the window's thread (from voice threads)
        self.moving = False            # a gesture is playing
        self.steps = []                # the rest of the gesture being played
        self.step = None               # the step being carried out right now
        self.when_done = []            # what to call when the gesture finishes
        self.voice_busy = False        # a conversation (once or live) is running
        self.loading = False           # voice models are loading
        self.stop_voice = threading.Event()
        self.live = False

        # Camera greeting: /person_detected comes from perception/detect.py
        self.last_person = None        # when a person was last seen
        self.camera_seen = False       # any message from detect.py at all
        self.decider = GreetDecider()
        self.greet_on = tk.BooleanVar(value=True)
        node.create_subscription(Bool, "/person_detected", self.on_person, 10)
        # Tell detect.py when Robo is busy talking, so it frees more of the GPU
        self.busy_pub = node.create_publisher(Bool, "/robo_busy", 10)
        self.busy_sent = (None, 0.0)  # what we last published, and when

        self.build_header()
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=PAGE, borderwidth=0, tabmargins=(12, 8, 12, 0))
        style.configure("TNotebook.Tab", font=BOLD, padding=(22, 10), background=GOLD_LIGHT,
                        foreground=TEXT, borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", CARD)],
                  foreground=[("selected", MAROON)])
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.main_tab = tk.Frame(self.tabs, bg=PAGE)
        self.build_tab = tk.Frame(self.tabs, bg=PAGE)
        self.tabs.add(self.main_tab, text="  Robo  ")
        self.tabs.add(self.build_tab, text="  Build your own move  ")
        self.build_main_tab(self.main_tab)
        self.build_builder_tab(self.build_tab)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        # Get the voice ready right away: speaking first (a few seconds, so greetings can
        # talk), then listening and the LLM, so Talk once / Live start immediately
        self.after_load = None  # what to do once it's ready (a click while loading)
        self.with_voice_loaded(lambda: None)

        # Keep ROS messages (joint angles, video) coming in while the window is open
        self.spin()

    # ================= Layout =================

    def build_header(self):
        bar = tk.Frame(self.root, bg=MAROON)
        bar.pack(fill="x")
        names = tk.Frame(bar, bg=MAROON)
        names.pack(side="left", padx=18, pady=10)
        tk.Label(names, text="Robo", font=(FAMILY, 22, "bold"), bg=MAROON,
                 fg="white").pack(anchor="w")
        tk.Label(names, text="OpenMANIPULATOR-X  ·  Ingram Hall Makerspace, Texas State University",
                 font=SMALL, bg=MAROON, fg=GOLD_LIGHT).pack(anchor="w")
        right = tk.Frame(bar, bg=MAROON)
        right.pack(side="right", padx=18)
        button(right, "Quit", self.quit, kind="light").pack(side="right", padx=(12, 0))
        self.status = tk.Label(right, text="Ready", font=BOLD, bg=CARD, fg=GREEN,
                               padx=14, pady=6)
        self.status.pack(side="right")

    def build_main_tab(self, tab):
        left, middle, right = (tk.Frame(tab, bg=PAGE) for _ in range(3))
        left.grid(row=0, column=0, sticky="n", pady=6)
        middle.grid(row=0, column=1, sticky="n", pady=6)
        right.grid(row=0, column=2, sticky="n", pady=6)

        inside = card(left, "Gestures", "Click to play. Moves you build appear here too.")
        self.gesture_buttons = tk.Frame(inside, bg=CARD)
        self.gesture_buttons.pack(fill="x")
        self.show_gestures()

        inside = card(left, "Gripper")
        row = tk.Frame(inside, bg=CARD)
        row.pack(anchor="w")
        for name, position in GRIPPER.values():
            button(row, name.capitalize(), lambda p=position, n=name: self.gripper(n, p),
                   width=8).pack(side="left", padx=(0, 8))

        self.build_camera(middle)
        self.build_voice(right)

    def build_builder_tab(self, tab):
        tk.Label(tab, text="Build your own move: pose the arm, add each pose, test it, then "
                           "save it with a name. Camera greetings are paused while this tab "
                           "is open, so the arm stays exactly where you put it.",
                 font=FONT, bg=PAGE, fg=TEXT, wraplength=1300, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 0))
        left, middle, right = (tk.Frame(tab, bg=PAGE) for _ in range(3))
        left.grid(row=1, column=0, sticky="n", pady=6)
        middle.grid(row=1, column=1, sticky="n", pady=6)
        right.grid(row=1, column=2, sticky="n", pady=6)

        # Step 1: move the arm
        inside = card(left, "Step 1 · Move the arm",
                      "Hold - or + to keep a joint moving. Angles update live.")
        self.angles = []  # live angle of each joint, in degrees
        for i, name in enumerate(JOINT_NAMES):
            text(inside, name, bold=True, width=9, anchor="w").grid(row=i, column=0, pady=3)
            for col, (sign, direction) in enumerate([("-", -1), ("+", 1)], start=1):
                button(inside, sign, lambda j=i, d=direction: self.nudge(j, d),
                       width=3, repeat=True).grid(row=i, column=col, padx=3, pady=3)
            angle = text(inside, "", width=6, anchor="e")
            angle.grid(row=i, column=3, padx=(10, 0))
            self.angles.append(angle)
        button(inside, "Go home", lambda: self.play("home", GESTURES["h"][1])).grid(
            row=len(JOINT_NAMES), column=0, columnspan=4, sticky="w", pady=(10, 0))

        # Step 2: gripper
        inside = card(left, "Step 2 · Gripper",
                      "Each pose remembers whether the gripper is open or closed.")
        row = tk.Frame(inside, bg=CARD)
        row.pack(anchor="w")
        for name, position in GRIPPER.values():
            button(row, name.capitalize(), lambda p=position, n=name: self.gripper(n, p),
                   width=8).pack(side="left", padx=(0, 8))

        # Step 3: add poses
        inside = card(middle, "Step 3 · Add poses",
                      "Add a pose every time the arm is where you want it. The move goes "
                      "through them in order, starting and ending at home.")
        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x")
        text(row, "Seconds to reach this pose").pack(side="left")
        self.seconds = tk.Spinbox(row, from_=0.3, to=5.0, increment=0.1, width=5, font=FONT,
                                  format="%.1f", relief="solid", bd=1)
        self.seconds.delete(0, "end")
        self.seconds.insert(0, "1.0")
        self.seconds.pack(side="left", padx=8)
        button(row, "Add pose", self.add_pose, kind="primary").pack(side="right")
        self.pose_list = tk.Listbox(inside, font=(FAMILY, 10), width=62, height=12,
                                    relief="solid", bd=1, highlightthickness=0,
                                    selectbackground=GOLD_LIGHT, selectforeground=TEXT,
                                    activestyle="none")
        self.pose_list.pack(fill="x", pady=(10, 6))
        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x")
        button(row, "Delete selected pose", self.delete_pose, kind="danger").pack(side="left")
        button(row, "Clear all", self.start_over, kind="danger").pack(side="left", padx=8)

        # Step 4: test and save
        inside = card(middle, "Step 4 · Test and save",
                      "Test plays your poses without saving. Then give the move a name: "
                      "you'll play it from Gestures, or by saying its name to Robo.")
        button(inside, "Test the move", self.test_move, kind="gold").pack(anchor="w")
        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        text(row, "Name").pack(side="left")
        self.name_entry = tk.Entry(row, font=FONT, width=26, relief="solid", bd=1)
        self.name_entry.pack(side="left", padx=8, ipady=4)
        button(row, "Save move", self.save, kind="primary").pack(side="left")

        # Saved moves
        inside = card(right, "Your saved moves",
                      "Select a move, then play it, load it into the builder to change it "
                      "(save with the same name to replace it), or delete it.")
        self.saved_list = tk.Listbox(inside, font=FONT, width=30, height=14, relief="solid",
                                     bd=1, highlightthickness=0, selectbackground=GOLD_LIGHT,
                                     selectforeground=TEXT, activestyle="none")
        self.saved_list.pack(fill="x", pady=(0, 8))
        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x")
        button(row, "Play", self.play_saved, kind="gold").pack(side="left")
        button(row, "Edit", self.edit_saved).pack(side="left", padx=8)
        button(row, "Delete", self.delete_saved_move, kind="danger").pack(side="left")
        self.show_poses()
        self.show_saved()

    def building(self):
        """True while the Build your own move tab is open."""
        return self.tabs.select() == str(self.build_tab)

    # ================= Main loop =================

    def spin(self):
        # Handle every waiting ROS message, and any work sent from the voice thread
        catch_up(self.node)
        self.advance_gesture()
        while not self.jobs.empty():
            self.jobs.get_nowait()()
        for label, joint in zip(self.angles, JOINTS):
            if joint in self.node.joints:
                label.config(text=f"{math.degrees(self.node.joints[joint]):+.0f}°")
        self.check_greeting()
        self.show_video()
        self.publish_busy()
        self.next_spin = self.root.after(50, self.spin)

    def publish_busy(self):
        """Busy = a conversation is running or Robo is talking. Sent when it changes, and
        repeated every second while busy (detect.py goes back to normal if repeats stop)."""
        busy = self.voice_busy or self.robo.talking()
        now = time.monotonic()
        last, sent_at = self.busy_sent
        if busy != last or (busy and now - sent_at >= 1.0):
            self.busy_pub.publish(Bool(data=busy))
            self.busy_sent = (busy, now)

    def say(self, words, error=False):
        self.status.config(text=words, fg=RED if error else GREEN)
        self.root.update_idletasks()

    def post(self, job):
        """Run job on the window's thread (Tkinter and the arm must only be used there)."""
        self.jobs.put(job)

    # ================= Arm =================

    def show_gestures(self):
        """The gesture buttons on the Robo tab: built-in ones, then saved moves."""
        for widget in self.gesture_buttons.winfo_children():
            widget.destroy()
        keys = [k for k in GESTURES if k in BUILT_IN] + \
               [k for k in GESTURES if k not in BUILT_IN]
        for i, key in enumerate(keys):
            name, moves = GESTURES[key]
            kind = "light" if key in BUILT_IN else "gold"
            label = name.capitalize() if key in BUILT_IN else name  # saved: as typed
            button(self.gesture_buttons, label,
                   lambda m=moves, n=name: self.play(n, m), kind=kind, width=13).grid(
                row=i // 2, column=i % 2, padx=4, pady=4, sticky="w")

    def play(self, name, moves, when_done=None):
        """Start a gesture. It plays step by step while the window keeps running (camera,
        buttons), so the window never freezes. Gestures can't overlap: while one plays,
        another is refused. when_done() is called once it has finished (or was refused)."""
        if self.moving:
            self.say("Wait for the current move to finish", error=True)
            if when_done:
                when_done()
            return
        self.moving = True
        self.say(f"{name.capitalize()} ...")
        self.steps = plan_gesture(self.node, moves)
        self.when_done = [when_done] if when_done else []
        self.next_step()

    def next_step(self):
        """Send the next step of the gesture to the arm (or the gripper)."""
        if not self.steps:
            self.finish_gesture()
            return
        kind, value = self.steps.pop(0)
        if kind == "arm":
            goal = FollowJointTrajectory.Goal()
            goal.trajectory.joint_names = JOINTS
            goal.trajectory.points = value
            self.step = {"kind": "arm", "sent": self.node.client.send_goal_async(goal),
                         "result": None}
        else:  # gripper: send it, then give it a moment (it stops early when holding something)
            if self.node.gripper.server_is_ready():
                goal = GripperCommand.Goal()
                goal.command.position = value
                goal.command.max_effort = 100.0
                self.node.gripper.send_goal_async(goal)
            self.step = {"kind": "wait", "until": time.monotonic() + GRIPPER_TIME}

    def advance_gesture(self):
        """Called every 50 ms: move on to the next step once the current one is done."""
        step = self.step
        if not self.moving or step is None:
            return
        if step["kind"] == "wait":
            if time.monotonic() >= step["until"]:
                self.next_step()
        elif step["result"] is None:
            if step["sent"].done():
                handle = step["sent"].result()
                if handle is None or not handle.accepted:
                    self.finish_gesture("The arm controller rejected the move")
                else:
                    step["result"] = handle.get_result_async()
        elif step["result"].done():
            self.next_step()

    def finish_gesture(self, error=None):
        self.moving, self.step, self.steps = False, None, []
        self.say(error or "Ready", error=bool(error))
        callbacks, self.when_done = self.when_done, []
        for callback in callbacks:
            callback()

    def nudge(self, joint, direction):
        """A joint button: move one joint a little (not while a gesture is playing)."""
        if self.moving:
            self.say("Wait for the current move to finish", error=True)
            return
        jog(self.node, joint, direction)

    def gripper(self, name, position):
        self.say(f"Gripper {name}")
        move_gripper(self.node, position)

    # ================= Build your own move =================

    def show_poses(self):
        self.pose_list.delete(0, "end")
        for i, pose in enumerate(self.node.recording, start=1):
            self.pose_list.insert("end", describe_pose(i, pose))
        if not self.node.recording:
            self.pose_list.insert("end", "  No poses yet. Move the arm, then click Add pose.")

    def add_pose(self):
        try:
            seconds = min(5.0, max(0.3, float(self.seconds.get())))
        except ValueError:
            seconds = 1.0
        record_pose(self.node, seconds)
        self.show_poses()
        self.pose_list.see("end")
        self.say(f"Pose {len(self.node.recording)} added")

    def delete_pose(self):
        chosen = self.pose_list.curselection()
        if not chosen or not self.node.recording:
            self.say("Select a pose in the list first", error=True)
            return
        del self.node.recording[chosen[0]]
        self.show_poses()
        self.say(f"Pose {chosen[0] + 1} deleted")

    def start_over(self):
        if self.node.recording and not messagebox.askyesno(
                "Clear all poses", "Remove all the poses you've added?"):
            return
        self.node.recording = []
        self.show_poses()
        self.say("Poses cleared")

    def test_move(self):
        if not self.node.recording:
            self.say("Add some poses first", error=True)
            return
        self.play("your move", [tuple(p) for p in self.node.recording])

    def save(self):
        if not self.node.recording:
            self.say("Add some poses first", error=True)
            return
        name = self.name_entry.get().strip()
        problem = name_problem(name)
        if problem:
            self.say(problem, error=True)
            return
        if saved_key(name) and not messagebox.askyesno(
                "Replace move", f"A move called '{name}' already exists. Replace it?"):
            return
        save_recording(self.node, name)
        self.name_entry.delete(0, "end")
        self.show_poses()
        self.show_gestures()
        self.show_saved()
        self.say(f"Saved '{name}'")

    def show_saved(self):
        self.saved_list.delete(0, "end")
        self.saved_keys = [k for k in GESTURES if k not in BUILT_IN]
        for key in self.saved_keys:
            name, moves = GESTURES[key]
            seconds = sum(m[4] for m in moves)
            poses = f"{len(moves)} pose" + ("s" if len(moves) != 1 else "")
            self.saved_list.insert("end", f"  {name}   ({poses}, {seconds:.0f} s)")
        if not self.saved_keys:
            self.saved_list.insert("end", "  No saved moves yet.")

    def chosen_saved(self):
        chosen = self.saved_list.curselection()
        if not chosen or not self.saved_keys:
            self.say("Select a saved move first", error=True)
            return None
        return self.saved_keys[chosen[0]]

    def play_saved(self):
        key = self.chosen_saved()
        if key:
            self.play(*GESTURES[key])

    def edit_saved(self):
        key = self.chosen_saved()
        if not key:
            return
        if self.node.recording and not messagebox.askyesno(
                "Edit move", "This replaces the poses you're building now. Continue?"):
            return
        name, moves = GESTURES[key]
        self.node.recording = [list(m) for m in moves]
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, name)
        self.show_poses()
        self.say(f"Editing '{name}': save with the same name to replace it")

    def delete_saved_move(self):
        key = self.chosen_saved()
        if not key:
            return
        name = GESTURES[key][0]
        if not messagebox.askyesno("Delete move", f"Delete '{name}'? This can't be undone."):
            return
        delete_saved(key)
        self.show_saved()
        self.show_gestures()
        self.say(f"Deleted '{name}'")

    # ================= Talk with Robo =================

    def build_voice(self, parent):
        inside = card(parent, "Talk with Robo",
                      "Talk once: ask one question, Robo answers, then stops listening. "
                      "Live: keeps listening and answering until you turn it off.")
        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x")
        self.once_button = button(row, "Talk once", self.talk_once, kind="primary", width=10)
        self.once_button.pack(side="left")
        self.live_button = button(row, "Live: OFF", self.toggle_live, kind="gold", width=10)
        self.live_button.pack(side="left", padx=8)
        button(row, "Stop talking", self.robo.stop_talking).pack(side="left")

        row = tk.Frame(inside, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        text(row, "Speaker volume").pack(side="left")
        button(row, "-", lambda: self.change_volume(-5), width=2).pack(side="left", padx=(10, 4))
        self.volume_label = text(row, "?", width=5)
        self.volume_label.pack(side="left")
        button(row, "+", lambda: self.change_volume(+5), width=2).pack(side="left", padx=4)
        self.show_volume(self.robo.volume())

        self.voice_status = text(inside, "Getting the voice ready ...", muted=True,
                                 wraplength=440, justify="left")
        self.voice_status.pack(anchor="w", pady=(10, 6))

        frame = tk.Frame(inside, bg=CARD)
        frame.pack(fill="both")
        self.transcript = tk.Text(frame, font=SMALL, width=52, height=17, wrap="word",
                                  state="disabled", relief="solid", bd=1, bg="#FBFAF7",
                                  padx=8, pady=6, highlightthickness=0)
        scroll = tk.Scrollbar(frame, command=self.transcript.yview)
        self.transcript.config(yscrollcommand=scroll.set)
        self.transcript.pack(side="left", fill="both")
        scroll.pack(side="right", fill="y")
        self.transcript.tag_config("you", foreground=BLUE, font=(FAMILY, 10, "bold"))
        self.transcript.tag_config("robo", foreground=MAROON, font=(FAMILY, 10, "bold"))
        self.transcript.tag_config("note", foreground=MUTED)

    def show_volume(self, percent):
        self.volume_label.config(text="?" if percent is None else f"{percent}%")

    def change_volume(self, step):
        percent = self.robo.volume(step)
        self.show_volume(percent)
        if percent is None:
            self.say("Couldn't change the speaker volume (is the USB speaker plugged in?)",
                     error=True)

    def voice_says(self, words, error=False):
        self.voice_status.config(text=words, fg=RED if error else MUTED)

    def add_line(self, who, words):
        self.transcript.config(state="normal")
        self.transcript.insert("end", f"{who}: ", "you" if who == "You" else "robo")
        self.transcript.insert("end", words + ("\n" if who == "Robo" else "\n\n"))
        self.transcript.see("end")
        self.transcript.config(state="disabled")

    def add_note(self, words):
        """A small grey line in the transcript, like the timing of the last answer."""
        if not words:
            return
        self.transcript.config(state="normal")
        self.transcript.insert("end", f"({words})\n\n", "note")
        self.transcript.see("end")
        self.transcript.config(state="disabled")

    def talk_once(self):
        if not self.voice_busy:
            self.with_voice_loaded(lambda: self.start_voice(live=False))

    def toggle_live(self):
        if self.live:
            self.stop_voice.set()  # the live loop notices and stops
            self.robo.stop_talking()
            self.live_button.config(text="Live: OFF")
            self.voice_says("Stopping ...")
        elif not self.voice_busy:
            self.with_voice_loaded(lambda: self.start_voice(live=True))

    def with_voice_loaded(self, then):
        """Run then() once the voice is ready, loading it in the background if needed."""
        if self.robo.loaded:
            then()
            return
        self.after_load = then  # a click while loading runs as soon as it's ready
        if self.loading:
            self.voice_says("Still getting ready ... it will start listening in a moment.")
            return
        self.loading = True

        def load():
            try:
                self.robo.load_speech()  # quick: greetings can talk from now on
                self.robo.load(log=lambda m: self.post(lambda: self.voice_says(m)))
                self.post(self.voice_ready)
            except Exception as error:
                self.post(lambda e=error: self.voice_says(f"Couldn't start the voice: {e}", True))
            finally:
                self.loading = False

        threading.Thread(target=load, daemon=True).start()

    def voice_ready(self):
        self.voice_says("Voice ready. Click Talk once, or turn Live on.")
        then, self.after_load = self.after_load, None
        if then:
            then()

    def start_voice(self, live):
        self.voice_busy, self.live = True, live
        self.stop_voice.clear()
        self.once_button.config(state="disabled")
        if live:
            self.live_button.config(text="Live: ON")
        else:
            self.live_button.config(state="disabled")
        threading.Thread(target=self.conversation, args=(live,), daemon=True).start()

    def conversation(self, live):
        """Runs in the background: listen, answer, talk and gesture (once, or until stopped)."""
        try:
            while not self.stop_voice.is_set():
                self.post(lambda: self.voice_says(
                    "Listening ... speak now." if live
                    else f"Listening ... speak now (within {ONCE_TIMEOUT} s)."))
                heard = self.robo.listen(timeout=None if live else ONCE_TIMEOUT,
                                         stop=self.stop_voice)
                if self.stop_voice.is_set():
                    break
                if not heard:
                    if live:
                        continue
                    self.post(lambda: self.voice_says("I didn't hear anything. "
                                                      "Click Talk once to try again."))
                    return
                self.post(lambda h=heard: self.add_line("You", h))
                self.post(lambda: self.voice_says("Thinking ..."))

                # Answer from memory if asked before; otherwise speak each sentence as
                # soon as the LLM writes it. The gesture starts with the first sentence
                # (the arm only moves on the window's thread).
                moved = None

                def first_sentence(sentence):
                    nonlocal moved
                    self.post(lambda: self.voice_says("Talking ..."))
                    key = choose_gesture(heard, sentence, GESTURES)
                    if key:
                        moved = self.move_in_window(*GESTURES[key])

                try:
                    said, from_memory, written = self.robo.respond(
                        heard, on_first_sentence=first_sentence, stop=self.stop_voice)
                except Exception as error:  # Ollama not running, timeout, ...
                    self.post(lambda e=error: self.voice_says(
                        f"Couldn't get an answer from the LLM: {e}", True))
                    if not live:
                        return
                    continue
                self.post(lambda r=" ".join(said): self.add_line("Robo", r))
                self.robo.wait_until_quiet()
                if moved:
                    moved.wait()
                self.post(lambda t=self.robo.timing(written, from_memory): self.add_note(t))
                if not live or is_goodbye(heard):
                    break
        finally:
            self.post(self.voice_finished)

    def move_in_window(self, name, moves):
        """Ask the window's thread to play a gesture; returns an Event set when it's done."""
        done = threading.Event()

        def move():
            try:
                self.play(name, moves, when_done=done.set)
            except Exception:
                done.set()  # never leave the voice thread waiting
                raise

        self.post(move)
        return done

    def voice_finished(self):
        self.voice_busy = self.live = False
        self.once_button.config(state="normal")
        self.live_button.config(state="normal", text="Live: OFF")
        # Keep messages like "I didn't hear anything" or errors; replace progress messages
        if self.voice_status.cget("text").startswith(("Listening", "Thinking", "Talking",
                                                       "Stopping")):
            self.voice_says("Voice ready. Click Talk once, or turn Live on.")

    # ================= Camera and greeting =================

    def build_camera(self, parent):
        inside = card(parent, "Camera", "Live video with what YOLO sees.")
        # The video from perception/detect.py, with YOLO's boxes
        frame = tk.Frame(inside, width=VIDEO_SIZE[0], height=VIDEO_SIZE[1], bg="#111111")
        frame.pack_propagate(False)  # keep the size while it shows text instead of video
        frame.pack()
        self.video = tk.Label(frame, bg="#111111", fg="white", font=TITLE,
                              text="Starting the camera ...")
        self.video.pack(fill="both", expand=True)
        self.photo = None          # the picture currently shown (Tkinter needs a reference)
        self.video_msg = None      # the newest video frame, not shown yet
        self.video_at = None       # when the last video frame arrived
        self.started_at = time.monotonic()
        self.node.create_subscription(CompressedImage, "/detections/image/compressed",
                                      self.on_video, 1)
        self.camera_status = text(inside, "Camera: no detections yet", muted=True)
        self.camera_status.pack(anchor="w", pady=(8, 0))

        inside = card(parent, "Camera greeting",
                      "When someone new appears, Robo waves and says hello on its own. "
                      "Paused while you're talking with Robo or building a move.")
        tk.Checkbutton(inside, text="Wave and say hello to new people", variable=self.greet_on,
                       font=FONT, bg=CARD, activebackground=CARD, fg=TEXT,
                       selectcolor=CARD).pack(anchor="w")

    def on_video(self, msg):
        self.video_msg, self.video_at = msg, time.monotonic()

    def show_video(self):
        """Show the newest camera frame, or say the camera isn't connected."""
        now = time.monotonic()
        if self.video_msg is not None and cv2 is not None:
            msg, self.video_msg = self.video_msg, None
            image = cv2.imdecode(np.frombuffer(bytes(msg.data), np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                ppm = b"P6 %d %d 255\n" % (width, height) + rgb.tobytes()
                self.photo = tk.PhotoImage(data=ppm, format="PPM")
                self.video.config(image=self.photo, text="")
            return
        # No video lately: give detection time to load at startup, then say so
        quiet_since = self.video_at if self.video_at is not None else self.started_at
        limit = NO_VIDEO_AFTER if self.video_at is not None else CAMERA_START_TIME
        if now - quiet_since > limit and self.photo is not False:
            self.photo = False  # remember we're showing the message
            self.video.config(image="", text="Camera not connected" if cv2 is not None
                              else "Camera view needs OpenCV (python3 -m pip install opencv-python)")

    def on_person(self, msg):
        self.camera_seen = True
        if msg.data:
            self.last_person = time.monotonic()

    def check_greeting(self):
        now = time.monotonic()
        if self.voice_busy or self.building():
            # Talking with someone, or building a move: no greetings. Count it as a
            # greeting, so whoever is there isn't greeted the moment it ends.
            self.decider.greeted(now)
            if self.camera_seen:
                self.camera_status.config(
                    text="Greeting paused while talking with Robo" if self.voice_busy
                    else "Greeting paused while you build a move")
            return
        if self.camera_seen:
            in_view = self.last_person is not None and now - self.last_person < 1.0
            self.camera_status.config(text="Camera: person in view" if in_view
                                      else "Camera: nobody in view")
        if not self.decider.should_greet(self.last_person, now):
            return
        self.decider.greeted(now)
        # Don't interrupt: skip the greeting while busy
        if not self.greet_on.get() or self.moving or self.robo.talking():
            return
        if self.robo.piper is not None:  # the speaking voice is ready
            self.robo.say(GREETING)
            self.add_line("Robo", GREETING)
        self.play("wave", GESTURES["w"][1])

    def quit(self):
        self.root.after_cancel(self.next_spin)
        self.stop_voice.set()
        self.robo.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Robo's control panel.")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model for Robo")
    parser.add_argument("--whisper", default="small", help="Whisper model")
    args, ros_args = parser.parse_known_args()

    load_saved()
    rclpy.init(args=ros_args)
    node = Gesturer()

    if not connect(node):
        node.destroy_node()
        rclpy.shutdown()
        return
    print("Opening the window.")

    root = tk.Tk()
    app = App(root, node, RoboVoice(model=args.model, whisper_size=args.whisper))
    # Ctrl+C in the terminal closes the window (otherwise Tkinter swallows it)
    signal.signal(signal.SIGINT, lambda *_: root.after(0, app.quit))
    root.mainloop()

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
