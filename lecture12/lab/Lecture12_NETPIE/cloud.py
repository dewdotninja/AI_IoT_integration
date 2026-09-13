"""
cloud.py  --  Lecture 12
01211271 Industrial AI and IoT

Two halves, matching the lecture.

UPLINK   the message schema, the four publish policies, and what each one
         costs in bytes per hour and in detection delay.

CLOUD    what a subscriber with history and peers can see that a device with
         one window and 200 KB of RAM cannot.

Nothing here runs on the ESP32.  The device-side equivalents are in the lab
package; these are their NumPy mirrors, so the notebook can measure them.
"""
import json

import numpy as np

from rig import FEATURE_NAMES

# ---------------------------------------------------------------- the schema
SCHEMA_VERSION = 1
TOPIC_FEAT = "@msg/feat"            # one window's twelve features + the verdict
TOPIC_EVENT = "@msg/event"          # something changed
TOPIC_SUMMARY = "@msg/summary"      # a minute of machine, in one message
TOPIC_SHADOW = "@shadow/data/update"   # last known state, for the dashboard

IMPULSIVE = ("kurt", "crest", "e_hi", "e_bpfo")   # the bearing signature
MIN_MARGIN = 0.25                   # below this the Lecture 11 device says so
T0 = 1789000000                     # a plausible unix epoch second, so the
                                    # measured payload sizes are the real ones


def q(v, sig=4):
    """Round to `sig` significant figures.  Sending float64 to three decimals of
    meaning is paying for noise."""
    return float(f"{float(v):.{sig}g}")


def stamp(t):
    """Device seconds -> a real unix timestamp, to the millisecond."""
    return round(T0 + float(t), 3)


def msg_feature(t, x, label, margin, score, driver, raised, dec=4):
    """One window, in full.  The message a naive design sends 15 times a second."""
    return {"v": SCHEMA_VERSION, "t": stamp(t),
            "f": [q(v, dec) for v in x],
            "l": label, "m": q(margin, 3), "a": q(score, 3),
            "d": driver, "r": int(raised)}


def msg_event(t, ev, label, margin, score, driver, raised):
    """Something changed.  No features -- the device already decided."""
    return {"v": SCHEMA_VERSION, "t": stamp(t), "e": ev,
            "l": label, "m": q(margin, 3), "a": q(score, 3),
            "d": driver, "r": int(raised)}


def msg_summary(t, n, score, raised, label, driver, n_imp=None):
    """A minute of machine: how many windows, how bad it got, what it was.

    `ni` is the number of those windows that alarmed with an impulsive driver.
    It costs about six bytes and it is the single most useful number in this
    lecture -- see section 4.
    """
    m = {"v": SCHEMA_VERSION, "t": stamp(t), "n": int(n),
         "a_med": q(np.median(score), 3), "a_max": q(np.max(score), 3),
         "r": int(np.sum(raised)), "l": label, "d": driver}
    if n_imp is not None:
        m["ni"] = int(n_imp)
    return m


def msg_verbose(t, x, label, margin, score, driver, raised):
    """The same content with self-documenting keys.  Measured, not dismissed."""
    return {"schema_version": SCHEMA_VERSION, "timestamp": stamp(t),
            "features": {n: q(v) for n, v in zip(FEATURE_NAMES, x)},
            "predicted_label": label, "classifier_margin": q(margin, 3),
            "anomaly_score": q(score, 3), "anomaly_driver": driver,
            "alarm_raised": bool(raised)}


def encoded(obj):
    """Exactly the bytes a client would hand to publish()."""
    return json.dumps(obj, separators=(",", ":"))


