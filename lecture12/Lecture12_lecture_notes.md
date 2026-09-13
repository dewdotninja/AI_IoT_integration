# Lecture 12 — The cloud side: NETPIE as data and model backbone
 
**01211271 Industrial AI and IoT** · built 2026-09-13 · follows Lectures 8–11
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture12_The_Cloud_Side_NETPIE.pptx`, renamed to `iaiiot26_Lect12.pptx` | 12 slides (dark title, 10 light, dark summary), 13.333 × 7.5 in, speaker notes 1205–1636 chars on every slide |
| `Lecture12_The_Cloud_Side_NETPIE.ipynb`, renamed to `iaiiot26_Lect12_nb.ipynb` | 54 cells, executed end to end, 0 errors, 0 stderr, ~12 s runtime, **runs offline with no broker** |
| `Lecture12_Lab_Sheet.md`, renamed to `iaiiot26_Lect12_Lab_Sheet.md` | 180 min, three parts (publish / subscribe+measure / dashboard+alert rule), marking scheme |
| `Lecture12_NETPIE.zip` | `net_pub.py` (MicroPython + umqtt.simple), `cloud_sub.py` (paho-mqtt), plus `netpie.py` and `cloud.py` for reference |
 
Source directory `/home/claude/lecture12/`: `rig.py` (extended), `netpie.py`, `cloud.py`,
`pkg/net_pub.py`, `pkg/cloud_sub.py`, `make_figs.py`, `build_notebook.py`,
`build_deck.js`, `results.json`, `figs/`.
 
## The instructor's choices for this lecture
 
* **NETPIE handling:** mock broker in the notebook + real NETPIE code in the lab package.
  `netpie.py` is an in-process stand-in with `+`/`#` wildcards, retained messages, a
  device shadow and an exact byte counter. Every notebook cell runs with no credentials
  and no network.
* **Centrepiece:** *both*, one per half — the publish-policy trade-off first, then what
  the cloud sees that the device cannot.
* **Scope:** keep to the outlined topics. The downlink and redeploy stay in Lecture 13.
## New generators in `rig.py`
 
* **`make_shift(seed=53, minutes=20, load_at_min=5, load_until_min=9, fault_at_min=12)`**
  — a *continuous* run of one machine returning the **feature stream**, not samples
  (18,300 windows, one every 64 ms). Synthesised in 4-second segments (`SHIFT_SEG`).
  Two events, and only one is a fault: a **heavier cut** at minute 5–9 (healthy) and a
  **bearing spall** from minute 12 with severity ramping 0.18 → 1.23.
* **`make_month_campaign(seed=61, n_machines=12, n_months=24, degrader=7,
  degrade_from=8)`** — monthly acquisitions from a small fleet with two superimposed
  effects: a **plant-wide ambient ramp** (`ambient = 1 + 0.38·u`, common mode, nothing
  wrong) and **one machine** degrading slowly (`sev = 0.15 + 1.35·frac`).
* **`build_month_table(runs)`** → `(X, machine, month, label, severity)`.
## Headline numbers
 
All in `results.json`; deck and notebook both read from it.
 
### Half 1 — the publish policy
 
Measured on-wire bytes through the mock broker, 20-minute shift, one machine.
 
| policy | msgs | feature msgs | bytes/hour | MB/machine/day | detect after onset | false alerts |
|---|---|---|---|---|---|---|
| every window | 18,300 | 18,300 | 9,832,215 | 236.0 | **0.03 min** | 0 |
| 1 in 16 | 1,144 | 1,144 | 614,833 | 14.8 | 5.29 min | 0 |
| on change + heartbeat | 31 | 0 | 9,784 | 0.23 | 6.00 min | 0 |
| on alarm + context | 87 | 56 | 39,866 | 0.96 | 6.00 min | 0 |
| **counting heartbeat** | **31** | **0** | **10,222** | **0.25** | **1.00 min** | 0 |
 
