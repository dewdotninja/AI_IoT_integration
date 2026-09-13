"""
features_lite.py  --  Lecture 11, the fallback path
01211271 Industrial AI and IoT

Nine features instead of twelve, and no FFT.

Use this only if `bench.py` tells you the full path does not fit your window
budget.  It replaces the four band energies and the dominant frequency with two
cheap substitutes:

    e_1x_cheap   Goertzel on bins 3, 4, 5 (the 20-42 Hz band), summed and
                 normalised by the window's total AC power.  Three bins, three
                 two-variable recurrences -- no spectrum is ever formed.

    e_hi_cheap   the output power of one band-pass biquad centred on the
                 400-900 Hz housing resonance, normalised the same way.
                 Five multiplies per sample, no buffer.

A model trained on these nine features is NOT the model trained on the twelve.
Retrain, re-validate, and re-export before you deploy this.
"""
import math

WIN = 256
FS = 2000.0

E1X_BINS = (3, 4, 5)                    # 23.4, 31.2, 39.1 Hz

_GO_COEF = tuple(2.0 * math.cos(2.0 * math.pi * k / WIN) for k in E1X_BINS)

# RBJ constant-skirt band-pass, 400-900 Hz at fs = 2000 Hz, normalised by a0
_f0 = math.sqrt(400.0 * 900.0)
_w0 = 2.0 * math.pi * _f0 / FS
_alpha = math.sin(_w0) * math.sinh(math.log(2.0) / 2.0
                                   * (math.log(900.0 / 400.0) / math.log(2.0))
                                   * _w0 / math.sin(_w0))
_a0 = 1.0 + _alpha
B0 = _alpha / _a0
B2 = -_alpha / _a0
A1 = (-2.0 * math.cos(_w0)) / _a0
A2 = (1.0 - _alpha) / _a0


def time_features(buf):
    """Identical to features.time_features -- kept here so this file stands alone."""
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
    return (mean, rms, rms, ptp, crest, kurt, zc / (n - 1)), s2


def cheap_freq(buf, mean, s2):
    """(e_1x_cheap, e_hi_cheap) without ever forming a spectrum."""
    if s2 <= 0.0:
        return 0.0, 0.0

    # --- Goertzel, three bins at once
    p = 0.0
    for c in _GO_COEF:
        s1 = 0.0
        s2g = 0.0
        for v in buf:
            s0 = (v - mean) + c * s1 - s2g
            s2g = s1
            s1 = s0
        p += s1 * s1 + s2g * s2g - c * s1 * s2g

    # --- one band-pass biquad, direct form I
    x1 = 0.0
    x2 = 0.0
    y1 = 0.0
    y2 = 0.0
    acc = 0.0
    for v in buf:
        x0 = v - mean
        y0 = B0 * x0 + B2 * x2 - A1 * y1 - A2 * y2
        acc += y0 * y0
        x2 = x1
        x1 = x0
        y2 = y1
        y1 = y0

    return p / s2, acc / s2


def all_features(buf):
    """The nine lite features, in the order the lite model expects."""
    t, s2 = time_features(buf)
    e1, ehi = cheap_freq(buf, t[0], s2)
    return (t[0], t[1], t[2], t[3], t[4], t[5], t[6], e1, ehi)