# ------------------------------------------------------- the device, in NumPy
class EdgeDevice:
    """The Lecture 11 device: classifier, alarm, persistence rule, driver name."""

    def __init__(self, model_json, alarm_json):
        clf = json.load(open(model_json)) if isinstance(model_json, str) else model_json
        alm = json.load(open(alarm_json)) if isinstance(alarm_json, str) else alarm_json
        mu, sd = np.array(clf["scaler_mean"]), np.array(clf["scaler_scale"])
        W, b = np.array(clf["coef"]), np.array(clf["intercept"])
        self.W = W / sd                                  # the Lecture 11 fold
        self.b = b - (W * (mu / sd)).sum(axis=1)
        self.classes = list(clf["classes"])
        self.amu = np.array(alm["scaler_mean"])
        self.ainv = 1.0 / np.array(alm["scaler_scale"])
        self.names = list(alm["feature_names"])
        self.threshold = float(alm["threshold"])
        self.m = int(alm["persistence"]["m"])
        self.n = int(alm["persistence"]["n"])

    def run(self, X):
        """Decide on every window.  Returns a dict of per-window arrays."""
        S = X @ self.W.T + self.b
        best = S.argmax(1)
        part = np.partition(S, -2, axis=1)
        margin = part[:, -1] - part[:, -2]
        label = np.array(self.classes, dtype=object)[best]
        label = np.where(margin < MIN_MARGIN, "uncertain", label)

        Z = np.abs((X - self.amu) * self.ainv)
        score = Z.max(1)
        driver = np.array(self.names, dtype=object)[Z.argmax(1)]

        over = (score > self.threshold).astype(int)
        raised = np.zeros(len(X), dtype=bool)
        hist = np.zeros(self.n, dtype=int)
        for i, o in enumerate(over):
            hist[i % self.n] = o
            raised[i] = hist.sum() >= self.m
        return {"label": label, "margin": margin, "score": score,
                "driver": driver, "raised": raised, "over": over.astype(bool)}


# ----------------------------------------------------------- publish policies
def policy_every(t, dev, X, **kw):
    """Send every window.  The default a student writes on the first attempt."""
    return [(t[i], TOPIC_FEAT,
             msg_feature(t[i], X[i], dev["label"][i], dev["margin"][i],
                         dev["score"][i], dev["driver"][i], dev["raised"][i]))
            for i in range(len(t))]


def policy_decimate(t, dev, X, every=16, **kw):
    """Send one window in `every`.  Cheaper, and blind in between."""
    return [(t[i], TOPIC_FEAT,
             msg_feature(t[i], X[i], dev["label"][i], dev["margin"][i],
                         dev["score"][i], dev["driver"][i], dev["raised"][i]))
            for i in range(0, len(t), every)]


def _modal(a):
    a = list(a)
    return max(set(a), key=a.count)


def _minute_blocks(t, heartbeat):
    edges = np.arange(0.0, t[-1] + heartbeat, heartbeat)
    return np.clip(np.searchsorted(edges, t, side="right") - 1, 0, None)


def family(driver):
    """Which kind of thing is driving the alarm.

    Two families is enough, and the split is the physics: impulsive features
    move when a rolling element hits a defect; amplitude features move when the
    operator takes a heavier cut.  A device that reports only `raised` cannot
    tell the cloud which of those just happened.
    """
    return "impulsive" if driver in IMPULSIVE else "amplitude"


