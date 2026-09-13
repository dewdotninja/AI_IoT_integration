"""
model.py  --  Lecture 11
01211271 Industrial AI and IoT

The Lecture 9 classifier, on the device.

Generated from lecture9_model.json.  The standardiser has been FOLDED INTO the
coefficients, so this file holds 39 numbers instead of
63 and does no subtraction or division at inference
time:

    w . (x - mu)/sigma + b   ==   (w/sigma) . x  +  (b - w . mu/sigma)

Inference is 36 multiply-accumulates and an argmax over 3.
"""
CLASSES = ('bearing', 'imbalance', 'normal')

# one row per class, one column per feature, in FEATURE_NAMES order
COEF = (
    (
        3.635836, -0.2896101, -0.2896101, 0.1041714,
        0.7507597, 0.3303283, -2.457207, -0.002660429,
        -0.6664433, -3.94146, -15.8365, 3.429931,
    ),
    (
        0.134412, 1.955565, 1.955565, 0.4972783,
        -0.2524321, -0.1308921, -1.382013, -3.325341e-05,
        1.335247, 3.491781, -1.134162, -0.9265764,
    ),
    (
        -3.385322, -1.995164, -1.995164, -0.4989754,
        -0.4365172, -0.1677007, 2.363967, 0.01950218,
        -0.1572236, 2.189229, 13.89641, -2.860629,
    ),
)

INTERCEPT = (
    -2.231817, -2.636284, 2.922453,
)


def scores(x):
    """Decision value for each class.  x is the 12 raw features."""
    out = []
    for c in range(len(COEF)):
        w = COEF[c]
        s = INTERCEPT[c]
        for j in range(len(w)):
            s += w[j] * x[j]
        out.append(s)
    return out


def predict(x):
    """(label, margin).  margin is how far ahead the winner is."""
    s = scores(x)
    best = 0
    for i in range(1, len(s)):
        if s[i] > s[best]:
            best = i
    second = None
    for i in range(len(s)):
        if i != best and (second is None or s[i] > second):
            second = s[i]
    return CLASSES[best], s[best] - second
