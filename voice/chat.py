"""
Talk with Robo in the terminal: it listens (Whisper), thinks (a local LLM through
Ollama), answers out loud (Piper) and does a matching gesture with the arm.
(The control panel, gestures/gui.py, has the same thing as buttons.)

Robo only talks about robotics, simulation, itself, Texas State University and the
Ingram Hall Makerspace. Its facts come from robo_knowledge.md next to this file, and
its personality is PERSONALITY in robo_voice.py.

Test the talking first (no arm needed):
    python3 chat.py --test

Then with the arm (or the simulation) launched (see README.md):
    python3 chat.py

Options:
    --wake robo        only answer sentences that contain this word
    --model NAME       Ollama model (default llama3.2:3b)
    --whisper SIZE     Whisper model: base (faster) or small (more accurate, default)
    --voice PATH       Piper voice (default ~/piper_voices/en_US-lessac-medium.onnx)
    --speaker DEVICE   speaker (default plughw:CARD=Device,DEV=0, the USB speaker)
    --mic DEVICE       microphone (default plughw:CARD=BRIO,DEV=0)

Press Enter while Robo is talking to cut it off.
Say "goodbye" to stop, or press Ctrl+C.
"""

import argparse
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robo_voice import DEFAULT_VOICE, RoboVoice, choose_gesture, is_goodbye  # noqa: E402


def cut_off_with_enter(robo):
    """Every press of Enter stops Robo talking."""
    def watch():
        for _ in sys.stdin:
            if robo.talking():
                robo.stop_talking()
                print("  (stopped talking)")
    threading.Thread(target=watch, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="Talk with Robo, the robot arm.")
    parser.add_argument("--test", action="store_true",
                        help="talk only; don't move the arm")
    parser.add_argument("--wake", help="only answer sentences containing this word")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model")
    parser.add_argument("--whisper", default="small",
                        help="Whisper model: base (faster) or small (more accurate)")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Piper voice file")
    parser.add_argument("--speaker", default="plughw:CARD=Device,DEV=0", help="speaker device")
    parser.add_argument("--mic", default="plughw:CARD=BRIO,DEV=0", help="microphone device")
    parser.add_argument("--threshold", type=float,
                        help="loudness that counts as speech (default: measured)")
    args, ros_args = parser.parse_known_args()

    from gestures import GESTURES, load_saved
    load_saved()

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

    robo = RoboVoice(args.model, args.whisper, args.voice, args.speaker, args.mic,
                     args.threshold)
    robo.load()
    print("Listening. Talk to Robo! Press Enter to cut it off while it's talking.")
    print("(Say 'goodbye' or press Ctrl+C to stop.)")
    if args.wake:
        print(f"Start each sentence with '{args.wake}'.")
    cut_off_with_enter(robo)

    try:
        while True:
            heard = robo.listen()
            if not heard:
                continue
            print(f"You:   {heard}")
            if args.wake and args.wake.lower() not in heard.lower():
                continue
            try:
                reply = robo.answer(heard)
            except Exception as error:  # Ollama not running, timeout, ...
                print(f"  (couldn't get an answer from the LLM: {error})")
                continue
            gesture = choose_gesture(heard, reply, GESTURES)
            print(f"Robo:  {reply}" + (f"  [{GESTURES[gesture][0]}]" if gesture else ""))

            # Talk and move at the same time, then wait for both
            robo.say(reply)
            if node is not None and gesture:
                run_gesture(node, GESTURES[gesture][1])
            robo.wait_until_quiet()
            if is_goodbye(heard):
                break
    except KeyboardInterrupt:
        pass
    finally:
        robo.close()
        if node is not None:
            import rclpy
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == "__main__":
    main()
