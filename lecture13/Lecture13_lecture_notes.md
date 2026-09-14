# Lecture 13 — Hybrid architecture, and closing the loop
 
**01211271 Industrial AI and IoT** · built 2026-09-14 · follows Lectures 8–12
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture13_Closing_the_Loop.pptx`, renamed to `iaiiot26_Lect13.pptx` | 12 slides (dark title, 10 light, dark summary), 13.333 × 7.5 in, speaker notes 1146–1878 chars on every slide |
| `Lecture13_Closing_the_Loop.ipynb`, renamed to `iaiiot26_Lect13_nb.ipynb` | 49 cells, executed end to end, 0 errors, 0 stderr, ~10 s runtime |
| `Lecture13_Lab_Sheet.md`, renamed to `iaiiot26_Lect13_Lab_Sheet.md` | 180 min, three parts (downlink / pull the plug / break the sensor), marking scheme |
| `Lecture13_Device.zip` | `net_apply.py`, `validity.py` (MicroPython), `cloud_push.py` (paho), plus `downlink.py` and `sensors.py` for reference |
 
Source directory `/home/claude/lecture13/`: `rig.py`, `cloud.py`, `netpie.py` (copied from
Lecture 12), `downlink.py`, `sensors.py`, `pkg/`, `make_figs.py`, `build_notebook.py`,
`build_deck.js`, `results.json`, `figs/`, plus `lecture13_alarm_v4.json` and
`lecture13_classifier_v4.json` (the legitimate v4 artefacts).
 
## The instructor's choices for this lecture
 
* **Centrepiece:** both, one per half — the hostile-update gauntlet, then the sensor faults.
* **Downlink carries both artefacts**, with the asymmetry argued explicitly.
* **Scope:** keep to the outlined topics; signed updates, watchdogs and a formalised
  human-approval workflow were offered and declined, leaving Lecture 14 the integrated run.
## Headline numbers
 
All in `results.json`; deck and notebook both read from it.
 
### Half 1 — the downlink
 
**19 update messages** (2 legitimate, 17 that must be refused), three apply paths. The
measurement is not "did it parse" but **what the machine is left with**, evaluated by
running the resulting spec on healthy and faulty windows from `make_shift`.
 
| apply path | correct | what the machine is left with |
|---|---|---|
| one assignment | **4 / 19** | 3 crash, 3 deaf to a real spall, 3 alarm flood, 8 harmless-or-silently-wrong |
| structural gate (~40 lines) | **17 / 19** | 1 deaf, 1 flood still get through |
| + shadow test | **19 / 19** | — |
 
**The two the structural gate cannot catch** are `refit that absorbed the fault` (deaf)
and `refit taken during a heavy cut` (flood). Both have twelve finite means, twelve
positive standard deviations, a threshold in range, a sane persistence rule, a fresh
timestamp and a correct checksum. Only *running* them catches them.
 
**The shadow test needs two buffers and the second is the one people forget:**
`QUIET` (1200 windows from a stretch nothing happened in) catches the flood;
`ALARMED` (400 windows that made *this device* raise) catches the deafness, which is
invisible on healthy data by construction. **Those windows are Lecture 12's "on alarm +
context" bursts** — the cross-lecture payoff, and it was not planned when Lecture 12 was
written.
 
**The hot-swap asymmetry** (classifier 39 numbers, alarm 25):
 
| swap | labels changed | actuator transitions | windows raised |
|---|---|---|---|
| the CLASSIFIER | 2.7 % | 371 → 371 | 27.1 % → 27.1 % |
| the ALARM | 0.0 % | 371 → **241** | 27.1 % → **51.6 %** |
 
Plus the discontinuity: at commit the **reported anomaly score jumps ×3.4** (2.05 → 7.04)
while both thresholds stay ≈ 4.0 — because the *baseline* changed, not the threshold.
Anything accumulating the score across a spec change (Lecture 12's `a_max`, the fleet
trend, every dashboard chart) now has an unexplained step. Fix: carry `spec_ver` in the
uplink and re-baseline at version boundaries.
 
**Latency budget:** device path **129.3 ms** (128 ms window + 1.25 ms of computing).
Affordable round trip = budget − 129.3 ms: **121 / 371 / 871 / 1871 ms** for budgets of
250 / 500 / 1000 / 2000 ms — at the 99th percentile, not the mean.
 
### Half 2 — when the sensor lies
 
Four faults injected into a healthy machine (and two into a spalled one), through a
simulated int16 ADC:
 
| case | classifier | margin | alarm score | raised | gate |
|---|---|---|---|---|---|
| healthy, good sensor | normal | 1.42 | 1.4 | 0 % | passes |
| SPALL, good sensor | bearing | 1.30 | 3.2 | 9 % | passes |
| healthy + stuck channel | normal | **9.79** | 2240 | 98 % | dead channel |
| healthy + clipped range | normal | 1.71 | 2.2 | 0 % | clipped |
| healthy + **loose mount** | **bearing** | 1.50 | 3.2 | 29 % | **passes** |
| healthy + gain ×0.25 | normal | **3.02** | 3.9 | 0 % | level implausible |
| **SPALL + clipped range** | **normal** | 1.78 | 3.2 | **0 %** | clipped |
| SPALL + gain ×0.25 | **normal** | 0.84 | 3.4 | 3 % | level implausible |
 
**The headline:** a clipped sensor made a spalled bearing look *calmer than health* —
kurtosis **1.79 against 2.23**, crest **1.58 against 2.42** — and the alarm never raised.
Clipping removes the peaks and the peaks *are* the fault, so a sensor that cannot see
peaks does not make the fault noisy, it **erases** it. Noise makes a model uncertain; a
sensor fault makes it confident and wrong.
 
**The gate:** five comparisons, one pass, no allocation. Catches **5 of 6** fault cases,
false-rejection rate **0.0000** over **30 runs** of healthy/imbalance/bearing machines,
and costs **~99 µs** under MicroPython (median of 7 runs × 400 reps) — about **8 %** of
the 1156 µs pipeline.
 
**The one it misses is `loose sensor mount`, and that is the honest finish.** A rattling
sensor produces a genuine impulsive signal; distinguishing it needs the repetition rate
(a spall repeats at 3.6× shaft, a loose bolt at whatever the mount wants), which needs a
tachometer or a cepstrum. So the architecture is three-layered: the gate rejects what is
cheaply impossible, the cloud's fleet comparison (Lecture 12 §7) flags what is merely
unlikely, and **a human with a spanner** closes the rest. That earns the "human in the
loop" bullet instead of asserting it.
 
## Deck outline
 
1. dark title — "Hybrid architecture, and closing the loop"
2. The whole system, finally — `fig_arch`
3. How much loop is there? — `fig_latency`
4. The update message, and the apply path — `fig_update`
5. What a hostile update does to a device — `fig_gauntlet` ← centrepiece 1
6. What a structural check cannot see — two boxes + `codeBox`
7. Which artefact is dangerous to update — `fig_swap`
8. When the sensor lies — `fig_sensor` ← centrepiece 2
9. Five comparisons, before any feature — `fig_gate`
10. Degraded modes, and the log — `fig_degraded`
11. Lab 13 — three boxes + a serial transcript
12. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
1. The whole system, and the one rule that holds it together
2. The latency budget for a safety action
3. The update message, and the apply path
4. The gauntlet ← centrepiece 1
5. What a structural check cannot see (the two-buffer shadow test)
6. Which artefact is dangerous to update (+ the score discontinuity)
7. When the sensor lies ← centrepiece 2
8. The validity gate: what it catches, what it costs, what it misses
9. Degraded modes, and what the log must contain
10. The device code
→ the protocol (12 steps), 8 exercises, references
## Reuse notes for Lecture 14
 
* **`results.json` is the single source of truth.** `make_figs.py` re-times the gate under
  MicroPython (median of 7 runs), so the number moves by a few µs each run — **rebuild the
  notebook and the deck after any figure change** or they will disagree.
* **The `cut()` pattern continues**: the notebook lifts real blocks out of `downlink.py`
  and `sensors.py` by their `def`/constant lines. The §3 cut must start at
  `TOPIC_MODEL = "@private/model"`, not at `def checksum(` — otherwise the module
  constants (`MAX_AGE_S`, `N_FEATURES`, `MIN_SD`) are missing and three cells fail.
* **`alarm_rate()` must honour the persistence rule.** A 9-of-5 rule parses, stores and
  scores perfectly and never raises; without the rule in the evaluation the gauntlet
  scores it "no harm" instead of "deaf".
* **Clipping must be detected against the *observed* extreme**, not the configured full
  scale, and the tolerance must be a few LSB — a 1 %-of-span tolerance false-rejects a
  third of healthy windows (measured).
* **Gate ordering matters**: dead-channel before clipped, or a stuck channel is reported
  as "clipped" (every sample is pinned).
* **The persistence-reset-on-commit story is not measurable on this data** (the new spec
  raises immediately, so the ring fills within 3 windows either way). The *score
  discontinuity* is the measurable version of the same lesson — use that.
* **Deck gotchas unchanged:** `defineLayout` for 13.333 in; callouts **w 11.55**; one-line
  bullets; and make sure the callout does not restate the figure's own caption (it did on
  two slides before the QA pass).
## What Lecture 14 inherits
 
* A complete working chain: sensor → gate → features → classifier + alarm → actuator →
  NETPIE → cloud → `@private/model` → validated, verified, committed spec → actuator.
* The device now keeps two ring buffers (`_quiet`, `_alarmed`) and a `last_good` slot, so
  it can test and undo its own updates.
* Eight degraded modes with a defined behaviour for each, five of which lose no
  protection at all.
* Notebook exercise 8 is Lecture 14's script: the student writes the sequence of events
  for the integrated run and, at each step, **what they would have to see to believe the
  system worked**. The lab sheet tells them to bring that list.
* The debrief question, given to them a week early: *which of the design decisions made
  across these seven weeks would you change in a real plant, and what would you need to
  know to decide?*

# Slide Notes

## Slide 1
Open by naming what is different about today. Lecture 12 ended with a refitted alarm specification sitting in Colab - twenty-five numbers, a threshold, a persistence rule and an expiry date - and it is completely useless there. Today it comes down. Then say the sentence that makes this lecture different from the five before it: the downlink is the only channel in this entire course that can make the machine LESS safe. Everything else either adds information or fails quietly. If the uplink breaks you lose visibility; if the dashboard breaks you lose a picture. If a bad specification lands on @private/model you lose the protection itself, and - this is the part to labour - nothing on the plant floor will tell you. The machine keeps running, the LED stays off, the dashboard stays green, and the alarm is deaf. Then set the two halves: first the downlink, where we will fire nineteen update messages at three different implementations and count how many leave the machine unprotected; second the sensor, where we will break the accelerometer four ways and watch a good model answer confidently and wrongly. Ask one question before slide 2: how would you know, this afternoon, whether the alarm on a machine in your lab still works? Almost nobody has an answer, and that discomfort is the right frame for the whole hour.

## Slide 2
Six lectures in one picture, so take a moment on each box and let them recognise their own work. The machine and its sensor, from Lecture 8. The device: a validity gate which is new today, then the twelve features from Lecture 8, the classifier from Lecture 9 and the alarm from Lecture 10, all running on the ESP32 since Lecture 11. The actuator hanging below the device, owned by the alarm alone, firing in about 129 milliseconds whatever else is happening. NETPIE and the cloud from Lecture 12. Then the red arrow, which is today. Make the asymmetry explicit and put it to the room as a question: which of these arrows can hurt you? The uplink can only lose information - a message dropped costs you one window of history. The dashboard can only be wrong on a screen. The downlink reaches into the thing that decides whether the machine gets protected, and a bad update there is silent. Then the division-of-labour rule in the banner, which they should be able to recite by now: fast and simple at the edge, slow and rich in the cloud, and the actuator never waits for either. Everything in the next hour is an elaboration of the third clause.

## Slide 3
Left panel, log scale, same visual language as Lecture 11's budget slide. Filling the window is 128 000 microseconds; the twelve features and the FFT are 1143; the new validity gate is 106; the classifier and alarm together are nine. Say the consequence out loud because it is counter-intuitive: optimising the code is NOT how you make this device respond faster. All the computing is about one per cent of the path. The only way to shorten the path is to shorten the window, and that costs frequency resolution - which is the Lecture 8 trade-off arriving in a new disguise. Right panel is the design tool. The device has spent 129 milliseconds of whatever the application allows. If the actuator must fire within 250 milliseconds of the defect, the entire round trip to a broker and back must fit in 120.7 milliseconds. Not on average - at the tail. At 15.6 windows a second, a design that works at the median and fails at the 99th percentile fails about fifteen times an hour. Ask the room what a plant WiFi round trip actually is; collect guesses, then tell them the honest answer is that nobody knows until they measure it, and that Lab 12 exercise 7 was that measurement. This table is why nothing in this course puts the cloud in the loop: the cloud proposes, the device disposes.

## Slide 4
Left, the message. Go field by field but keep saying WHY, because every one of these corresponds to something that has actually gone wrong in the field. The version field means the device refuses a schema it does not speak, instead of misreading it. The monotonic counter means an old message replayed on the topic cannot roll a fleet backwards. The timestamp and time-to-live enforce the expiry date that Lecture 10 wrote into the spec and that, until now, lived only in a wiki. The checksum catches corruption - and be precise here, because students will assume otherwise: it catches corruption, NOT malice. Anyone who can publish to the topic can recompute it. Say that this lecture deliberately leaves authentication out and that the reference list has where to read about it. And the approver field, because Lecture 12 showed a retrain can silently make things worse and somebody has to own that. Right, the apply path, and the order is not negotiable. Validate before staging, stage before verifying, verify before committing, and acknowledge whatever happens. The commit being a single pointer assignment is the oldest idea in embedded updates and it is what makes a power cut survivable. End on the sentence at the bottom: any of the five may refuse, and refusing is not a failure - the device keeps running the spec it already had.

## Slide 5
This is the first centrepiece; give it the time. Explain the experiment before the result: nineteen messages arrive on @private/model. Two are legitimate and must be accepted - insist on that, because a gate that refuses everything is not a gate, it is a disconnected wire, and students will otherwise optimise for zero acceptances. The other seventeen are things that have really turned up on a downlink topic: a number changed in transit, a truncated payload, a NaN, a zero standard deviation, a threshold of a billion, a threshold of zero, a nine-of-five persistence rule, features in a different order, a newer schema, a replayed old spec, a spec issued two hundred days ago and one issued forty days in the future. Then the measurement, and stress that it is not 'did it parse': it is whether the device still raises on a genuine spall and stays quiet on a healthy machine. Walk the first column. The one-line apply gets 4 of 19 right. Three crash on the first window - and those are the LUCKY ones, because a crash is visible. Three go deaf to a real spall and three flood the plant with alarms. Point at the deaf rows and say the sentence: these are the dangerous ones and they are also the quiet ones. Nothing on the device, the dashboard or the log says anything is wrong. Second column: 17 of 19 from about forty lines of range checking - an extremely good return. Then set up slide 6 by pointing at the two rows still coloured in the middle column.

## Slide 6
Two updates got through the structural gate. Read their properties aloud and let the room agree that nothing is obviously wrong with either: twelve finite means, twelve positive standard deviations, a threshold in range, a sane persistence rule, a fresh timestamp, a correct checksum. They are well formed. They are also wrong in opposite directions, and this is the pedagogically important pair. The first was refitted on data that included the fault - exactly the Lecture 12 mistake - so it has learned that a spalled bearing is normal and it will never raise again. The second was refitted during a heavy cut, so it has learned that a loaded machine is the baseline and it raises on everything. No amount of range checking finds either. The only thing that does is running the candidate before committing it. Now the code, and spend the time on why it needs BOTH buffers, because this is the part people get wrong: quiet windows catch the spec that will flood, and only retained ALARM windows catch the spec that has gone deaf - deafness is invisible on healthy data by construction. Then the payoff, which is worth pausing on: where does a device get a set of windows that made it raise? It kept them. Lecture 12's on-alarm-plus-context policy published a burst of raw feature vectors around every alarm, and the reason to keep a copy in RAM was never stated at the time. This is it. Ask how many windows you need - exercise 2 sweeps it.

## Slide 7
Put the question to the room before showing anything: here are two artefacts, one is 39 numbers and one is 25; which one would you gate harder? Almost everyone says the bigger one. Then the measurement. Swapping the classifier changed 3 per cent of the labels and nothing else at all - the actuator history is identical to the last transition. The classifier drives the log; a wrong label is a wrong word in a file. Swapping the alarm changed no labels whatsoever and rewrote the entire actuator history: 371 transitions became 241, and the fraction of windows under alarm went from 27 to 52 per cent. So the rule is: gate an update in proportion to what it can break, not to how big it is. Now the left panel, which is the second consequence and the one that bites six months later. At the moment of commit the reported anomaly score jumps by a factor of 3.4 - and the machine did not change at all. The two thresholds are almost identical; what moved is the baseline the z-score is measured against, so the number being compared to the threshold changed meaning. Anything that accumulates that score across a spec change is now telling a story that did not happen: Lecture 12's a_max in the heartbeat, the fleet trend, and every dashboard chart of the last two years. The fix is six bytes: carry the spec version in the uplink and re-baseline the history at each version boundary.

## Slide 8
Second centrepiece. Set it up by admitting what the course has assumed for six lectures: that the twelve features describe the machine. They describe the SIGNAL, and the signal comes from an accelerometer with a bolt, a cable, a bias, a full-scale setting and an adhesive bond, every one of which fails eventually. Four faults, none exotic. Walk them in order of increasing nastiness. The stuck channel produces the most confident classification in the whole course - the label is normal with a margin of 9.8, against 1.4 on a genuinely healthy machine, which is the Lecture 11 lesson about margins arriving from a new direction - while the alarm screams two thousand. Both models are wrong and the sensor is simply not connected. The loose mounting bolt is the nasty one: a sensor rattling on its own bolt produces sharp decaying impulses, which is exactly what we trained the model to find, so it calls a perfectly healthy machine bearing and raises on 29 per cent of windows. That is a work order, a strip-down, and nothing wrong with the bearing. Then the row to remember, and slow right down for it: a spalled bearing through a clipped sensor has kurtosis 1.79 against 2.23 for a healthy machine on a good one. The broken machine looks CALMER than health, and the alarm raised on zero per cent of windows. Clipping removes the peaks and the peaks are the fault, so a sensor that cannot see peaks does not make the fault noisy - it erases it. This is why 'the model will degrade gracefully' is false here: noise makes a model uncertain, a sensor fault makes it confident and wrong.

## Slide 9
Five comparisons on the raw window, before any feature is computed. Walk them and note that each catches a different physical failure: peak-to-peak below twenty milli-g is a dead or disconnected channel; more than one per cent of samples sitting within three LSB of the extreme is clipping, and note that this is deliberately tested against the OBSERVED extreme and not the configured full scale, because a signal can be clipped by an amplifier or a cable just as easily as by a wrong range setting; a large DC offset is a bias or mounting problem; an implausible rms catches the gain drift; and a missing shaft line means this is not a running rotor at all. Then insist on the sentence that makes this engineering rather than copying: every limit is a property of the INSTALLATION, not of the datasheet, and must come from that installation's own history - the same discipline as the Lecture 10 baseline. Copying these numbers to a different rig is the mistake the file exists to prevent. Right panel: 106 microseconds, about eight per cent of the pipeline, protecting all of it - the cheapest insurance in the course, and the false-rejection rate over thirty runs of healthy, imbalance and bearing machines is zero. Then be honest about the miss, because it is the most valuable part of the slide. The loose bolt gets through, and no sixth comparison will fix it: a rattling sensor produces a genuine impulsive vibration signal. Telling it from a bearing defect needs the repetition rate - a spall repeats at 3.6 times shaft speed, a loose bolt at whatever the mount wants - and that needs a tachometer or a cepstrum. So the honest architecture has three layers: the gate rejects what is cheaply impossible, the cloud's fleet comparison flags what is merely unlikely, and a human with a spanner closes the rest. That third step is not a failure of the design. It is the design.

## Slide 10
Walk the table, but group it rather than reading every row. The first five are green: the network drops, the broker refuses, an update fails validation, a committed spec misbehaves, the classifier is uncertain - in every one of those the device carries on protecting the machine, and that is the whole payoff of six lectures of local decision-making. The last three are different and the distinction is the point of the slide: when the sensor fails the gate, when feature extraction raises, or when the spec is past its expiry, the device is still SAFE - it holds its last actuator state - but it is no longer PROTECTING. Somebody has to know that. Say the rule plainly: hold and be quiet about it is the one behaviour that is never acceptable, because it is indistinguishable from working. Then move to the log, and frame it with a scenario rather than a list: it is four months from now, the line stopped for two hours, and somebody asks why. What do you need to have written down? Let them propose, then give the list: the window timestamp, the twelve features so the decision can be recomputed exactly, BOTH spec versions so you know which model decided, the verdict with its margin and driver, the gate result so you know whether the input was even trusted, and the actuator state before and after. For an update, the version, the decision, the reason and the approver. About two hundred bytes a decision, so you keep every event and a sample of the rest. A decision you cannot reconstruct is a decision you cannot defend.

## Slide 11
Part A is the downlink and should take two hours including the inevitable checksum argument - warn them now that MicroPython's json.dumps does not sort keys, so the cloud must canonicalise the payload before hashing it, and that if their checksums disagree this is why. They push one good spec and watch the five steps in the ack, then three broken ones of their own devising and record which gate caught each and what the reason string said. Insist the reason strings are in the report: a rejection without a reason is indistinguishable from a lost message. Part B is the one they will remember and it is the payoff of the entire course. With the new spec running, disconnect the WiFi in Wokwi and prove the device still detects and still actuates - the LED must still respond to wave_bearing with no network at all. Then reconnect and show the queued reports arriving. Tell them to record it; it is the single most convincing artefact they will produce all term. Part C is the sensor. They inject a stuck channel and a clipped range, record what the model said before adding the gate and what happened after, and then - the part that is actually being marked - defend one limit they changed, using their own machine's history rather than the numbers on slide 9. Remind them that copying my limits is the mistake the file exists to prevent, so a report that changes nothing and explains nothing loses those marks.

## Slide 12
Walk the strip: Lecture 12 sends statistics up, the cloud proposes and a human approves, the device validates, verifies, commits, gates its own sensor, and actuates locally whatever happens. Point at the dashed box and say the property that unifies the hour: every step in it is allowed to refuse, and none of it is in the actuator's way. Then the six rules. Spend the time on three, four and five. Rule three is the intellectual content - a structural check tells you an update is well formed, and well formed is not the same as right; the only test for right is running it, and you need both kinds of kept window. Rule four is the one they will get wrong in industry if they do not get it right here. Rule five is the cheapest thing in the whole course. Then set up Lecture 14, which is not a lecture but a session: the entire chain in one run - signal, features, edge inference, NETPIE, the cloud model, a spec coming back down, and actuation - with a fault injected halfway through and the WiFi pulled out somewhere they are not expecting. Tell them the debrief question in advance so they can think about it: which of the design decisions we made across these seven weeks would you change in a real plant, and what would you need to know to decide? Exercise 8 in tonight's notebook is the rehearsal - write the sequence of events and, at each step, what you would have to SEE to believe the system worked.