def policy_on_change(t, dev, X, heartbeat=60.0, smooth=32, dwell=15.0,
                     count_impulsive=False, **kw):
    """Publish when the SITUATION changes, plus a heartbeat so that silence is
    not indistinguishable from a dead device.

    The situation is (alarm raised or not, which family of feature is driving
    it).  Two pieces of alarm management make this usable instead of a storm:

      * `smooth` -- the state is the majority over the last `smooth` windows
        (about two seconds), not the instantaneous flag.  The 3-of-5 persistence
        rule was tuned in Lecture 10 for driving an actuator, and it chatters
        far too fast to be a reporting rule.
      * `dwell`  -- at most one event every `dwell` seconds.  An alarm system
        that can emit 15 events a second is an alarm system nobody reads.
    """
    out = []
    raised = dev["raised"].astype(bool)
    fam = np.array([family(d) for d in dev["driver"]], dtype=object)
    published, last_t = (False, None), -1e9
    for i in range(smooth, len(t)):
        sl = slice(i - smooth, i)
        r = raised[sl].mean() > 0.5
        if r:
            f = fam[sl][raised[sl]]
            state = (True, max(set(f), key=list(f).count))
        else:
            state = (False, None)
        if state != published and (t[i] - last_t) >= dwell:
            ev = ("raise" if state[0] and not published[0]
                  else "clear" if published[0] and not state[0] else "driver")
            d = dev["driver"][sl][raised[sl]] if r else dev["driver"][sl]
            out.append((t[i], TOPIC_EVENT,
                        msg_event(t[i], ev, _modal(dev["label"][sl]),
                                  np.median(dev["margin"][sl]),
                                  np.median(dev["score"][sl]),
                                  _modal(d), state[0])))
            published, last_t = state, t[i]

    blk = _minute_blocks(t, heartbeat)
    for b in np.unique(blk):
        sel = blk == b
        i_end = int(np.flatnonzero(sel)[-1])
        drv = dev["driver"][sel][raised[sel]] if raised[sel].any() else dev["driver"][sel]
        ni = (int(np.sum(raised[sel] & np.isin(dev["driver"][sel], IMPULSIVE)))
              if count_impulsive else None)
        out.append((t[i_end], TOPIC_SUMMARY,
                    msg_summary(t[i_end], sel.sum(), dev["score"][sel],
                                dev["raised"][sel], _modal(dev["label"][sel]),
                                _modal(drv), n_imp=ni)))
    out.sort(key=lambda r: r[0])
    return out


def policy_on_alarm_context(t, dev, X, heartbeat=60.0, burst=8, **kw):
    """Heartbeat and events, plus the raw windows around every raise so the
    cloud can run its own model on the evidence instead of trusting a verdict."""
    out = policy_on_change(t, dev, X, heartbeat=heartbeat, **kw)
    fires = [i for i, (tm, tp, b) in enumerate(out)
             if tp == TOPIC_EVENT and b.get("r")]
    for k in fires:
        tm = out[k][0]
        j = int(np.searchsorted(t, tm))
        lo = max(0, j - burst)
        for i in range(lo, min(len(t), lo + burst)):
            out.append((t[i], TOPIC_FEAT,
                        msg_feature(t[i], X[i], dev["label"][i],
                                    dev["margin"][i], dev["score"][i],
                                    dev["driver"][i], dev["raised"][i])))
    out.sort(key=lambda r: r[0])
    return out


def policy_counting(t, dev, X, **kw):
    """Events and a heartbeat, and the heartbeat carries a COUNT of the windows
    that alarmed impulsively.  The device sends the statistic, not the samples."""
    kw = dict(kw)
    kw["count_impulsive"] = True
    return policy_on_change(t, dev, X, **kw)


POLICIES = {
    "every window": policy_every,
    "1 in 16": policy_decimate,
    "on change + heartbeat": policy_on_change,
    "on alarm + context": policy_on_alarm_context,
    "counting heartbeat": policy_counting,
}


# -------------------------------------------------- what the cloud can decide
def cloud_detects(msgs, fault_at, k=3, window_s=120.0):
    """Seconds from the spall starting to the cloud raising a work order.

    ONE rule, applied to every policy, so the comparison is about information
    and not about cleverness:

        raise a bearing alert as soon as `k` of the messages received in the
        last `window_s` seconds report an alarm whose driver is an impulsive
        feature.

    A single impulsive window is noise -- the spall is faint when it starts, and
    kurtosis is a fourth moment.  Three within two minutes is a pattern.  The
    load change earlier in the shift also raises the alarm, but its driver is
    `rms`, so this rule never sees it: that is the entire reason `driver` is in
    the schema.
    """
    hits = []
    for tm, topic, body in msgs:
        n = 0
        if body.get("r", 0) and body.get("d") in IMPULSIVE:
            n = 1
        n = max(n, int(body.get("ni", 0)))       # a counting heartbeat
        if n:
            hits += [tm] * n
            hits = [h for h in hits if h >= tm - window_s]
            if len(hits) >= k:
                return tm - fault_at
    return None


