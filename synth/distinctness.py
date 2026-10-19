#!/usr/bin/env python3
"""
Rough, objective check that a sound set is distinguishable.

For every pair of clips it compares log-mel spectrograms on a shared time grid
(so length, rhythm, pitch and timbre all count) and reports a similarity from
0 (nothing in common) to 1 (identical). Lower is better. It's a proxy for what
your ear does, not a replacement, but it reliably flags near-duplicates.

Usage: python3 distinctness.py DIR [DIR2]   # DIR2 to compare two versions
"""
import glob
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

SR, FRAME, MAX_S, BANDS = 44100, 0.02, 1.2, 40


def mel_filterbank(n_fft, sr, bands, fmin=80, fmax=9000):
    def hz2mel(f): return 2595 * np.log10(1 + f / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(fmin), hz2mel(fmax), bands + 2))
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((bands, n_fft // 2 + 1))
    for i in range(bands):
        l, c, r = bins[i], bins[i + 1], bins[i + 2]
        fb[i, l:c] = np.linspace(0, 1, max(c - l, 1), endpoint=False)
        fb[i, c:r] = np.linspace(1, 0, max(r - c, 1), endpoint=False)
    return fb


HOP = int(SR * FRAME)
NFFT = 2048
FB = mel_filterbank(NFFT, SR, BANDS)


def features(path):
    sr, x = wavfile.read(path)
    x = x.astype(float)
    if x.ndim > 1:
        x = x.mean(axis=1)
    x /= np.max(np.abs(x)) + 1e-9
    n = int(SR * MAX_S)
    x = np.pad(x[:n], (0, max(0, n - len(x))))
    _, _, Z = stft(x, fs=SR, nperseg=NFFT, noverlap=NFFT - HOP, boundary=None)
    S = 20 * np.log10(FB @ np.abs(Z) + 1e-6)
    S = np.clip(S - S.max(), -70, 0) + 70  # 0..70 dB above floor
    return S


def sim(a, b):
    a, b = a.ravel(), b.ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def report(d):
    files = sorted(glob.glob(os.path.join(d, "*.wav")))
    names = [os.path.basename(f).replace(".raw.wav", "").replace(".wav", "") for f in files]
    F = [features(f) for f in files]
    k = len(F)
    M = np.array([[sim(F[i], F[j]) for j in range(k)] for i in range(k)])
    pairs = sorted(((M[i, j], names[i], names[j]) for i in range(k) for j in range(i + 1, k)), reverse=True)
    off = M[~np.eye(k, dtype=bool)]
    return names, M, pairs, off


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print(__doc__)
        sys.exit(1)
    for d in dirs:
        names, M, pairs, off = report(d)
        print(f"\n== {d}")
        print(f"mean pairwise similarity {off.mean():.3f}   worst pair {pairs[0][0]:.3f}")
        print("closest pairs:")
        for s, a, b in pairs[:6]:
            print(f"  {s:.3f}  {a} ~ {b}")


if __name__ == "__main__":
    main()
