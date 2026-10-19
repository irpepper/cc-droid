#!/usr/bin/env python3
"""
Synthesize an original set of droid-style notification sounds for Claude Code hooks.

Every sound is "spoken" by the same little droid voice: short FM-synth syllables
with pitch contours, vibrato and warbles, so the set has one personality. Mood and
gesture carry the meaning, and the categories stay easy to tell apart:

  Category    Droid mood             Signature gesture                  Siblings differ by
  ----------  ---------------------  ---------------------------------  ----------------------------
  Needs you   eager, curious         knocks or chatter ending on a rise hail / soft knock + hm / firm knock + beep-boop
  Finished    content, cheerful      a phrase that falls to rest        full "done-zo" phrase vs two-note nod
  Problems    sad, grumpy, tired     falling, low, growly               "uh-oh" + grumble / one droop / sigh + snore
  Lifecycle   waking up, nodding off long whistle slides                long (session) vs short zip (subagent)

All of it is generated from scratch (oscillators, filtered noise, envelopes), so the
output is yours to commit, share, or tweak.

Requires: numpy, scipy  (pip install numpy scipy)
Usage:    python3 make_sounds.py [output_dir]      # default: ../build/raw
"""
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
rng = np.random.default_rng(7)  # fixed seed -> reproducible output

# Note frequencies (Hz). The happy sounds sit in C major.
N = {
    "C4": 261.63, "E4": 329.63, "G4": 392.00, "A4": 440.00,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46, "G5": 783.99, "A5": 880.00,
    "C6": 1046.50, "D6": 1174.66, "E6": 1318.51, "G6": 1567.98, "C7": 2093.00,
}


# ---------------------------------------------------------------- primitives
def t_axis(dur):
    return np.arange(int(SR * dur)) / SR


def contour(dur, points):
    """Pitch curve through (time_fraction, Hz) points, interpolated in log-frequency
    so slides sound like intonation, not sirens."""
    t = t_axis(dur) / dur
    xs = [p[0] for p in points]
    ys = np.log([p[1] for p in points])
    return np.exp(np.interp(t, xs, ys))


def env(dur, a=0.006, r=0.03):
    n = int(SR * dur)
    e = np.ones(n)
    na, nr = min(n, max(1, int(SR * a))), min(n, max(1, int(SR * r)))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


def decay(dur, rate, attack=0.003):
    t = t_axis(dur)
    e = np.minimum(t / attack, 1.0) * np.exp(-t * rate)
    tail = min(len(e), int(SR * 0.012))
    e[-tail:] *= np.linspace(1, 0, tail)
    return e


def noise(dur):
    return rng.standard_normal(int(SR * dur))


def lowpass(x, cutoff, order=4):
    return sosfilt(butter(order, cutoff, btype="low", fs=SR, output="sos"), x)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def silence(dur):
    return np.zeros(int(SR * dur))


def cat(*parts):
    return np.concatenate(parts)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


def at(offset, x):
    return cat(silence(offset), x)


# ---------------------------------------------------------------- the droid voice
def syl(dur, points, vib=(0, 0), index=0.7, ratio=2.0, a=0.006, r=0.03, gain=1.0):
    """One droid 'syllable': an FM tone following a pitch contour.
    vib=(rate Hz, depth fraction) adds the wobble that makes it sound alive.
    index/ratio set the metallic bite: higher index = brighter, ratio<1 = growly."""
    t = t_axis(dur)
    f = contour(dur, points)
    if vib[0]:
        f = f * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(phase + index * np.sin(ratio * phase))
    return s * env(dur, a, r) * gain


def trill(dur, f_lo, f_hi, rate=22, index=0.6, gain=1.0, fall=None):
    """Rapid flutter between two pitches - the droid's happy warble.
    `fall` optionally lets the whole trill glide to a new centre."""
    t = t_axis(dur)
    w = 0.5 + 0.5 * np.tanh(3 * np.sin(2 * np.pi * rate * t))
    f = f_lo * (f_hi / f_lo) ** w
    if fall:
        f = f * (fall ** (t / dur))
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase + index * np.sin(2 * phase)) * env(dur, 0.008, 0.05) * gain


