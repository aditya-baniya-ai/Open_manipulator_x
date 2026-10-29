"""
Which speaker Robo plays through (its voice and the game sounds), chosen when it starts:

  1. ROBO_SPEAKER, if it's set (e.g. export ROBO_SPEAKER=plughw:CARD=HDA,DEV=3)
  2. the USB speaker, if it's plugged in (sound card "Device")
  3. otherwise the desktop's sound output: whatever Settings > Sound is set to, such as
     the monitor's speakers over HDMI or DisplayPort

Check which one it picks:  python3 speaker.py
"""

import os
import re
from pathlib import Path

USB_SPEAKER = "plughw:CARD=Device,DEV=0"
DESKTOP = "default"     # the desktop's sound output (PulseAudio / PipeWire)
CARDS = Path("/proc/asound/cards")


def find_speaker():
    chosen = os.environ.get("ROBO_SPEAKER")
    if chosen:
        return chosen
    try:
        cards = CARDS.read_text()
    except OSError:
        cards = ""
    # A line like " 1 [Device         ]: USB-Audio - USB PnP Audio Device"
    if re.search(r"\[Device\s*\]", cards):
        return USB_SPEAKER
    return DESKTOP


if __name__ == "__main__":
    speaker = find_speaker()
    print(f"Robo will play through: {speaker}")
    if speaker == DESKTOP:
        print("(the desktop's sound output: choose the speaker in Settings > Sound)")
