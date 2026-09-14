"""
downlink.py  --  Lecture 13
01211271 Industrial AI and IoT

The model comes down.

Lecture 12 sent features up and left a refitted alarm specification sitting in
Colab, useless.  This file is how it reaches the device, and -- much more of the
file -- how it reaches the device *without being able to break it*.

The asymmetry that organises everything here:

    the CLASSIFIER drives the log.          39 numbers.  Swap it freely.
    the ALARM drives the ACTUATOR.          25 numbers.  Gate it hard.

An update that corrupts the classifier produces a wrong word in a log file.  An
update that corrupts the alarm produces a machine that is no longer protected,
and nothing on the plant floor will tell you.
"""
import copy
import hashlib
import json
import math

import numpy as np

TOPIC_MODEL = "@private/model"        # downlink: NETPIE private topic
TOPIC_ACK = "@msg/ack"                # the device says what it did

SCHEMA_VERSION = 1
N_FEATURES = 12
N_CLASSES = 3

# What a sane alarm specification looks like.  These are not tastes; each one is
# a property the device can check in microseconds and each one has been violated
# by a real update somewhere.
THRESHOLD_RANGE = (2.0, 12.0)         # a max-|z| threshold outside this is wrong
MIN_SD = 1e-6                         # a zero standard deviation is a divide by 0
MAX_AGE_S = 30 * 86400                # a spec issued a month ago is stale
MAX_SKEW_S = 3600                     # issued in the future by more than an hour


