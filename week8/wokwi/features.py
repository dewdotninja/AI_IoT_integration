"""
features.py  --  Week 8, Lab 8
01211271 Industrial AI and IoT

Time-domain features for one window of accelerometer samples, in plain
MicroPython.  No NumPy, no SciPy -- this is what actually fits on an ESP32.

The five frequency-domain features stay on the laptop this week.  Week 11
brings them across once you have seen what an FFT costs on this device.
"""


def time_features(buf):
    """Seven time-domain features of one window.

    buf is a list of floats in g.  Returns
    (mean, rms, std, ptp, crest, kurt, zcr).

    Everything is computed in ONE pass over the samples after the DC
    component is removed, because a second pass costs another len(buf)
    iterations of interpreted Python.
    """
    n = len(buf)

    # pass 1: the window mean, the DC component we must remove
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

    # pass 2: everything else, on the AC part only
    s2 = 0.0          # sum of squares
    s4 = 0.0          # sum of fourth powers
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
    zcr = zc / (n - 1)

    # std equals rms once the DC component is gone
    return (mean, rms, rms, ptp, crest, kurt, zcr)


def goertzel(buf, k, n):
    """STRETCH TASK: power in FFT bin k of an n-sample window.

    The Goertzel algorithm gets one bin with two state variables and a single
    loop, instead of the 2048 butterflies a 256-point FFT would cost.  Bin k
    sits at frequency k * fs / n.

    Use it to build e_1x (bins 3, 4, 5 at fs = 2000 Hz, n = 256) without ever
    computing a full spectrum.  Note that a rectangular window is assumed
    here, so the value will not match the Hanning-windowed notebook exactly.
    """
    import math
    w = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(w)
    s1 = 0.0
    s2 = 0.0
    mean = sum(buf) / len(buf)
    for v in buf:
        s0 = (v - mean) + coeff * s1 - s2
        s2 = s1
        s1 = s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2