def cloud_false_alerts(msgs, before, k=3, window_s=120.0):
    """Would the same rule have fired before the spall existed?"""
    pre = [m for m in msgs if m[0] < before]
    return 0 if cloud_detects(pre, 0.0, k, window_s) is None else 1


def run_policy(name, t, dev, X, broker, device_id="rig-07", hours=None, **kw):
    """Publish a whole shift under one policy and report what it cost."""
    broker.reset()
    msgs = POLICIES[name](t, dev, X, **kw)
    for tm, topic, body in msgs:
        broker.publish(device_id, topic, body, t=tm)
    hours = hours if hours is not None else (t[-1] - t[0]) / 3600.0
    s = broker.summary(hours)
    s["policy"] = name
    return s, msgs


# =========================================== the fleet, month by month
BASE_MONTHS = 8                       # the reference period, months 0..7
SIGNATURE = ("kurt", "crest", "e_hi")  # chosen a priori: the bearing signature


def monthly_medians(X, mach, mon):
    """(n_machines, n_months, 12) -- one acquisition summarised to one row."""
    M, T = int(mach.max()) + 1, int(mon.max()) + 1
    out = np.zeros((M, T, X.shape[1]))
    for m in range(M):
        for t in range(T):
            out[m, t] = np.median(X[(mach == m) & (mon == t)], axis=0)
    return out


def edge_alarm_rate(X, mach, mon, device):
    """The only thing an edge-only fleet can report: how often each machine
    alarmed, per month."""
    M, T = int(mach.max()) + 1, int(mon.max()) + 1
    Z = np.abs((X - device.amu) * device.ainv).max(1)
    out = np.zeros((M, T))
    for m in range(M):
        for t in range(T):
            out[m, t] = np.mean(Z[(mach == m) & (mon == t)] > device.threshold)
    return out


def _residual_scores(med, base=BASE_MONTHS, signature=SIGNATURE,
                     subtract_common=True):
    idx = [FEATURE_NAMES.index(f) for f in signature]
    D = med[:, :, idx] - med[:, :base, idx].mean(1, keepdims=True)
    if subtract_common:
        D = D - np.median(D, axis=0, keepdims=True)
    scale = D[:, :base].std((0, 1), keepdims=True)
    return (D / scale).max(2)


def fleet_trend(med, **kw):
    """Each machine against its own history, with the plant-wide shift removed."""
    return _residual_scores(med, subtract_common=True, **kw)


def device_trend(med, **kw):
    """Each machine against its own history only.  Cannot tell a failing machine
    from a changing building."""
    return _residual_scores(med, subtract_common=False, **kw)


def first_sustained(v, threshold, months=2):
    """First month at which a score has been over threshold for `months` running."""
    run = 0
    for t, x in enumerate(v):
        run = run + 1 if x >= threshold else 0
        if run >= months:
            return t
    return None


def detector_report(score, threshold, degrader, months=2):
    """When it caught the degrader, and which healthy machines it also flagged."""
    hit = first_sustained(score[degrader], threshold, months)
    false = [m for m in range(score.shape[0])
             if m != degrader and first_sustained(score[m], threshold, months)
             is not None]
    return {"detect_month": hit, "false_machines": false,
            "n_false": len(false)}


# ------------------------------------------------------------- retraining
def refit_baseline(X, quantile=0.99, persistence=(3, 5), months=12):
    """The Lecture 10 recipe, applied to whatever healthy history you kept."""
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    z = np.abs((X - mu) / sd).max(1)
    return {"scaler_mean": mu.tolist(), "scaler_scale": sd.tolist(),
            "threshold": float(np.quantile(z, quantile)),
            "threshold_quantile": quantile,
            "persistence": {"m": persistence[0], "n": persistence[1]},
            "feature_names": list(FEATURE_NAMES),
            "fitted_on_healthy_windows": int(len(X)),
            "review_after_months": months}


def false_alarm_rate(spec, X):
    """Fraction of windows that exceed a spec's threshold."""
    mu = np.array(spec["scaler_mean"])
    sd = np.array(spec["scaler_scale"])
    z = np.abs((X - mu) / sd).max(1)
    return float(np.mean(z > spec["threshold"]))
