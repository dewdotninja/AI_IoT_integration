"""
features.py  --  Lecture 11
01211271 Industrial AI and IoT

All twelve features, on the device, in MicroPython.  Lab 8 computed the seven
time-domain ones; this file adds the five frequency-domain ones, which means a
real 256-point FFT written in plain Python.

Nothing here imports NumPy, because nothing here can.

Memory
------
Four arrays of WIN floats and two of WIN/2 live for the lifetime of the module:

    _han   WIN      Hanning window            1 KB
    _re    WIN      FFT real part             1 KB
    _im    WIN      FFT imaginary part        1 KB
    _cos   WIN/2    twiddle factors, cos      0.5 KB
    _sin   WIN/2    twiddle factors, sin      0.5 KB
    _rev   WIN      bit-reversal permutation  0.5 KB (uint16)

About 4.5 KB, allocated once at import.  Allocating inside the inner loop
instead would fragment the heap and eventually fail at three in the morning.
"""
import math
from array import array

WIN = 256
FS = 2000.0
DF = FS / WIN                     # 7.8125 Hz per bin

BANDS = ((20.0, 42.0),            # e_1x    shaft rate
         (48.0, 78.0),            # e_2x
         (90.0, 132.0),           # e_bpfo  outer-race defect order
         (400.0, 900.0))          # e_hi    housing resonance

# --------------------------------------------------------------- work buffers
_han = array('f', [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (WIN - 1))
                   for i in range(WIN)])
_re = array('f', [0.0] * WIN)
_im = array('f', [0.0] * WIN)
_cos = array('f', [math.cos(-2.0 * math.pi * k / WIN) for k in range(WIN // 2)])
_sin = array('f', [math.sin(-2.0 * math.pi * k / WIN) for k in range(WIN // 2)])


def _bitrev_table(n):
    bits = 0
    while (1 << bits) < n:
        bits += 1
    t = array('H', [0] * n)
    for i in range(n):
        r = 0
        x = i
        for _ in range(bits):
            r = (r << 1) | (x & 1)
            x >>= 1
        t[i] = r
    return t


_rev = _bitrev_table(WIN)

# band edges as bin indices, computed once
_BAND_BINS = tuple((max(1, int(lo / DF + 0.9999)), int(hi / DF))
                  for lo, hi in BANDS)


def time_features(buf):
    """Seven time-domain features.  Two passes, no allocation.

    Returns (mean, rms, std, ptp, crest, kurt, zcr).
    """
    n = len(buf)
    total = 0.0
    lo = hi = buf[0]
    for v in buf:
        total += v
        if v < lo:
            lo = v
        if v > hi:
            hi = v
    mean = total / n
    ptp = hi - lo

    s2 = 0.0
    s4 = 0.0
    peak = 0.0
    zc = 0
    prev = buf[0] - mean
    for v in buf:
        d = v - mean
        dd = d * d
        s2 += dd
        s4 += dd * dd
        if dd > peak:
            peak = dd
        if (d < 0.0) != (prev < 0.0):
            zc += 1
        prev = d

    rms = (s2 / n) ** 0.5
    r2 = rms * rms
    crest = (peak ** 0.5) / rms if rms > 0.0 else 0.0
    kurt = (s4 / n) / (r2 * r2) if rms > 0.0 else 0.0
    return (mean, rms, rms, ptp, crest, kurt, zc / (n - 1))


def _fft(buf, mean):
    """In-place radix-2 decimation-in-time FFT of (buf - mean) * hanning.

    Writes into the module-level _re and _im.  n must be a power of two.
    """
    n = WIN
    rev = _rev
    re = _re
    im = _im
    han = _han
    for i in range(n):                       # load, de-mean, window, bit-reverse
        re[rev[i]] = (buf[i] - mean) * han[i]
        im[i] = 0.0

    size = 2
    while size <= n:
        half = size >> 1
        step = n // size
        for start in range(0, n, size):
            k = 0
            for j in range(start, start + half):
                wr = _cos[k]
                wi = _sin[k]
                j2 = j + half
                tr = wr * re[j2] - wi * im[j2]
                ti = wr * im[j2] + wi * re[j2]
                re[j2] = re[j] - tr
                im[j2] = im[j] - ti
                re[j] += tr
                im[j] += ti
                k += step
        size <<= 1
    return re, im


def freq_features(buf, mean):
    """Dominant frequency plus four normalised band energies.

    Returns (dom_freq, e_1x, e_2x, e_bpfo, e_hi).
    """
    re, im = _fft(buf, mean)

    half = WIN // 2
    total = 0.0
    best = 0.0
    best_k = 0
    # bin 0 is the DC term; we removed the mean, so it carries no information
    for k in range(1, half + 1):
        p = re[k] * re[k] + im[k] * im[k]
        total += p
        if p > best:
            best = p
            best_k = k

    if total <= 0.0:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    out = [best_k * DF]
    for k0, k1 in _BAND_BINS:
        s = 0.0
        for k in range(k0, k1 + 1):
            s += re[k] * re[k] + im[k] * im[k]
        out.append(s / total)
    return tuple(out)


def all_features(buf):
    """The twelve features, in the order the model expects."""
    t = time_features(buf)
    f = freq_features(buf, t[0])
    return (t[0], t[1], t[2], t[3], t[4], t[5], t[6],
            f[0], f[1], f[2], f[3], f[4])
