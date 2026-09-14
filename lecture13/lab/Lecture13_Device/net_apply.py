"""
net_apply.py  --  Lecture 13, Lab 13
01211271 Industrial AI and IoT

The downlink, on the ESP32.

Subscribe to @private/model, and let nothing through that could stop this
device protecting its machine.  The order is the whole design:

    validate -> stage -> verify -> commit -> ack

and every one of the five is allowed to refuse.  Refusing is not a failure
mode: the device keeps running the specification it already had, says why on
@msg/ack, and carries on deciding.

What this file must never do
----------------------------
* raise out of the MQTT callback.  A device that crashes on a bad message can
  be switched off by anyone who can publish to its topic.
* block the control loop.  `pending` is set in the callback; the work happens
  in the main loop, between windows.
* commit anything it has not run first.  See `verify()`.
"""
import gc
import json

import alarm
import model

TOPIC_MODEL = "@private/model"
TOPIC_ACK = "@msg/ack"

SCHEMA_VERSION = 1
N_FEATURES = 12
N_CLASSES = 3
THR_LO, THR_HI = 2.0, 12.0
MIN_SD = 1e-6
MAX_AGE_S = 30 * 86400
MAX_SKEW_S = 3600

FEATURES = ("mean", "rms", "std", "ptp", "crest", "kurt", "zcr",
            "dom_freq", "e_1x", "e_2x", "e_bpfo", "e_hi")

# the shadow-test buffers: what the device kept so it can try an update out
KEEP_QUIET = 64          # windows from a stretch nothing happened in
KEEP_ALARM = 64          # windows that made THIS device raise, last time
FA_MAX = 0.25            # a candidate may not raise on more than this
RECALL_MIN = 0.30        # ...and must still raise on this many retained alarms

_quiet = []
_alarmed = []
_pending = None
_ver = {"alarm": 1, "classifier": 1}
_last_good = {"alarm": None, "classifier": None}


# --------------------------------------------------------------- the buffers
def remember(x, raised):
    """Call once per window from the main loop.  Two bounded ring buffers."""
    if raised:
        if len(_alarmed) >= KEEP_ALARM:
            _alarmed.pop(0)
        _alarmed.append(tuple(x))
    else:
        if len(_quiet) >= KEEP_QUIET:
            _quiet.pop(0)
        _quiet.append(tuple(x))


# ------------------------------------------------------------- the validator
def _finite(a):
    for v in a:
        if not isinstance(v, (int, float)):
            return False
        if v != v or v in (float("inf"), float("-inf")):
            return False
    return True


def validate(msg, now):
    """Returns (payload, None) or (None, reason).  Never raises."""
    try:
        if not isinstance(msg, dict):
            return None, "not an object"
        for k in ("v", "kind", "ver", "t", "sum", "payload"):
            if k not in msg:
                return None, "missing " + k
        if msg["v"] != SCHEMA_VERSION:
            return None, "schema v%s" % msg["v"]
        kind = msg["kind"]
        if kind not in ("alarm", "classifier"):
            return None, "unknown kind"
        if checksum(msg["payload"]) != msg["sum"]:
            return None, "checksum mismatch"
        if not isinstance(msg["ver"], int) or msg["ver"] <= _ver[kind]:
            return None, "not newer than v%d" % _ver[kind]
        if msg["t"] > now + MAX_SKEW_S:
            return None, "issued in the future"
        if now - msg["t"] > msg.get("ttl", MAX_AGE_S):
            return None, "expired"

        p = msg["payload"]
        if kind == "alarm":
            mu = p.get("scaler_mean")
            sd = p.get("scaler_scale")
            if mu is None or sd is None:
                return None, "no baseline"
            if len(mu) != N_FEATURES or len(sd) != N_FEATURES:
                return None, "wrong feature count"
            if not (_finite(mu) and _finite(sd)):
                return None, "non-finite baseline"
            for v in sd:
                if v < MIN_SD:
                    return None, "zero standard deviation"
            thr = p.get("threshold")
            if not isinstance(thr, (int, float)) or thr != thr:
                return None, "bad threshold"
            if thr < THR_LO or thr > THR_HI:
                return None, "threshold out of range"
            m = p["persistence"]["m"]
            n = p["persistence"]["n"]
            if not (1 <= m <= n <= 64):
                return None, "persistence not sane"
            if tuple(p.get("feature_names", ())) != FEATURES:
                return None, "feature order differs"
        else:
            W = p.get("coef")
            b = p.get("intercept")
            if W is None or b is None:
                return None, "no coefficients"
            if len(W) != N_CLASSES or len(b) != N_CLASSES:
                return None, "wrong class count"
            allzero = True
            for row in W:
                if len(row) != N_FEATURES:
                    return None, "wrong row length"
                if not _finite(row):
                    return None, "non-finite coefficients"
                for v in row:
                    if v != 0.0:
                        allzero = False
            if allzero:
                return None, "all coefficients zero"
        return p, None
    except Exception as e:
        return None, "malformed: " + type(e).__name__


