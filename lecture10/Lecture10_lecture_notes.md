# Lecture 10 — build notes and reuse guide
 
**Topic:** Evaluation and Anomaly Detection
**Course:** 01211271 Industrial AI and IoT, lectures 8–14 (AI and integration half)
**Session format:** 5 hours — ~2 h lecture, ~3 h lab (laptop only)
**Built:** September 2026
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture10_Evaluation_and_Anomaly_Detection.pptx` | 12 slides, 13.333 × 7.5 in, speaker notes 1118–1361 chars on every slide |
| `Lecture10_Evaluation_and_Anomaly_Detection.ipynb` | 41 cells, executed end to end, zero errors, zero stderr, ~11 s runtime; 8 exercises + real references |
| `Lecture10_Lab_Sheet.md` | Parts A/B/C, deliverables, marking scheme, traps table, look-ahead to Lecture 11 |
| `lecture10_alarm.json` | the alarm spec: 25 numbers, a 3-of-5 persistence rule, an expiry date — **the second input to Lecture 11** |
| `source/` | `rig.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `results.json`, `figs/` |
 
Rebuild order: `make_figs.py` → `build_notebook.py` (then execute) → `build_deck.js`.
 
---
 
## Changes to `rig.py`
 
Backwards compatible — `make_dataset(seed=7)` still reproduces the Lecture 8/9 table
exactly (verified against the mean of `rms`).
 
* **refactored** `make_run` into `_synth(rng, params, …)` + a thin wrapper, so every
  campaign shares one waveform synthesiser. `make_speed_sweep` now routes through it too.
* **added** `make_fleet(seed=23)` — 150 runs, **132 normal / 12 imbalance / 6 bearing**.
  Fault severity is drawn wider than in Lectures 8–9 (`a_1x` U(0.42, 1.10) for
  imbalance, `a_imp` U(0.22, 1.40) for bearing) so that incipient faults exist.
  Returns runs shuffled, each with a `severity` field.
* **added** `make_drift_campaign(seed=31, n_months=48, fault_from=42)` — one healthy
  machine measured monthly, with `noise` 0.06→0.11, `a_struct` 0.04→0.085,
  `f_struct` 180→290 Hz and `gain` 1.00→1.10 over four years, then a real spall
  (`a_imp = 1.10`) from month 42.
**Prevalence is tuned, not arbitrary.** 132/150 = **0.880**, deliberately equal to
Lecture 9's best model accuracy. The opening slide depends on those two numbers being
identical — if you change the counts, the hook breaks.
 
---
 
## Headline numbers (all from `results.json`)
 
### Supervised, on the fleet
 
| quantity | value |
|---|---|
| majority-class ("always normal") accuracy | **0.880** |
| linear SVM (C = 0.0032, out-of-fold) accuracy | **0.983** |
| bearing recall / precision / F1 | **0.577** / 1.000 / 0.731 |
| imbalance recall | 1.000 |
| confusion: bearing windows called normal | 155 of 366 |
| with `class_weight='balanced'` | recall 0.740, precision 0.839 |
| class-weight sweep, w = 1 → 100 | recall 0.577 → 0.839, precision 1.000 → 0.507 |
 
### Cost asymmetry (bearing-vs-rest score)
 
| cost ratio | best threshold | recall | false alarms | cost / 1000 windows |
|---|---|---|---|---|
| default (t = 0) | 0.000 | 0.555 | 0.000 | — |
| 10 : 1 | −0.622 | 0.822 | 0.029 | 99 (vs 178 at default) |
| 100 : 1 | −0.952 | 0.962 | 0.270 | 413 (vs 1781 at default) |
 
The 100:1 answer demands a **27 % per-window false-alarm rate**. This is correct and
operationally unusable, and the lecture says so — it is the setup for the persistence
rule.
 
### Cross-validation
 
| | mean | sd | folds |
|---|---|---|---|
| plain KFold over windows | 0.593 | 0.062 | 0.60, 0.50, 0.62, 0.68, 0.55 |
| StratifiedGroupKFold over runs | 0.592 | **0.342** | 0.49, 0.50, 0.93, 0.98, 0.05 |
 
Bearing runs per grouped fold: 1, 2, 1, 1, 1.
 
### Anomaly detection (fitted on healthy windows only)
 