def growl(dur, f0, f1, gain=1.0):
    """Low grumpy raspberry: sub-octave FM with a heavy index. Problems only."""
    t = t_axis(dur)
    f = contour(dur, [(0, f0), (1, f1)]) * (1 + 0.04 * np.sin(2 * np.pi * 31 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(phase + 2.6 * np.sin(0.5 * phase))
    return lowpass(s, 2200) * env(dur, 0.01, 0.06) * gain


def knock(dur=0.09, f=430):
    """Soft knuckle-on-hull tap (used only by `waiting`). Pitched high enough that
    laptop speakers still reproduce it."""
    t = t_axis(dur)
    body = np.sin(2 * np.pi * np.cumsum(f * (1 - 0.25 * t / dur)) / SR) * np.exp(-t * 45)
    click = bandpass(noise(dur), 900, 3500) * np.exp(-t * 220) * 0.35
    return (body + click) * decay(dur, 2)


# ---------------------------------------------------------------- Needs you
def attention():
    """permission_prompt - EAGER, URGENT. Three quick excited high syllables, then a
    big rising whistle that flutters at the top: 'hey! hey! over here!'"""
    b = [syl(0.06, [(0, N["E6"]), (1, N["G6"])], index=1.0, r=0.02, gain=0.8),
         syl(0.06, [(0, N["D6"]), (1, N["E6"])], index=1.0, r=0.02, gain=0.8),
         syl(0.06, [(0, N["E6"]), (1, N["G6"])], index=1.0, r=0.02, gain=0.8)]
    whistle = syl(0.26, [(0, N["C6"]), (0.55, N["C7"]), (1, N["C7"] * 1.04)], vib=(24, 0.035), index=0.5, r=0.08)
    return cat(b[0], silence(0.025), b[1], silence(0.025), b[2], silence(0.03), whistle)


def waiting():
    """idle_prompt - PATIENT. Two soft knocks, a pause, then a small curious 'hm-mm?'
    that dips and lifts: tapping on the glass, 'hello? still waiting on you.'
    The knock is unique to this sound so it never gets confused with the others."""
    hm = syl(0.13, [(0, N["A4"]), (1, N["G4"])], vib=(6, 0.01), index=0.35, a=0.015, r=0.04, gain=0.7)
    mm = syl(0.3, [(0, N["G4"]), (0.45, N["G4"]), (1, N["D5"])], vib=(7, 0.015), index=0.35, a=0.015, r=0.08, gain=0.8)
    return cat(knock(), silence(0.09), knock() * 0.85, silence(0.22), hm, silence(0.03), mm)


def firm_knock(dur=0.06, f=560):
    """A sharper, brighter knock than waiting's: harder knuckle, more click, quick decay."""
    t = t_axis(dur)
    body = np.sin(2 * np.pi * np.cumsum(f * (1 - 0.2 * t / dur)) / SR) * np.exp(-t * 70)
    click = bandpass(noise(dur), 1500, 6000) * np.exp(-t * 260) * 0.7
    return (body + click) * decay(dur, 1)


def query():
    """agent_needs_input / elicitation - BRISK BUT FRIENDLY. Three rapid, firm knocks,
    then a round, friendly 'beep-boop' whose boop lilts up at the end: 'knock knock,
    over here, need you for a sec.' Waiting's idea, quicker and harder to miss. The
    boop rises rather than falls, so it never sounds like task-complete's nod."""
    beep = syl(0.08, [(0, N["G5"]), (1, N["G5"])], index=0.35, a=0.006, r=0.025)
    boop = syl(0.17, [(0, N["C6"]), (0.55, N["C6"]), (1, N["E6"])], vib=(7, 0.012), index=0.35, a=0.006, r=0.05)
    knocks = cat(firm_knock(), silence(0.045), firm_knock(), silence(0.045), firm_knock())
    return cat(knocks, silence(0.07), beep, silence(0.035), boop)


# ---------------------------------------------------------------- Finished
def done():
    """Stop - CONTENT. 'Done-zo': a falling dee-doo-doo (G-E-C) that comes to rest the
    way a finished sentence does, then a little cheerful blip up top as a smile."""
    return cat(
        syl(0.075, [(0, N["G5"]), (1, N["G5"])], index=0.5, r=0.02),
        silence(0.02),
        syl(0.075, [(0, N["E5"]), (1, N["E5"])], index=0.5, r=0.02),
        silence(0.02),
        syl(0.2, [(0, N["C5"]), (1, N["C5"])], vib=(6, 0.012), index=0.5, r=0.08),
        silence(0.05),
        syl(0.06, [(0, N["C6"]), (1, N["E6"])], index=0.7, r=0.03, gain=0.7),
    )


def task_complete():
    """TaskCompleted - SATISFIED NOD. 'Bip-boop': a tiny falling fourth. Falls to rest
    like done, in two notes instead of a phrase."""
    return cat(syl(0.055, [(0, N["C6"]), (1, N["C6"])], index=0.6, r=0.02),
               silence(0.03),
               syl(0.1, [(0, N["G5"]), (1, N["G5"])], index=0.6, r=0.05))


# ---------------------------------------------------------------- Problems
def ratelimit():
    """StopFailure rate_limit - TIRED. A long drooping sigh, then two slow wobbling
    low hums like a droid snoozing: 'I need a breather, try again in a bit.'"""
    sigh = syl(0.4, [(0, N["G5"]), (0.25, N["A5"]), (1, N["C5"])], vib=(5, 0.02), index=0.4, r=0.12)
    def snore(g):
        return syl(0.24, [(0, N["C4"]), (0.5, N["E4"]), (1, N["C4"])], vib=(4, 0.03), index=1.4, ratio=0.5,
                   a=0.06, r=0.1, gain=g)
    return cat(sigh, silence(0.1), snore(0.7), silence(0.12), snore(0.55))


def error():
    """StopFailure (other) - SAD + GRUMPY. A falling 'uh-oh' with a sour drop, then a
    low grumbling raspberry. The growl is the Problems family signature."""
    uh = syl(0.11, [(0, N["E5"]), (1, N["D5"])], index=0.9, r=0.03)
    oh = syl(0.19, [(0, N["A4"] * 1.06), (1, N["E4"])], vib=(8, 0.02), index=0.9, r=0.05)
    return cat(uh, silence(0.035), oh, growl(0.22, 140, 95, gain=0.85))


def tool_failure():
    """PostToolUseFailure - SMALL OOPS. One short drooping 'bwomp' with a little growl
    underneath. The quietest, quickest problem sound."""
    d = 0.2
    droop = syl(d, [(0, N["C5"]), (1, N["E4"])], index=1.0, r=0.06)
    return droop + growl(d, 160, 110, gain=0.4)


# ---------------------------------------------------------------- Lifecycle
def session_start():
    """SessionStart - WAKING UP. A long low whistle sliding up like a droid powering
    on, then a bright two-syllable 'dee-dee!' hello."""
    rise = syl(0.42, [(0, 140), (0.7, N["C5"]), (1, N["G5"])], vib=(5, 0.01), index=0.3, a=0.08, r=0.04)
    hello = cat(syl(0.07, [(0, N["G5"]), (1, N["C6"])], index=0.7),
                silence(0.03),
                syl(0.12, [(0, N["C6"]), (1, N["E6"])], index=0.7, r=0.05))
    return cat(rise * 0.75, silence(0.04), hello)


def session_end():
    """SessionEnd - NODDING OFF. A soft 'doo-dee' goodbye, then the whistle slides all
    the way down and out. The mirror of session-start."""
    bye = cat(syl(0.09, [(0, N["E6"]), (1, N["C6"])], index=0.7),
              silence(0.03),
              syl(0.11, [(0, N["G5"]), (1, N["E5"])], index=0.7, r=0.05))
    fall = syl(0.42, [(0, N["G5"]), (0.3, N["C5"]), (1, 110)], vib=(5, 0.01), index=0.3, a=0.01, r=0.15)
    return cat(bye, silence(0.04), fall * 0.75)


def subagent_start():
    """SubagentStart - OFF YOU GO. A quick 'zip!' up and a tiny high 'bip':
    a little helper droid sent on an errand."""
    return cat(syl(0.1, [(0, 420), (1, 2300)], index=0.4, r=0.015),
               silence(0.02),
               syl(0.05, [(0, N["C7"]), (1, N["C7"])], index=0.8, r=0.03, gain=0.6))


def subagent_stop():
    """SubagentStop - BACK AGAIN. The launch mirrored: a quick 'zoop' down landing on
    a soft low 'boop': the helper is home."""
    return cat(syl(0.1, [(0, 2300), (1, 480)], index=0.4, r=0.015),
               silence(0.015),
               syl(0.09, [(0, N["C5"]), (1, N["C5"] * 0.92)], index=0.5, r=0.05, gain=0.8))


def compact():
    """PreCompact - SQUISH. A wobbly 'wub-wub-wub' whose wobble narrows to nothing,
    ending in a tiny pop: memory squeezed down small."""
    d = 0.42
    t = t_axis(d)
    depth = 0.25 * (1 - t / d) ** 1.5
    f = N["G5"] * (1 + depth * np.sin(2 * np.pi * 9 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    wub = np.sin(phase + 0.6 * np.sin(2 * phase)) * env(d, 0.01, 0.02)
    pop = syl(0.05, [(0, N["C6"]), (1, N["G5"])], index=0.6, r=0.03, gain=0.7)
    return cat(wub, silence(0.02), pop)


SOUNDS = {
    "attention": attention,
    "waiting": waiting,
    "query": query,
    "done": done,
    "task-complete": task_complete,
    "ratelimit": ratelimit,
    "error": error,
    "tool-failure": tool_failure,
    "session-start": session_start,
    "session-end": session_end,
    "subagent-start": subagent_start,
    "subagent-stop": subagent_stop,
    "compact": compact,
}

# Loudness matching happens in ../normalize.sh, driven by ../offsets.txt.


def to_wav(name, x, out_dir):
    x = x - np.mean(x)
    fade = int(SR * 0.004)  # click guard at both ends
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.7
    pcm = np.int16(np.clip(x, -1, 1) * 32767)
    wavfile.write(os.path.join(out_dir, f"{name}.raw.wav"), SR, pcm)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "build", "raw")
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in SOUNDS.items():
        to_wav(name, fn(), out_dir)
        print(f"  synthesized {name}")


if __name__ == "__main__":
    main()
