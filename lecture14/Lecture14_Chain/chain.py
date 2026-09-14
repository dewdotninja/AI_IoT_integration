"""
chain.py  --  Lecture 14
01211271 Industrial AI and IoT

The whole thing, in one loop.

Six lectures built six pieces and each was tested on its own.  This file wires
them together and runs them against a scripted twenty-minute session in which
things go wrong on purpose:

    signal -> validity gate -> 12 features -> classifier + alarm -> actuator
                                     |
                                     +-> NETPIE -> cloud subscriber -> alert
                                     |
              @private/model <-------+  (validate, stage, verify, commit)

Nothing here is new.  Every component is the one from its own lecture:

    rig.py        the rotor rig                     Lecture 8
    features      the twelve features               Lecture 8
    classifier    a linear SVM, scaler folded in    Lecture 9, 11
    alarm         max |z| + 3-of-5 persistence      Lecture 10, 11
    sensors.py    the validity gate                 Lecture 13
    netpie.py     the broker, and the byte count    Lecture 12
    downlink.py   validate/stage/verify/commit      Lecture 13

What IS new is that they now have to work at the same time, in the presence of
each other's failure modes, and the interesting bugs live in the joins.
"""
import copy
import json

import numpy as np

import rig
import sensors
import downlink as dl
from netpie import Broker, wire_bytes
from downlink import SpecStore, apply_verified, make_update, alarm_rate

SEG = 4.0                      # seconds of signal synthesised at a time
HEARTBEAT_S = 60.0
SMOOTH = 32                    # windows of majority vote before an event
DWELL_S = 15.0
MIN_MARGIN = 0.25
IMPULSIVE = ("kurt", "crest", "e_hi", "e_bpfo")
ALERT_K, ALERT_WINDOW = 3, 120.0
KEEP_QUIET, KEEP_ALARM = 1200, 400

TOPIC_EVENT, TOPIC_SUMMARY, TOPIC_FEAT = "@msg/event", "@msg/summary", "@msg/feat"
TOPIC_ACK, TOPIC_CLOUD = "@msg/ack", "@msg/cloud"


# ============================================================== the session
# One scripted shift.  Every entry is (start_min, end_min, what), and "what" is
# either a machine state, a load change, or a fault in the SENSOR rather than
# in the machine -- which is the distinction Lecture 13 was about.
SESSION_MIN = 22.0
SCRIPT = [
    (0.0, 6.0, "normal"),
    (6.0, 9.0, "loaded"),            # heavier cut. The machine is FINE.
    (9.0, 11.0, "normal"),
    (11.0, 13.0, "clipped"),         # the sensor, not the machine
    (13.0, 15.0, "normal"),
    (15.0, SESSION_MIN, "bearing"),  # a spall, growing
]

# Things the cloud does to the device, by wall-clock minute.
INJECTS = [
    (18.0, "network down", "the WiFi is pulled out"),
    (20.0, "network up", "and put back"),
]

# The three model updates the cloud pushes, by minute.  One is right and the
# other two are wrong in opposite directions -- and each is caught by a
# different half of the shadow test, which is why they arrive when they do.
# WHEN the deaf spec arrives decides whether it is caught, and that is not a
# detail -- it is the limit of the shadow test.  Pushed at minute 15.5 it is
# ACCEPTED, because the windows the device has kept as "alarmed" are still the
# heavy-cut ones (amplitude, not impulse) and a deaf spec still raises on those.
# By 16.0 the retained buffer has turned over to spall and the same spec is
# refused.  The test can only defend the device against faults it has already
# seen; a spec that is deaf to something new gets in.  Ask the room what that
# implies for the FIRST fault of a kind on a fleet.
UPDATE_TIMES = {"good": 3.0, "over-tight": 5.0, "deaf": 17.5}


