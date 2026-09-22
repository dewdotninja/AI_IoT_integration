# Lab 12 — The Uplink, End to End

**01211271 Industrial AI and IoT** · Lecture 12 · Electromechanical Manufacturing Engineering

* **Time:** 180 minutes (the second half of today's session)
* **Files:** `iaiiot26_Lect12_nb.ipynb`, `Lecture12_NETPIE.zip`
* **Platform:** Wokwi ESP32 (device) + Google Colab or a PC (cloud) + a NETPIE account

---

## What you are building

The other half of the system.

Lecture 11's device decides for itself and tells nobody. By the end of this lab it
publishes to NETPIE, a subscriber in Colab keeps the history and raises its own alert,
and a dashboard shows the raw features, the device's verdict and the cloud's verdict
side by side.

You are also going to measure your own bytes per hour under two publish policies, and
argue for one of them. That argument — not the plumbing — is what is being marked.

---

## Before you start (15 min)

1. **A NETPIE device.** Log in at https://netpie.io/, create a project and one device.
   Copy its **Device ID**, **Token** and **Secret**. Each of you needs your own; they go
   in `net_pub.py` and `cloud_sub.py`.
2. **Your Lecture 11 Wokwi project**, working. Part A adds to it; it does not replace
   it. If `bench.py` never ran on your board, do that first — you cannot reason about
   publishing on a device that cannot keep up with its sensor.
3. **Unzip `Lecture12_NETPIE.zip`.** You get:

| file | where it runs |
|---|---|
| `net_pub.py` | on the ESP32, next to `features.py`, `model.py`, `alarm.py` |
| `cloud_sub.py` | in Colab or on your PC |
| `netpie.py`, `cloud.py` | the notebook's offline stand-ins, for reference |

4. **In Colab:** `!pip install paho-mqtt`

> Wokwi's simulated WiFi reaches the internet through your browser. `Wokwi-GUEST` with
> an empty password works and needs no configuration.

---

## Part A — Publish (60 min)

**A1. Fill in the four constants** at the top of `net_pub.py` and copy it to the board.

**A2. Wire it into the loop.** In `main.py`, after the alarm has decided:

```python
import net_pub

net_pub.connect()                  # returns False if there is no network. That is fine.
pub = net_pub.Publisher()

# ... inside the window loop, after label / score / driver / raised:
pub.feed(x, label, margin, score, driver, raised)
```

**A3. Watch the traffic.** From a terminal (or the NETPIE web console's message view):

```
$ mosquitto_sub -h broker.netpie.io -p 1883 \
      -u <token> -P <secret> -i <device-id> -t '@msg/#' -v
```

Record one message of each kind — event, summary, shadow update — exactly as it
arrived. You will need them in the report.

**A4. The offline test, and this is the point of the whole course.** Comment out
`net_pub.connect()` so the uplink never comes up. Run the device.

Confirm, and state in one sentence in your report, that:

* the LED still responds to the alarm;
* the serial output is unchanged;
* nothing raises an exception.

A device whose control loop depends on its broker is a device that stops protecting the
machine the moment the WiFi does.

---

## Part B — Subscribe and measure (60 min)

**B1. Run the subscriber.** Fill in the same three credentials in `cloud_sub.py` and run
it in Colab. Set `WAVE = "wave_normal"` on the device first, and watch the heartbeats
arrive with `ni = 0`.

**B2. Make it alert.** Switch the device to `WAVE = "wave_bearing"`. Record:

| | |
|---|---|
| time of the first `@msg/event` with an impulsive driver | |
| value of `ni` in the heartbeats after the switch | |
| time the subscriber printed `ALERT published` | |
| the contents of `history.csv` after five minutes (rows, columns) | |

**B3. Measure your own bytes.** Add a byte counter to `net_pub.publish` — it already
returns the payload length; accumulate it, and add the MQTT overhead yourself:

```
wire = 1 + remaining_length_bytes + 2 + len(topic) + len(payload)
```

Run for five minutes under two policies and extrapolate:

| policy | messages | payload bytes | wire bytes | **bytes/hour** | **MB per machine per day** |
|---|---|---|---|---|---|
| `HEARTBEAT_S = 60`, events on (as shipped) | | | | | |
| every window (call `publish(TOPIC_FEAT, msg_feature(...))` unconditionally) | | | | | |

State the ratio. The notebook measured about 960×; you will not get exactly that, and
the reason is interesting — say what it is.

**B4. One number, argued.** `HEARTBEAT_S` is 60 s and the detection latency is one
heartbeat. Pick the value you would actually deploy on a machine whose bearing failure
takes about **two hours** to go from detectable to destructive, and justify it in three
sentences with your own bytes-per-hour figure.

---

## Part C — The dashboard and the alert rule (60 min)

**C1. Build the dashboard.** In NETPIE, three panels:

1. the raw features (or a useful subset — twelve traces is not a dashboard);
2. the device's own verdict: label, score, and **the driver name**;
3. the cloud's alert, from `@msg/cloud`.

The driver name should be the most prominent thing on the screen. A technician sent to
a machine with "score 6.4" has been told nothing.

**C2. The naive alert.** Add a NETPIE alert rule of the form *"notify when rms exceeds
X"*. Choose X from your own `wave_normal` run. Then run `wave_imbalance` — a healthy
machine under a different condition as far as this rule is concerned — and record how
often it fires.

**C3. The rule you would defend.** Write the alert rule you would actually deploy. It
may use any field in the schema, any number of messages, and any time window. Then
write half a page containing:

* the rule, precisely enough that someone else could implement it;
* what it does on `wave_normal`, `wave_imbalance` and `wave_bearing`;
* **what it costs when it is wrong**, in both directions;
* one sentence on why it is not a threshold on `rms`.

A defended threshold on `rms` is an acceptable answer. An undefended anything is not.

---

## What to hand in

A report, four to five pages:

1. **The three recorded messages** from A3, verbatim.
2. **The offline statement** from A4 — one sentence, but it must be true.
3. **The B2 alert table** and a screenshot of the subscriber's output at the moment it
   alerted.
4. **The B3 byte table**, your measured ratio, and your explanation of why it differs
   from the notebook's.
5. **Your heartbeat interval** from B4, with the justification.
6. **A screenshot of the dashboard**, and the alert rule from C3 with its half page.

---

## Marking

| | weight |
|---|---|
| A — publishing works and is evidenced; the offline test done and reported | 20 % |
| B2 — the subscriber alerts, with the timing recorded | 15 % |
| B3 — bytes measured correctly, including the MQTT overhead | 20 % |
| B4 — heartbeat interval chosen and justified with your own numbers | 10 % |
| C1 — dashboard legible, driver name prominent | 10 % |
| C3 — the defended alert rule, including what it costs when wrong | 25 % |

Marks are lost for: quoting the notebook's bytes instead of your own; a dashboard that
plots twelve features and nothing else; and an alert rule with no stated failure cost.

---

## If you get stuck

**`MQTTException: 5` or an immediate disconnect.** NETPIE wants the **Device ID** as the
MQTT client id, the **Token** as the username and the **Secret** as the password. Getting
two of the three right still fails.

**Nothing arrives, and no error.** You are probably publishing to `@msg/feat` but
subscribing to `@msg/feats`, or to `msg/feat` without the `@`. Subscribe to `@msg/#`
first and narrow down afterwards.

**`MemoryError` once publishing starts.** `json.dumps` allocates. Reduce `BURST`, call
`gc.collect()` in the heartbeat branch (it is already there), and check you are not
keeping a Python list of every window — the `Publisher` deliberately keeps counters, not
history.

**The device falls behind its budget after adding the uplink.** That is a real result,
not a mistake — report it. Then look at where the time goes: a `publish` that blocks on
a slow network inside the window loop is the usual cause, and it is the argument for
events over per-window publishing arriving in the most direct way possible.

**`ni` is always zero even on `wave_bearing`.** Check `IMPULSIVE` matches the feature
names your `alarm.py` uses, and print `driver` for a few windows. On a faint spall the
driver genuinely is `mean` or `dom_freq` for the first minute or two.

---

## Looking ahead

You now have a refitted alarm specification sitting in Colab — 25 numbers, a threshold,
a persistence rule and an expiry date — and it is useless there. Next week it comes down
over MQTT, the device applies it without being reflashed, and then we disconnect the
WiFi and confirm the machine is still protected.

Exercise 8 in the notebook is that message. Attempt it before Lecture 13, especially the
last part: what the device must do if it arrives corrupted or half-received.
