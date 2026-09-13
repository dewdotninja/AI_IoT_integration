"""
net_pub.py  --  Lecture 12, Lab 12
01211271 Industrial AI and IoT

The uplink, on the ESP32.  Real MicroPython, real NETPIE, real WiFi.

Add this to the Lecture 11 device and it publishes what the device decided --
not what the device measured.  Three topics, and a policy that decides which
of them to use and when:

    @msg/event      the situation changed
    @msg/summary    one heartbeat a minute, with a count in it
    @msg/feat       the raw features, in a short burst, only around an alarm

The counting heartbeat is the important one.  `ni` is how many windows in the
last minute alarmed with an impulsive driver, and it costs six bytes.  Without
it the cloud waits for the next event; with it the cloud knows within one
heartbeat.  Section 4 of the notebook measures the difference.

Fill in the four constants below from your NETPIE device page, copy this file
to the board next to features.py, model.py and alarm.py, and import it from
main.py.
"""
import gc
import json
import time

import network
from umqtt.simple import MQTTClient

import alarm

# ------------------------------------------------------------ your settings
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""
DEVICE_ID = "<your NETPIE device id>"
DEVICE_TOKEN = "<your NETPIE token>"
DEVICE_SECRET = "<your NETPIE secret>"

BROKER = "broker.netpie.io"
PORT = 1883

TOPIC_FEAT = b"@msg/feat"
TOPIC_EVENT = b"@msg/event"
TOPIC_SUMMARY = b"@msg/summary"
TOPIC_SHADOW = b"@shadow/data/update"

SCHEMA_VERSION = 1
HEARTBEAT_S = 60                 # one summary a minute
DWELL_S = 15                     # at most one event every 15 s
SMOOTH = 32                      # windows of majority vote before believing it
BURST = 8                        # feature messages around a raise
IMPULSIVE = ("kurt", "crest", "e_hi", "e_bpfo")

_client = None


# ----------------------------------------------------------------- transport
def connect(timeout_s=20):
    """WiFi, then the broker.  Returns True if the uplink is up.

    Everything in this file is written so that False is an acceptable answer.
    The device decides locally; the network is how it reports, not how it runs.
    """
    global _client
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        t0 = time.time()
        while not wlan.isconnected():
            if time.time() - t0 > timeout_s:
                print("# wifi timeout -- running offline")
                return False
            time.sleep(0.2)
    try:
        c = MQTTClient(DEVICE_ID, BROKER, port=PORT,
                       user=DEVICE_TOKEN, password=DEVICE_SECRET,
                       keepalive=120)
        c.connect()
        _client = c
        print("# uplink up:", wlan.ifconfig()[0])
        return True
    except Exception as e:
        print("# broker unreachable:", e)
        _client = None
        return False


def publish(topic, obj):
    """Publish one JSON object.  Never raises, never blocks the control loop."""
    if _client is None:
        return 0
    body = json.dumps(obj)
    try:
        _client.publish(topic, body)
        return len(body)
    except Exception as e:
        print("# publish failed:", e)
        return 0


def stamp():
    """Unix seconds.  Set the RTC from NTP first, or the cloud cannot order
    anything you send it."""
    return time.time()


# -------------------------------------------------------------- the messages
def _q(v, n=4):
    """Round to n significant figures.  Sending eight is paying for noise."""
    if v == 0:
        return 0.0
    return float("%.*g" % (n, v))


def msg_feature(x, label, margin, score, driver, raised):
    return {"v": SCHEMA_VERSION, "t": stamp(),
            "f": [_q(v) for v in x], "l": label, "m": _q(margin, 3),
            "a": _q(score, 3), "d": driver, "r": 1 if raised else 0}


def msg_event(ev, label, margin, score, driver, raised):
    return {"v": SCHEMA_VERSION, "t": stamp(), "e": ev, "l": label,
            "m": _q(margin, 3), "a": _q(score, 3), "d": driver,
            "r": 1 if raised else 0}


def msg_summary(n, a_med, a_max, n_raised, n_imp, label, driver):
    return {"v": SCHEMA_VERSION, "t": stamp(), "n": n,
            "a_med": _q(a_med, 3), "a_max": _q(a_max, 3), "r": n_raised,
            "ni": n_imp, "l": label, "d": driver}


def family(driver):
    return "impulsive" if driver in IMPULSIVE else "amplitude"


# ---------------------------------------------------------------- the policy
class Publisher:
    """Decides what to send.  Holds one minute of counters and nothing else.

    Memory: five small counters, a ring buffer of BURST feature vectors, and
    the smoothing window.  Everything is preallocated -- see Lecture 11 on why
    a loop that allocates is a loop that fails in a fortnight.
    """

    def __init__(self):
        self.reset_minute()
        self._published = (False, None)
        self._cand = (False, None)
        self._held = 0
        self._last_event = -1e9
        self._ring = [None] * BURST
        self._ri = 0
        self._burst_left = 0

    def reset_minute(self):
        self.n = 0
        self.n_raised = 0
        self.n_imp = 0
        self.a_sum = 0.0
        self.a_max = 0.0
        self.a_list = []
        self.labels = {}
        self.drivers = {}
        self.t_minute = time.time()

    def _bump(self, d, k):
        d[k] = d.get(k, 0) + 1

    def _modal(self, d):
        best, n = "-", -1
        for k in d:
            if d[k] > n:
                best, n = k, d[k]
        return best

    def feed(self, x, label, margin, score, driver, raised):
        """One window.  Returns the number of payload bytes published."""
        sent = 0
        self.n += 1
        self.a_sum += score
        self.a_list.append(score)
        if score > self.a_max:
            self.a_max = score
        if raised:
            self.n_raised += 1
            if driver in IMPULSIVE:
                self.n_imp += 1
        self._bump(self.labels, label)
        self._bump(self.drivers, driver)

        self._ring[self._ri] = (x, label, margin, score, driver, raised)
        self._ri = (self._ri + 1) % BURST

        # --- the debounced situation
        cur = (bool(raised), family(driver) if raised else None)
        self._held = self._held + 1 if cur == self._cand else 1
        self._cand = cur
        now = time.time()
        if (self._held >= SMOOTH and cur != self._published
                and now - self._last_event >= DWELL_S):
            ev = ("raise" if cur[0] and not self._published[0]
                  else "clear" if self._published[0] and not cur[0]
                  else "driver")
            sent += publish(TOPIC_EVENT,
                            msg_event(ev, label, margin, score, driver, cur[0]))
            self._published = cur
            self._last_event = now
            if ev == "raise":
                self._burst_left = BURST      # send the evidence, once

        # --- the context burst, one window per call so nothing blocks
        if self._burst_left:
            r = self._ring[(self._ri + BURST - self._burst_left) % BURST]
            if r is not None:
                sent += publish(TOPIC_FEAT, msg_feature(*r))
            self._burst_left -= 1

        # --- the heartbeat
        if now - self.t_minute >= HEARTBEAT_S:
            self.a_list.sort()
            med = self.a_list[len(self.a_list) // 2] if self.a_list else 0.0
            sent += publish(TOPIC_SUMMARY,
                            msg_summary(self.n, med, self.a_max, self.n_raised,
                                        self.n_imp, self._modal(self.labels),
                                        self._modal(self.drivers)))
            sent += publish(TOPIC_SHADOW,
                            {"data": {"label": self._modal(self.labels),
                                      "a_max": _q(self.a_max, 3),
                                      "raised": 1 if self._published[0] else 0,
                                      "driver": self._modal(self.drivers)}})
            self.reset_minute()
            gc.collect()
        return sent