def make_session(seed=101, minutes=SESSION_MIN, fs=rig.FS, win=rig.WIN, hop=rig.HOP):
    """Synthesise the session and return raw windows plus ground truth.

    Returns a dict with
        W        (n_windows, win)  the RAW samples the device would read
        t        window start time, seconds
        truth    per-window: normal | loaded | clipped | bearing
    """
    rng = np.random.default_rng(seed)
    base = rig._run_params(rng, "normal")
    n_seg = int(round(minutes * 60.0 / SEG))

    Ws, ts, truth = [], [], []
    for k in range(n_seg):
        t0 = k * SEG
        state = _state_at(t0 / 60.0)
        p = dict(base)
        p["f_r"] = base["f_r"] + 0.6 * np.sin(2 * np.pi * t0 / 420.0) + rng.normal(0, 0.05)
        p["noise"] = base["noise"] * float(rng.uniform(0.94, 1.06))

        if state == "loaded":
            p["a_1x"] = base["a_1x"] * 1.85
            p["gain"] = base["gain"] * 1.10
        if state == "bearing":
            frac = (t0 / 60.0 - 15.0) / (SESSION_MIN - 15.0)
            # Growth rate matters twice over.  Too slow and the retained-alarm
            # buffer never turns over to spall, so the deaf spec at 17.5 gets
            # in.  Too fast (try 1.90) and by minute 20 the impulses hit the
            # +-2 g rail, the validity gate calls the sensor clipped, and it
            # starts refusing the very windows you most want -- notebook ex. 5.
            p["a_imp"] = float(0.55 + 1.30 * max(0.0, frac))

        x = rig._synth(rng, p, SEG, fs)
        if state == "clipped":
            x = sensors.fault_clip(x, rng)          # the SENSOR fails, not the rig
        x = _adc(x)

        w = rig.frame(x, win, hop)
        Ws.append(w)
        ts.append(t0 + np.arange(len(w)) * hop / fs)
        truth += [state] * len(w)

    return {"W": np.vstack(Ws), "t": np.concatenate(ts),
            "truth": np.array(truth), "minutes": minutes,
            "hop_s": hop / fs}


def _state_at(minute):
    for a, b, s in SCRIPT:
        if a <= minute < b:
            return s
    return SCRIPT[-1][2]


def _adc(x, full=2.0):
    """What the converter hands to the code: int16, clipped at the rail."""
    lsb = full / 32768.0
    return np.round(np.clip(x, -full, full) / lsb) * lsb


# ================================================================ the device
class Device:
    """The Lecture 11 device, reading its models out of a SpecStore so that a
    committed update actually takes effect mid-run."""

    def __init__(self, store):
        self.store = store
        self.hist = np.zeros(5, dtype=int)
        self.i = 0
        self.actuator = False
        self._refresh()

    def _refresh(self):
        c = self.store.classifier
        mu, sd = np.array(c["scaler_mean"]), np.array(c["scaler_scale"])
        W, b = np.array(c["coef"]), np.array(c["intercept"])
        self.W = W / sd
        self.b = b - (W * (mu / sd)).sum(axis=1)
        self.classes = list(c["classes"])
        a = self.store.alarm
        self.amu = np.array(a["scaler_mean"])
        self.ainv = 1.0 / np.array(a["scaler_scale"])
        self.names = list(a["feature_names"])
        self.thr = float(a["threshold"])
        self.m = int(a["persistence"]["m"])
        self.n = int(a["persistence"]["n"])
        if len(self.hist) != self.n:
            self.hist = np.zeros(self.n, dtype=int)

    def on_commit(self, kind):
        """Called by the store after a commit.  The persistence ring holds
        scores computed under the OLD baseline, so it must be cleared."""
        self._refresh()
        self.hist[:] = 0
        self.i = 0

    def step(self, buf):
        """One window.  Returns a record, and never raises."""
        ok, why = sensors.validity(buf)
        if not ok:
            return {"gate": why, "label": "-", "margin": 0.0, "score": 0.0,
                    "driver": "-", "raised": self.actuator, "x": None}
        try:
            x = rig.features_of(buf[None, :])[0]
        except Exception:
            return {"gate": "feature-error", "label": "-", "margin": 0.0,
                    "score": 0.0, "driver": "-", "raised": self.actuator,
                    "x": None}

        s = x @ self.W.T + self.b
        order = np.argsort(s)
        margin = float(s[order[-1]] - s[order[-2]])
        label = self.classes[int(order[-1])]
        if margin < MIN_MARGIN:
            label = "uncertain"

        z = np.abs((x - self.amu) * self.ainv)
        score = float(z.max())
        driver = self.names[int(z.argmax())]

        self.hist[self.i % self.n] = 1 if score > self.thr else 0
        self.i += 1
        raised = bool(self.hist.sum() >= self.m)
        self.actuator = raised
        return {"gate": "ok", "label": label, "margin": margin, "score": score,
                "driver": driver, "raised": raised, "x": x}


