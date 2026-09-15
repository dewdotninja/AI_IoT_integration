"""
spectral.py  --  Lecture 8, Supplement 1

Everything the supplement measures, in one place, so the deck, the notebook and
the project notes cannot quote different numbers.

Nothing here is a new method.  It is the arithmetic underneath
`week8_common.freq_features`, written out one step at a time:

    samples  ->  DFT  ->  bins  ->  a window  ->  band energy

and two ways of getting the bins: a full FFT, and Goertzel one bin at a time.

Both implementations below are written the way the ESP32 would have to do it --
plain loops, no NumPy inside the algorithm -- because the point of the
comparison is the operation count, and NumPy hides it.
"""
import cmath
import math

import numpy as np

import week8_common as w8

FS = w8.FS                 # 2000 Hz
WIN = w8.WIN               # 256 samples = 128 ms
BANDS = w8.BANDS
DF = FS / WIN              # 7.8125 Hz -- the bin width, and it is not a choice


# ===================================================================== bins
def band_bins(bands=BANDS, n=WIN, fs=FS):
    """Which DFT bins each named band actually covers.

    This is the number that decides the whole FFT-vs-Goertzel argument, and
    almost nobody works it out before choosing an algorithm.
    """
    f = np.fft.rfftfreq(n, 1.0 / fs)
    out = {}
    for name, (lo, hi) in bands.items():
        k = np.where((f >= lo) & (f < hi))[0]
        out[name] = {"bins": [int(v) for v in k], "n_bins": int(len(k)),
                     "lo": lo, "hi": hi,
                     "f_lo": float(f[k[0]]), "f_hi": float(f[k[-1]])}
    return out


# ============================================================== the naive DFT
class Counter:
    """Counts real multiplications.  Crude, deliberate, and comparable."""

    def __init__(self):
        self.mul = 0
        self.add = 0

    def cmul(self, k=1):
        self.mul += 4 * k       # (a+bi)(c+di): 4 real multiplies
        self.add += 2 * k

    def rmul(self, k=1):
        self.mul += k

    def radd(self, k=1):
        self.add += k


