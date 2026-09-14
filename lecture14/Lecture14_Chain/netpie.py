"""
netpie.py  --  Lecture 12
01211271 Industrial AI and IoT

A small in-process stand-in for NETPIE, so that every cell of the notebook runs
with no broker, no credentials and no network.

It is deliberately NOT a general MQTT implementation.  It reproduces the three
things this lecture reasons about:

  * topic filters with the `+` and `#` wildcards, as NETPIE's broker has them;
  * retained messages, so a dashboard that connects late still sees the last
    known state;
  * the device shadow -- publishing to `@shadow/data/update` merges a JSON
    object into a per-device document that anyone can read.

and one thing a real broker will not give you: an exact count of the bytes that
crossed the wire.  The real code, against the real broker, is in the lab package
(`net_pub.py` for the ESP32 and `cloud_sub.py` for Colab); every topic name and
payload in this file is the one that code sends.
"""
import fnmatch
import json
import re
import time


# --------------------------------------------------------------- wire sizing
def wire_bytes(topic, payload, qos=0):
    """Bytes on the wire for one MQTT 3.1.1 PUBLISH packet.

    Fixed header (1) + remaining-length field (1-4) + topic length prefix (2)
    + topic + packet id if qos > 0 + payload.  This is what your data plan is
    billed for, not `len(payload)`.
    """
    if isinstance(payload, str):
        payload = payload.encode()
    if isinstance(topic, str):
        topic = topic.encode()
    rest = 2 + len(topic) + (2 if qos else 0) + len(payload)
    rl = 1 if rest < 128 else 2 if rest < 16384 else 3
    return 1 + rl + rest


def topic_matches(filt, topic):
    """MQTT topic-filter matching, including `+` (one level) and `#` (rest)."""
    f, t = filt.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t):
            return False
        if part != "+" and part != t[i]:
            return False
    return len(f) == len(t)


# -------------------------------------------------------------------- broker
class Broker:
    """The smallest thing that behaves like NETPIE for our purposes."""

    def __init__(self):
        self.subs = []                 # (filter, callback, client)
        self.retained = {}             # topic -> payload
        self.shadow = {}               # device -> dict
        self.tx_bytes = 0
        self.tx_msgs = 0
        self.log = []                  # (t, device, topic, payload, bytes)

    # -- broker side ------------------------------------------------------
    def subscribe(self, filt, callback, client="cloud"):
        self.subs.append((filt, callback, client))
        for topic, payload in self.retained.items():
            if topic_matches(filt, topic):
                callback(topic, payload)

    def publish(self, device, topic, payload, t=None, retain=False, qos=0):
        """Publish one message.  `topic` is relative, as NETPIE clients send it."""
        if not isinstance(payload, (str, bytes)):
            payload = json.dumps(payload, separators=(",", ":"))
        n = wire_bytes(topic, payload, qos)
        self.tx_bytes += n
        self.tx_msgs += 1
        self.log.append((t if t is not None else time.time(), device, topic,
                         payload, n))

        if topic == "@shadow/data/update":
            body = json.loads(payload)
            doc = self.shadow.setdefault(device, {})
            doc.update(body.get("data", body))

        full = f"{device}/{topic}"
        if retain:
            self.retained[full] = payload
        for filt, cb, _ in self.subs:
            if topic_matches(filt, full):
                cb(full, payload)
        return n

    # -- reporting --------------------------------------------------------
    def reset(self):
        self.tx_bytes = 0
        self.tx_msgs = 0
        self.log.clear()

    def summary(self, hours=1.0):
        return {"messages": self.tx_msgs, "bytes": self.tx_bytes,
                "bytes_per_hour": self.tx_bytes / hours,
                "msgs_per_hour": self.tx_msgs / hours}


# -------------------------------------------------------------------- client
class Device:
    """What `net_pub.py` does on the ESP32, minus the WiFi."""

    def __init__(self, broker, device_id):
        self.broker = broker
        self.id = device_id

    def publish(self, topic, payload, t=None, retain=False):
        return self.broker.publish(self.id, topic, payload, t=t, retain=retain)

    def shadow_update(self, data, t=None):
        return self.publish("@shadow/data/update", {"data": data}, t=t)


class CloudClient:
    """What `cloud_sub.py` does in Colab, minus paho-mqtt."""

    def __init__(self, broker, name="cloud"):
        self.broker = broker
        self.name = name
        self.received = []

    def subscribe(self, filt):
        self.broker.subscribe(filt, self._on_message, client=self.name)

    def _on_message(self, topic, payload):
        try:
            body = json.loads(payload)
        except (ValueError, TypeError):
            body = payload
        self.received.append((topic, body))

    def publish(self, topic, payload, t=None):
        return self.broker.publish(self.name, topic, payload, t=t)
