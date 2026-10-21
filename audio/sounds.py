"""Synthesized sound effects + ambient music.

Every sound is generated with plain Python math (no audio files needed) and
cached as WAV in the user's app-data folder on first launch. Custom sounds can
be dropped into ``assets/sounds/<name>.wav`` (and ``assets/music/theme.wav``)
to override the generated ones.
"""
from __future__ import annotations

import math
import os
import random
import sys
import threading
import wave
from array import array

RATE = 22050
CACHE_VERSION = "v3"

try:
    from PyQt6.QtCore import QObject, QUrl, pyqtSignal
    from PyQt6.QtMultimedia import QSoundEffect
    HAVE_QT_AUDIO = True
except Exception:  # pragma: no cover
    HAVE_QT_AUDIO = False
    from PyQt6.QtCore import QObject, pyqtSignal


def _cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "WizardWarChess", f"audio_{CACHE_VERSION}")
    os.makedirs(path, exist_ok=True)
    return path


def _asset_dir(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", *parts)


# ================================================================ synthesis
class Buf:
    def __init__(self, seconds: float, rate: int = RATE):
        self.rate = rate
        self.data = [0.0] * int(seconds * rate)

    def __len__(self):
        return len(self.data)

    def add_tone(self, freq, start, dur, amp, attack=0.005, decay=None, freq_end=None, wave_kind="sine",
                 vibrato=0.0, vib_rate=5.0, tremolo=0.0, harmonics=None):
        r = self.rate
        i0 = int(start * r)
        n = int(dur * r)
        f0, f1 = freq, (freq_end if freq_end is not None else freq)
        phase = 0.0
        tau = math.tau
        harmonics = harmonics or [(1, 1.0)]
        data = self.data
        for k in range(n):
            i = i0 + k
            if i >= len(data):
                break
            t = k / r
            u = k / n
            f = f0 + (f1 - f0) * u
            if vibrato:
                f *= 1 + vibrato * math.sin(tau * vib_rate * t)
            phase += f / r
            if wave_kind == "sine":
                s = 0.0
                for h, ha in harmonics:
                    s += ha * math.sin(tau * phase * h)
            elif wave_kind == "saw":
                s = 2 * (phase % 1.0) - 1
            elif wave_kind == "square":
                s = 1.0 if (phase % 1.0) < 0.5 else -1.0
            else:  # triangle
                x = phase % 1.0
                s = 4 * abs(x - 0.5) - 1
            env = min(1.0, t / attack) if attack > 0 else 1.0
            if decay:
                env *= math.exp(-t / decay)
            else:
                env *= min(1.0, (dur - t) / 0.03) if dur - t < 0.03 else 1.0
            if tremolo:
                env *= 1 - tremolo * (0.5 + 0.5 * math.sin(tau * 9 * t))
            data[i] += s * amp * env

    def add_noise(self, start, dur, amp, decay=None, attack=0.002, lowpass=1.0, lowpass_end=None, seed=None):
        rng = random.Random(seed)
        r = self.rate
        i0 = int(start * r)
        n = int(dur * r)
        y = 0.0
        a0 = lowpass
        a1 = lowpass if lowpass_end is None else lowpass_end
        data = self.data
        for k in range(n):
            i = i0 + k
            if i >= len(data):
                break
            t = k / r
            a = a0 + (a1 - a0) * (k / n)
            y += a * (rng.uniform(-1, 1) - y)
            env = min(1.0, t / attack) if attack > 0 else 1.0
            if decay:
                env *= math.exp(-t / decay)
            if dur - t < 0.02:
                env *= (dur - t) / 0.02
            data[i] += y * amp * env

    def normalize(self, peak=0.85):
        m = max((abs(v) for v in self.data), default=0.0)
        if m > 0:
            k = peak / m
            self.data = [v * k for v in self.data]
        return self

    def save(self, path):
        pcm = array("h", (int(max(-1.0, min(1.0, v)) * 32000) for v in self.data))
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(pcm.tobytes())


def _note(n: int) -> float:
    """MIDI note number to frequency."""
    return 440.0 * 2 ** ((n - 69) / 12)


def synth(name: str) -> Buf:
    b: Buf
    if name == "move":
        b = Buf(0.22)
        b.add_tone(150, 0, 0.2, 0.9, decay=0.045, freq_end=70)
        b.add_noise(0, 0.05, 0.35, decay=0.012, lowpass=0.35)
    elif name == "move_start":
        b = Buf(0.18)
        b.add_noise(0, 0.18, 0.4, attack=0.05, decay=0.06, lowpass=0.08, lowpass_end=0.2)
    elif name == "select":
        b = Buf(0.25)
        b.add_tone(1318, 0, 0.25, 0.25, decay=0.06)
        b.add_tone(1976, 0, 0.2, 0.12, decay=0.04)
    elif name == "whoosh":
        b = Buf(0.45)
        b.add_noise(0, 0.45, 0.8, attack=0.15, decay=0.12, lowpass=0.04, lowpass_end=0.35)
    elif name == "charge":
        b = Buf(0.45)
        b.add_tone(220, 0, 0.42, 0.45, attack=0.3, freq_end=880, harmonics=[(1, 1), (2, 0.3), (3, 0.15)])
        b.add_tone(330, 0.05, 0.38, 0.2, attack=0.3, freq_end=1320, vibrato=0.02, vib_rate=14)
    elif name == "charge_small":
        b = Buf(0.25)
        b.add_tone(400, 0, 0.24, 0.4, attack=0.15, freq_end=1000)
    elif name == "zap":
        b = Buf(0.2)
        b.add_tone(1400, 0, 0.18, 0.35, decay=0.07, freq_end=250, wave_kind="square")
        b.add_noise(0, 0.08, 0.3, decay=0.03, lowpass=0.6)
    elif name == "beam":
        b = Buf(0.6)
        for f in (220, 331, 440):
            b.add_tone(f, 0, 0.58, 0.18, attack=0.04, wave_kind="saw", vibrato=0.01, vib_rate=18)
        b.add_noise(0, 0.58, 0.15, attack=0.04, lowpass=0.5)
    elif name == "cannon":
        b = Buf(0.7)
        b.add_tone(90, 0, 0.6, 1.0, decay=0.18, freq_end=35)
        b.add_noise(0, 0.5, 0.7, decay=0.09, lowpass=0.25)
    elif name == "boom":
        b = Buf(1.0)
        b.add_noise(0, 1.0, 1.0, decay=0.22, lowpass=0.5, lowpass_end=0.05)
        b.add_tone(60, 0, 0.9, 0.9, decay=0.3, freq_end=30)
    elif name == "impact":
        b = Buf(0.5)
        b.add_noise(0, 0.5, 0.8, decay=0.1, lowpass=0.4, lowpass_end=0.08)
        b.add_tone(90, 0, 0.4, 0.6, decay=0.12, freq_end=45)
    elif name == "thunder":
        b = Buf(1.6)
        b.add_noise(0, 0.08, 1.0, decay=0.03, lowpass=0.95)
        b.add_noise(0.03, 1.55, 0.9, attack=0.05, decay=0.45, lowpass=0.06, lowpass_end=0.02)
        b.add_tone(48, 0.02, 1.2, 0.5, decay=0.4)
    elif name == "shatter":
        b = Buf(0.7)
        rng = random.Random(5)
        for _ in range(9):
            b.add_tone(rng.uniform(1800, 4200), rng.uniform(0, 0.15), 0.5, 0.12, decay=rng.uniform(0.05, 0.15))
        b.add_noise(0, 0.25, 0.3, decay=0.06, lowpass=0.9)
    elif name == "shield":
        b = Buf(0.9)
        for f, a in ((523, 0.4), (784, 0.3), (1046, 0.25), (1568, 0.12)):
            b.add_tone(f, 0, 0.88, a, decay=0.3)
    elif name == "capture":
        b = synth("impact")
    elif name == "castle":
        b = Buf(0.6)
        b.add_tone(150, 0, 0.2, 0.9, decay=0.04, freq_end=70)
        b.add_tone(150, 0.16, 0.2, 0.9, decay=0.04, freq_end=70)
        b.add_tone(1046, 0.25, 0.35, 0.25, decay=0.12)
    elif name == "promote":
        b = Buf(1.1)
        for i, n in enumerate((72, 76, 79, 84, 88)):
            b.add_tone(_note(n), i * 0.09, 0.7, 0.32, decay=0.25, harmonics=[(1, 1), (2, 0.25)])
    elif name == "check":
        b = Buf(1.1)
        b.add_tone(196, 0, 1.05, 0.7, decay=0.45, harmonics=[(1, 1), (2.01, 0.5), (3.02, 0.25)], tremolo=0.25)
        b.add_tone(392, 0, 0.6, 0.25, decay=0.2)
    elif name == "doom":
        b = Buf(1.8)
        b.add_tone(110, 0, 1.75, 0.6, attack=0.2, freq_end=55, harmonics=[(1, 1), (2, 0.4), (3, 0.2)])
        b.add_noise(0, 1.75, 0.3, attack=0.4, lowpass=0.03)
    elif name == "freeze":
        b = Buf(1.2)
        rng = random.Random(9)
        for _ in range(8):
            b.add_tone(rng.uniform(2000, 3600), rng.uniform(0, 0.4), 0.8, 0.08, attack=0.05, decay=0.25,
                       tremolo=0.5)
        b.add_noise(0, 1.1, 0.25, attack=0.3, decay=0.4, lowpass=0.7)
    elif name == "victory_horn":
        b = Buf(2.0)
        for st, dur, n in ((0, 0.25, 67), (0.25, 0.25, 72), (0.5, 0.25, 76), (0.75, 1.2, 79)):
            b.add_tone(_note(n), st, dur + 0.1, 0.32, attack=0.03, decay=0.6 if dur > 1 else None,
                       wave_kind="saw", vibrato=0.006)
            b.add_tone(_note(n - 12), st, dur + 0.1, 0.22, attack=0.03, decay=0.6 if dur > 1 else None)
    elif name == "defeat":
        b = Buf(1.8)
        for st, n in ((0, 67), (0.4, 63), (0.8, 60), (1.2, 55)):
            b.add_tone(_note(n), st, 0.6, 0.3, attack=0.03, decay=0.3, wave_kind="triangle")
    elif name == "draw":
        b = Buf(1.0)
        b.add_tone(_note(67), 0, 0.5, 0.3, decay=0.2)
        b.add_tone(_note(67), 0.4, 0.6, 0.3, decay=0.25)
    elif name == "success":
        b = Buf(0.8)
        for i, n in enumerate((72, 76, 79, 84)):
            b.add_tone(_note(n), i * 0.07, 0.6, 0.3, decay=0.2)
    elif name == "illegal":
        b = Buf(0.18)
        b.add_tone(110, 0, 0.17, 0.4, wave_kind="square")
    elif name == "hint":
        b = Buf(0.6)
        for i, n in enumerate((84, 88, 91)):
            b.add_tone(_note(n), i * 0.06, 0.45, 0.18, decay=0.15)
    elif name == "start":
        b = Buf(1.2)
        for st, n in ((0, 60), (0.18, 67), (0.36, 72)):
            b.add_tone(_note(n), st, 0.75, 0.3, attack=0.04, decay=0.35, wave_kind="saw", vibrato=0.005)
    else:
        b = Buf(0.1)
    return b.normalize(0.8)


SFX_NAMES = ["move", "move_start", "select", "whoosh", "charge", "charge_small", "zap", "beam", "cannon",
             "boom", "impact", "thunder", "shatter", "shield", "capture", "castle", "promote", "check", "doom",
             "freeze", "victory_horn", "defeat", "draw", "success", "illegal", "hint", "start"]

SFX_GAIN = {"move_start": 0.4, "select": 0.5, "whoosh": 0.6, "move": 0.8, "hint": 0.6, "boom": 0.9,
            "thunder": 0.85}


def synth_music(seconds: float = 32.0, rate: int = 16000) -> Buf:
    """A slow, mysterious pad loop: Am - F - C - G with drifting bells."""
    b = Buf(seconds, rate)
    chords = [(57, 60, 64), (53, 57, 60), (48, 55, 64), (55, 59, 62)]
    seg = seconds / len(chords)
    for i, chord in enumerate(chords):
        st = i * seg
        for n in chord:
            b.add_tone(_note(n), st, seg + 1.2, 0.10, attack=1.4, decay=seg * 0.9,
                       harmonics=[(1, 1), (2, 0.35), (3, 0.12)], vibrato=0.003, vib_rate=0.3)
        b.add_tone(_note(chord[0] - 12), st, seg + 0.5, 0.12, attack=1.0, decay=seg)
    rng = random.Random(4)
    scale = [69, 72, 74, 76, 79, 81, 84]
    t = 0.6
    while t < seconds - 2:
        b.add_tone(_note(rng.choice(scale)), t, 2.2, 0.05, decay=0.8, harmonics=[(1, 1), (2.76, 0.2)])
        t += rng.choice((1.0, 1.5, 2.0))
    # make the loop seamless: fade both ends slightly
    n = len(b.data)
    fade = int(0.8 * rate)
    for k in range(fade):
        g = k / fade
        b.data[k] *= g
        b.data[n - 1 - k] *= g
    return b.normalize(0.55)


# ================================================================== player
class SoundBank(QObject):
    ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.music_enabled = True
        self.volume = 0.7
        self.music_volume = 0.35
        self.paths: dict[str, str] = {}
        self._effects: dict[str, list] = {}
        self._rr: dict[str, int] = {}
        self._music = None
        self._ready = False
        self.ready.connect(self._on_ready)
        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self):
        try:
            cache = _cache_dir()
            for name in SFX_NAMES:
                custom = _asset_dir("sounds", f"{name}.wav")
                if os.path.isfile(custom):
                    self.paths[name] = custom
                    continue
                path = os.path.join(cache, f"{name}.wav")
                if not os.path.isfile(path):
                    synth(name).save(path)
                self.paths[name] = path
            custom_music = _asset_dir("music", "theme.wav")
            if os.path.isfile(custom_music):
                self.paths["music"] = custom_music
            else:
                path = os.path.join(cache, "music.wav")
                if not os.path.isfile(path):
                    synth_music().save(path)
                self.paths["music"] = path
        except Exception as exc:  # audio must never crash the game
            print("audio disabled:", exc)
            return
        self.ready.emit()

    def _on_ready(self):
        self._ready = True
        if not HAVE_QT_AUDIO:
            return
        for name, path in self.paths.items():
            if name == "music":
                continue
            pool = []
            for _ in range(3 if name in ("move", "select", "impact", "shatter", "thunder", "zap") else 2):
                fx = QSoundEffect(self)
                fx.setSource(QUrl.fromLocalFile(path))
                pool.append(fx)
            self._effects[name] = pool
        self._music = QSoundEffect(self)
        self._music.setSource(QUrl.fromLocalFile(self.paths["music"]))
        self._music.setLoopCount(QSoundEffect.Loop.Infinite.value)
        self._apply_music()

    def play(self, name: str):
        if not (self.enabled and self._ready):
            return
        if HAVE_QT_AUDIO:
            pool = self._effects.get(name)
            if not pool:
                return
            i = self._rr.get(name, 0)
            self._rr[name] = (i + 1) % len(pool)
            fx = pool[i]
            fx.setVolume(self.volume * SFX_GAIN.get(name, 1.0))
            fx.play()
        elif sys.platform == "win32":
            import winsound
            path = self.paths.get(name)
            if path:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)

    def set_enabled(self, on: bool):
        self.enabled = on

    def set_volume(self, v: float):
        self.volume = max(0.0, min(1.0, v))

    def set_music(self, on: bool, volume: float | None = None):
        self.music_enabled = on
        if volume is not None:
            self.music_volume = max(0.0, min(1.0, volume))
        self._apply_music()

    # ---- soundtrack (your own music files) -----------------------------
    def use_soundtrack(self, player: "MusicPlayer | None"):
        """Play real music files through ``player``; the synthesized loop is the fallback."""
        self.soundtrack = player if player is not None and player.has_tracks() else None
        self._apply_music()

    def set_mood(self, mood: str):
        if getattr(self, "soundtrack", None):
            self.soundtrack.set_mood(mood)

    def next_track(self):
        if getattr(self, "soundtrack", None):
            self.soundtrack.next_track()

    def _apply_music(self):
        st = getattr(self, "soundtrack", None)
        if st is not None:
            if self._music is not None and self._music.isPlaying():
                self._music.stop()
            st.set_volume(self.music_volume)
            st.set_enabled(self.music_enabled)
            return
        if self._music is None:
            return
        self._music.setVolume(self.music_volume)
        if self.music_enabled and not self._music.isPlaying():
            self._music.play()
        elif not self.music_enabled and self._music.isPlaying():
            self._music.stop()


