"""
Talk with the robot: it listens (Whisper), thinks (a local LLM through Ollama),
answers out loud (Piper) and does a matching gesture with the arm.

Test the talking first (no arm needed):
    python3 chat.py --test

Then with the arm (or the simulation) launched (see README.md):
    python3 chat.py

Options:
    --wake robot       only answer sentences that contain this word
    --model NAME       Ollama model (default llama3.2:3b)
    --voice PATH       Piper voice (default ~/piper_voices/en_US-lessac-medium.onnx)
    --speaker DEVICE   speaker (default plughw:CARD=Device,DEV=0, the USB speaker)
    --mic DEVICE       microphone (default plughw:CARD=BRIO,DEV=0)

Say "goodbye" to stop, or press Ctrl+C.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from listen import loudness, listen_for_sentence, start_mic  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/chat"
HISTORY = 6  # how many earlier exchanges the robot remembers

PERSONALITY = """You are a friendly robot arm on a table in a makerspace. You have no
face, just an arm with a gripper, a camera and a voice. Answer in one or two short,
cheerful sentences (under 25 words), like you're talking out loud. Choose one gesture
that fits your answer, or "none". Available gestures: {gestures}."""


def ask_llm(model, messages, gesture_names):
    """Send the conversation to Ollama and return (reply, gesture name)."""
    schema = {
        "type": "object",
        "properties": {
            "say": {"type": "string"},
            "gesture": {"type": "string", "enum": gesture_names + ["none"]},
        },
        "required": ["say", "gesture"],
    }
    body = json.dumps({"model": model, "messages": messages, "format": schema,
                       "stream": False}).encode()
    request = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        answer = json.loads(json.loads(response.read())["message"]["content"])
    return answer["say"].strip(), answer["gesture"]


def speak(voice, text, speaker):
    """Start saying text on the speaker; returns the playing process."""
    path = Path(tempfile.gettempdir()) / "robot_says.wav"
    with wave.open(str(path), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return subprocess.Popen(["aplay", "-q", "-D", speaker, str(path)])


def main():
    parser = argparse.ArgumentParser(description="Talk with the robot arm.")
    parser.add_argument("--test", action="store_true",
                        help="talk only; don't move the arm")
    parser.add_argument("--wake", help="only answer sentences containing this word")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model")
    parser.add_argument("--voice", default=str(Path.home() / "piper_voices/en_US-lessac-medium.onnx"),
                        help="Piper voice file")
    parser.add_argument("--speaker", default="plughw:CARD=Device,DEV=0", help="speaker device")
    parser.add_argument("--mic", default="plughw:CARD=BRIO,DEV=0", help="microphone device")
    parser.add_argument("--threshold", type=float,
                        help="loudness that counts as speech (default: measured)")
    args, ros_args = parser.parse_known_args()

    from gestures import GESTURES, load_saved
    load_saved()
    # The LLM picks gestures by name; skip "home", it's not much of an answer
    by_name = {name.lower(): moves for key, (name, moves) in GESTURES.items() if key != "h"}

    print("Loading Whisper and the voice ...")
    import whisper
    from piper import PiperVoice
    ears = whisper.load_model("base", device="cuda")
    voice = PiperVoice.load(args.voice)

    node = None
    if not args.test:
        import rclpy
        from gestures import Gesturer, connect, run_gesture
        rclpy.init(args=ros_args)
        node = Gesturer()
        if not connect(node):
            node.destroy_node()
            rclpy.shutdown()
            return

    messages = [{"role": "system",
                 "content": PERSONALITY.format(gestures=", ".join(by_name))}]

    proc, chunks = start_mic(args.mic)
    threshold = args.threshold
    if threshold is None:
        print("Measuring background noise, please stay quiet for 1 second ...")
        noise = np.median([loudness(chunks.get()) for _ in range(10)])
        threshold = max(3 * noise, 200)
    print("Listening. Talk to the robot! (Say 'goodbye' or press Ctrl+C to stop.)")
    if args.wake:
        print(f"Start each sentence with '{args.wake}'.")

    try:
        while True:
            audio = listen_for_sentence(chunks, threshold)
            if audio is None:
                continue
            heard = ears.transcribe(audio, fp16=True, language="en",
                                    condition_on_previous_text=False)["text"].strip()
            if not heard:
                continue
            print(f"You:   {heard}")
            if args.wake and args.wake.lower() not in heard.lower():
                continue

            messages.append({"role": "user", "content": heard})
            try:
                reply, gesture = ask_llm(args.model, messages, list(by_name))
            except Exception as error:  # Ollama not running, bad answer, ...
                print(f"  (couldn't get an answer from the LLM: {error})")
                messages.pop()
                continue
            messages.append({"role": "assistant", "content": reply})
            messages[1:] = messages[1:][-2 * HISTORY:]
            print(f"Robot: {reply}" + (f"  [{gesture}]" if gesture != "none" else ""))

            # Talk and move at the same time, then wait for both
            playing = speak(voice, reply, args.speaker)
            if node is not None and gesture in by_name:
                run_gesture(node, by_name[gesture])
            playing.wait()
            # Throw away what the mic heard while the robot talked and moved
            while not chunks.empty():
                chunks.get_nowait()

            if "goodbye" in heard.lower() or "bye bye" in heard.lower():
                break
    except KeyboardInterrupt:
        pass
    finally:
        proc.kill()  # stop the mic recorder quietly (terminate makes it print an error)
        if node is not None:
            import rclpy
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == "__main__":
    main()
