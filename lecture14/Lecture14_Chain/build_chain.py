"""
build_chain.py  --  Lecture 14

Drives chain.py once, end to end, and writes the record the figures, the
notebook and the observation sheet all read.  Keeping this in one file means
the deck, the run sheet and the notebook can never quote different numbers.

    python build_chain.py          -> prints the events and the checkpoints
"""
import json

import numpy as np

import rig
import chain
import downlink as dl
from downlink import make_update


# ------------------------------------------------------------------ baselines
def baseline_specs(rig_seed=101, seed=7):
    """The models the device boots with: Lecture 9's classifier and an alarm
    spec fitted the Lecture 10 way, on healthy windows from a quiet shift.

    The baseline has to come from THIS machine.  `rig_seed` is the session's
    seed, so `_run_params` draws the same shaft speed, gain and mounting; only
    the noise realisation differs.  Fitting on a different rig is exactly the
    mistake Lecture 10 warned about, and it shows up here as an alarm that
    raises on four windows in five before anything has gone wrong.
    """
    clf = json.load(open("lecture9_model.json"))
    Xh = healthy_features(rig_seed=rig_seed, seed=seed, minutes=8.0)
    return chain.fit_alarm(Xh, q=0.995), clf, Xh


def healthy_features(rig_seed=101, seed=7, minutes=8.0, loaded=False):
    """Feature matrix from a stretch of the same rig running healthy."""
    base = rig._run_params(np.random.default_rng(rig_seed), "normal")
    rng = np.random.default_rng(seed)
    out = []
    for k in range(int(round(minutes * 60.0 / chain.SEG))):
        t0 = k * chain.SEG
        p = dict(base)
        # the same slow speed drift the session has, so the baseline covers it
        p["f_r"] = base["f_r"] + 0.6 * np.sin(2 * np.pi * t0 / 420.0) + rng.normal(0, 0.05)
        p["noise"] = base["noise"] * float(rng.uniform(0.94, 1.06))
        if loaded:
            p["a_1x"] = base["a_1x"] * 1.85
            p["gain"] = base["gain"] * 1.10
        x = chain._adc(rig._synth(rng, p, chain.SEG, rig.FS))
        out.append(rig.features_of(rig.frame(x, rig.WIN, rig.HOP)))
    return np.vstack(out)


# ------------------------------------------------------------------- updates
def make_updates(base_alarm, seed=11):
    """Three specs the cloud pushes at the device during the session.

    good        refitted on a fresh healthy month.  Should be committed.
    over-tight  fitted on a stretch so quiet the scale is too small, so
                ordinary running exceeds it -- caught by the QUIET half of
                the shadow test.
    deaf        threshold inflated to swallow everything -- caught only by
                the RETAINED-ALARM half, and only if the device has kept
                windows from a fault it is actually seeing.
    """
    Xg = healthy_features(rig_seed=101, seed=seed, minutes=8.0)
    good = chain.fit_alarm(Xg, q=0.995)

    # Both bad specs are ARITHMETICALLY PERFECT: twelve finite features, no zero
    # standard deviation, a threshold inside the allowed range, a good checksum,
    # a fresh timestamp, the right version.  validate() has nothing to object to.
    # Only running them against kept windows finds them out.
    tight = chain.fit_alarm(Xg, q=0.995)
    tight["scaler_scale"] = [s * 0.25 for s in tight["scaler_scale"]]

    deaf = chain.fit_alarm(Xg, q=0.995)
    deaf["scaler_scale"] = [s * 3.0 for s in deaf["scaler_scale"]]

    ups = []
    for tag, spec, ver in (("good", good, 4), ("over-tight", tight, 5),
                           ("deaf", deaf, 6)):
        # issued_at is offset so the age the device computes is a few seconds,
        # not the whole session -- chain.py hands validate() msg["t"] + now.
        m = make_update("alarm", spec, ver, issued_at=-2.0,
                        fitted_on=f"{len(Xg)} healthy windows",
                        approved_by="V. Toochinda")
        ups.append((chain.UPDATE_TIMES[tag], m, tag))
    ups.sort(key=lambda u: u[0])
    return ups


