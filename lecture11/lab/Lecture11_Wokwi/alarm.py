"""
alarm.py  --  Lecture 11
01211271 Industrial AI and IoT

The Lecture 10 anomaly alarm, on the device.

Generated from lecture10_alarm.json.  The score is the largest absolute
z-score across the twelve features, measured against a baseline fitted on
healthy machines only.  It needs no fault labels and no model -- just
25 numbers.

The reciprocal of each standard deviation is stored instead of the standard
deviation itself, because a multiply is cheaper than a divide on a device with
no hardware divider worth the name.

THRESHOLD is the 99% quantile of healthy scores, so about
1 % of healthy windows will exceed it.  PERSIST_M of the last
PERSIST_N windows must exceed it before the device raises anything.

Fitted on 8052 healthy windows.
REVIEW AFTER 12 MONTHS -- the baseline drifts.
"""
MEAN = (
        -0.004580056, 0.2805834, 0.2805834, 1.320697,
        2.534602, 2.337895, 0.1935108, 31.24321,
        0.6415923, 0.06894806, 0.013422, 0.1450005,
)

INV_SD = (
        27.60075, 18.80094, 18.80094, 3.335559,
        3.353133, 3.644204, 13.61313, 4.343119,
        8.337267, 48.78102, 110.9179, 12.08148,
)

THRESHOLD = 4.037817
PERSIST_M = 3
PERSIST_N = 5

_hist = [0] * PERSIST_N
_i = 0


FEATURES = ('mean', 'rms', 'std', 'ptp', 'crest', 'kurt', 'zcr', 'dom_freq', 'e_1x', 'e_2x', 'e_bpfo', 'e_hi')


def score(x):
    """Largest absolute z-score over the twelve features."""
    worst = 0.0
    for j in range(len(MEAN)):
        z = (x[j] - MEAN[j]) * INV_SD[j]
        if z < 0.0:
            z = -z
        if z > worst:
            worst = z
    return worst


def worst_feature(x):
    """(score, name) -- WHICH feature fired, which is what an engineer needs.

    The magnitude is not a severity scale.  A feature whose healthy standard
    deviation is very small -- dom_freq is 0.23 Hz here, because a healthy
    machine's spectrum peaks in the same bin every time -- produces enormous
    z-scores for a modest physical change.  Report the name, treat the number
    as "over threshold" and nothing more.
    """
    worst = 0.0
    at = 0
    for j in range(len(MEAN)):
        z = (x[j] - MEAN[j]) * INV_SD[j]
        if z < 0.0:
            z = -z
        if z > worst:
            worst = z
            at = j
    return worst, FEATURES[at]


def update(x):
    """Feed one window.  Returns (raised, score) after the persistence rule."""
    global _i
    s = score(x)
    _hist[_i] = 1 if s > THRESHOLD else 0
    _i = (_i + 1) % PERSIST_N
    return (sum(_hist) >= PERSIST_M), s


def reset():
    global _i
    for k in range(PERSIST_N):
        _hist[k] = 0
    _i = 0