# ------------------------------------------------------------ the message
def checksum(payload):
    """A short digest over the canonical payload.

    Not a signature -- it catches corruption, not malice, and the difference
    matters enough that the device logs which one it is relying on.
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def make_update(kind, payload, version, issued_at, expires_in=MAX_AGE_S,
                fitted_on=None, approved_by=None):
    """One downlink message.

    kind        "alarm" or "classifier" -- which artefact this replaces
    version     monotonically increasing.  The device refuses to go backwards.
    issued_at   unix seconds, from the cloud's clock
    expires_in  after this the device stops trusting it
    fitted_on   how many windows, and from when -- for the log, not the device
    approved_by a named human.  Lecture 12 showed a retrain can silently make
                things worse; somebody has to own that.
    """
    return {"v": SCHEMA_VERSION, "kind": kind, "ver": int(version),
            "t": float(issued_at), "ttl": float(expires_in),
            "fitted_on": fitted_on, "by": approved_by,
            "sum": checksum(payload), "payload": payload}


# ------------------------------------------------------------ the validator
class Reject(Exception):
    """Why the device refused.  The reason goes in the ack, and in the log."""


def _finite(a):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in a)


def validate(msg, current_ver, now, n_features=N_FEATURES, n_classes=N_CLASSES):
    """Every check the device makes before an update is allowed anywhere near
    the running alarm.  Raises Reject with a reason; returns the payload.

    Read it as a list of things that have gone wrong in the field:
    """
    if not isinstance(msg, dict):
        raise Reject("not an object")
    for k in ("v", "kind", "ver", "t", "sum", "payload"):
        if k not in msg:
            raise Reject(f"missing field {k}")
    if msg["v"] != SCHEMA_VERSION:
        raise Reject(f"schema v{msg['v']}, device speaks v{SCHEMA_VERSION}")
    if msg["kind"] not in ("alarm", "classifier"):
        raise Reject(f"unknown kind {msg['kind']!r}")
    if checksum(msg["payload"]) != msg["sum"]:
        raise Reject("checksum mismatch -- truncated or corrupted")
    if not isinstance(msg["ver"], int) or msg["ver"] <= current_ver:
        raise Reject(f"version {msg['ver']} not newer than {current_ver}")
    if msg["t"] > now + MAX_SKEW_S:
        raise Reject("issued in the future -- check the cloud's clock")
    if now - msg["t"] > msg.get("ttl", MAX_AGE_S):
        raise Reject("expired -- a spec has a shelf life")

    p = msg["payload"]
    if msg["kind"] == "alarm":
        for k in ("scaler_mean", "scaler_scale", "threshold", "persistence",
                  "feature_names"):
            if k not in p:
                raise Reject(f"alarm spec missing {k}")
        mu, sd = p["scaler_mean"], p["scaler_scale"]
        if len(mu) != n_features or len(sd) != n_features:
            raise Reject(f"expected {n_features} features, got {len(mu)}/{len(sd)}")
        if not (_finite(mu) and _finite(sd)):
            raise Reject("non-finite baseline -- NaN or inf in the numbers")
        if min(sd) < MIN_SD:
            raise Reject("a standard deviation is zero -- divide by zero on device")
        thr = p["threshold"]
        if not isinstance(thr, (int, float)) or not math.isfinite(thr):
            raise Reject("threshold is not a finite number")
        if not (THRESHOLD_RANGE[0] <= thr <= THRESHOLD_RANGE[1]):
            raise Reject(f"threshold {thr:.4g} outside {THRESHOLD_RANGE}")
        m, n = p["persistence"]["m"], p["persistence"]["n"]
        if not (1 <= m <= n <= 64):
            raise Reject(f"persistence {m}-of-{n} is not sane")
        if list(p["feature_names"]) != list(EXPECTED_FEATURES):
            raise Reject("feature order does not match the device's")
    else:
        for k in ("coef", "intercept", "classes"):
            if k not in p:
                raise Reject(f"classifier missing {k}")
        W, b = p["coef"], p["intercept"]
        if len(W) != n_classes or len(b) != n_classes:
            raise Reject(f"expected {n_classes} classes, got {len(W)}/{len(b)}")
        if any(len(r) != n_features for r in W):
            raise Reject("a coefficient row is the wrong length")
        if not all(_finite(r) for r in W) or not _finite(b):
            raise Reject("non-finite coefficients")
        if all(all(v == 0.0 for v in r) for r in W):
            raise Reject("all coefficients zero -- the model predicts nothing")
    return p


EXPECTED_FEATURES = ["mean", "rms", "std", "ptp", "crest", "kurt", "zcr",
                     "dom_freq", "e_1x", "e_2x", "e_bpfo", "e_hi"]


# -------------------------------------------------------- the two-slot store
class SpecStore:
    """Two slots and a pointer.  The oldest idea in embedded updates.

    `active` is what the alarm is using this second.  `standby` is where a
    candidate lands.  Commit is one pointer assignment, so a power cut during an
    update leaves the device running the old spec rather than half of two.

    `last_good` is the spec the device will fall back to if the new one turns
    out to misbehave after commit -- which is a different failure from an
    invalid one, and the reason `verify()` exists.
    """

    def __init__(self, alarm, classifier, ver_alarm=1, ver_clf=1):
        self.alarm = alarm
        self.classifier = classifier
        self.ver = {"alarm": ver_alarm, "classifier": ver_clf}
        self.last_good = {"alarm": copy.deepcopy(alarm),
                          "classifier": copy.deepcopy(classifier)}
        self.standby = {}
        self.log = []

    # -- the three steps, kept separate on purpose -------------------------
    def stage(self, msg, now):
        """Validate into the standby slot.  Nothing running is touched."""
        p = validate(msg, self.ver[msg["kind"]], now)
        self.standby[msg["kind"]] = (msg["ver"], copy.deepcopy(p), msg)
        return p

    def commit(self, kind, on_commit=None):
        """One assignment.  Atomic as far as the alarm is concerned."""
        if kind not in self.standby:
            raise Reject("nothing staged")
        ver, p, msg = self.standby.pop(kind)
        self.last_good[kind] = copy.deepcopy(getattr(self, kind))
        setattr(self, kind, p)
        self.ver[kind] = ver
        if on_commit is not None:
            on_commit(kind)          # e.g. reset the persistence ring buffer
        self.log.append({"event": "commit", "kind": kind, "ver": ver,
                         "by": msg.get("by")})
        return p

    def rollback(self, kind, reason):
        setattr(self, kind, copy.deepcopy(self.last_good[kind]))
        self.ver[kind] -= 1
        self.log.append({"event": "rollback", "kind": kind, "reason": reason})

    def apply(self, msg, now, on_commit=None):
        """stage -> commit, with the reason recorded either way.

        Returns (accepted, reason).  Never raises: a device that crashes on a
        bad message is a device anyone can switch off from the internet.
        """
        try:
            self.stage(msg, now)
        except Reject as e:
            self.log.append({"event": "reject", "kind": msg.get("kind"),
                             "reason": str(e)})
            return False, str(e)
        except Exception as e:                       # malformed beyond parsing
            self.log.append({"event": "reject", "kind": None,
                             "reason": f"malformed: {type(e).__name__}"})
            return False, f"malformed: {type(e).__name__}"
        self.commit(msg["kind"], on_commit=on_commit)
        return True, "committed"


def apply_verified(store, msg, now, X_quiet, X_alarmed=None, on_commit=None,
                   fa_budget=(0.0, 0.25), recall_min=0.30):
    """Validate, then STAGE AND TEST before committing.

    The structural gate cannot catch a specification that is perfectly well
    formed and simply wrong -- the Lecture 12 refit that learned a failing
    machine was normal has twelve finite means, twelve positive standard
    deviations and a threshold of 5.09.  The only thing that catches it is
    running it, in shadow, against windows the device has kept.
    """
    try:
        p = store.stage(msg, now)
    except Reject as e:
        store.log.append({"event": "reject", "kind": msg.get("kind"),
                          "reason": str(e)})
        return False, str(e)
    except Exception as e:
        store.log.append({"event": "reject", "kind": None,
                          "reason": f"malformed: {type(e).__name__}"})
        return False, f"malformed: {type(e).__name__}"

    if msg["kind"] == "alarm":
        h = spec_health(p, X_quiet, X_alarmed, fa_budget, recall_min)
        if not h["ok"]:
            store.standby.pop("alarm", None)
            store.log.append({"event": "reject", "kind": "alarm",
                              "reason": "shadow test: " + h["why"]})
            return False, "shadow test: " + h["why"]
    store.commit(msg["kind"], on_commit=on_commit)
    return True, "committed"


def apply_naive(store, msg):
    """What most first attempts look like.  One line, no checks.

    It is here to be measured, not to be copied.
    """
    try:
        store.__dict__[msg["kind"]] = msg["payload"]
        store.ver[msg["kind"]] = msg["ver"]
        return True, "applied"
    except Exception as e:
        return False, f"crashed: {type(e).__name__}"


# ------------------------------------------------- is the running spec sane?
def spec_health(spec, X_quiet, X_alarmed=None, fa_budget=(0.0, 0.25),
                recall_min=0.30):
    """Run a candidate spec, in shadow, against windows the device kept.

    This is the check that catches an update which is perfectly well formed and
    still wrong.  It needs BOTH halves and the second one is the one people
    forget:

      X_quiet    windows from a stretch nothing happened in.  Catches a spec
                 that will flood -- fitted during a heavy cut, say.
      X_alarmed  the windows that made this device raise, last time it did.
                 Catches a spec that has gone DEAF, which is invisible on
                 healthy data by construction.

    The device has `X_alarmed` because Lecture 12's "on alarm + context" policy
    published the windows around every raise -- and, if you kept a copy on the
    device, this is what they were for.
    """
    try:
        rate = alarm_rate(spec, X_quiet)
    except Exception:
        return {"ok": False, "rate": None, "recall": None,
                "why": "unevaluable on the quiet stretch"}
    lo, hi = fa_budget
    if rate > hi:
        return {"ok": False, "rate": rate, "recall": None,
                "why": f"would raise on {rate:.0%} of a quiet stretch"}
    if rate < lo:
        return {"ok": False, "rate": rate, "recall": None, "why": "never raises"}

    rec = None
    if X_alarmed is not None and len(X_alarmed):
        try:
            rec = alarm_rate(spec, X_alarmed)
        except Exception:
            return {"ok": False, "rate": rate, "recall": None,
                    "why": "unevaluable on the retained alarm windows"}
        if rec < recall_min:
            return {"ok": False, "rate": rate, "recall": rec,
                    "why": f"deaf: raises on only {rec:.0%} of the windows that "
                           f"alarmed last time"}
    r_txt = "n/a" if rec is None else f"{rec:.0%}"
    return {"ok": True, "rate": rate, "recall": rec,
            "why": f"{rate:.1%} quiet, {r_txt} on retained alarms"}


# ------------------------------------------------- the hostile update corpus
def hostile_updates(good_alarm, good_clf, now, cur_ver=3, old_alarm=None,
                    overfit_alarm=None, loaded_alarm=None):
    """Everything that has actually arrived on a downlink topic somewhere.

    Returns a list of (name, message, what_it_is).  Four of them are legitimate
    and must be ACCEPTED; the rest must be refused.  A gate that rejects
    everything is not a gate, it is a disconnected wire.
    """
    ok_alarm = make_update("alarm", good_alarm, cur_ver + 1, now,
                           approved_by="V. Toochinda")
    ok_clf = make_update("classifier", good_clf, cur_ver + 1, now,
                         approved_by="V. Toochinda")

    def broken(payload, **kw):
        base = dict(kind="alarm", payload=payload, version=cur_ver + 1,
                    issued_at=now)
        base.update(kw)
        m = make_update(base["kind"], base["payload"], base["version"],
                        base["issued_at"])
        return m

    out = [("a good alarm spec", ok_alarm, "accept"),
           ("a good classifier", ok_clf, "accept")]

    # -- corruption in transit
    m = copy.deepcopy(ok_alarm)
    m["payload"]["threshold"] = 4.9                     # changed after signing
    out.append(("one number changed in transit", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["scaler_mean"] = m["payload"]["scaler_mean"][:7]
    m["sum"] = checksum(m["payload"])                   # truncated AND resummed
    out.append(("truncated to 7 features", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["scaler_scale"][3] = float("nan")
    m["sum"] = checksum(m["payload"])
    out.append(("a NaN in the baseline", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["scaler_scale"][5] = 0.0
    m["sum"] = checksum(m["payload"])
    out.append(("a zero standard deviation", m, "reject"))

    # -- wrong numbers that parse perfectly
    m = copy.deepcopy(ok_alarm)
    m["payload"]["threshold"] = 1e9
    m["sum"] = checksum(m["payload"])
    out.append(("threshold 1e9 (deaf)", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["threshold"] = 0.0
    m["sum"] = checksum(m["payload"])
    out.append(("threshold 0 (screams)", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["persistence"] = {"m": 9, "n": 5}
    m["sum"] = checksum(m["payload"])
    out.append(("9-of-5 persistence", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["payload"]["feature_names"] = list(reversed(EXPECTED_FEATURES))
    m["payload"]["scaler_mean"] = list(reversed(m["payload"]["scaler_mean"]))
    m["payload"]["scaler_scale"] = list(reversed(m["payload"]["scaler_scale"]))
    m["sum"] = checksum(m["payload"])
    out.append(("features in a different order", m, "reject"))

    # -- protocol problems
    m = copy.deepcopy(ok_alarm)
    m["v"] = 2
    out.append(("schema v2 from a newer cloud", m, "reject"))

    m = make_update("alarm", old_alarm if old_alarm else good_alarm,
                    cur_ver - 1, now)
    out.append(("last year's spec replayed", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["t"] = now - 200 * 86400
    out.append(("issued 200 days ago", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    m["t"] = now + 40 * 86400
    out.append(("issued 40 days in the future", m, "reject"))

    m = copy.deepcopy(ok_alarm)
    del m["ver"]
    out.append(("no version field", m, "reject"))

    m = copy.deepcopy(ok_clf)
    m["payload"]["coef"] = [[0.0] * N_FEATURES for _ in range(N_CLASSES)]
    m["sum"] = checksum(m["payload"])
    out.append(("a classifier of all zeros", m, "reject"))

    out.append(("a bare string on the topic", "OK", "reject"))

    # -- the two that every structural check in this file will pass
    if overfit_alarm is not None:
        out.append(("refit that absorbed the fault",
                    make_update("alarm", overfit_alarm, cur_ver + 1, now,
                                approved_by="nobody"), "reject"))
    if loaded_alarm is not None:
        out.append(("refit taken during a heavy cut",
                    make_update("alarm", loaded_alarm, cur_ver + 1, now,
                                approved_by="nobody"), "reject"))
    return out


# ------------------------------------------------- what the device then does
def alarm_rate(spec, X):
    """Fraction of windows this spec would RAISE on, persistence included.

    Including the persistence rule is not fussiness.  A spec with a 9-of-5 rule
    parses, stores and scores perfectly well, and never raises anything: the
    machine is unprotected and the device reports no error at all.
    """
    mu = np.asarray(spec["scaler_mean"], dtype=float)
    sd = np.asarray(spec["scaler_scale"], dtype=float)
    if len(mu) != X.shape[1] or len(sd) != X.shape[1]:
        raise ValueError("feature count mismatch")
    if not np.all(np.isfinite(sd)) or np.any(np.abs(sd) < MIN_SD):
        raise FloatingPointError("degenerate scale")
    z = np.abs((X - mu) / sd).max(1)
    if not np.isfinite(z).all():
        raise FloatingPointError("non-finite score")
    over = (z > spec["threshold"]).astype(int)
    m = int(spec["persistence"]["m"])
    n = int(spec["persistence"]["n"])
    if m > n:
        return 0.0                       # unsatisfiable: the device is deaf
    k = np.convolve(over, np.ones(n, dtype=int), mode="full")[:len(over)]
    return float(np.mean(k >= m))


def outcome_of(store, kind, X_healthy, X_faulty, base_faulty,
               flood=0.5, deaf=0.10):
    """Classify what the machine is now living with.

    A structural check says whether an update is well formed.  This says
    whether the device can still do its job -- which is the only question the
    plant cares about.
    """
    if kind == "classifier":
        return "log only"                  # the classifier drives no actuator
    try:
        rh = alarm_rate(store.alarm, X_healthy)
        rf = alarm_rate(store.alarm, X_faulty)
    except Exception:
        return "crash"
    if rh > flood:
        return "alarm flood"
    if rf < deaf:
        return "deaf to the fault"
    if rf < 0.5 * base_faulty:
        return "degraded"
    return "no harm"
