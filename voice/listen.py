"""
Voice commands: listen to the microphone, turn speech into text with Whisper,
and do a gesture when you say its name.

Test the listening first (no arm needed):
    python3 listen.py --test

Then with the arm (or the simulation) launched (see README.md):
    python3 listen.py

Say for example "wave", "hello", "nod", "shake your head", "bow", "look around",
"go home", or the name of a move you saved yourself.

Options:
    --wake robot     only act on sentences that contain this word
    --threshold 800  how loud speech must be to start listening (default: measured
                     from the room's background noise when it starts)
    --mic plughw:2,0 which microphone to use (default: the Logitech BRIO)

Publishes what it heard on /voice_text (std_msgs/String).
"""

import argparse
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gestures"))

RATE = 16000                 # samples per second (what Whisper expects)
CHUNK = RATE // 10           # read the mic in 0.1 s pieces
SILENCE_END = 0.8            # seconds of quiet that end a sentence
MAX_SPEECH = 8.0             # longest sentence, in seconds
MIN_SPEECH = 0.3             # shorter sounds are ignored (clicks, bumps)
PRE_ROLL = 3                 # chunks kept from before the speech started

# Words that trigger each built-in gesture key from gestures.py
COMMANDS = {
    "w": ["wave", "hello", "hi"],
    "n": ["nod"],
    "s": ["shake"],
    "b": ["bow"],
    "l": ["look"],
    "h": ["home", "rest"],
}


def start_mic(device):
    """Read the microphone in a background thread, one chunk at a time."""
    proc = subprocess.Popen(
        ["arecord", "-q", "-D", device, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )
    chunks = queue.Queue()

    def reader():
        while True:
            data = proc.stdout.read(CHUNK * 2)
            if not data:
                break
            chunks.put(np.frombuffer(data, dtype=np.int16))

    threading.Thread(target=reader, daemon=True).start()
    return proc, chunks


def loudness(chunk):
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def listen_for_sentence(chunks, threshold):
    """Wait for speech, and return it once there's a pause (or None if too short)."""
    before = []
    while True:
        chunk = chunks.get()
        if loudness(chunk) > threshold:
            break
        before = (before + [chunk])[-PRE_ROLL:]

    speech, quiet = before + [chunk], 0
    while len(speech) * 0.1 < MAX_SPEECH and quiet * 0.1 < SILENCE_END:
        chunk = chunks.get()
        speech.append(chunk)
        quiet = quiet + 1 if loudness(chunk) <= threshold else 0

    if (len(speech) - quiet) * 0.1 < MIN_SPEECH:
        return None
    return np.concatenate(speech).astype(np.float32) / 32768.0


def find_gesture(text, gestures):
    """Return the key of the gesture named in the text, or None."""
    words = re.findall(r"[a-z']+", text.lower())
    sentence = " ".join(words)
    # Moves you saved yourself, matched by their full name
    for key, (name, _) in gestures.items():
        if key not in COMMANDS and name.lower() in sentence:
            return key
    for key, triggers in COMMANDS.items():
        if any(t in words for t in triggers):
            return key
    return None


def main():
    parser = argparse.ArgumentParser(description="Voice commands for the robot arm.")
    parser.add_argument("--test", action="store_true",
                        help="only print what it hears; don't move the arm")
    parser.add_argument("--wake", help="only act on sentences containing this word")
    parser.add_argument("--threshold", type=float,
                        help="loudness that counts as speech (default: measured)")
    parser.add_argument("--mic", default="plughw:2,0",
                        help="microphone device (default plughw:2,0, the BRIO)")
    parser.add_argument("--model", default="base",
                        help="Whisper model: tiny, base, small (default base)")
    args, ros_args = parser.parse_known_args()

    from gestures import GESTURES, load_saved
    load_saved()

    print("Loading Whisper ...")
    import whisper
    model = whisper.load_model(args.model, device="cuda")

    node = None
    if not args.test:
        import rclpy
        from std_msgs.msg import String
        from gestures import Gesturer, run_gesture

        rclpy.init(args=ros_args)
        node = Gesturer()
        text_pub = node.create_publisher(String, "/voice_text", 10)
        print("Waiting for the arm ...")
        while rclpy.ok() and node.base is None:
            rclpy.spin_once(node, timeout_sec=0.1)
        node.client.wait_for_server()

    proc, chunks = start_mic(args.mic)
    threshold = args.threshold
    if threshold is None:
        print("Measuring background noise, please stay quiet for 1 second ...")
        noise = np.median([loudness(chunks.get()) for _ in range(10)])
        threshold = max(3 * noise, 200)
    print(f"Listening (speech threshold {threshold:.0f}). Press Ctrl+C to stop.")
    if args.wake:
        print(f"Start each command with '{args.wake}'.")

    try:
        while True:
            audio = listen_for_sentence(chunks, threshold)
            if audio is None:
                continue
            text = model.transcribe(audio, fp16=True, language="en",
                                    condition_on_previous_text=False)["text"].strip()
            if not text:
                continue
            print(f"Heard: {text}")
            if node is not None:
                text_pub.publish(String(data=text))

            if args.wake and args.wake.lower() not in text.lower():
                continue
            key = find_gesture(text, GESTURES)
            if key is None:
                continue
            name, moves = GESTURES[key]
            print(f"  -> {name}")
            if node is not None:
                run_gesture(node, moves)
                # Throw away what the mic heard while the arm was moving
                while not chunks.empty():
                    chunks.get_nowait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        if node is not None:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
