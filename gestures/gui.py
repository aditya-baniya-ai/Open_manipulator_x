"""
Buttons for everything in gestures.py: gestures, moving each joint, the gripper,
and recording your own moves. Same features as the keyboard menu, in a window.

Run it while the arm (or the simulation) is launched (see README.md):
    python3 gui.py
Or start the arm and the window together:
    ../launch/gestures.sh --gui          (add --sim for the simulated arm)
"""

import signal
import tkinter as tk

import rclpy

from gestures import (
    GESTURES, GRIPPER, Gesturer, jog, key_problem, load_saved, move_gripper,
    record_pose, run_gesture, save_recording,
)

JOINT_NAMES = ["Base", "Shoulder", "Elbow", "Wrist"]
FONT = ("Helvetica", 14)
BIG = ("Helvetica", 14, "bold")


class App:
    def __init__(self, root, node):
        self.root, self.node = root, node
        root.title("Robot arm")
        root.resizable(False, False)

        self.status = tk.Label(root, text="Ready", font=BIG, fg="#1a7f37")
        self.status.pack(pady=(10, 4))

        # Gestures (rebuilt whenever a move is saved)
        self.gesture_box = tk.LabelFrame(root, text="Gestures", font=FONT, padx=8, pady=8)
        self.gesture_box.pack(fill="x", padx=10, pady=4)
        self.show_gestures()

        # Joints: hold a button to keep moving
        joints = tk.LabelFrame(root, text="Move joints (hold to keep moving)",
                               font=FONT, padx=8, pady=8)
        joints.pack(fill="x", padx=10, pady=4)
        for i, name in enumerate(JOINT_NAMES):
            tk.Label(joints, text=name, font=FONT, width=9, anchor="w").grid(row=i, column=0)
            for col, (label, direction) in enumerate([("−", -1), ("+", 1)], start=1):
                tk.Button(joints, text=label, font=BIG, width=4,
                          repeatdelay=300, repeatinterval=100,
                          command=lambda j=i, d=direction: jog(self.node, j, d),
                          ).grid(row=i, column=col, padx=4, pady=2)

        # Gripper
        gripper = tk.LabelFrame(root, text="Gripper", font=FONT, padx=8, pady=8)
        gripper.pack(fill="x", padx=10, pady=4)
        for col, (key, (name, position)) in enumerate(GRIPPER.items()):
            tk.Button(gripper, text=name.capitalize(), font=FONT, width=10,
                      command=lambda p=position, n=name: self.gripper(n, p),
                      ).grid(row=0, column=col, padx=4)

        # Recording your own move
        record = tk.LabelFrame(root, text="Record your own move", font=FONT, padx=8, pady=8)
        record.pack(fill="x", padx=10, pady=4)
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

        tk.Button(root, text="Quit", font=FONT, width=10,
                  command=root.destroy).pack(pady=10)

        # Keep ROS messages (joint angles) coming in while the window is open
        self.spin()

    def spin(self):
        rclpy.spin_once(self.node, timeout_sec=0.0)
        self.root.after(50, self.spin)

    def say(self, text, error=False):
        self.status.config(text=text, fg="#cf222e" if error else "#1a7f37")
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
        self.say(f"{name.capitalize()} ...")
        run_gesture(self.node, moves)
        self.say("Ready")

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


def main():
    load_saved()
    rclpy.init()
    node = Gesturer()

    print("Waiting for the arm ...")
    while rclpy.ok() and node.base is None:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.client.wait_for_server()
    node.home_base = node.base
    print("Ready. Opening the window.")

    root = tk.Tk()
    App(root, node)
    # Ctrl+C in the terminal closes the window (otherwise Tkinter swallows it)
    signal.signal(signal.SIGINT, lambda *_: root.after(0, root.destroy))
    root.mainloop()

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
