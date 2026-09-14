"""
sensors.py  --  Lecture 13
01211271 Industrial AI and IoT

A faulty sensor can fool a good model.

Every model in this course was trained on windows from a working accelerometer,
so every model in this course assumes the accelerometer is working.  Nothing in
Lectures 8 to 12 checks that assumption, and the models do not degrade
gracefully when it fails -- they answer confidently and wrongly, which is worse
than answering badly.

Four faults, all of them ordinary:

    stuck        the I2C read returns the last value forever
    clipping     the range is set to +-2 g and the machine is louder than that
    loose mount  the sensor rattles on its own bolt, not the machine's
    gain drift   the adhesive has aged, or somebody set the wrong full scale

and one cheap gate that runs on the raw window, before any feature, in about
the time one feature takes.
"""
import numpy as np

ADC_FULL_SCALE = 2.0          # g, the range the sensor is configured for
LSB = ADC_FULL_SCALE / 32768.0


# ------------------------------------------------------------- the faults
def fault_stuck(x, rng, at=0.0):
    """The bus read stops updating.  A dead channel is not a quiet channel: it
    is the last value, forever, plus the noise of the converter itself."""
    y = x.copy()
    i = int(at * len(x))
    y[i:] = x[i] + rng.normal(0, LSB, len(x) - i)
    return y


def fault_clip(x, rng, level=0.55):
    """The range is set too low.  The signal is intact in the middle and gone
    at the edges -- which is where the bearing impulses live."""
    return np.clip(x, -level, level)


def fault_loose(x, rng, amp=1.40, f_mount=850.0, rate=90.0, fs=2000.0):
    """The sensor rattles on its own mounting bolt.

    This is the nastiest of the four because it looks like exactly the thing we
    trained the model to find: a train of sharp, decaying impulses.
    """
    n = len(x)
    t = np.arange(n) / fs
    y = x.copy()
    period = fs / rate
    k = 0
    while True:
        i = int(k * period * (1.0 + rng.normal(0, 0.05)))
        if i >= n:
            break
        tail = np.arange(n - i) / fs
        y[i:] += (amp * rng.uniform(0.6, 1.4) * np.exp(-tail / 0.0014)
                  * np.sin(2 * np.pi * f_mount * tail))
        k += 1
    return y


def fault_gain(x, rng, g=0.25):
    """The bonding has aged, or somebody wrote 16 g where 2 g was meant.
    Everything scales.  The normalised band energies do not move at all."""
    return g * x


FAULTS = {
    "stuck channel": fault_stuck,
    "clipped range": fault_clip,
    "loose sensor mount": fault_loose,
    "gain drift ×0.25": fault_gain,
}


# --------------------------------------------------------------- the gate
# Every limit here is a property of the INSTALLATION, not of the machine, and
# every one is checkable in one pass over the raw window.
SAT_FRAC = 0.010              # more than 1 % of samples pinned at one value
FLAT_TOL = 3.0                # "pinned" means within 3 LSB of the extreme --
                              # a natural signal never repeats its peak, a
                              # clipped one repeats it dozens of times
DEAD_PTP = 0.02               # g: a running machine is never this quiet
MAX_DC = 0.50                 # g: the accelerometer's bias is specified
RMS_RANGE = (0.12, 4.0)       # g: from THIS installation's own history,
                              # not from the datasheet -- same discipline as
                              # the alarm baseline
MIN_E1X = 0.02                # a running rotor always has a shaft line


def validity(buf, fs=2000.0, full_scale=ADC_FULL_SCALE, e_1x=None):
    """Is this window plausibly from a working accelerometer on this machine?

    Returns (ok, reason).  Four of the five checks are two comparisons per
    sample; the fifth reuses a feature the device computes anyway.

    The order matters: report the cheapest, most specific failure first, because
    the reason is what a technician acts on.
    """
    x = np.asarray(buf, dtype=float)
    hi, lo = float(x.max()), float(x.min())
    span = hi - lo
    if span < DEAD_PTP:
        return False, "dead channel"
    # Clipping is not detected against the CONFIGURED range -- a signal can be
    # clipped by an amplifier, a cable or a badly chosen full scale, and all of
    # them look the same: a pile of samples sitting on one value.  A natural
    # signal never repeats its own peak; a clipped one repeats it dozens of
    # times.
    tol = FLAT_TOL * LSB
    pinned = max(np.mean(x >= hi - tol), np.mean(x <= lo + tol))
    if pinned > SAT_FRAC:
        return False, "clipped"
    mean = float(x.mean())
    if abs(mean) > MAX_DC:
        return False, "dc offset"
    rms = float(np.sqrt(np.mean((x - mean) ** 2)))
    if not (RMS_RANGE[0] <= rms <= RMS_RANGE[1]):
        return False, "level implausible"
    if e_1x is not None and e_1x < MIN_E1X:
        return False, "no shaft line"
    return True, "ok"


def validity_table(W, e1x=None, **kw):
    """Apply the gate to every row of a window matrix."""
    out = []
    for i, w in enumerate(W):
        out.append(validity(w, e_1x=None if e1x is None else e1x[i], **kw))
    ok = np.array([o[0] for o in out])
    why = np.array([o[1] for o in out], dtype=object)
    return ok, why