| detector | ROC-AUC | recall @ 99th pct | imbalance recall |
|---|---|---|---|
| mean ± kσ (max abs z) | 0.959 | 0.514 | 0.993 |
| isolation forest | **0.963** | **0.577** | 0.954 |
| PCA residual (7 of 12 components, 95 % variance) | 0.943 | 0.637 | **0.557** |
 
### The persistence rule (max ± kσ detector at the 99th percentile)
 
| rule | FA / window | bearing recall | healthy machines alarmed | added delay |
|---|---|---|---|---|
| 1-of-1 | 0.0101 | 0.514 | **25.0 %** | 0 ms |
| 2-of-3 | 0.0029 | 0.500 | 6.8 % | 128 ms |
| **3-of-5** | **0.0004** | **0.492** | **1.5 %** | 256 ms |
| 4-of-7 | 0.0000 | 0.475 | 0.0 % | 384 ms |
 
### Drift
 
| | healthy months 12–41 | months 36–41 | the real spall |
|---|---|---|---|
| threshold fixed in year 1 | 0.212 | **0.478** | 1.000 |
| baseline re-estimated monthly | **0.066** | — | 1.000 |
 
---
 
## The four arguments the lecture makes
 
1. **Accuracy is a prevalence measurement in disguise.** 0.880 from a model that never
   predicts a fault; 0.983 from one that misses 42 % of spalls. The identity with
   Lecture 9's headline number is the hook.
2. **The threshold is where engineering judgement enters the pipeline.** A stated cost
   ratio determines it; class weights move you along the same curve without adding
   information.
3. **Zero fault labels cost you almost nothing here.** The isolation forest matches the
   supervised bearing recall (0.577) having never seen a fault — at 1 % false alarms
   the supervised model does not pay, and without the ability to name the fault. Stated
   with both caveats on the slide.
4. **The cheapest improvement in the lecture is not machine learning.** A 3-of-5
   persistence rule cuts the fraction of healthy machines raising a nuisance alarm from
   25 % to 1.5 %, for 0.022 of recall and 256 ms. This lands as the Lab 10 centrepiece.
---
 
## Findings that changed the planned design
 
* **The CV slide was going to be about leakage inflation. It is not.** Plain KFold and
  grouped CV give the *same mean* (0.593 vs 0.592) because a heavily regularised linear
  model has almost no capacity to memorise a run. The slide was rebuilt around the
  **spread** (sd 0.062 vs 0.342), which is a better and non-repeating lesson. The
  incidental finding — leakage hurts flexible models most — is in the notes.