# ================================================================= the uplink
class Uplink:
    """Lecture 12's counting heartbeat, plus a queue for when the link is down."""

    def __init__(self, broker, device_id="rig-07"):
        self.broker = broker
        self.id = device_id
        self.up = True
        self.queue = []
        self.published, self.queued = 0, 0
        self.state = (False, None)
        self.cand, self.held, self.last_event = (False, None), 0, -1e9
        self.reset_minute(0.0)

    def reset_minute(self, t):
        self.t0 = t
        self.n = 0
        self.n_raised = 0
        self.n_imp = 0
        self.scores = []
        self.labels = {}
        self.drivers = {}
        self.n_gate = 0

    def _send(self, topic, body, t):
        if self.up:
            self.broker.publish(self.id, topic, body, t=t)
            self.published += 1
            while self.queue:                    # drain on reconnect
                tp, bd, tt = self.queue.pop(0)
                self.broker.publish(self.id, tp, bd, t=t)
                self.published += 1
        else:
            self.queue.append((topic, body, t))
            self.queued += 1

    def feed(self, t, rec):
        self.n += 1
        self.scores.append(rec["score"])
        if rec["gate"] != "ok":
            self.n_gate += 1
        if rec["raised"]:
            self.n_raised += 1
            if rec["driver"] in IMPULSIVE:
                self.n_imp += 1
        self.labels[rec["label"]] = self.labels.get(rec["label"], 0) + 1
        self.drivers[rec["driver"]] = self.drivers.get(rec["driver"], 0) + 1

        fam = ("impulsive" if rec["driver"] in IMPULSIVE else "amplitude")
        cur = (bool(rec["raised"]), fam if rec["raised"] else None)
        self.held = self.held + 1 if cur == self.cand else 1
        self.cand = cur
        if (self.held >= SMOOTH and cur != self.state
                and t - self.last_event >= DWELL_S):
            ev = ("raise" if cur[0] and not self.state[0]
                  else "clear" if self.state[0] and not cur[0] else "driver")
            self._send(TOPIC_EVENT,
                       {"v": 1, "t": round(t, 3), "e": ev, "l": rec["label"],
                        "a": round(rec["score"], 3), "d": rec["driver"],
                        "r": int(cur[0])}, t)
            self.state, self.last_event = cur, t

        if rec["gate"] != "ok" and self.n_gate == 1:
            self._send(TOPIC_EVENT,
                       {"v": 1, "t": round(t, 3), "e": "sensor-fault",
                        "l": "-", "a": 0.0, "d": rec["gate"], "r": 0}, t)

        if t - self.t0 >= HEARTBEAT_S:
            mod = lambda d: max(d, key=d.get)
            self._send(TOPIC_SUMMARY,
                       {"v": 1, "t": round(t, 3), "n": self.n,
                        "a_med": round(float(np.median(self.scores)), 3),
                        "a_max": round(float(np.max(self.scores)), 3),
                        "r": self.n_raised, "ni": self.n_imp,
                        "gate": self.n_gate,
                        "l": mod(self.labels), "d": mod(self.drivers)}, t)
            self.reset_minute(t)