# ================================================================ soundtrack
MUSIC_EXTS = (".mp3", ".ogg", ".wav", ".m4a", ".flac", ".aac", ".wma")
MOODS = ("menu", "battle", "learn", "victory", "defeat")
# A track can belong to several moods. Anything that matches nothing is battle music.
MOOD_KEYWORDS = {
    "menu": ("eternal", "destin", "send off", "menu", "main theme"),
    "learn": ("hope", "eternal", "calm", "peace", "learn"),
    "victory": ("victory", "triumph", "win"),
    "defeat": ("send off", "defeat", "sad", "lament"),
    "battle": ("epic music", "motivational", "fight", "go", "ripper", "hisoka", "megumi", "battle", "war"),
}


def music_dirs(extra: str | None = None) -> list[str]:
    """Where to look for music: chosen folder, next to the .exe, and the project folder."""
    dirs = []
    if extra:
        dirs.append(extra)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        dirs += [os.path.join(exe_dir, "music"), os.path.join(os.path.dirname(exe_dir), "music")]
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirs += [os.path.join(project, "music"), os.path.join(project, "dist", "music")]
    return [d for d in dict.fromkeys(dirs) if os.path.isdir(d)]


class MusicPlayer(QObject):
    """Plays your music files by mood (menu, battle, learn, victory, defeat) with crossfades.

    Put files in a ``music`` folder next to the game. Optional sub-folders named after a mood
    (music/battle, music/menu, ...) decide the mood explicitly; otherwise titles are used.
    """
    track_changed = pyqtSignal(str)

    def __init__(self, folders: list[str], parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import QTimer
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        self._QMediaPlayer = QMediaPlayer
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(lambda *_: QTimer.singleShot(500, self.next_track))
        self.volume = 0.35
        self.enabled = True
        self.mood = "menu"
        self.current = ""
        self.tracks: dict[str, list[str]] = {m: [] for m in MOODS}
        self.all_tracks: list[str] = []
        self._level = 0.0          # fade level 0..1
        self._target = 0.0
        self._pending: str | None = None
        self._fade = QTimer(self)
        self._fade.timeout.connect(self._fade_step)
        self._fade.start(40)
        self.scan(folders)

    def scan(self, folders: list[str]):
        self.tracks = {m: [] for m in MOODS}
        self.all_tracks = []
        for folder in folders:
            for root, _dirs, files in os.walk(folder):
                sub = os.path.basename(root).lower()
                for f in sorted(files):
                    if not f.lower().endswith(MUSIC_EXTS):
                        continue
                    path = os.path.join(root, f)
                    if path in self.all_tracks:
                        continue
                    self.all_tracks.append(path)
                    if sub in MOODS and root != folder:
                        self.tracks[sub].append(path)
                        continue
                    title = os.path.splitext(f)[0].lower()
                    matched = False
                    for mood, words in MOOD_KEYWORDS.items():
                        if mood != "battle" and any(w in title for w in words):
                            self.tracks[mood].append(path)
                            matched = True
                    if not matched or any(w in title for w in MOOD_KEYWORDS["battle"]):
                        self.tracks["battle"].append(path)

    def has_tracks(self) -> bool:
        return bool(self.all_tracks)

    @staticmethod
    def title(path: str) -> str:
        return os.path.splitext(os.path.basename(path))[0]

    def _pick(self) -> str | None:
        pool = self.tracks.get(self.mood) or self.tracks["battle"] or self.all_tracks
        if not pool:
            return None
        choices = [t for t in pool if t != self.current] or pool
        return random.choice(choices)

    def set_mood(self, mood: str):
        if mood == self.mood and self.current and self._pending is None and \
                self.player.playbackState() == self._QMediaPlayer.PlaybackState.PlayingState:
            if self.current in (self.tracks.get(mood) or []):
                return
        self.mood = mood
        self.next_track()

    def next_track(self):
        nxt = self._pick()
        if nxt is None:
            return
        self._pending = nxt
        self._target = 0.0          # fade out, then switch in _fade_step

    def set_volume(self, v: float):
        self.volume = max(0.0, min(1.0, v))
        self._apply_volume()

    def set_enabled(self, on: bool):
        self.enabled = on
        if not on:
            self.player.pause()
        elif self.current:
            self.player.play()
        else:
            self.next_track()

    def _apply_volume(self):
        level = self._level * self._level  # perceptual-ish curve
        self.output.setVolume(self.volume * level)

    def _fade_step(self):
        if self._level < self._target:
            self._level = min(self._target, self._level + 0.05)
        elif self._level > self._target:
            self._level = max(self._target, self._level - 0.06)
        self._apply_volume()
        if self._pending is not None and (self._level <= 0.001 or not self.current):
            path, self._pending = self._pending, None
            self.current = path
            self.player.setSource(QUrl.fromLocalFile(path))
            if self.enabled:
                self.player.play()
            self._target = 1.0
            self.track_changed.emit(self.title(path))

    def _on_status(self, status):
        if status == self._QMediaPlayer.MediaStatus.EndOfMedia:
            if self.mood in ("victory", "defeat"):
                self.mood = "menu"
            self._level = 0.0
            self.next_track()
