# Lab 13 — Closing the Loop

**01211271 Industrial AI and IoT** · Lecture 13 · Electromechanical Manufacturing Engineering

* **Time:** 180 minutes (the second half of today's session)
* **Files:** `iaiiot26_Lect13_nb.ipynb`, `Lecture13_Device.zip`
* **Platform:** Wokwi ESP32 (device) + Colab or a PC (cloud) + your NETPIE device from Lab 12

---

## What you are building

The last arrow.

Your device has decided for itself since Lab 11 and reported since Lab 12. Today the
cloud sends something back — and the entire lab is about doing that without being able
to break the machine.

Then you are going to prove the point the whole course has been building towards:
**pull the WiFi out and watch the device carry on protecting the machine.** Record that.
It is the most convincing thing you will produce all term.

Three parts. Part A is the downlink, Part B is the plug, Part C is the sensor.

---

## Setting up (15 min)

Unzip `Lecture13_Device.zip` into your Lab 12 Wokwi project, beside `features.py`,
`model.py`, `alarm.py`, `main.py` and `net_pub.py`:

| file | what it is |
|---|---|
| `net_apply.py` | the downlink handler: validate → stage → verify → commit → ack |
| `validity.py` | the sensor gate, five comparisons, one pass |
| `cloud_push.py` | the Colab side: builds and publishes a signed-ish update |

Then wire both into `main.py`:

```python
import net_apply, validity

client.set_callback(lambda t, p: net_apply.on_model_message(t, p))
client.subscribe(net_apply.TOPIC_MODEL)

# ... in the window loop, BEFORE features:
ok, why = validity.validity(buf, e_1x=None)
if not ok:
    publish_sensor_fault(why)          # hold the actuator; do not guess
    continue

x = features.all_features(buf)
# ... classify, alarm, actuate as before ...
net_apply.remember(x, raised)          # keep windows for the shadow test

# ... once per loop, between windows:
client.check_msg()
net_apply.service(time.time(), publish=net_pub.publish)
```

> **The checksum will disagree the first time.** MicroPython's `json.dumps` does not sort
> keys, so the cloud must canonicalise the payload before hashing it — `cloud_push.py`
> does, with `sort_keys=True, separators=(",", ":")`. If your device rejects a perfectly
> good update with `checksum mismatch`, this is why, and finding it yourself is part of
> the exercise.

---

## Part A — The downlink (75 min)

**A1. Push a good one.** In Colab, fit a new alarm spec on recent healthy windows from
your own `history.csv` (Lab 12 part B2 wrote it), and publish it with `cloud_push.py` at
version 2.

Record the ack, verbatim:

```
# downlink: {'v':1,'kind':'alarm','ver':2,'ok':1,
#            'why':'committed: quiet 1%, retained 100%',
#            'running':{'alarm':2,'classifier':1}}
```

Then confirm on the device that the new threshold is actually in use — print
`alarm.THRESHOLD` before and after.

**A2. Break it on purpose.** Push **three** bad updates of your own design. You must
include at least one from each row:

| kind | examples |
|---|---|
| structurally invalid | a NaN, a zero standard deviation, eleven features instead of twelve, a threshold of 1e9 |
| protocol-invalid | a stale timestamp, a replayed version, a schema the device does not speak |
| **well formed and wrong** | a spec fitted on data that includes a fault, or fitted while the machine was loaded |

For each one record: what you sent, which of the five steps refused it, and **the exact
reason string**.

| # | what you sent | refused at | reason |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

The third row is the interesting one. A structurally invalid update is caught by
arithmetic; a well-formed wrong one is caught only by `verify()` running it against
windows the device kept.

**A3. Empty buffers.** Reboot the device and immediately push a good update, before it
has seen enough windows to fill `_quiet` and `_alarmed`.

What happens? Is that the right behaviour? Write two sentences arguing either way — there
is a real design decision here and both answers are defensible, but only a defended one
earns the marks.

**A4. Rollback.** `net_apply.rollback()` exists and nothing calls it. Trigger it by hand
after a commit and confirm the device returns to the previous spec and version. Then
write, in three sentences, the rule that *should* call it automatically, and say how you
would stop that rule from rolling back a spec that is correctly reporting a machine which
really has begun to fail.

---

## Part B — Pull the plug (45 min)

This is the part to record.

**B1. Baseline.** With the new spec running and WiFi up, set `WAVE = "wave_bearing"` and
confirm the LED responds and the cloud subscriber sees the events.

**B2. Disconnect.** In Wokwi, stop the WiFi (comment out `connect()`, or use the
simulator's network control). Keep the device running. Record:

| | |
|---|---|
| does the LED still respond to the fault? | |
| is the serial output unchanged? | |
| mean microseconds per window, before and after | |
| what the device printed when a publish failed | |

**B3. Reconnect.** Bring the network back. Show that the queued or subsequent reports
arrive and that the device did not need restarting.

**B4. The awkward question.** While the network was down, the cloud could not have sent
an update. Suppose a genuinely important one had been issued during that window. How
would the device ever get it, and what in your current design guarantees that? If nothing
does, say so — and say what you would add.

**Deliverable:** a short screen recording, or a serial log with timestamps, showing the
device detecting and actuating with no network.

---

## Part C — Break the sensor (60 min)

**C1. Without the gate.** Comment out the validity check. Then corrupt the waveform in
`wave_normal.py` two ways and record what the model says:

| injected fault | how to make it | label | margin | alarm score | raised |
|---|---|---|---|---|---|
| stuck channel | return the same sample forever after window 20 | | | | |
| clipped range | clip the samples to ±0.55 g | | | | |

Do the same on `wave_bearing.py` with the clip. Note what happens to `kurt` and `crest`,
and state in one sentence why a clipped sensor is worse than a noisy one.

**C2. With the gate.** Put `validity.validity()` back. Confirm both faults are rejected,
record the reason string, and check that the actuator **held** rather than changing state.

**C3. Defend one limit.** The constants in `validity.py` are mine, and copying them is
the mistake the file exists to prevent. Pick **one** — `RMS_LO`, `DEAD_PTP`, `MAX_DC`,
`SAT_FRAC` or `MIN_E1X` — and rederive it from your own machine's healthy history, the
way Lecture 10 derived its threshold. State:

* the data you used and how much of it;
* the new value, and the false-rejection rate it buys on data you did not fit it to;
* one sentence on what physically would have to change for your value to become wrong.

**C4. The one it misses.** Section 8 of the notebook shows the gate does not catch a
loose sensor mount, because a rattling sensor produces a genuine impulsive signal. In half
a page: what would you actually do about this in a plant? Your answer may involve the
cloud, a technician, a second sensor or a maintenance procedure — but it must be
something a person could be asked to do on a Tuesday.

---

## What to hand in

A report, four to six pages:

1. **The A1 ack**, verbatim, and the threshold before and after.
2. **The A2 table** — three bad updates, where each was refused, and the reason strings.
3. **Your A3 answer**, two sentences, defended.
4. **The A4 rollback rule**, three sentences.
5. **The B2 table** and the recording or log from Part B.
6. **Your B4 answer.**
7. **The C1 and C2 tables**, with the `kurt` and `crest` numbers.
8. **Your C3 rederived limit**, with its false-rejection rate.
9. **Your C4 half page.**

---

## Marking

| | weight |
|---|---|
| A1–A2 — the downlink works and three bad updates are refused with reasons | 25 % |
| A3–A4 — empty buffers and the rollback rule, defended | 10 % |
| B — the device runs with no network, evidenced | 20 % |
| B4 — the missed-update question, answered honestly | 5 % |
| C1–C2 — sensor faults recorded before and after the gate | 20 % |
| C3 — one limit rederived from your own data | 10 % |
| C4 — what you would actually do about the loose mount | 10 % |

Marks are lost for: an update rejected without a recorded reason string; copying the gate
limits unchanged; and claiming the device kept working with the network down without
evidence anybody could check.

---

## If you get stuck

**`checksum mismatch` on a good update.** Canonicalise the payload on the cloud side
before hashing — see the note in Setting up. Compare the two digests by printing both.

**`no quiet windows kept yet`.** The device has not run long enough to fill `_quiet`.
That is A3, not a bug.

**Every update refused with `not newer than vN`.** The version counter lives on the
device and survives a soft reset in your code but not a power cycle in Wokwi. Decide
where it *should* live — flash, or re-synchronised from the cloud at connect — and say
which you chose.

**`MemoryError` after adding the buffers.** `KEEP_QUIET` and `KEEP_ALARM` are 64 windows
of 12 floats each. On a board already running an FFT that may be too much; halve them and
report the effect on the shadow test (this is notebook exercise 2).

**The gate rejects healthy windows.** `RMS_LO` is set for *my* rig. Yours has a different
mounting and a different gain. That is C3 arriving early.

**The device stops deciding when the network drops.** Then `service()` or `check_msg()`
is blocking. Neither may block; the whole architecture of Lecture 11 depends on it.

---

## Looking ahead

Next week there is no new material. There is one session, one machine, and the whole
chain: signal → features → edge inference → NETPIE → cloud model → a spec coming back
down → actuation. A fault will be injected partway through, and the network will be
pulled out at a moment you are not expecting.

Notebook exercise 8 is the rehearsal: write the sequence of events, and at each step say
what you would have to **see** to believe the system worked. Bring that list. It is what
we will run against.
