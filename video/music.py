"""An original ambient bed for the demo, synthesized from scratch (no samples, no licences):
a slow pad on a four-chord loop, soft shimmer notes, a riser into the logo and a low hit as
it lands, all quiet enough to sit under the voice. Writes music.wav (48 kHz stereo)."""
import sys
import wave

import numpy as np

SR = 48_000


def note(n):  # MIDI note -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def pad(total, rng):
    t = np.arange(int(total * SR)) / SR
    out = np.zeros((len(t), 2))
    chords = [[45, 57, 60, 64, 71], [41, 53, 57, 60, 64], [48, 55, 59, 64, 67], [43, 55, 59, 62, 66]]  # Am9 Fmaj7 Cmaj7 G
    bar = 8.0
    for i in range(int(total / bar) + 2):
        c = chords[i % 4]
        s, e = i * bar - 1.5, (i + 1) * bar + 1.5  # overlap for smooth crossfades
        a, b = max(0, int(s * SR)), min(len(t), int(e * SR))
        if a >= b:
            continue
        tt = t[a:b] - s
        env = np.clip(tt / 2.5, 0, 1) * np.clip((e - s - tt) / 2.5, 0, 1)
        env = env ** 1.5
        for k, n in enumerate(c):
            f = note(n)
            for det, pan in ((-0.12, 0.25), (0.12, 0.75)):
                ph = rng.uniform(0, 6.28)
                w = np.sin(2 * np.pi * (f + det) * tt + ph) + 0.25 * np.sin(2 * np.pi * 2 * (f + det) * tt + ph)
                amp = 0.05 / (1 + 0.35 * k)
                out[a:b, 0] += w * env * amp * (1 - pan)
                out[a:b, 1] += w * env * amp * pan
    # slow breathing
    out *= (0.8 + 0.2 * np.sin(2 * np.pi * t / 11))[:, None]
    return out


def shimmer(total, rng):
    out = np.zeros((int(total * SR), 2))
    scale = [69, 72, 76, 79, 81, 84, 88]
    tnext = 9.0
    while tnext < total - 4:
        f = note(rng.choice(scale))
        d = 3.0
        n = int(d * SR)
        tt = np.arange(n) / SR
        env = np.exp(-tt * 1.6) * np.clip(tt / 0.01, 0, 1)
        w = np.sin(2 * np.pi * f * tt) * env * 0.035
        pan = rng.uniform(0.2, 0.8)
        a = int(tnext * SR)
        b = min(len(out), a + n)
        out[a:b, 0] += w[: b - a] * (1 - pan)
        out[a:b, 1] += w[: b - a] * pan
        tnext += rng.uniform(1.6, 3.4)
    return out


def riser_and_hit(total, hit_at):
    out = np.zeros((int(total * SR), 2))
    rng = np.random.default_rng(3)
    # riser: filtered noise swelling up to the hit
    d = hit_at
    n = int(d * SR)
    noise = rng.standard_normal(n)
    k = np.linspace(0, 1, n)
    smooth = np.convolve(noise, np.ones(40) / 40, mode="same")  # crude low-pass
    bright = noise - smooth
    w = (smooth * (1 - k) + bright * k) * (k ** 2.2) * 0.09
    out[:n, 0] += w
    out[:n, 1] += w
    # hit: a low sine boom with a soft click
    a = int(hit_at * SR)
    m = int(2.5 * SR)
    tt = np.arange(m) / SR
    f = 55 * np.exp(-tt * 1.5) + 38
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 1.8) * 0.35
    b = min(len(out), a + m)
    out[a:b, 0] += boom[: b - a]
    out[a:b, 1] += boom[: b - a]
    return out


def echo(x, delay=0.38, fb=0.35, mix=0.35):
    d = int(delay * SR)
    y = x.copy()
    for i in range(1, 5):
        y[d * i:] += x[: len(x) - d * i] * (fb ** i) * mix
    return y


def main(total, hit_at, out_path):
    rng = np.random.default_rng(11)
    mix = pad(total, rng) + echo(shimmer(total, rng)) + riser_and_hit(total, hit_at)
    # fade the bed in and out
    n = len(mix)
    fade = np.ones(n)
    fi, fo = int(1.0 * SR), int(4.0 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    mix *= fade[:, None]
    mix /= max(1e-9, np.abs(mix).max()) / 0.8
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3])