# ================================================================== the cloud
class Cloud:
    """Lecture 12's subscriber: keep everything, count the evidence, alert once."""

    def __init__(self, broker):
        self.hits = []
        self.alerted = False
        self.alert_t = None
        self.history = []
        self.acks = []
        broker.subscribe("+/@msg/#", self._on)

    def _on(self, topic, payload):
        body = json.loads(payload) if isinstance(payload, str) else payload
        self.history.append((topic, body))
        if topic.endswith("/@msg/ack"):
            self.acks.append(body)
            return
        t = body.get("t", 0.0)
        k = 1 if (body.get("r") and body.get("d") in IMPULSIVE) else 0
        k = max(k, int(body.get("ni", 0)))
        for _ in range(k):
            self.hits.append(t)
        self.hits = [h for h in self.hits if h >= t - ALERT_WINDOW]
        if len(self.hits) >= ALERT_K and not self.alerted:
            self.alerted = True
            self.alert_t = t


# =================================================================== the run
def fit_alarm(X, q=0.99):
    m_, s_ = X.mean(0), X.std(0)
    s_ = np.where(s_ > 0, s_, 1.0)
    z = np.abs((X - m_) / s_).max(1)
    return {"scaler_mean": m_.tolist(), "scaler_scale": s_.tolist(),
            "threshold": float(np.quantile(z, q)), "threshold_quantile": q,
            "persistence": {"m": 3, "n": 5},
            "feature_names": list(dl.EXPECTED_FEATURES),
            "fitted_on_healthy_windows": int(len(X)), "review_after_months": 12}


def run_session(session, alarm_spec, clf_spec, updates=None, verbose=False):
    """Drive the whole chain through the session.  Returns a record dict."""
    store = SpecStore(copy.deepcopy(alarm_spec), copy.deepcopy(clf_spec), 3, 3)
    dev = Device(store)
    broker = Broker()
    up = Uplink(broker)
    cloud = Cloud(broker)

    W, t, truth = session["W"], session["t"], session["truth"]
    quiet, alarmed = [], []
    rec = {k: [] for k in ("t", "gate", "label", "margin", "score", "driver",
                           "raised", "spec_ver", "bytes", "msgs")}
    events = []
    pending = list(updates or [])
    injects = list(INJECTS)

    for i in range(len(t)):
        now = float(t[i])

        # -- things the cloud or the world does to the device
        while injects and now >= injects[0][0] * 60.0:
            _, kind, _ = injects.pop(0)
            if kind == "network down":
                up.up = False
                events.append((now, "network down", "the WiFi is pulled out"))
            elif kind == "network up":
                up.up = True
                events.append((now, "network up", "and put back"))
        while pending and now >= pending[0][0] * 60.0:
            _, msg, tag = pending.pop(0)
            ok, why = apply_verified(store, msg, msg["t"] + now,
                                     np.array(quiet) if quiet else np.zeros((0, 12)),
                                     np.array(alarmed) if alarmed else None,
                                     on_commit=dev.on_commit)
            up._send(TOPIC_ACK,
                     {"v": 1, "kind": msg["kind"], "ver": msg["ver"],
                      "ok": int(ok), "why": why,
                      "running": {"alarm": store.ver["alarm"],
                                  "classifier": store.ver["classifier"]}}, now)
            events.append((now, f"update {tag}", ("accepted: " if ok else "refused: ") + why))

        r = dev.step(W[i])
        up.feed(now, r)
        if r["x"] is not None:
            (alarmed if r["raised"] else quiet).append(r["x"])
            if len(quiet) > KEEP_QUIET:
                quiet.pop(0)
            if len(alarmed) > KEEP_ALARM:
                alarmed.pop(0)

        rec["t"].append(now)
        rec["gate"].append(r["gate"])
        rec["label"].append(r["label"])
        rec["margin"].append(r["margin"])
        rec["score"].append(r["score"])
        rec["driver"].append(r["driver"])
        rec["raised"].append(r["raised"])
        rec["spec_ver"].append(store.ver["alarm"])
        rec["bytes"].append(broker.tx_bytes)
        rec["msgs"].append(broker.tx_msgs)

    for k in rec:
        rec[k] = np.array(rec[k])
    rec["truth"] = truth
    rec["events"] = events
    rec["store"] = store
    rec["cloud"] = cloud
    rec["uplink"] = up
    rec["broker"] = broker
    return rec


