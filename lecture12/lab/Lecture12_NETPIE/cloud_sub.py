"""
cloud_sub.py  --  Lecture 12, Lab 12
01211271 Industrial AI and IoT

The cloud side, for Colab or any PC.  Subscribes to a NETPIE device, applies
the alert rule from section 5 of the notebook, appends everything to a CSV so
that section 6 has a history to retrain from, and publishes its own verdict
back to the device's topic tree.

    pip install paho-mqtt

Two things this file deliberately does NOT do:

  * it does not decide anything the device depends on.  The device drives its
    own actuator; this is a second opinion with a longer memory.
  * it does not trust a single message.  ALERT_K messages within ALERT_WINDOW
    seconds, all reporting an impulsive driver -- one kurtosis spike is noise.
"""
import csv
import json
import os
import time
from collections import deque

import paho.mqtt.client as mqtt

# ------------------------------------------------------------ your settings
DEVICE_ID = "<your NETPIE device id>"
DEVICE_TOKEN = "<your NETPIE token>"
DEVICE_SECRET = "<your NETPIE secret>"
BROKER, PORT = "broker.netpie.io", 1883

SUB_TOPICS = ["@msg/feat", "@msg/event", "@msg/summary"]
PUB_TOPIC = "@msg/cloud"

IMPULSIVE = ("kurt", "crest", "e_hi", "e_bpfo")
ALERT_K = 3                     # messages of evidence
ALERT_WINDOW = 120.0            # within this many seconds
CSV_PATH = "history.csv"

FEATURES = ["mean", "rms", "std", "ptp", "crest", "kurt", "zcr",
            "dom_freq", "e_1x", "e_2x", "e_bpfo", "e_hi"]

_hits = deque()
_alerted = False


def on_connect(client, userdata, flags, rc, *a):
    print("connected, rc =", rc)
    for t in SUB_TOPICS:
        client.subscribe(t)
        print("  subscribed", t)


def append_csv(body):
    """Keep everything.  Section 6: you cannot retrain on what you threw away."""
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["t", "kind", "label", "margin", "score", "driver",
                        "raised", "n", "ni"] + FEATURES)
        f = body.get("f", [None] * 12)
        w.writerow([body.get("t"), body.get("e", "feat" if "f" in body else "summary"),
                    body.get("l"), body.get("m"), body.get("a"), body.get("d"),
                    body.get("r"), body.get("n"), body.get("ni")] + list(f))


def evidence(body):
    """How many pieces of impulsive-alarm evidence this one message carries."""
    n = 1 if (body.get("r") and body.get("d") in IMPULSIVE) else 0
    return max(n, int(body.get("ni", 0)))


def on_message(client, userdata, msg):
    global _alerted
    try:
        body = json.loads(msg.payload.decode())
    except ValueError:
        print("unparseable payload on", msg.topic)
        return
    append_csv(body)

    now = body.get("t", time.time())
    k = evidence(body)
    for _ in range(k):
        _hits.append(now)
    while _hits and _hits[0] < now - ALERT_WINDOW:
        _hits.popleft()

    if len(_hits) >= ALERT_K and not _alerted:
        _alerted = True
        out = {"v": 1, "t": now, "alert": "bearing",
               "evidence": len(_hits), "window_s": ALERT_WINDOW,
               "driver": body.get("d")}
        client.publish(PUB_TOPIC, json.dumps(out))
        print("ALERT published:", out)
    elif len(_hits) == 0 and _alerted:
        _alerted = False
        client.publish(PUB_TOPIC, json.dumps({"v": 1, "t": now, "alert": "clear"}))
        print("cleared")

    print(f"{msg.topic:16s} {body.get('e', '-'):8s} "
          f"a={body.get('a', '-')!s:>7} d={body.get('d', '-'):9s} "
          f"r={body.get('r', 0)} ni={body.get('ni', '-')} "
          f"[evidence {len(_hits)}]")


def main():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
    c.username_pw_set(DEVICE_TOKEN, DEVICE_SECRET)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(BROKER, PORT, 60)
    print("writing history to", CSV_PATH)
    c.loop_forever()


if __name__ == "__main__":
    main()