# --------------------------------------------------------------- the numbers
def write_results(session, rec, checks, path="results.json"):
    """Every number the deck, the notebook and the observation sheet quote.
    One file, written once, so they cannot drift apart."""
    t, tr, r, g = rec["t"], rec["truth"], rec["raised"], rec["gate"]
    b, cl, up = rec["broker"], rec["cloud"], rec["uplink"]
    fault_at = 15.0

    def frac(state, expr):
        s = tr == state
        return float(expr[s].mean()) if s.any() else 0.0

    down = (t >= 18 * 60) & (t < 20 * 60)
    out = {
        "session_min": float(session["minutes"]),
        "windows": int(len(t)),
        "hop_s": float(session["hop_s"]),
        "windows_per_s": round(1.0 / float(session["hop_s"]), 3),
        "script": [[a, b_, s] for a, b_, s in chain.SCRIPT],
        "injects": [[m, k] for m, k, _ in chain.INJECTS],
        "update_times": dict(chain.UPDATE_TIMES),
        "events": [[round(tt / 60.0, 2), k, w] for tt, k, w in rec["events"]],
        "checks": checks,
        "checks_passed": int(sum(c["pass"] for c in checks)),
        "checks_total": len(checks),
        "raised": {s: round(frac(s, r), 4)
                   for s in ("normal", "loaded", "clipped", "bearing")},
        "gate_reject": {s: round(frac(s, g != "ok"), 4)
                        for s in ("normal", "loaded", "clipped", "bearing")},
        "msgs": int(b.tx_msgs),
        "bytes": int(b.tx_bytes),
        "bytes_per_min": round(b.tx_bytes / float(session["minutes"]), 1),
        "mb_per_day": round(b.tx_bytes / float(session["minutes"]) * 1440 / 1e6, 3),
        "raw_bytes_per_min": int(rig.FS * 2 * 60),
        "cloud_alert_min": round(cl.alert_t / 60.0, 2) if cl.alerted else None,
        "cloud_lead_min": round(cl.alert_t / 60.0 - fault_at, 2) if cl.alerted else None,
        "offline_windows": int((g[down] == "ok").sum()),
        "offline_queued": int(up.queued),
        "queue_left": int(len(up.queue)),
        # measured by the notebook's section 6 sweep: the same deaf spec is
        # accepted up to 16.0 min and refused from 16.5 on, because that is
        # when the retained-alarm buffer has turned over to spall windows.
        "deaf_accepted_until_min": 16.0,
        "deaf_refused_from_min": 16.5,
        "alarm_threshold": round(float(rec["store"].alarm["threshold"]), 3),
        "alarm_version": int(rec["store"].ver["alarm"]),
    }
    json.dump(out, open(path, "w"), indent=1)
    return out


# ---------------------------------------------------------------------- main
def run(seed=101, verbose=True):
    alarm, clf, _ = baseline_specs()
    session = chain.make_session(seed=seed)
    ups = make_updates(alarm)
    rec = chain.run_session(session, alarm, clf, ups)
    checks = chain.checkpoints(rec, session)

    write_results(session, rec, checks)

    if verbose:
        print("\nevents:")
        for t, k, w in rec["events"]:
            print(f"  {t/60:5.2f} min  {k:<18} {w}")
        print("\ncheckpoints:")
        for c in checks:
            print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['checkpoint']:<45} "
                  f"{c['observed']}")
        b = rec["broker"]
        print(f"\nmsgs {b.tx_msgs}  bytes {b.tx_bytes}  "
              f"queued {rec['uplink'].queued}  "
              f"cloud alert {rec['cloud'].alert_t/60:.2f} min")
    return session, rec, checks


if __name__ == "__main__":
    run()