def checksum(payload):
    """sha256 of the canonical payload, first 16 hex digits.

    MicroPython's json.dumps does not sort keys, so the cloud must send the
    payload already canonicalised -- see cloud_push.py.  If your checksums
    disagree, this is why.
    """
    import hashlib
    import ubinascii
    blob = json.dumps(payload)
    return ubinascii.hexlify(hashlib.sha256(blob).digest()).decode()[:16]


# ---------------------------------------------------------- the shadow test
def _rate(spec, buf):
    """Fraction of the buffer this spec would flag.  No persistence: the
    buffers are not contiguous in time, so a run rule means nothing on them."""
    if not buf:
        return None
    mu = spec["scaler_mean"]
    sd = spec["scaler_scale"]
    thr = spec["threshold"]
    hits = 0
    for x in buf:
        worst = 0.0
        for j in range(len(mu)):
            z = (x[j] - mu[j]) / sd[j]
            if z < 0.0:
                z = -z
            if z > worst:
                worst = z
        if worst > thr:
            hits += 1
    return hits / len(buf)


def verify(spec):
    """Run the candidate on windows the device kept.  (ok, reason)."""
    q = _rate(spec, _quiet)
    if q is None:
        return False, "no quiet windows kept yet"
    if q > FA_MAX:
        return False, "would flag %d%% of a quiet stretch" % int(100 * q)
    a = _rate(spec, _alarmed)
    if a is None:
        return True, "quiet ok, no retained alarms to test against"
    if a < RECALL_MIN:
        return False, "deaf: flags only %d%% of retained alarms" % int(100 * a)
    return True, "quiet %d%%, retained %d%%" % (int(100 * q), int(100 * a))


# ---------------------------------------------------------------- the apply
def on_model_message(topic, payload):
    """MQTT callback.  Does the minimum and returns: no parsing in here."""
    global _pending
    _pending = payload


def service(now, publish=None):
    """Call from the main loop, between windows.  Returns (accepted, reason)."""
    global _pending
    if _pending is None:
        return None
    raw, _pending = _pending, None
    try:
        msg = json.loads(raw)
    except Exception:
        return _ack(publish, None, None, False, "unparseable")

    p, why = validate(msg, now)
    if p is None:
        return _ack(publish, msg.get("kind"), msg.get("ver"), False, why)

    if msg["kind"] == "alarm":
        ok, why = verify(p)
        if not ok:
            return _ack(publish, "alarm", msg["ver"], False, "shadow: " + why)
        _last_good["alarm"] = (alarm.MEAN, alarm.INV_SD, alarm.THRESHOLD)
        inv = [1.0 / v for v in p["scaler_scale"]]
        alarm.MEAN = tuple(p["scaler_mean"])          # commit: three names
        alarm.INV_SD = tuple(inv)
        alarm.THRESHOLD = p["threshold"]
        alarm.reset()                 # the ring holds scores from the OLD spec
    else:
        _last_good["classifier"] = (model.COEF, model.INTERCEPT)
        model.COEF = tuple(tuple(r) for r in p["coef"])
        model.INTERCEPT = tuple(p["intercept"])

    _ver[msg["kind"]] = msg["ver"]
    gc.collect()
    return _ack(publish, msg["kind"], msg["ver"], True, "committed: " + why)


def rollback(kind, reason, publish=None):
    """Put the previous artefact back.  Used when a committed spec misbehaves."""
    g = _last_good.get(kind)
    if g is None:
        return False
    if kind == "alarm":
        alarm.MEAN, alarm.INV_SD, alarm.THRESHOLD = g
        alarm.reset()
    else:
        model.COEF, model.INTERCEPT = g
    _ver[kind] -= 1
    _ack(publish, kind, _ver[kind], False, "rolled back: " + reason)
    return True


def _ack(publish, kind, ver, ok, reason):
    body = {"v": 1, "kind": kind, "ver": ver,
            "ok": 1 if ok else 0, "why": reason,
            "running": {"alarm": _ver["alarm"], "classifier": _ver["classifier"]}}
    print("# downlink:", body)
    if publish is not None:
        try:
            publish(TOPIC_ACK, json.dumps(body))
        except Exception:
            pass
    return ok, reason
