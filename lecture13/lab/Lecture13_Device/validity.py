"""
validity.py  --  Lecture 13, Lab 13
01211271 Industrial AI and IoT

Is this window plausibly from a working accelerometer on this machine?

Five comparisons, one pass over the buffer, no allocation.  It runs BEFORE
features.py, and if it says no the device computes nothing, publishes a
sensor-fault event and holds the actuator where it is.

Every limit below is a property of THIS INSTALLATION and must come from its own
history -- the same discipline as the Lecture 10 alarm baseline.  Copying these
numbers onto a different rig is the mistake the file exists to prevent.
"""
WIN = 256
FULL_SCALE = 2.0
LSB = FULL_SCALE / 32768.0

DEAD_PTP = 0.02          # g   a running machine is never this quiet
FLAT_TOL = 3.0 * LSB     # g   "pinned" means within 3 LSB of the extreme
SAT_FRAC = 0.010         #     more than 1 % of samples pinned = clipped
MAX_DC = 0.50            # g   the accelerometer's bias is specified
RMS_LO = 0.12            # g   from this installation's own history
RMS_HI = 4.00            # g
MIN_E1X = 0.02           #     a running rotor always has a shaft line


def validity(buf, e_1x=None):
    """(ok, reason).  Never allocates, never raises."""
    n = len(buf)
    lo = hi = buf[0]
    total = 0.0
    for v in buf:
        total += v
        if v < lo:
            lo = v
        if v > hi:
            hi = v
    span = hi - lo
    if span < DEAD_PTP:
        return False, "dead channel"

    n_hi = 0
    n_lo = 0
    s2 = 0.0
    mean = total / n
    for v in buf:
        if v >= hi - FLAT_TOL:
            n_hi += 1
        if v <= lo + FLAT_TOL:
            n_lo += 1
        d = v - mean
        s2 += d * d
    pinned = (n_hi if n_hi > n_lo else n_lo) / n
    if pinned > SAT_FRAC:
        return False, "clipped"

    if mean > MAX_DC or mean < -MAX_DC:
        return False, "dc offset"
    rms = (s2 / n) ** 0.5
    if rms < RMS_LO or rms > RMS_HI:
        return False, "level implausible"
    if e_1x is not None and e_1x < MIN_E1X:
        return False, "no shaft line"
    return True, "ok"