**The result the lecture is built on:** the counting heartbeat adds one integer `ni`
(windows this minute that alarmed with an impulsive driver) to the summary — about six
bytes — and takes detection from 6.0 min to **1.0 min at 962× fewer bytes than sending
everything**. Decimation is **Pareto-dominated**: on-change is cheaper *and* faster.
 
Generalisation for the board: *Lecture 11 — features go up, not waveforms. Lecture 12 —
**statistics go up, not samples.*** Detection latency of a counting heartbeat is **one
heartbeat interval**, whatever the window rate.
 
**Message sizes** (measured on a fixed representative window, `X_DEMO` in `make_figs.py`,
identical literal in the notebook so they cannot drift):
 
| message | payload | wire |
|---|---|---|
| verbose JSON | 349 | 363 |
| short keys | 165 | **179** |
| event | 86 | 100 |
| minute summary | 95 | 111 |
 
**The cloud's decision rule, one rule for all five policies:** alert on **3** messages in
**120 s** reporting an alarm whose driver is impulsive (`kurt`, `crest`, `e_hi`,
`e_bpfo`); a counting heartbeat contributes `ni` hits at once. The healthy load change
raises the alarm on **100 %** of its windows driven by `rms`, so the rule never sees it —
**that is the whole justification for `"d"` in the schema.**
 
### Half 2 — what the cloud adds
 
12 machines, 24 months; machine 7 degrades from month 8.
 
| detector | catches the degrader | healthy machines also flagged |
|---|---|---|
| edge alarm rate ≥ 0.25, two months running | month **19** (severity 1.14) | 0 |
| trend on own history only, ≥ 5 | month 13 | **5 of 11** |
| trend, fleet common-mode removed, ≥ 5 | month **13** (severity 0.60) | **0** |
 
**6 months of warning at half the spall severity — and only because the plant-wide
change was subtracted first.** The cloud's advantage is *context*, not model size.
 
### Retraining
 
| spec | threshold | false alarms (healthy, months 20–23) | alarms on the failing machine |
|---|---|---|---|
| Lecture 10 spec (fitted year 1) | 4.04 | 0.046 | 0.619 |
| refit on labelled-healthy recent | 4.55 | 0.017 | 0.225 |
| **refit on everything recent** | 5.09 | **0.015 (best)** | **0.107 (worst)** |
 
The deployed spec's false-alarm rate ages from 0.025 → 0.046. Retraining buys it back
*with detection*. Refitting on "everything recent" scores **best on false alarms and
worst as a detector** because the failing machine's own data was in the window — the
metric that improved is not the metric that matters (Lecture 10's opening mistake in
different clothes). Four gates: exclude what alarmed; hold out the future; re-measure
detection; write the expiry date.
 
## Deck outline
 
1. dark title — "The cloud side — NETPIE as data and model backbone"
2. What actually goes on the wire — `fig_schema`
3. Topics, the shadow, and retained messages — `fig_topics`
4. One shift, and two things happening in it — `fig_stream`
5. Bytes against delay — `fig_policy` ← centrepiece 1
6. A fixed threshold, on a healthy machine — `fig_alerts`
7. Keeping the history — `fig_history`
8. What the cloud sees that the device cannot — `fig_cloud` ← centrepiece 2
9. Retraining is not free — `fig_retrain`
10. The cloud subscriber, in one loop — `codeBox`
11. Lab 12 — three boxes + a `mosquitto_sub` transcript
12. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
1. How little can the device say? (bandwidth arithmetic)
2. The message (four schema rules; sizes measured on the wire)
3. NETPIE in one cell (the mock broker; topics, shadow, retained, wildcards)
4. One shift, five publish policies ← centrepiece 1
5. Dashboards: a fixed threshold against a model-based alert
6. Keeping the history (fleet-year arithmetic, the REST pull, the month campaign)
7. What the cloud sees that the device cannot ← centrepiece 2
8. Retraining and the four gates
9. The real thing (`net_pub.py`, `cloud_sub.py` as code to read)
   → the protocol (10 steps), 8 exercises, references
## Reuse notes for Lecture 13
 