def dft_naive(x, count=None):
    """The definition, straight off the page.  O(N^2), and unusable on a device.

    X[k] = sum_n x[n] * exp(-2i*pi*k*n/N)
    """
    n = len(x)
    out = []
    for k in range(n // 2 + 1):
        acc = 0.0 + 0.0j
        for i, v in enumerate(x):
            acc += v * cmath.exp(-2j * math.pi * k * i / n)
            if count:
                count.cmul()        # one complex multiply-accumulate per term
        out.append(acc)
    return out


# ===================================================================== the FFT
def fft_radix2(x, count=None, twiddles="recurrence"):
    """Iterative radix-2 decimation in time -- the same routine Lecture 11 runs
    on the ESP32, written here in plain Python so the butterflies are visible.

    Returns the full complex spectrum of length N.
    """
    n = len(x)
    if n & (n - 1):
        raise ValueError("radix-2 needs a power of two")
    re = [float(v) for v in x]
    im = [0.0] * n

    # bit-reversal permutation: no arithmetic, just addressing
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]

    size = 2
    while size <= n:
        ang = -2.0 * math.pi / size
        wr, wi = math.cos(ang), math.sin(ang)
        for start in range(0, n, size):
            cr, ci = 1.0, 0.0
            for k in range(size // 2):
                a, b = start + k, start + k + size // 2
                tr = cr * re[b] - ci * im[b]
                ti = cr * im[b] + ci * re[b]
                if count:
                    count.cmul()            # one twiddle multiply
                    count.radd(4)           # the butterfly's adds
                re[b], im[b] = re[a] - tr, im[a] - ti
                re[a], im[a] = re[a] + tr, im[a] + ti
                cr, ci = cr * wr - ci * wi, cr * wi + ci * wr
                if count and twiddles == "recurrence":
                    count.cmul()            # advancing the twiddle by recurrence
                    # with twiddles="table" these multiplies are precomputed at
                    # import and cost flash instead -- which is what Lecture 11
                    # actually does on the ESP32.
        size <<= 1
    return [complex(r, i) for r, i in zip(re, im)]


def fft_power(x, count=None, twiddles="recurrence"):
    """|X[k]|^2 for k = 0 .. N/2, which is all a band feature needs."""
    X = fft_radix2(x, count, twiddles)
    n = len(x)
    p = []
    for k in range(n // 2 + 1):
        p.append(X[k].real * X[k].real + X[k].imag * X[k].imag)
        if count:
            count.rmul(2)
    return p


# ================================================================== Goertzel
def goertzel_power(x, k, count=None):
    """Power in bin k, with two state variables and one multiply per sample.

    The recurrence is a second-order IIR filter tuned to bin k:

        s[n] = x[n] + 2*cos(2*pi*k/N) * s[n-1] - s[n-2]

    After N samples the last two states hold everything needed:

        |X[k]|^2 = s1^2 + s2^2 - coeff*s1*s2

    No complex arithmetic, no array of twiddle factors, and no output buffer --
    which is why it is the right answer on a device that is short of RAM and
    wants two or three numbers.
    """
    n = len(x)
    coeff = 2.0 * math.cos(2.0 * math.pi * k / n)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + coeff * s1 - s2
        s2, s1 = s1, s0
        if count:
            count.rmul(1)       # ONE real multiply per sample
            count.radd(2)
    if count:
        count.rmul(4)
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def goertzel_bands(x, bins, count=None):
    """Band powers by running Goertzel once per bin in each band."""
    out = {}
    for name, spec in bins.items():
        out[name] = sum(goertzel_power(x, k, count) for k in spec["bins"])
    return out


# ========================================================== the band features
def band_power_from_spectrum(p, bins):
    """Sum |X[k]|^2 over each band's bins.  `p` is indexed by bin number."""
    return {name: sum(p[k] for k in spec["bins"]) for name, spec in bins.items()}


def normalise(bands_abs, p):
    """What Lecture 8 actually stores: each band as a fraction of the window's
    total a.c. power, so the feature does not move when the sensor gain does."""
    total = max(sum(p[1:]), 1e-20)          # bin 0 is DC and carries nothing
    return {k: v / total for k, v in bands_abs.items()}


def prepare(x, window="hann"):
    """What must happen to a raw buffer BEFORE any transform.

    1. remove the mean -- an accelerometer's dc offset is mounting, not vibration
    2. apply a window -- otherwise the ends of the buffer are a step change

    Both apply to Goertzel exactly as they apply to the FFT.  The version in
    Lecture 8's `features.py` skips step 2, which is the single most common
    reason a device's band values do not match the notebook's.
    """
    a = np.asarray(x, dtype=float)
    a = a - a.mean()
    if window == "hann":
        a = a * np.hanning(len(a))
    elif window not in ("rect", None):
        raise ValueError(window)
    return a


# ================================================================== crossover
def crossover(n=WIN):
    """How many bins you can afford with Goertzel before a full FFT is cheaper.

    Measured, not asserted: instrument both and find where the multiply counts
    cross.
    """
    cf = Counter()
    fft_power([0.0] * n, cf)
    fft_mul = cf.mul

    ct = Counter()
    fft_power([0.0] * n, ct, twiddles="table")
    fft_mul_table = ct.mul

    cg = Counter()
    goertzel_power([0.0] * n, 4, cg)
    per_bin = cg.mul

    return {"fft_mul": fft_mul, "fft_mul_table": fft_mul_table,
            "goertzel_mul_per_bin": per_bin,
            "crossover_bins": int(math.ceil(fft_mul / per_bin)),
            "crossover_bins_table": int(math.ceil(fft_mul_table / per_bin))}
