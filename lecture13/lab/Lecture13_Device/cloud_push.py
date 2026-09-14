"""
cloud_push.py  --  Lecture 13, Lab 13
01211271 Industrial AI and IoT

The cloud side of the downlink.  Fits a new alarm specification from the history
your Lab 12 subscriber has been keeping, wraps it in an update message, and
publishes it to the device's private topic.

    pip install paho-mqtt

Two things this file does that matter more than they look:

  * it CANONICALISES the payload before hashing -- sorted keys, no spaces.  The
    device recomputes the digest with MicroPython's json.dumps, which does not
    sort keys, so the bytes must already be in a fixed order or the checksums
    will never agree.  This is the first thing that goes wrong in Lab 13.
  * it refuses to publish an update it has not scored itself.  The device will
    shadow-test it too, but a cloud that pushes specs it has not evaluated is
    just a faster way of being wrong.
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt

DEVICE_ID = "<your NETPIE device id>"
DEVICE_TOKEN = "<your NETPIE token>"
DEVICE_SECRET = "<your NETPIE secret>"
BROKER, PORT = "broker.netpie.io", 1883
TOPIC_MODEL = "@private/model"

FEATURES = ["mean", "rms", "std", "ptp", "crest", "kurt", "zcr",
            "dom_freq", "e_1x", "e_2x", "e_bpfo", "e_hi"]
APPROVER = "<your name>"          # somebody owns this. Section 3 of the notebook.
TTL_DAYS = 30


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def checksum(payload):
    return hashlib.sha256(canonical(payload).encode()).hexdigest()[:16]


def fit_alarm(X, quantile=0.99, persistence=(3, 5)):
    """The Lecture 10 recipe.  X is healthy windows only -- and Lecture 12
    section 8 is about how easy that sentence is to get wrong."""
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd > 1e-9, sd, 1.0)
    z = np.abs((X - mu) / sd).max(1)
    return {"scaler_mean": mu.tolist(), "scaler_scale": sd.tolist(),
            "threshold": float(np.quantile(z, quantile)),
            "threshold_quantile": quantile,
            "persistence": {"m": persistence[0], "n": persistence[1]},
            "feature_names": list(FEATURES),
            "fitted_on_healthy_windows": int(len(X)),
            "review_after_months": 12}


def score(spec, X):
    mu = np.array(spec["scaler_mean"])
    sd = np.array(spec["scaler_scale"])
    return float(np.mean(np.abs((X - mu) / sd).max(1) > spec["threshold"]))


def build(kind, payload, version, ttl_days=TTL_DAYS, fitted_on=None):
    return {"v": 1, "kind": kind, "ver": int(version),
            "t": time.time(), "ttl": ttl_days * 86400.0,
            "fitted_on": fitted_on, "by": APPROVER,
            "sum": checksum(payload), "payload": payload}


def publish(msg):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
    c.username_pw_set(DEVICE_TOKEN, DEVICE_SECRET)
    c.connect(BROKER, PORT, 60)
    c.loop_start()
    body = canonical(msg)
    c.publish(TOPIC_MODEL, body)
    time.sleep(1.0)
    c.loop_stop()
    c.disconnect()
    print(f"published {len(body)} bytes to {TOPIC_MODEL}: "
          f"{msg['kind']} v{msg['ver']}")


def main(csv_path="history.csv", version=2):
    hist = pd.read_csv(csv_path)
    rows = hist.dropna(subset=FEATURES)
    quiet = rows[(rows["raised"] == 0) & (rows["label"] == "normal")]
    X = quiet[FEATURES].to_numpy()
    if len(X) < 200:
        raise SystemExit(f"only {len(X)} quiet windows in {csv_path} -- "
                         "run the device longer before retraining")

    spec = fit_alarm(X)
    print(f"fitted on {len(X)} quiet windows, threshold {spec['threshold']:.2f}")
    print(f"  would raise on {score(spec, X):.1%} of the data it was fitted to")

    alarmed = rows[rows["raised"] == 1][FEATURES].to_numpy()
    if len(alarmed):
        print(f"  would raise on {score(spec, alarmed):.1%} of the windows that "
              f"alarmed ({len(alarmed)} of them)")
        if score(spec, alarmed) < 0.30:
            raise SystemExit("refusing to publish: this spec is deaf to the "
                             "fault this machine already had")
    else:
        print("  no alarmed windows in the history -- the device will shadow-test "
              "it, but you have not")

    publish(build("alarm", spec, version,
                  fitted_on=f"{len(X)} quiet windows from {csv_path}"))


if __name__ == "__main__":
    main()
