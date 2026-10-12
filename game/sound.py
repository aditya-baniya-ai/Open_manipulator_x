"""
Arcade sounds for the games: background music, sound effects, and a ticking timer that
speeds up as time runs out. All of it is made right here in code (little chiptune
tunes), so there's nothing to download.

Everything is mixed together and sent to the speaker through one `aplay`, so the music,
the timer and the effects can all play at the same time. If there's no speaker (or no
aplay, like on a Mac), the game simply runs without sound.

    sound = Sound()            # starts the speaker (or stays silent)
    sound.music(True)          # background music on (loops)
    sound.play("grab")         # a one-off effect (see EFFECTS)
    sound.timer(0.4)           # timer ticking, 0.4 = 40% of the time left (None = off)
    sound.close()

Hear them all on the Jetson:  python3 sound.py
"""

import math
import shutil
import subprocess
import threading
import time

import numpy as np

RATE = 22050            # samples a second (plenty for chiptune, light on the CPU)
CHUNK = 512             # samples mixed at a time (about 23 ms)
DEFAULT_SPEAKER = "plughw:CARD=Device,DEV=0"   # the USB speaker (as Robo's voice uses)
MUSIC_VOLUME = 0.30
MUSIC_UNDER_TIMER = 0.12   # quieter music while the timer ticks


EFFECTS = ["grab", "score", "drop", "fail", "buzzer", "beep", "go", "fanfare", "lose"]


# --- Making the sounds ---------------------------------------------------------------

def note(name):
    """'A4' -> 440.0 Hz (sharps with #)."""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2,
             "G#": -1, "A": 0, "A#": 1, "B": 2}
    return 440.0 * 2 ** ((names[name[:-1]] + 12 * (int(name[-1]) - 4)) / 12)