* **`results.json` is the single source of truth.** Re-running `make_figs.py` re-runs the
  policy simulation; rebuild the notebook *and* the deck after any figure change.
* **Message sizes are pinned to a literal** (`X_DEMO` / `DEMO` in `make_figs.py`, copied
  verbatim into the notebook's §2 cell). Keep them identical or the deck and notebook
  will disagree by a few bytes.
* **`cut()` / `slice_src()` pattern** (as in Lecture 11): the notebook lifts real blocks
  out of `cloud.py` and `netpie.py` by their `def` lines, so the shipping code and the
  taught code cannot diverge. Section markers in those files are load-bearing — do not
  reword the `# ---- ...` comment banners without updating `build_notebook.py`.
* **The notebook needs module-level constants**, not just the functions: the §2 cell cuts
  from `SCHEMA_VERSION = 1` (not from `def q(`) so `TOPIC_*`, `IMPULSIVE`, `MIN_MARGIN`
  and `T0` come with it, and `FEATURE_NAMES` is defined literally because `rig.py` is not
  run until §4.
* **Event-driven publishing needs alarm management or it is a storm.** The Lecture 10
  3-of-5 persistence rule chatters ~15 Hz as a *reporting* rule. `policy_on_change` uses a
  32-window majority (`smooth`) plus a 15 s `dwell`, and triggers on
  `(raised, driver family)` rather than `raised` alone. Without the family term the
  detection measurement is meaningless.
* **Deck gotchas unchanged from Lectures 8–11:** `defineLayout` for 13.333 in; callouts
  **w 11.55** so they do not cover the page number; one-line bullets only.
* **Figure gotchas new here:** plot a **rolling median** (not mean) of the anomaly score —
  `dom_freq` z-scores saturate at ~34 and a mean smears them across the trace; give
  `axvspan` `zorder=0`; schematic axes need ~3 units of slack past the rightmost box.
## What Lecture 13 inherits
 
* A working uplink: `@msg/feat`, `@msg/event`, `@msg/summary`, `@shadow/data/update`,
  and a subscriber that writes `history.csv` and publishes to `@msg/cloud`.
* A **refitted alarm specification** produced by `refit_baseline()` — 25 numbers, a
  threshold, a persistence rule and an expiry date — sitting in Colab and useless there.
* The topic reserved for the downlink: **`@private/model`**, already drawn greyed-out on
  `fig_topics` and named in the notebook.
* Notebook exercise 8 is Lecture 13's opening problem: design that downlink message,
  choose its topic, and say what the device must do if it arrives corrupted or
  half-received.
* The framing to carry over: **the device is already correct without the network**, so the
  downlink must be an improvement that can fail safely — never a dependency.

# Slide Notes

## Slide 1
Open by describing where the course now stands, because it is a comfortable place and students should notice it. Lecture 11 left them with a device that decides for itself: every 64 milliseconds it produces a label, a margin, an anomaly score, the name of the feature that drove the alarm, and a raised flag - and it has no idea whether anybody is listening. Today it starts talking, and because the device is already correct without the network, the network is an optimisation problem rather than a safety one. Say that sentence slowly; it is the payoff for four lectures of work and it changes what kind of decisions today involves. Then set the two questions. First, how little can the device say and still be useful - which sounds like a bandwidth question and turns out to be a question about what a message should contain. Second, what can a subscriber with history and peers see that a device with one window and 200 kilobytes cannot - and we will put a number of months on the answer. Ask the room a question before slide 2: the device produces 15.6 decisions a second; how often should it publish? Collect answers. Most will say 'once a second' or 'when something changes'. Write both on the board and tell them slide 5 measures which is right, and that the answer is neither.


## Slide 2
Go field by field on the left, but spend the time on the four design rules rather than on the JSON. Version it: 'v': 1 costs six bytes and is the difference between a fleet you can upgrade and a fleet you cannot; without it, the day you add a field you have to reflash every device in the plant at once. Timestamp at the source: the broker's arrival time is not the measurement time, and the gap between them is exactly the quantity today is about. Round to what you measured: Lecture 11 showed float32 gives about seven significant figures and the features are noisier than that, so four is generous - sending eight is paying to transmit noise. Right panel is the measurement, and note out loud that it is the WIRE, not len(payload): the topic string goes with every single message. Self-documenting keys cost 184 bytes a message, which at 15.6 windows a second is about a quarter of a gigabyte a day of readability that nothing reads - the dashboard works from the schema document, not from the key names. Then point at how small the event and summary messages are: 100 and 111 bytes against 179. They are small because the device did the work. That observation is the whole of slide 5. Expected objection: 'short keys are unreadable.' Agree, and say the answer is a schema document in the repository, not longer keys in the firmware.


## Slide 3
Recap from the first half of the course, but with the ML use in mind. Four topics, and each one exists for a different reason. @msg/feat carries the evidence and is used in short bursts only - slide 5 explains why it is not the default. @msg/event says the situation changed. @msg/summary is the heartbeat, one a minute, and slide 5 will put the most important number in this lecture inside it. @shadow/data/update is different in kind and that difference is worth labouring: a message is an event in a stream, the shadow is a current value. The dashboard tile that says what the machine is doing right now should read the shadow; if it reads the message stream it has to replay history to draw one panel, and it will be slow and wrong after every broker restart. Retained messages are the third piece: the broker keeps the last message on a topic, so a dashboard that opens at nine o'clock still sees the 08:59 state instead of a blank panel. Then the subscriber side. Show the wildcard filter and explain that plus matches exactly one level and hash matches everything below, so one cloud service can take every machine's traffic and the device id arrives as part of the topic - there is no need to put it in the payload as well. Finally point at the dashed arrow coming back and say it out loud: that is the downlink, that is how a new threshold reaches the device, and it is next week. Everything today is one direction.


## Slide 4
Lectures 8 to 11 worked in four-second acquisitions. A deployed device does not take acquisitions, it runs, so rig.py gains one more campaign: twenty minutes continuous. Two things happen and only one of them is a fault. Top panel: the anomaly score, smoothed, on a log axis. The yellow band is a heavier cut - the operator is working the machine harder and the machine is completely fine. The red line at minute 12 is a bearing spall starting, faint at first and growing. Ask the room which of the two events the alarm from Lecture 10 fires on. The answer is both, and the healthy one harder: 100 per cent of windows during the cut, driven by rms, against 17 per cent after the spall, driven by kurt. Let that land, because it looks like a failure of the alarm and it is not - the alarm was asked whether this window looks like a healthy machine, and during a heavy cut it honestly does not. What separates them is not the score, it is which feature moved. That is why Lecture 11's worst_feature returns a name and why 'd' is in the schema. Bottom panel is the preview of slide 5: every tick is one message, four policies stacked. Do not give the numbers away yet - just let them look at the density and ask which row they would be willing to pay for.


## Slide 5
This is the slide. Take it slowly and in the order the points fall. First fix the cloud's rule, because the comparison only means anything if it does not change between policies: alert on three messages within two minutes reporting an alarm whose driver is impulsive. Three not one, because the spall is faint at onset and kurtosis is a fourth moment. Impulsive-only, because slide 4 showed the healthy cut raises the alarm with rms. Now the results. Every window: 236 megabytes a day per machine, detects immediately. One in sixteen: sixteen times cheaper, 5.3 minutes slower - which sounds like a reasonable trade until the next row. On change plus heartbeat: 31 messages in twenty minutes instead of 18,300, about 1004 times fewer bytes, and it detects SOONER than decimation. Stop there and make the point: decimation is not on the frontier at all, it is simply worse on both axes, and it is the first thing almost everyone reaches for. Then the answer. The counting heartbeat sends the same 31 messages and adds one integer to the summary - ni, how many windows this minute alarmed with an impulsive driver. Six bytes. Detection goes from 6.0 minutes to 1.0, at 961 times fewer bytes than sending everything. Say the generalised rule and write it on the board: Lecture 11 said features go up not waveforms; Lecture 12 says statistics go up not samples. And the latency is one heartbeat interval whatever the window rate, which makes it a design knob rather than an accident. Objection to expect: 'but the cloud cannot run its own model on a count.' Correct - that is what the on alarm plus context row is for, and slide 8 needs it.


## Slide 6
Left panel: a fixed threshold on rms, set at the 99.9th percentile of a quiet start, which is how a careful person would set it. It fires on 100 per cent of the healthy heavy cut. Be concrete about the consequence - a maintenance team paged for a machine that is working correctly will have muted that alert within a fortnight, and then it is not protecting anything. Note honestly that the same threshold does eventually catch the spall, on about half the windows from minute 15 - it is not useless, it is indiscriminate. Right panel is the same alarm split by what drove it. Grey is every alarmed window; red is the ones with an impulsive driver. During the cut: zero red. After the spall: red and growing. One field separates them. Be fair about what the model-based rule gives up: it fires on fewer of the spall windows than the raw threshold does, because rms genuinely rises as the bearing degrades. But the cloud's rule needs only three pieces of evidence in two minutes, so a lower per-window rate costs nothing, while a hundred per cent false rate on a healthy cut costs the whole system its credibility. Then the design instruction, which is the practical takeaway: build the dashboard so the first thing anyone sees is the driver, not the score. A technician sent to a machine with 'score 6.4' has been told nothing; one sent with 'impulsive, kurt, six windows a minute and rising' has been told where to put the stethoscope.


## Slide 7
Two halves. Left: storage, on a log scale because otherwise four of the six bars are invisible. A year of 40 machines is 5,045.8 gigabytes of raw waveform, 3,445.21 of every-window JSON, and about 3.6 gigabytes under the counting heartbeat. But make the point that this is NOT simply 'smaller is better', because the cheap policies also keep the least. On change plus heartbeat keeps no feature vectors at all, which means next year's retraining has nothing to fit on. On alarm plus context keeps a few thousand windows from exactly the moments that mattered, for four times the bytes, and that is usually the right answer. Right: the collect-to-retrain pipeline. NETPIE keeps a data feed you pull over its REST API with a device id and a time range; the notebook shows the request. Then one CSV per machine, then a training table, then a refitted spec - which is 25 numbers and a date, exactly the artefact Lecture 10 produced. Ask the room: if you were only allowed to keep one gigabyte a year per machine, which windows would you keep? A good answer names the alarmed periods AND a random sample of healthy ones, because a training set of nothing but alarms cannot teach a model what normal looks like.


## Slide 8
Set the scene first. Twelve machines, one acquisition each per month, two years. Two things are superimposed: the plant-wide ambient level creeps up as the building fills with new equipment, and one machine develops a spall so slowly that no single monthly acquisition looks alarming. Telling those apart is the whole argument. Three detectors. The edge alarm alone - how often each machine alarmed, by month - finds it in month 19 with no false alarms, and that is a perfectly respectable detector needing no cloud at all. A trend on each machine's own history finds it in month 13, six months earlier, and also flags 5 of the eleven healthy machines - the red lines on the right panel - because a plant-wide ambient rise looks exactly like slow degradation when you have nothing to compare against. Hand a maintenance team that list and they stop trusting the system. The same trend with the fleet's common mode subtracted finds it in month 13 with zero false machines. Read the severity numbers aloud: 0.6 against 1.14 - roughly half the damage. Then the sentence to remember: the cloud's advantage is not a bigger model, it is context - history to compare against and peers to subtract. The heavy model can come later; the context is free and it was worth six months. Objection to expect: 'what if the whole fleet degrades together?' Excellent question - then the fleet reference hides it, and you need an absolute reference too. Say so.


## Slide 9
Start with the ageing, because it is the reason anybody retrains: the deployed spec's false-alarm rate on healthy machines has gone from 0.025 in year one to 0.046 by year two, roughly double, and nothing is wrong with the machines. Now the three candidate specs on the left, and read the pairs of bars rather than the bars. The original spec: false alarms 0.046, alarms on the genuinely failing machine 0.619. Refit carefully on labelled healthy history: false alarms fall to 0.017 - good - and detection falls to 0.225. That may be the right trade, but it IS a trade and it has to be stated. Then the third bar, which is the trap. Refitting on everything recent - the natural thing to write, since recent data is what the machines look like now - gives the best false-alarm rate on the whole slide and the worst detector on it, because the failing machine's own data was in the training window and the new baseline learned that a spalled bearing is normal. Say the sentence: the metric that improved is not the metric that matters. Point out that Lecture 10 opened with exactly that mistake wearing different clothes - accuracy 0.880 from a model that never predicts a fault. Then the four gates on the right, and insist on gate three in particular: a spec that only improved its false-alarm rate has not improved. Close by saying the new spec still has to reach the device, which is a downlink, which is next week.


## Slide 10
Walk the code and connect every line to a slide. json.loads and append_csv: keep everything, because slide 7 said you cannot retrain on what you threw away, and the CSV is what section 6 of the notebook reads. The evidence count is the clever line - a feature or event message contributes one piece of evidence if it reports an alarm with an impulsive driver, and a counting heartbeat contributes ni, a whole minute of them, which is how slide 5's six bytes turn into five minutes of latency. The deque and the while loop are a rolling two-minute window, three lines and no dependency. And the publish at the bottom goes to @msg/cloud, a topic the device does not subscribe to. Make that explicit: this service never decides anything the machine depends on. The device drives its own actuator on its own alarm, exactly as Lecture 11 specified; the cloud is a second opinion with a longer memory. If this process dies, the machine is still protected - which is the property that made today an optimisation problem. Ask the room what is missing from this file that a production version needs. Good answers: reconnection handling, a bound on the CSV, a clock-skew check on 't', and some way of knowing that a device has gone silent - which is what the heartbeat is for and which this code does not yet use.


## Slide 11
Part A is plumbing and should take an hour. They add net_pub.py next to the Lecture 11 files, fill in four constants from their NETPIE device page, and call Publisher.feed from the main loop. Insist they verify with mosquitto_sub or the NETPIE console before believing anything - a publish that silently fails looks exactly like a quiet machine, which is the failure mode the heartbeat exists to catch. Part B is the interesting hour. cloud_sub.py in Colab, watching the evidence counter tick, then switch WAVE to wave_bearing on the device and watch an alert appear. Then have them measure their own bytes per hour for two policies - the easiest way is to count publishes and payload lengths in the firmware, which also teaches them that the topic string is part of the cost. Part C is where the judgement is. A dashboard with three panels: the raw features, the device's own verdict, and the cloud's alert. Warn them the temptation is to plot all twelve features and call it done; push for a layout where the driver name is the most prominent thing on the screen. The written deliverable matters more than the screenshot: an alert rule they would defend to a maintenance manager, with a sentence on why it is not a threshold on rms. Accept any defended answer, including a threshold, if they can say what it costs during a load change.


## Slide 12
Walk the strip and point at the dashed box: schema, policy, NETPIE, history, context - all of it one direction, all of it uplink. Then the six rules, and spend the time on three, four and five. Rule three is the one that saves the most and is skipped the most; rule four is the intellectual content of the lecture and generalises far beyond this course - when the edge can compute a statistic, send the statistic; rule five is the one that will still be true when NETPIE and MQTT have been replaced by something else. Then set up next week properly, because Lecture 13 closes the loop the course opened in Lecture 8. They now have a refitted alarm specification sitting in Colab: 25 numbers, a threshold, a persistence rule and an expiry date. It is useless there. Next week it comes down over MQTT on @private/model, the device applies it without being reflashed, and then - the part they will enjoy - we disconnect the WiFi in Wokwi and confirm the machine is still protected. Ask them to attempt exercise 8 before next week: design the downlink message, choose its topic, and say what the device must do if it arrives corrupted or half-received. That last clause is the whole of Lecture 13 in one question.