# ============================================================== the checkpoints
def checkpoints(rec, session):
    """What a group has to observe, and whether it happened.

    Each entry is a claim about the system that the run either supports or
    refutes.  A checkpoint nobody could have failed is not a checkpoint.
    """
    t, tr = rec["t"], rec["truth"]
    out = []

    def add(name, expect, got, ok):
        out.append({"checkpoint": name, "expected": expect, "observed": got,
                    "pass": bool(ok)})

    sel = (tr == "normal") & (t < 6 * 60)
    add("quiet start", "alarm raised on < 5 % of windows",
        f"{rec['raised'][sel].mean():.1%}", rec["raised"][sel].mean() < 0.05)

    ups = {e[1][len("update "):]: e[2] for e in rec["events"]
           if e[1].startswith("update ")}
    add("good update accepted", "committed; alarm version 3 -> 4",
        ups.get("good", "never arrived")[:52],
        ups.get("good", "").startswith("accepted"))
    add("the flooding spec refused", "refused: would raise on a quiet stretch",
        ups.get("over-tight", "never arrived")[:52],
        ups.get("over-tight", "").startswith("refused") and "quiet" in ups.get("over-tight", ""))
    add("the deaf spec refused", "refused: raises on too few retained alarms",
        ups.get("deaf", "never arrived")[:52],
        ups.get("deaf", "").startswith("refused"))

    sel = tr == "loaded"
    drv = rec["driver"][sel][rec["raised"][sel]]
    top = max(set(drv), key=list(drv).count) if len(drv) else "-"
    add("heavy cut raises the alarm", "alarm raises, driver is an amplitude feature",
        f"raised {rec['raised'][sel].mean():.0%}, driver {top}",
        rec["raised"][sel].mean() > 0.5 and top not in IMPULSIVE)

    sel = tr == "clipped"
    add("sensor fault caught by the gate", "every window rejected, reason 'clipped'",
        f"{(rec['gate'][sel] != 'ok').mean():.0%} rejected",
        (rec["gate"][sel] != "ok").mean() > 0.95)
    add("actuator held during the sensor fault",
        "no actuator transition while the sensor is bad",
        f"{int(np.sum(rec['raised'][sel][1:] != rec['raised'][sel][:-1]))} transitions",
        np.sum(rec["raised"][sel][1:] != rec["raised"][sel][:-1]) == 0)

    sel = (tr == "bearing") & (t > 17 * 60)
    drv = rec["driver"][sel][rec["raised"][sel]]
    top = max(set(drv), key=list(drv).count) if len(drv) else "-"
    add("the spall raises the alarm", "alarm raises, driver is impulsive",
        f"raised {rec['raised'][sel].mean():.0%}, driver {top}",
        rec["raised"][sel].mean() > 0.5 and top in IMPULSIVE)

    cl = rec["cloud"]
    fault_at = 15 * 60.0
    add("the cloud alerts, and only on the spall",
        "one alert, after minute 15, none during the heavy cut",
        f"alert at {cl.alert_t / 60:.1f} min" if cl.alerted else "no alert",
        cl.alerted and cl.alert_t > fault_at)

    down = (t >= 18 * 60) & (t < 20 * 60)
    add("the device keeps deciding with no network",
        "decisions continue while the uplink is down",
        f"{int((rec['gate'][down] == 'ok').sum())} windows decided",
        (rec["gate"][down] == "ok").mean() > 0.95)
    add("nothing published while the link is down",
        "messages queued, not lost",
        f"{rec['uplink'].queued} queued",
        rec["uplink"].queued > 0)
    add("queued reports arrive on reconnect",
        "the queue drains after minute 20",
        f"{len(rec['uplink'].queue)} still queued at the end",
        len(rec["uplink"].queue) == 0)
    return out