* **PCA reconstruction error is nearly blind to imbalance** (0.557 vs the isolation
  forest's 0.954) because imbalance scales a direction the healthy data already varies
  along, so it reconstructs perfectly. Kept as the honest nuance, not tuned away.
* **The first version of §10 drew an unlucky holdout fold** (bearing recall 0.049 — it
  contained the faintest spall) and made the alarm spec look broken. Rewritten to use
  the out-of-fold scores across the whole fleet, which is also what a real spec would
  quote.
* **The drift "fix" needs an exclusion rule.** A naive trailing-window re-estimate
  absorbs the fault from the second month onward and the recall collapses. The working
  version admits a month to the baseline only if its alarm rate was below 0.20. The
  trap is called out explicitly in both notebook and notes.
* **`make_drift_campaign` drift magnitudes were halved** from the first attempt; the
  original values made a 12-month rolling window non-stationary and the fix looked as
  bad as the problem.
---
 
## Build gotchas hit and fixed
 
* **`IsolationForest(200, …)` fails in sklearn 1.8** — `n_estimators` is keyword-only,
  unlike `RandomForestClassifier`.
* **Invented numbers crept into the no-labels schematic** (62/12/22 %). Removed; the
  figure now says "(proportions illustrative)" and carries no percentages.
* **A JS template literal was closed with `" +`** in the slide-10 notes, which node
  reports as `missing ) after argument list` many lines later. When patching
  `build_deck.js`, keep each notes block entirely in one quoting style.
* **Do not patch `build_*.py` with a Python heredoc containing `'''`** — it terminates
  the outer string. Write the patch to a file instead.
* Long single-line `fig.text` captions inflate the tight bbox and shrink the plotted
  area once the figure is fitted to a slide band — wrap to two lines with `va="top"`.
  (Same trap as Lecture 9.)
---
 
## Hooks into Lecture 11
 
Students arrive with **two** artefacts, and the contrast is deliberate:
 
| | `lecture9_model.json` | `lecture10_alarm.json` |
|---|---|---|
| size | 63 numbers | 25 numbers + a 3-of-5 rule |
| needs | labelled faults | healthy data only |
| says | which fault | that something changed |
| expires | — | `review_after_months: 12` |
 
The deck's closing note sets Lecture 11 up as: export both with m2cgen, measure
inference time against the 128 ms window budget from Lab 8, and close the loop on the
device that produced the features.
 
The hybrid-architecture argument is already seeded: **mean ± kσ is the detector that
fits on an ESP32 (25 numbers); the isolation forest's 200 trees stay in the cloud.**
That is the concrete justification for the hybrid design the course committed to in the
Weeks 8–14 outline, and Lectures 12–13 should pick it up directly.

# Lecture 10 slide notes

## Slide 1
Open by taking something away. Lecture 9 ended with a linear SVM at 0.880 and a feeling that the hard part was done; today removes both the score and the comfort. Say the structure plainly: the first half is evaluation - what accuracy hides and how to choose an operating point - and the second half is the situation every real plant is actually in, which is plenty of healthy data and almost no labelled faults. Then flag the change of dataset and say why it matters, because students will otherwise think we just swapped files. Lectures 8 and 9 used sixteen runs of each fault, perfectly balanced. No factory has that. Today is a fleet: 150 acquisitions across a year, of which twelve are imbalance and six are bearing spalls, and the fault severities now run from incipient to severe, because the spall worth catching is the faint one. Warn them the first slide is designed to be uncomfortable and that the number on it will look familiar. Ask the room, before showing anything: if I tell you a fault detector is 98 % accurate, what have I actually told you? Collect a couple of answers and hold them until slide 3.


## Slide 2
Left panel: the fleet. 132 healthy acquisitions, 12 imbalance, 6 bearing spalls - read the counts aloud and let the asymmetry land. Say that this is not a pessimistic simulation, it is roughly what a year of monitoring on a real fleet looks like, and that if anything six spalls in 150 acquisitions is generous. Right panel is the whole point of the slide. This is the confusion matrix of a classifier that always says normal. It has one column. It has never predicted a fault. Its accuracy is 0.880. Now connect it: Lecture 9's best of five tuned models scored 0.880 on balanced data and we were pleased. The numbers are identical and one of them came from a model that does no work at all. Explain the arithmetic - accuracy is the fraction of windows you get right, and when 88 % of windows are healthy, getting the healthy ones right is worth 0.880 on its own. Give them the rule as a habit: compute the majority-class accuracy first, every time, and treat it as the floor. Expected objection: 'but our real model will do better.' It will - slide 3 shows it scoring 0.983 - and that is where the argument gets interesting.


## Slide 3
The real model now. Same linear SVM, same C from Lecture 9, only the dataset changed. Accuracy climbed from 0.880 to 0.983, which looks like a triumph until you read the bottom row. Walk the matrix row by row, not cell by cell: normal, perfect; imbalance, perfect; bearing, 211 caught and 155 called normal. Point at the red box. Then define the two words carefully, because students routinely swap them. Recall answers 'of the spalls that happened, how many did we catch' - 0.577. Precision answers 'of the alarms we raised, how many were real' - 1.000. Make them say which one a maintenance manager cares about and why the answer is 'both, for different reasons'. Now the mechanical point, which stops this looking like a quirk of the simulator: imbalance is easy because a trial mass moves a lot of metal and puts a big peak where we already have a feature. An incipient spall is a small amount of energy delivered sharply, overlapping the structure. The fault that is hardest to detect is usually the one worth most, because catching it early is the entire value proposition. Close with the habit: a confusion matrix is one line of code and cannot be argued with.


## Slide 4
Two ingredients are needed to choose an operating point: a continuous score instead of a hard label, and a cost ratio. The score is decision_function - how far a window sits on the bearing side of the boundary - and the default prediction is simply score greater than zero, which is the dashed line. The cost ratio is an engineering input, not a statistic: if a missed spall destroys a gearbox and a false alarm costs an hour of a technician's time, the ratio is large. Tell them to ask the maintenance manager and write down the answer rather than guessing. Left panel, log scale: at 10 to 1 the minimum sits at 0.82 recall and 2.9 % false alarms, an operating point a plant would accept. At 100 to 1 the arithmetic demands 96 % recall and accepts a 27 % false-alarm rate. Stop there deliberately. That 27 % is the correct answer to the question we asked and it is unusable as stated - nobody actions an alarm that fires on a quarter of all windows. The resolution is that the alarm is per machine, not per window, and slide 11 gives the fix. Right panel: every threshold is a point on one curve, and the default is just one of them. Ask: who in your organisation should be choosing this number? The answer is not the data scientist.


## Slide 5
Left panel: as the weight on the bearing class rises from 1 to 100, recall climbs from 0.577 to 0.839 and precision falls from 1.000 to 0.507. Read both lines together and name the trade out loud, because students often see the rising orange line alone and conclude weights are free. Right panel is class_weight balanced as a confusion matrix, so they can compare it directly with the previous slide. Now the conceptual point, which is the one worth remembering. Class weights did not teach the model anything new about bearing spalls. They moved it along exactly the same precision-recall curve the threshold moved it along on the previous slide. Plot the weighted models on that curve and they land on it, not above it. So when do you use which? Threshold: when you have a score and want to pick an operating point after training - cheap, reversible, and changeable on the device in Lecture 11 without re-exporting anything. Class weight: when the optimiser itself is being swamped and the fit ignores the rare class entirely. Note the accuracy column barely moves across the whole sweep - a last nail in accuracy's coffin.


## Slide 6
This slide will surprise you if you are expecting Lecture 8's leakage story again, so set it up honestly. The two means are almost identical - 0.593 against 0.592 - which means plain KFold did NOT inflate the score here. Say why, because it is a real lesson: a heavily regularised linear model has almost no capacity to memorise which run it is looking at, so leakage has little to exploit. Leakage hurts flexible models most. Now the spreads, which is where the slide earns its place. Plain KFold reports a comfortable sd of 0.06 and five folds that all agree. Grouped, the folds run from 0.98 down to 0.05 - one fold caught nearly every spall, another caught almost none - with an sd of 0.34. The right panel explains it: each grouped fold contains one or two bearing runs, so each fold's recall is measured on one or two machines. The honest conclusion is uncomfortable and worth stating slowly: our recall estimate is worth roughly plus or minus 0.3, not plus or minus 0.06, and the tight KFold number was an artefact of testing on windows whose siblings were in training. Ask the room what they would write in a report. The answer is the mean AND the spread, and a sentence saying it rests on six machines.


## Slide 7
Pivot slide, and worth slowing down for because it reframes the second half. Ask where the label column came from. Somebody ran a machine with a known spall in it, or found the maintenance record afterwards and matched it to the right week of data, hoping the data had not already been overwritten. Now describe what a plant actually has after a year: thousands of hours of healthy running that nobody labelled because the machine simply did not break; a handful of known failures, usually noticed too late to keep the data; and a large middle ground that nobody wrote anything down about. Supervised learning needs the one part nobody has. Then the reframe: anomaly detection asks 'is this machine behaving as it always has?' instead of 'which of these three faults is this?', and that question can be answered from healthy data alone. Put the trade on the board as two columns. Supervised catches the faults you trained on and can name them, and is blind to a failure mode it has never seen. Anomaly detection notices anything unusual and cannot name any of it. Ask the room which they would deploy first on a new machine with no history. Almost every real monitoring system starts as an anomaly detector for exactly this reason.


## Slide 8
Name the three mechanisms before reading any numbers. Mean plus or minus k sigma: standardise with healthy statistics, score each window by its largest absolute z-score - what an engineer builds by hand, and the baseline the others must beat. Isolation forest: random splits isolate unusual points in fewer cuts, assumes nothing about the shape of the healthy region. PCA reconstruction error: project onto the principal directions of healthy data - 7 of twelve components here, chosen to keep 95 % of the variance - project back, and measure what did not survive. That is a linear autoencoder, same idea as the neural version but explainable. Left panel: the healthy and faulty score distributions with the 99th-percentile line. Right panel is the headline. Read the dotted line first, then the orange bars. The supervised model, given every fault label, reached 0.577. The isolation forest, given none, reaches 0.577. Be scrupulous about the caveat - the supervised model pays no false alarms and can name the fault - but the idea that you cannot start without labelled failures is simply wrong. Then the failure in the caption: PCA misses imbalance because imbalance mostly scales a direction the healthy data already varies along, so it reconstructs perfectly. Reconstruction error is blind to faults inside the healthy subspace. Run more than one detector.


## Slide 9
The mechanism first, because it is the bit that feels like cheating and is not. Set the threshold at the 99th percentile of healthy training scores and, by construction, about 1 % of healthy windows will alarm. You have not optimised anything against faults - you could not, you have none - you have simply stated how wrong you are willing to be on healthy data. Left panel: all three detectors as false-alarm rate against spalls caught. Note it is the same shape as the precision-recall curve from slide 4, which is the point - you are choosing a point on a curve, not a model. Right panel converts the x-axis into units a plant manager uses: false alarms per acquisition of 61 windows. At the 80th percentile you get twelve per acquisition and nobody will look at any of them. Two practical warnings. First, fit the quantile on healthy data the detector did not train on - training scores are optimistically low exactly as training accuracy is optimistically high. Second, nothing forces you to alarm on single windows, and slide 11 shows what requiring persistence buys. Ask the room: what false-alarm rate would your maintenance team tolerate before they stop answering the phone? That is the real question, and it is not a modelling question.


## Slide 10
This is the failure mode that kills monitoring projects in the field, and it is not a modelling error - the detector was right on day one and the machine changed underneath it. Left panel, log scale: the blue line is the monthly median anomaly score of a perfectly healthy machine, the shaded band is the 10 to 90 per cent range, and the dashed line is the threshold set from the first twelve months. Trace it with your finger: quiet for a year, creeping by month 18, crossing regularly by month 30, and by months 36 to 41 firing on 48 % of windows. Nothing has broken. Then the red segment at month 42 is the real spall, a factor of five above anything before it - and by then the alarm has been on for two years and nobody is listening. Right panel is the fix: re-estimate the baseline from a trailing window of months that did NOT alarm. False alarms drop from 21 % to 6.6 % across the healthy years and the spall is still caught in full. Stress the exclusion rule, because it is the trap: admit every month and the detector calmly learns that a failing bearing is the new normal. Adapt too slowly and you drown in false alarms; adapt too fast and you adapt to the fault. Ask: who in your plant will remember to re-estimate this in three years? That is why the alarm specification on slide 11 carries an expiry date.


## Slide 11
Hand over to the lab half. Part A is reproduction but with a writing requirement: for each of the three diagnostics, one sentence on what it told them that accuracy did not. That forces them to articulate the lecture rather than re-run it. Part B is the real work and it has two decisions in it. The cost ratio they must defend in writing - there is no correct answer, only a defended one, and 'I assumed 50 to 1 because a gearbox is about fifty technician-hours' is a fine answer. Then m and n for persistence. Walk the table on the right while you explain it, because it is the most practically valuable thing in the lecture. With no persistence, a quarter of perfectly healthy machines raise at least one alarm somewhere in a four-second acquisition. With 3-of-5 that falls to 1.5 %, costing 0.022 of recall and 256 milliseconds of delay. Twenty-five-fold fewer nuisance alarms for a quarter of a second and two lines of code - worth more than every hyperparameter in Lecture 9 put together, and routinely skipped because it does not look like machine learning. Part C is the deliverable. Insist the specification states the false-alarm rate being bought and a review date; an alarm spec without an expiry date is incomplete, as slide 10 showed.



## Slide 12
Walk the strip and make the dashed box the point: healthy data, baseline, score, threshold, cost, re-estimate - and not one fault label anywhere in that chain. Then read the six rules. Spend the time on one, four and six, because those are the ones that transfer. Rule one is a thirty-second habit that would prevent a large fraction of the overclaiming in this field. Rule four is the one they will resist: it is genuinely uncomfortable to write 'plus or minus 0.3' in a report, and it is the difference between an engineer and someone quoting a library. Rule six is the one that only bites after you have left the project. Then set up next week concretely, because Lecture 11 is where the whole course converges. They now have two artefacts: Lecture 9's classifier, 63 numbers, which names the fault but only faults it was trained on; and today's alarm specification, 25 numbers and a persistence rule, which needs no labels but cannot say what is wrong. Both fit on an ESP32 with room to spare. Lecture 11 exports them with m2cgen, measures the inference time against the 128 millisecond window budget from Lab 8, and finally closes the loop that Lecture 8 opened - the same device, the same features, a decision made locally.







