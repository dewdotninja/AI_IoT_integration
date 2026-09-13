# Lecture 11 — Edge AI: putting the model on the ESP32
 
**01211271 Industrial AI and IoT** · built 2026-09-13 · follows Lectures 8, 9, 10
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture11_Edge_AI_on_the_ESP32.pptx` renamed to `iaiiot26_Lect11.pptx` | 12 slides (dark title, 10 light, dark summary), 13.333 × 7.5 in, speaker notes 1195–1614 chars on every slide |
| `Lecture11_Edge_AI_on_the_ESP32.ipynb` renamed to `iaiiot26_Lect11_nb.ipynb`| 53 cells, executed end to end, 0 errors, 0 stderr, ~6 s runtime |
| `Lecture11_Lab_Sheet.md` renamed to `iaiiot26_Lect11_Lab_Sheet.md` | 180 min, three parts (measure / deploy+verify / break it), marking scheme |
| `Lecture11_Wokwi.zip` | 12 files: 6 MicroPython modules, 4 waveforms, `diagram.json`, `expected_features.csv` |
 
Source directory `/home/claude/lecture11/`: `rig.py` (copied unchanged from Lecture 10),
`edge.py`, `make_device.py`, `make_wokwi.py`, `make_figs.py`, `build_notebook.py`,
`build_deck.js`, `results.json`, `figs/`, `wokwi/`.
 
## The design choice the instructor made
 
Asked whether to use cheap spectral features or a full on-device FFT, the answer was:
**implement the full 256-point FFT as the primary path, and provide the cheap path as a
documented fallback.** Both arms are built, measured and shipped. `features.py` is the
FFT path; `features_lite.py` is the fallback; the lecture teaches the decision between
them rather than asserting one.
 
## Running example
 
The same rotor rig. `rig.py` unchanged. Four 2-second waveforms generated at
`LAB_SEED = 41` (fresh runs — neither model has seen them), quantised to int16 exactly
as an ADC would, base64-encoded into MicroPython modules:
 
* `wave_normal`, `wave_imbalance`, `wave_bearing` (with `a_imp = 0.9`, a clear
  mid-severity spall)
* **`wave_unknown`** — the pedagogical centrepiece. `EXTRA = {"unknown":
  dict(a_struct=0.45, f_struct=330.0)}` applied to *normal* run parameters: a loose
  mounting bolt putting a large structural resonance where no training run had one. It
  exists in no training set anywhere in this course.
## Headline numbers
 
Measured under **real MicroPython 1.22.1** (installed via `apt install micropython`),
desktop build, median of 7 runs × 60 reps. These are in `results.json`; the deck and the
notebook both read from it.
 
| stage | µs/window | % of 128 ms |
|---|---|---|
| 7 time-domain features | 113 | 0.09 |
| 256-point FFT | 957 | 0.75 |
| 5 frequency features (incl. FFT) | 1040 | 0.81 |
| all 12 features | 1147 | 0.90 |
| 9 lite features | 357 | 0.28 |
| classifier (36 MACs) | 6 | 0.005 |
| alarm (12 z-scores) | 3 | 0.002 |
| **total** | **1156** | **0.90** |
 
**Ratios (the transferable part):** FFT/time **8.5×**, full pipeline/time **10.2×**,
lite/time **3.3×**.
 
**The design rule:** *if your Lab 8 time-feature measurement is under 12.5 ms, the full
twelve-feature pipeline fits the 128 ms window; between 12.5 and 40 ms, take the lite
path.* This is the number Lab 11 asks students to apply to their own board.
 
**Accuracy (8 shared splits, LinearSVC, tuned C, protocol from Lecture 9):**
 
| feature set | accuracy | paired vs full |
|---|---|---|
| 12 features (full FFT) | 0.880 | baseline |
| 7 time-domain only | 0.869 | −0.011 ± 0.009 |
| 9 lite (no FFT) | 0.881 | +0.001 ± 0.006 |
 
**This is the honest awkward result and the lecture is built around it.** The FFT buys
about one accuracy point for 8.5× the compute, and the two cheap substitutes recover all
of it. The stated reason for deploying the FFT anyway is **fidelity to the validated
model** — the Lecture 9 classifier and Lecture 10 baseline were fitted on those twelve
features, and switching means retraining and re-validating both. The transferable lesson
on the slide: *a cheap uninformative feature is an easy decision; the hard case is
expensive and mildly informative.*
 
**Export:** scaler fold 63 → 39 numbers, 24 ops → 0, exact to 2.2e-15 over 500 probes.
Alarm 25 numbers. `model.py` 1,764 B, `alarm.py` 2,608 B, all deployed code 16,426 B,
heap per inference **992 B and constant**, against the 200 KB budget set in Lecture 9.
 
**float32 vs float64:** worst feature `kurt` at 3.5e-07 relative (fourth moment).
`zcr` and `dom_freq` exactly 0. Compared against the smallest healthy margin (1.47) and
the alarm threshold (4.04) — single precision is fine, and we checked.
 
**The unknown-fault demo (the money slide):**
 
| wave | classifier | median margin | median alarm score | driver | windows raised |
|---|---|---|---|---|---|
| normal | normal | 1.47 | 1.6 | kurt | 0 % |
| imbalance | imbalance | 1.17 | 4.5 | rms | 93 % |
| bearing | bearing | 2.34 | 4.3 | kurt | 43 % |
| **unknown** | **normal** | **7.47** | **1289** | **dom_freq** | **93 %** |
 
The classifier is **5× more confident about the broken machine than about the healthy
one**, because an SVM margin is a distance from a hyperplane and not a probability of
being right. The alarm, trained on no faults at all, fires.
 
**Caveat that must be taught with it:** the score of 1289 is not severity. `dom_freq`
has a healthy standard deviation of ~0.23 Hz because a healthy spectrum peaks in the
same bin every time, so a few bins is hundreds of sigma for a small physical change.
Hence `alarm.worst_feature()` returns `(score, name)` — **report the name, treat the
number as "over threshold" and nothing more.**
 
## Deck outline
 
1. dark title — "Edge AI — putting the model on the ESP32"
2. Edge, cloud, or both — `fig_decide`
3. The budget is set by the sensor — `fig_budget`
4. Does the FFT earn its place? — `fig_cost`
5. Exporting a model — `fig_export`
6. Two tricks that cost nothing (fold + float32) — `fig_fold`
7. Does it fit? (flash and heap) — `fig_memory`
8. A fault the classifier has never seen — `fig_unknown`
9. Who owns the actuator — `fig_failsafe`
10. The whole device, in one loop — `codeBox`
11. Lab 11 — three boxes + serial-output codeBox
12. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
1. Edge, cloud, hybrid (bandwidth arithmetic: 4000 → 750 B/s, 5.3×)
2. The twelve features in plain Python (device `time_features`, the FFT, `freq_features`),
   verified against NumPy to 3e-08
3. What it costs (MicroPython table, CPython re-measurement, the design rule)
4. Does the FFT earn its place? (three feature sets, Goertzel + biquad source)
5. Exporting the classifier (the fold, proved; the generator)
6. Exporting the alarm (reciprocal σ, `worst_feature`, ring buffer)
7. What single precision costs
8. Two models, and a fault neither was trained on
9. Fail-safe: who owns the actuator
10. Does it fit? — then "The protocol" (10 steps), 8 exercises, references
## Reuse notes for Lecture 12
 
* **`results.json` is the single source of truth.** Both builders read it. Re-running
  `make_figs.py` re-runs the MicroPython benchmark and the numbers move by ~1 %, so
  **rebuild the notebook and the deck after any figure change** or they will disagree.
* **Name collisions in the notebook.** `rig.py` defines NumPy `time_features` and
  `freq_features` that take a *matrix*; the device versions take a *list*. The notebook
  captures `time_features_py` / `freq_features_py` immediately after the device cells and
  *before* `code(GEN)`. This bit twice during the build.
* **`_run_params` and `_synth` have leading underscores** and are not exported by
  `from rig import *`. Use `import rig; rig._run_params(...)`.
* **`array('f')` and module-level buffers** are the core embedded lesson: ~4.5 KB
  allocated once at import (`_han`, `_re`, `_im`, `_cos`, `_sin`, `_rev`).
* **Deck gotchas repeated from Lectures 8–10:** `defineLayout` for 13.333 in; callouts
  must be **w 11.55, not 12.1**, or they cover the page number at x 12.3; one-line
  bullets only (`h: 0.46`, `valign: "top"`); LibreOffice vertically centres text boxes.
* **Figure gotchas:** axis-off schematics need `xlim` ~3 units wider than the rightmost
  box or the last box is clipped by `bbox_inches="tight"`; in-bar labels on a linear
  scale overflow short bars — put the label above when the bar is under ~28 % of the
  y-range.
* **MicroPython is installed in the container** (`apt install micropython`, 1.22.1) and
  `make_wokwi.py` verifies the device features against NumPy before packaging. Keep that
  check.
## What Lecture 12 inherits
 
The device emits, every 64 ms: `label`, `margin`, `anom_score`, `driver`, `raised`, and
a per-window microsecond count. Publishing all of it at ~15 Hz is absurd — the reporting
policy (immediate / aggregated / on-change) is Lecture 12's opening problem, and
exercise 8 of this notebook is its warm-up. The framing to carry over: **the device is
already correct without the network, so the network is an optimisation problem rather
than a safety one.**

# Slide notes 

## Slide 1
Open by naming what changes and what does not. For three lectures the models have lived on a laptop with NumPy, scikit-learn and as much memory as they wanted. Today they move to a chip with 200 kilobytes of usable RAM, no NumPy, no double precision worth the name, and a deadline that does not negotiate: the sensor produces a new window every 128 milliseconds whether or not you have finished the last one. The models themselves do not change at all - it is the same classifier from Lecture 9 and the same alarm from Lecture 10. What changes is that every choice now carries a price you can measure in microseconds and bytes, and the measuring is the lecture. Tell them explicitly that today is the lecture where the course converges: Lecture 8 built the features on the device, Lecture 9 built a classifier, Lecture 10 built an alarm, and today all three run on the same chip at the same time. Ask the room one question before any slide: why not just send the raw signal to a server and run the model there, where there is a GPU and no memory limit? Collect answers - most will say bandwidth - and hold them for slide 2, where the answer turns out to be a different row of the table entirely.

## Slide 2
Walk the three columns first, then walk the rows, because the rows are where the argument lives. Latency: a device decision takes one window, 128 milliseconds; a cloud decision takes that plus a round trip to the broker, which on a factory WiFi is anywhere from 40 milliseconds to several seconds. Bandwidth: do the arithmetic aloud - the raw waveform is 2000 samples a second times two bytes, 4 kilobytes a second; twelve float32 features every 64 milliseconds is 750 bytes a second, about five times less, and the reduction is free because the device computed the features anyway in order to decide. Now the row that matters. If the network drops, the cloud architecture is blind - not slow, blind - and the machine it was protecting is unprotected. The edge and hybrid architectures keep deciding and report when the link returns. Put it to the room: which of these four rows would you defend to a plant manager? Most students pick bandwidth because it is quantitative. Push back gently - bandwidth is a cost you can pay, latency is usually tolerable, and availability is the actual requirement. The objection you will get is that factory networks are reliable. Ask what the consequence of the one outage a year is, and whether it is worth the saving. Close by naming the hybrid column as what this course builds: decide locally, report upward, and let the cloud hold the history and the retraining.

## Slide 3
The budget is not a preference, it is arithmetic: 256 samples at 2000 hertz is 128 milliseconds of signal, and a device that takes longer than that per window falls permanently behind its own sensor. On a chip with 200 kilobytes of RAM that is a crash with a delay fuse in it. Left panel: the profile, on a log scale. The seven time-domain features cost 113 microseconds, the 256-point FFT costs 957 - about 8.5 times as much - and the two models together cost 9, which is nothing. Make that last point deliberately: students expect the machine learning to be the expensive part and it is under one percent of the pipeline. The expensive part is the signal processing, as it almost always is. Now the honesty slide. Say plainly that this host is a desktop MicroPython build, tens of times faster than an ESP32 at 240 megahertz, and that the absolute numbers are useless to them. What transfers is the ratio, because it is a ratio of interpreter operations and the interpreter is the same one. Right panel turns that into something they can use on a board this lecture has never seen: multiply their own Lab 8 measurement by 10.2 and compare with 128 milliseconds. Ask the room what they measured in Lab 8 and work one of their numbers through live. Expected objection: why not just time the whole thing and skip the ratios? Because then the answer is only valid for the board in front of you, and the point of a design rule is that it survives a change of hardware.

## Slide 4
This slide does not say what a lecture about FFTs wants it to say, and that is why it is here. Left panel: twelve features score 0.880; the seven time-domain ones alone score 0.869, a paired difference of -0.011 plus or minus 0.009. So the whole frequency-domain half of the feature set is worth about one accuracy point. Right panel: it costs ten times the compute. And the third bar is worse news for the FFT - nine 'lite' features, computed with three Goertzel recurrences and one band-pass biquad and no spectrum at all, score 0.881, a difference of 0.001 plus or minus 0.006, which is a tie, for a third of the cost. Now ask the room the obvious question: so why are we deploying the FFT? Let them argue. The answer is not performance, it is provenance. The Lecture 9 classifier was trained, tuned and tested on those twelve features and the Lecture 10 baseline was fitted on the same twelve. Switching to the lite path means retraining both, re-validating both, and redoing Lecture 10's threshold study - real work, to buy compute we have just measured and do not need, since the full pipeline uses 0.9 percent of the window. Deploy the model you validated. Use the lite path when bench.py on your own board says the full one does not fit, and then say in the report that you retrained. The transferable lesson is the callout: the awkward case is not the useless expensive feature, it is the mildly useful one.

## Slide 5
Top strip is the pipeline, left to right: a fitted scikit-learn model, the JSON artefact Lecture 9 already wrote, the algebraic step on the next slide, a generated Python file, and 1.8 kilobytes on the device. Emphasise that the JSON step is not decoration - it is the boundary between the laptop world and the device world, and it means the device build never needs scikit-learn installed. Bottom two boxes are the part worth remembering. What exports: linear and logistic models, because prediction is one dot product; decision trees, because prediction is a path through if-statements with no arithmetic at all; small shallow ensembles. What does not: k-nearest neighbours, because the training set IS the model and you would be shipping the dataset; an untuned random forest, which is hundreds of trees and megabytes; and anything that allocates memory while predicting, which will fragment the heap and fail after a fortnight of running. Connect this back to Lecture 9 explicitly - we chose the linear SVM on a joint argument about accuracy and size, and this table is the second half of that argument arriving. Mention m2cgen by name: it generates C, Python and a dozen other languages from a fitted model and is worth knowing about, but for a linear model the generated code is about twenty lines, and writing the generator yourself means you know exactly what is in flash. Question for the room: which of the five Lecture 9 models could you deploy, and did we pick the best one or the most deployable one?

## Slide 6
Two device tricks on one slide, both free. First, the fold. A linear model on standardised features is a linear model on raw features - divide the weights by sigma and adjust the bias, and the standardiser disappears. Not 'is made faster': ceases to exist. Left panel: 63 numbers in flash becomes 39, twelve divides per inference becomes zero, twelve subtracts becomes zero. Stress that the notebook asserts the equivalence on 500 random probes and gets agreement at 2 times 10 to the minus 15, which is double-precision round-off - this is algebra, not approximation, and the assertion is in the build script so it can never quietly stop being true. Second trick, or rather second question: the ESP32 has single precision in hardware and double precision in software, which means it does not really have double precision. Everything in this course so far has been float64. Right panel: the worst feature is kurt at 3e-7 relative error, seven decimal places out, and kurtosis is worst because it is a fourth moment so the errors get raised to the fourth power too. Put that beside the numbers it feeds: the classifier's healthy margin is about 1.5 and the alarm threshold is 4.0. A seventh-decimal perturbation cannot move either decision. So single precision is fine here - and say firmly that we checked rather than assumed, because it is not always fine: sum over a million samples, or subtract two nearly equal large numbers, and float32 will bite. This is also why Lab 8 asked for agreement to three decimal places and not to eight.

## Slide 7
Left panel: every file we deploy, by size. features.py is the biggest at under 5 kilobytes and it contains a complete FFT. The two models together are 4.3 kilobytes - the classifier is 39 numbers, the alarm is 25. Right panel puts all of it against the 200 kilobyte budget we set in Lecture 9, on a log scale because otherwise three of the four bars are invisible. Nothing is close to the limit. Now spend the time on the third bar, the heap. One inference allocates 992 bytes, and the important word is not 'small', it is 'constant'. The FFT work buffers - about 4.5 kilobytes of arrays for the window function, the real and imaginary parts, the twiddle factors and the bit-reversal table - are allocated once at import and reused forever, so the loop churns no memory and the garbage collector has almost nothing to do. Make the failure mode concrete: a version that allocated those buffers inside the FFT would put 4.5 kilobytes of garbage on the heap every 64 milliseconds, run perfectly on the bench during your demo, and die of fragmentation about a fortnight later, at three in the morning, with a MemoryError nobody can reproduce. That is the single most common way embedded machine learning fails in the field. Ask the room how they would detect it before shipping - the answer is on the slide: print gc.mem_free() before and after one pass and check the difference does not grow.

## Slide 8
This is the slide the whole lecture has been walking towards, so give it time. We synthesise a fourth machine state - a loose mounting bolt, which puts a large structural resonance at 330 hertz where no training run had one - and feed it to both models. Left panel: the classifier's margin on each of the four recordings. On a healthy machine the margin is 1.5. On the loose bolt it is 7.5, and the label is 'normal'. Read that twice for the room. It is not merely wrong; it is more confident about a broken machine than about a healthy one. Then explain why, because students will think it is a bug. A linear SVM's decision value is a distance from a hyperplane, and a point far from every training example on the normal side gets a large distance. The model was asked 'which of these three?' and answered correctly - of the three, this is most like normal. Nobody told it there was a fourth option, and the margin is not a probability of being right. Right panel: the alarm scores it enormously and raises on 93 % of windows. It has never seen this fault either - but it was never asked to recognise faults, only to recognise healthy, and this is not that. Now the caveat, and do not skip it: the driver is dom_freq and the score is over a thousand. That is not severity. A healthy machine's spectrum peaks in the same bin every time, so the healthy standard deviation of dom_freq is a fraction of a hertz, and a shift of a few bins is hundreds of sigma for a small physical change. Report the feature name; treat the number as 'over threshold' and nothing more. That is exactly why worst_feature returns a name.

## Slide 9
Slide 8 settles a design question and this slide writes it down. When the two models disagree, the alarm acts and the classifier annotates. Say the reason carefully because it is a principle, not a preference: you are allowed to act on a quantity you have characterised. Lecture 10 measured the alarm's false-alarm rate on healthy data and set a threshold from a quantile; nobody has ever measured how often a classifier is confidently wrong about an input unlike anything it was trained on, and slide 8 showed why you cannot. So the dashed arrow on the diagram goes to the actuator box but does not touch it - the label goes in the log, next to the alarm state. Then walk the four failure rows underneath. If feature extraction raises - a bad sample, a divide by zero - hold the last actuator state, log the window, and do not guess. Put the alternative to the room: a device that drops to 'safe' on every glitch will trip the line on electrical noise, and one that drops to 'no alarm' fails silently; holding and logging is the compromise that survives a real plant, and the log is what tells you the glitches are becoming frequent. If the model raises, the alarm still runs and the label becomes model-error. If the margin is under 0.25 the label becomes 'uncertain' and the alarm is unaffected. And if the network is down, nothing changes at all - which is the row to end on, because it is the entire argument of slide 2 arriving as code.

## Slide 10
This is the whole device. Twenty lines, and every one of them has been argued for somewhere in this lecture. Walk it slowly. The read loop fills 256 samples, which is 128 milliseconds of signal - that is the budget, set by the sensor, not by us. The try/except around feature extraction is the fail-safe from slide 9: no features, no decision, hold the actuator. Then the two models, in the order that matters - classify first because it is cheap and goes in the log, then the alarm, then worst_feature for the driver name. The actuator is written only when the alarm state changes, which matters more than it looks: writing every window would chatter a relay to death in a week. And the timing check at the bottom is not debug code to be removed before shipping - it is the thing that tells you, in the field, on a board you cannot get to, that the device has stopped keeping up with its own sensor. Ask the room what is deliberately missing from this loop. The answer is the network. There is no WiFi, no MQTT, no broker, no publish - and the device is fully functional without any of them. That is the hybrid architecture from slide 2, and next week we add the reporting layer on top of a device that already works.

## Slide 11
Five hours, three parts, and part A must come first because everything else is an argument about numbers they have not measured yet. Part A: copy the wokwi folder into a project, run bench.py, fill in the stage table, and compute the two ratios - FFT over time-features, and whole pipeline over time-features. Warn them the ESP32 numbers will be tens of times larger than the ones on slide 3 and that this is expected; what they should compare is the ratios. Part B: flash main.py and run the three known waveforms. Insist on the verification step against expected_features.csv before they look at a single label - a device that computes the wrong features will still print confident labels, and this is the habit that catches it. Three decimal places, not eight, for the reason on slide 6. Part C is the interesting hour. Switch to wave_unknown and watch the classifier be confidently wrong while the alarm fires, then write a paragraph about what the device should actually do. There is no single right answer and that is the point - some will say alarm and name nothing, some will say alarm and report the driver feature, and a good answer will mention that the event should be logged for retraining. If a group's board cannot fit the FFT, that is not a failure, it is part C's other branch: they take the lite path and must state in the report that the model would need retraining, which is the honest engineering answer.

## Slide 12
Walk the strip first and point at the dashed box: fold, generate, measure, fail-safe - this lecture - and none of it needs a network. That is the sentence to leave them with. Then the six rules, and spend the time on one, five and six because those are the ones that transfer to any embedded project they ever do. Rule one is a discipline that costs twenty minutes and prevents the worst category of bug, the confident wrong answer. Rule five is the one that separates code that demos from code that runs: allocation per iteration, not peak memory. Rule six is the intellectual content of the lecture - two models that cost almost nothing together, each blind where the other sees. Then set up next week. The device now produces, every 64 milliseconds, a label, a margin, an anomaly score, a driver name and a raised flag. Publishing all of that at 15 hertz is absurd, and Lecture 12 is about the reporting policy: what goes up immediately, what is aggregated, what is sent only on change, and how NETPIE carries it. Point out that we can design that policy freely precisely because no decision depends on it - the device is already correct without the network, and the network is now an optimisation problem rather than a safety one. Exercise 8 in the notebook is the warm-up for it; ask them to attempt it before next week.