def tone(freq, seconds, wave="square", volume=0.5, slide_to=None, vibrato=0.0):
    """One sound: a wave at freq Hz (sliding to slide_to), with a quick fade in/out."""
    n = max(1, int(RATE * seconds))
    t = np.arange(n) / RATE
    f = np.full(n, float(freq)) if slide_to is None else np.linspace(freq, slide_to, n)
    if vibrato:
        f = f * (1 + 0.03 * np.sin(2 * math.pi * vibrato * t))
    phase = 2 * math.pi * np.cumsum(f) / RATE
    if wave == "square":
        sound = np.sign(np.sin(phase)) * 0.6
    elif wave == "triangle":
        sound = 2 / math.pi * np.arcsin(np.sin(phase))
    elif wave == "noise":
        sound = np.random.default_rng(1).uniform(-1, 1, n)
    else:
        sound = np.sin(phase)
    fade = min(n // 4, int(RATE * 0.01))
    envelope = np.ones(n)
    if fade:
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
    return (sound * envelope * volume).astype(np.float32)


def sequence(notes, beat, wave="square", volume=0.5, gap=0.15):
    """Notes one after another: [(name or None for a rest, beats), ...]."""
    parts = []
    for name, beats in notes:
        length = beat * beats
        if name is None:
            parts.append(np.zeros(int(RATE * length), np.float32))
        else:
            sound = tone(note(name), length * (1 - gap), wave, volume)
            parts.append(np.concatenate([sound, np.zeros(int(RATE * length * gap), np.float32)]))
    return np.concatenate(parts)


def together(*sounds):
    """Mix sounds that start at the same time."""
    out = np.zeros(max(len(s) for s in sounds), np.float32)
    for s in sounds:
        out[:len(s)] += s
    return out


def background_music():
    """A bouncy 8-bar loop in C major: melody, bass and a little drum (about 16 s)."""
    beat = 0.25  # 120 beats a minute, in eighth notes
    melody = [("E5", 1), ("G5", 1), ("C6", 1), ("G5", 1), ("A5", 2), ("G5", 1), ("E5", 1),
              ("F5", 1), ("A5", 1), ("C6", 1), ("A5", 1), ("G5", 2), (None, 2),
              ("E5", 1), ("G5", 1), ("C6", 1), ("E6", 1), ("D6", 2), ("C6", 1), ("A5", 1),
              ("G5", 1), ("E5", 1), ("D5", 1), ("E5", 1), ("C5", 2), (None, 2)] * 2
    bass_line = ["C3", "C3", "F3", "F3", "C3", "C3", "G3", "G3"] * 2
    bass = [(name, 4) for name in bass_line]
    tune = sequence(melody, beat, "square", 0.35)
    low = sequence(bass, beat, "triangle", 0.55, gap=0.05)
    hits = np.zeros(len(low), np.float32)
    kick = tone(110, 0.08, "sine", 0.7, slide_to=50)
    hat = tone(0, 0.03, "noise", 0.12)
    step = int(RATE * beat)
    for i in range(len(hits) // step):
        spot = i * step
        sound = kick if i % 4 == 0 else hat
        hits[spot:spot + len(sound)] += sound[:len(hits) - spot]
    return loudness(together(tune, low, hits), 1.0)


def loudness(sound, peak):
    """The same sound, scaled so its loudest point is peak (so all effects match)."""
    top = float(np.max(np.abs(sound))) or 1.0
    return (sound * (peak / top)).astype(np.float32)


EFFECT_PEAK = 0.6        # every effect equally loud; music + effect stays under 1.0


def effects():
    beat = 0.09
    sounds = {
        # The claw goes down to grab: a quick rising bloop
        "grab": tone(300, 0.18, "square", 0.45, slide_to=900),
        # A chocolate in the basket: happy arpeggio with a sparkle
        "score": together(sequence([("C5", 1), ("E5", 1), ("G5", 1), ("C6", 3)], beat, "square", 0.5),
                          np.concatenate([np.zeros(int(RATE * 0.27), np.float32),
                                          tone(note("E7"), 0.25, "sine", 0.25, slide_to=note("C8"))])),
        # Dropped outside the basket: a cartoon "womp" slide
        "drop": tone(420, 0.55, "square", 0.45, slide_to=110),
        # Nothing in the claw, or time's up: the sad trombone (wah wah wah waaah)
        "fail": np.concatenate([tone(note(n), d, "triangle", 0.6, vibrato=6 if d > 0.4 else 0)
                                for n, d in (("D#4", 0.32), ("D4", 0.32), ("C#4", 0.32),
                                             ("C4", 0.9))]),
        # Time's up: a buzzer first
        "buzzer": tone(140, 0.5, "square", 0.45),
        # Countdown beeps, and GO!
        "beep": tone(note("A5"), 0.12, "square", 0.4),
        "go": tone(note("A6"), 0.35, "square", 0.45),
        # Game over with prizes: a little fanfare
        "fanfare": sequence([("G4", 1), ("C5", 1), ("E5", 1), ("G5", 2), ("E5", 1), ("G5", 4)],
                            0.12, "square", 0.5),
        # Game over with nothing: the sad trombone, slower
        "lose": np.concatenate([tone(note(n), d, "triangle", 0.6, vibrato=6 if d > 0.5 else 0)
                                for n, d in (("G4", 0.4), ("F#4", 0.4), ("F4", 0.4),
                                             ("E4", 1.2))]),
        # The timer's tick and heartbeat (used by the timer)
        "tick": tone(1800, 0.025, "square", 0.25),
        "tock": tone(1300, 0.025, "square", 0.22),
        "heart": tone(70, 0.12, "sine", 0.55, slide_to=45),
    }
    for name in EFFECTS:
        sounds[name] = loudness(sounds[name], EFFECT_PEAK)
    return sounds


# --- Playing them --------------------------------------------------------------------

class Sound:
    """Mixes the music, the timer and the effects, and sends them to the speaker."""

    def __init__(self, speaker=DEFAULT_SPEAKER, enabled=True, command=None):
        self.ok = False
        self.lock = threading.Lock()
        self.playing = []            # [sound, position] for each effect still playing
        self.music_on, self.music_at = False, 0
        self.urgency = None          # the timer: None = off, else the share of time left
        self.next_tick, self.ticks = 0, 0
        if not enabled:
            return
        if command is None:
            if shutil.which("aplay") is None:
                return               # no speaker program (e.g. on a Mac): no sound
            command = ["aplay", "-q", "-D", speaker, "-f", "S16_LE", "-r", str(RATE),
                       "-c", "1", "-t", "raw", "--buffer-time=100000"]
        try:
            self.sounds = effects()
            self.song = background_music()
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        except Exception as error:   # sound must never stop a game
            print(f"(no sound: {error})")
            return
        self.ok = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    # -- what the game calls ------------------------------------------------------------
    def play(self, name):
        if self.ok and name in self.sounds:
            with self.lock:
                self.playing.append([self.sounds[name], 0])

    def music(self, on):
        self.music_on = on

    def timer(self, left):
        """left: the share of time left (1 = just started, 0 = out of time), or None."""
        if left is None or self.urgency is None:
            self.next_tick, self.ticks = 0, 0
        self.urgency = left

    def close(self):
        if self.ok:
            self.ok = False
            try:
                self.proc.stdin.close()
                self.proc.terminate()
            except Exception:
                pass

    # -- the mixer ----------------------------------------------------------------------
    def mix(self):
        """The next CHUNK samples of everything that's playing."""
        out = np.zeros(CHUNK, np.float32)
        if self.music_on:
            volume = MUSIC_UNDER_TIMER if self.urgency is not None else MUSIC_VOLUME
            song, at = self.song, self.music_at
            piece = song[at:at + CHUNK]
            if len(piece) < CHUNK:                      # loop round to the start
                piece = np.concatenate([piece, song[:CHUNK - len(piece)]])
            out += piece * volume
            self.music_at = (at + CHUNK) % len(song)
        left = self.urgency
        if left is not None:
            # Ticks get faster as time runs out: twice a second, up to 8 times a second
            interval = int(RATE * (0.5 - 0.375 * (1 - max(0.0, left))))
            while self.next_tick < CHUNK:
                at = self.next_tick
                sound = self.sounds["tick" if self.ticks % 2 == 0 else "tock"]
                if self.ticks % 2 == 0 and left < 0.6:
                    sound = together(sound, self.sounds["heart"])   # a heartbeat, near the end
                self.playing.append([sound, -at])      # starts later in this chunk
                self.ticks += 1
                self.next_tick += interval
            self.next_tick -= CHUNK
        with self.lock:
            still = []
            for item in self.playing:
                sound, position = item
                start = max(0, -position)
                begin = max(0, position)
                piece = sound[begin:begin + CHUNK - start]
                out[start:start + len(piece)] += piece
                item[1] = position + CHUNK
                if item[1] < len(sound):
                    still.append(item)
            self.playing = still
        return np.clip(out, -1, 1)

    def run(self):
        while self.ok:
            try:
                self.proc.stdin.write((self.mix() * 32000).astype(np.int16).tobytes())
            except Exception:       # the speaker went away: carry on silently
                self.ok = False


def main():
    """Play every sound once, then a bit of the music and the timer."""
    sound = Sound()
    if not sound.ok:
        print("No sound: is the USB speaker plugged in (and aplay installed)?")
        return
    for name in EFFECTS:
        print(name)
        sound.play(name)
        time.sleep(len(sound.sounds[name]) / RATE + 0.4)
    print("music")
    sound.music(True)
    time.sleep(4)
    print("timer (speeding up)")
    for i in range(80):
        sound.timer(1 - i / 80)
        time.sleep(0.1)
    sound.timer(None)
    time.sleep(1)
    sound.close()


if __name__ == "__main__":
    main()
