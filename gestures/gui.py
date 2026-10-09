"""
Robo's control panel: buttons for gestures, moving each joint, the gripper and
recording your own moves; talking with Robo (once, or live); and greeting people the
camera sees.

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

import rclpy
from std_msgs.msg import Bool

from gestures import (
    GESTURES, GRIPPER, JOINTS, Gesturer, catch_up, connect, jog, key_problem, load_saved,
    move_gripper, record_pose, run_gesture, save_recording,
)
from greet import GreetDecider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
from robo_voice import GREETING, RoboVoice, choose_gesture, is_goodbye  # noqa: E402

JOINT_NAMES = ["Base", "Shoulder", "Elbow", "Wrist"]
FONT = ("Helvetica", 14)
BIG = ("Helvetica", 14, "bold")
SMALL = ("Helvetica", 12)
GREEN, RED, GREY = "#1a7f37", "#cf222e", "#57606a"
ONCE_TIMEOUT = 10  # seconds "Talk once" waits for you to start speaking


class App:
    def __init__(self, root, node, robo):
        self.root, self.node, self.robo = root, node, robo
        root.title("Robo")
        root.resizable(False, False)

        self.jobs = queue.Queue()      # work for the window's thread (from voice threads)
        self.moving = False            # a gesture is playing
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

        self.status = tk.Label(root, text="Ready", font=BIG, fg=GREEN)
        self.status.pack(pady=(10, 4))
        columns = tk.Frame(root)
        columns.pack(padx=6, pady=(0, 4))
        left, right = tk.Frame(columns), tk.Frame(columns)
        left.grid(row=0, column=0, sticky="n")
        right.grid(row=0, column=1, sticky="n")

        self.build_arm_controls(left)
        self.build_voice(right)
        self.build_greeting(right)

        tk.Button(root, text="Quit", font=FONT, width=10, command=self.quit).pack(pady=(4, 10))
        root.protocol("WM_DELETE_WINDOW", self.quit)

        # Get the voice ready right away: speaking first (a few seconds, so greetings can
        # talk), then listening and the LLM, so Talk once / Live start immediately
        self.after_load = None  # what to do once it's ready (a click while loading)
        self.with_voice_loaded(lambda: None)

        # Keep ROS messages (joint angles) coming in while the window is open
        self.spin()

    # ---------- Arm: gestures, joints, gripper, recording ----------

    def build_arm_controls(self, parent):
        # Gestures (rebuilt whenever a move is saved)
        self.gesture_box = tk.LabelFrame(parent, text="Gestures", font=FONT, padx=8, pady=8)
        self.gesture_box.pack(fill="x", padx=4, pady=4)
        self.show_gestures()

        # Joints: hold a button to keep moving
        joints = tk.LabelFrame(parent, text="Move joints (hold to keep moving)",
                               font=FONT, padx=8, pady=8)
        joints.pack(fill="x", padx=4, pady=4)
        self.angles = []  # live angle of each joint, in degrees
        for i, name in enumerate(JOINT_NAMES):
            tk.Label(joints, text=name, font=FONT, width=9, anchor="w").grid(row=i, column=0)
            for col, (label, direction) in enumerate([("-", -1), ("+", 1)], start=1):
                tk.Button(joints, text=label, font=BIG, width=4,
                          repeatdelay=300, repeatinterval=100,
                          command=lambda j=i, d=direction: jog(self.node, j, d),
                          ).grid(row=i, column=col, padx=4, pady=2)
            angle = tk.Label(joints, text="", font=FONT, width=7, anchor="e")
            angle.grid(row=i, column=3, padx=(8, 0))
            self.angles.append(angle)

        # Gripper
        gripper = tk.LabelFrame(parent, text="Gripper", font=FONT, padx=8, pady=8)
        gripper.pack(fill="x", padx=4, pady=4)
        for col, (key, (name, position)) in enumerate(GRIPPER.items()):
            tk.Button(gripper, text=name.capitalize(), font=FONT, width=10,
                      command=lambda p=position, n=name: self.gripper(n, p),
                      ).grid(row=0, column=col, padx=4)

        # Recording your own move
        record = tk.LabelFrame(parent, text="Record your own move", font=FONT, padx=8, pady=8)
        record.pack(fill="x", padx=4, pady=4)
        tk.Button(record, text="Add pose", font=FONT, width=10,
                  command=self.add_pose).grid(row=0, column=0, padx=4, pady=2)
        tk.Button(record, text="Start over", font=FONT, width=10,
                  command=self.start_over).grid(row=0, column=1, padx=4, pady=2)
        self.pose_count = tk.Label(record, text="Poses: 0", font=FONT)
        self.pose_count.grid(row=0, column=2, padx=4)
        tk.Label(record, text="Name", font=FONT).grid(row=1, column=0, sticky="e")
        self.name_entry = tk.Entry(record, font=FONT, width=16)
        self.name_entry.grid(row=1, column=1, columnspan=2, sticky="w", pady=2)
        tk.Label(record, text="Key (letter)", font=FONT).grid(row=2, column=0, sticky="e")
        self.key_entry = tk.Entry(record, font=FONT, width=4)
        self.key_entry.grid(row=2, column=1, sticky="w", pady=2)
        tk.Button(record, text="Save move", font=BIG, width=10,
                  command=self.save).grid(row=2, column=2, padx=4, pady=2)

    def spin(self):
        # Handle every waiting ROS message, and any work sent from the voice thread
        catch_up(self.node)
        while not self.jobs.empty():
            self.jobs.get_nowait()()
        for label, joint in zip(self.angles, JOINTS):
            if joint in self.node.joints:
                label.config(text=f"{math.degrees(self.node.joints[joint]):+.0f}°")
        self.check_greeting()
        self.next_spin = self.root.after(50, self.spin)

    def say(self, text, error=False):
        self.status.config(text=text, fg=RED if error else GREEN)
        self.root.update_idletasks()

    def show_gestures(self):
        for widget in self.gesture_box.winfo_children():
            widget.destroy()
        for i, (key, (name, moves)) in enumerate(GESTURES.items()):
            tk.Button(self.gesture_box, text=f"{name.capitalize()} ({key})", font=FONT, width=14,
                      command=lambda m=moves, n=name: self.play(n, m),
                      ).grid(row=i // 3, column=i % 3, padx=4, pady=2)

    def play(self, name, moves):
        # The window waits while the arm moves, so gestures can't overlap
        self.moving = True
        self.say(f"{name.capitalize()} ...")
        run_gesture(self.node, moves)
        self.say("Ready")
        self.moving = False

    def gripper(self, name, position):
        self.say(f"Gripper {name}")
        move_gripper(self.node, position)

    def add_pose(self):
        record_pose(self.node)
        self.pose_count.config(text=f"Poses: {len(self.node.recording)}")
        self.say(f"Pose {len(self.node.recording)} added")

    def start_over(self):
        self.node.recording = []
        self.pose_count.config(text="Poses: 0")
        self.say("Recording cleared")

    def save(self):
        if not self.node.recording:
            self.say("Add some poses first", error=True)
            return
        name = self.name_entry.get().strip() or "my move"
        key = self.key_entry.get().strip().lower()
        problem = key_problem(key)
        if problem:
            self.say(problem, error=True)
            return
        save_recording(self.node, name, key)
        self.pose_count.config(text="Poses: 0")
        self.name_entry.delete(0, tk.END)
        self.key_entry.delete(0, tk.END)
        self.show_gestures()
        self.say(f"Saved '{name}'")

    # ---------- Talk with Robo ----------

    def build_voice(self, parent):
        box = tk.LabelFrame(parent, text="Talk with Robo", font=FONT, padx=8, pady=8)
        box.pack(fill="x", padx=4, pady=4)
        buttons = tk.Frame(box)
        buttons.pack(fill="x")
        self.once_button = tk.Button(buttons, text="Talk once", font=BIG, width=10,
                                     command=self.talk_once)
        self.once_button.grid(row=0, column=0, padx=4, pady=2)
        self.live_button = tk.Button(buttons, text="Live: OFF", font=BIG, width=10,
                                     command=self.toggle_live)
        self.live_button.grid(row=0, column=1, padx=4, pady=2)
        tk.Button(buttons, text="Stop talking", font=FONT, width=10,
                  command=self.robo.stop_talking).grid(row=0, column=2, padx=4, pady=2)
        tk.Label(box, text="Talk once: one question and answer.   "
                           "Live: keeps listening until you turn it off.",
                 font=SMALL, fg=GREY).pack(anchor="w", pady=(2, 0))

        volume = tk.Frame(box)
        volume.pack(anchor="w", pady=(6, 0))
        tk.Label(volume, text="Speaker volume", font=FONT).grid(row=0, column=0, padx=(0, 8))
        tk.Button(volume, text="-", font=BIG, width=3,
                  command=lambda: self.change_volume(-5)).grid(row=0, column=1, padx=2)
        self.volume_label = tk.Label(volume, text="?", font=FONT, width=5)
        self.volume_label.grid(row=0, column=2)
        tk.Button(volume, text="+", font=BIG, width=3,
                  command=lambda: self.change_volume(+5)).grid(row=0, column=3, padx=2)
        self.show_volume(self.robo.volume())
        self.voice_status = tk.Label(box, text="Getting the voice ready ...",
                                     font=SMALL, fg=GREY, wraplength=480, justify="left")
        self.voice_status.pack(anchor="w", pady=(4, 4))

        frame = tk.Frame(box)
        frame.pack(fill="both")
        self.transcript = tk.Text(frame, font=SMALL, width=48, height=14, wrap="word",
                                  state="disabled")
        scroll = tk.Scrollbar(frame, command=self.transcript.yview)
        self.transcript.config(yscrollcommand=scroll.set)
        self.transcript.pack(side="left", fill="both")
        scroll.pack(side="right", fill="y")
        self.transcript.tag_config("you", foreground="#0969da")
        self.transcript.tag_config("robo", foreground=GREEN)

    def show_volume(self, percent):
        self.volume_label.config(text="?" if percent is None else f"{percent}%")

    def change_volume(self, step):
        percent = self.robo.volume(step)
        self.show_volume(percent)
        if percent is None:
            self.say("Couldn't change the speaker volume (is the USB speaker plugged in?)",
                     error=True)

    def post(self, job):
        """Run job on the window's thread (Tkinter and the arm must only be used there)."""
        self.jobs.put(job)

    def voice_says(self, text, error=False):
        self.voice_status.config(text=text, fg=RED if error else GREY)

    def add_line(self, who, text):
        self.transcript.config(state="normal")
        self.transcript.insert("end", f"{who}: ", "you" if who == "You" else "robo")
        self.transcript.insert("end", text + "\n\n")
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
                try:
                    reply = self.robo.answer(heard)
                except Exception as error:  # Ollama not running, timeout, ...
                    self.post(lambda e=error: self.voice_says(
                        f"Couldn't get an answer from the LLM: {e}", True))
                    if not live:
                        return
                    continue
                if self.stop_voice.is_set():  # Live was turned off while thinking
                    break
                key = choose_gesture(heard, reply, GESTURES)
                self.post(lambda r=reply: self.add_line("Robo", r))
                self.post(lambda: self.voice_says("Talking ..."))

                # Talk and move at the same time (the arm only moves on the window's thread)
                self.robo.say(reply)
                if key:
                    done = threading.Event()
                    name, moves = GESTURES[key]

                    def move(name=name, moves=moves, done=done):
                        try:
                            self.play(name, moves)
                        finally:
                            done.set()  # never leave the voice thread waiting

                    self.post(move)
                    done.wait()
                self.robo.wait_until_quiet()
                if not live or is_goodbye(heard):
                    break
        finally:
            self.post(self.voice_finished)

    def voice_finished(self):
        self.voice_busy = self.live = False
        self.once_button.config(state="normal")
        self.live_button.config(state="normal", text="Live: OFF")
        # Keep messages like "I didn't hear anything" or errors; replace progress messages
        if self.voice_status.cget("text").startswith(("Listening", "Thinking", "Talking",
                                                       "Stopping")):
            self.voice_says("Voice ready. Click Talk once, or turn Live on.")

    # ---------- Camera greeting ----------

    def build_greeting(self, parent):
        box = tk.LabelFrame(parent, text="Camera greeting", font=FONT, padx=8, pady=8)
        box.pack(fill="x", padx=4, pady=4)
        tk.Checkbutton(box, text="Wave and say hello when someone new appears",
                       variable=self.greet_on, font=SMALL).pack(anchor="w")
        tk.Label(box, text="Works on its own. Paused while you're talking with Robo.",
                 font=SMALL, fg=GREY).pack(anchor="w")
        self.camera_status = tk.Label(box, text="Camera: no detections yet", font=SMALL, fg=GREY)
        self.camera_status.pack(anchor="w", pady=(4, 0))

    def on_person(self, msg):
        self.camera_seen = True
        if msg.data:
            self.last_person = time.monotonic()

    def check_greeting(self):
        now = time.monotonic()
        if self.camera_seen:
            in_view = self.last_person is not None and now - self.last_person < 1.0
            self.camera_status.config(text="Camera: person in view" if in_view
                                      else "Camera: nobody in view")
        if not self.decider.should_greet(self.last_person, now):
            return
        self.decider.greeted(now)
        # Don't interrupt: skip the greeting while busy (they're probably talking to Robo)
        if not self.greet_on.get() or self.voice_busy or self.moving or self.robo.talking():
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
