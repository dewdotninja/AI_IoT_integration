# Lecture 9 — build notes and reuse guide
 
**Topic:** Supervised Learning for Machine Condition
**Course:** 01211271 Industrial AI and IoT, lectures 8–14 (AI and integration half)
**Session format:** 5 hours — ~2 h lecture, ~3 h lab (laptop only this week)
**Built:** September 2026
 
> **Naming:** from Lecture 9 onward the course uses "Lecture N", not "Week N", in all
> content and file prefixes. Lecture 8's materials still say "Week 8" and are being
> edited by hand.
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture9_Supervised_Learning_for_Machine_Condition.pptx` renamed to `iaiiot26_Lect09.pptx` | 12 slides (dark title, 10 light, dark summary), 13.333 × 7.5 in, speaker notes 1091–1419 chars on every slide |
| `Lecture9_Supervised_Learning_for_Machine_Condition.ipynb` renamed to `iaiiot26_Lect09_nb.ipynb`| 33 cells, executed end to end, zero errors, zero stderr, ~40 s runtime; 8 exercises + real references |
| `Lecture9_Lab_Sheet.md` renamed to `iaiiot26_Lect09_Lab_Sheet.md`| Parts A/B/C, deliverables, marking scheme, traps table, look-ahead to Lecture 10 |
| `lecture9_model.json` | the exported LinearSVC: 36 coefficients, 3 intercepts, 24 scaler constants — **the input to Lecture 11** |
| `source/` | `rig.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `results.json`, `figs/` |
 
Rebuild order: `make_figs.py` → `build_notebook.py` (then execute) → `build_deck.js`.
`results.json` is the single source of every number and is rewritten by `make_figs.py`,
so anything the deck needs must be computed there.
 
---
 
## Continuity with Lecture 8
 
`rig.py` is Lecture 8's `week8_common.py` with two additions and one deletion:
 
* **added** `make_speed_sweep(seed=11)` — 40 healthy runs with shaft speed drawn from
  U(22, 40) Hz, for the soft-sensor thread. The range deliberately stays inside the
  `e_1x` band (20–42 Hz) so the Lecture 8 band definitions still apply.
* **added** `build_speed_table()` — same features, target is true shaft speed in Hz.
* **removed** the `if __name__ == "__main__"` block. It sat in the middle of the file
  and truncated the notebook's inlined generator. Do not reintroduce it.
`make_dataset(seed=7)` is unchanged, so the classification table is bit-identical to
Lecture 8's export.
 
---
 
## Headline numbers (all from `results.json`)
 
### The comparison — tuned on validation, scored once on test, 8 splits
 
| model | chosen knob | test acc | paired gain vs tree | bytes (m2cgen) | ops / decision |
|---|---|---|---|---|---|
| decision tree | depth 2 | 0.827 | baseline | 303 | 2 |
| logistic reg. | C = 0.0032 | 0.876 | +0.049 ± 0.015 | 1 313 | 36 |
| **linear SVM** | C = 0.0001 | **0.880** | **+0.053 ± 0.016** | **1 322** | **36** |
| k-NN | k = 401 | 0.851 | +0.024 ± 0.018 | 111 264 | 27 816 |
| random forest | depth 2, 100 trees | 0.859 | +0.032 ± 0.011 | 38 233 | 200 |
| random forest, **untuned defaults** | — | 0.822 | — | 1 556 017 | 1 485 |
 
Raw sd across splits is ~0.08 for every model; the paired standard error is ~0.015.
**Always report the paired difference** — it is the only statistic here with enough
precision to separate the models.
 
### Sweeps
 
| | |
|---|---|
| tree depth: best / at 6 / at 16 | 2 → 0.820 · 6 → 0.734 · 16 → train 1.000, val 0.709 |
| k-NN: best / at k=1 | 401 → 0.889 · k=1 → train 1.000, val 0.787 |
| logistic C: best / at 100 | 0.0032 → 0.883 (Σ\|w\| = 5.5) · 100 → 0.808 (Σ\|w\| = 40.2) |
| learning curve, depth 2 | final gap 0.059, validation rose +0.262 over 24 runs |
| learning curve, depth 12 | final gap 0.281, validation +0.141 |
 
### The soft sensor (speed sweep, 40 runs, 2440 windows)
 
| estimator | RMSE |
|---|---|
| predict the mean | 4.47 Hz |
| `dom_freq` used directly | 2.35 Hz |
| ridge on the 12 features | 1.90 Hz |
| random forest on the 12 features | 2.15 Hz |
| ridge + parabolic peak interpolation | **0.35 Hz** |
 
`dom_freq` takes only **3** distinct values across the 18 Hz range (7.81 Hz bins).
 
---
 
## The three arguments the lecture actually makes
 
1. **Capacity must match the number of independent observations, not the number of
   rows.** 2928 rows, 48 runs. Every model independently asked to be simplified —
   depth 2, k = 401, C = 0.003, forest depth 2. This is the intellectual core of the
   lecture and it ties directly back to Lecture 8's leakage material.
2. **The smallest model won.** Not a general law, and the slide says so explicitly —
   the reason is that (a) 48 runs cannot support high capacity and (b) Lecture 8's
   features already did the separating work, so the classes are close to linearly
   separable. With 5000 runs the forest would likely lead. The honest framing is the
   rule in point 1, not "linear models are best".
3. **When several model families plateau at the same error, fix the features.** The
   soft sensor stalls at ~1.9 Hz for ridge *and* random forest; one interpolated
   spectral peak gets to 0.35 Hz. This is the positive counterpart to Lecture 8's
   `e_bpfo`, which looked essential and carried nothing.
---
 
## Design decisions worth knowing before editing
 
* **k-NN's exclusion is about ops, not bytes.** At 111 KB it fits in the ESP32's RAM.
  What rules it out is 27 816 operations per decision against 36 — and that number
  grows with every new run recorded. Slide 9 makes this point explicitly because
  students reach for the size argument and it is the weaker one.
* **The untuned random forest is the honest villain.** With tuning the forest shrinks
  to 38 KB and would technically deploy; the dramatic 1.5 MB figure is
  `RandomForestClassifier()` with defaults, which is what a student actually writes.
  Both are on the plot.
* **The learning-curve panels are depth 2 vs depth 12, not depth 1 vs depth 12.**
  Depth 1 is pathological on three balanced classes (two leaves, ceiling of 0.667) and
  produced a misleading curve at small sample sizes. Underfitting is still taught, on
  the depth sweep where depth 1 scores 0.574.
* **The scaling demo is inherited from Lecture 8** and not repeated; slide 3 just
  states which models need it and why.
* **Lecture 8 used depth 6.** The validation curve says depth 2. The notebook and the
  slide 5 notes both address this head-on rather than quietly changing it.
---
 
## Build gotchas hit and fixed
 
* **Long single-line `fig.text` captions inflate the `bbox_inches="tight"` width**,
  which shrinks the plot area once the figure is fitted to a slide band.
  `fig_models` came out at aspect 3.54 and rendered tiny; wrapping the caption to two
  lines (with `va="top"`) brought it to 2.23 and the figure filled the slide. Watch
  for this on any figure whose caption is longer than its axes.
* **`make_figs.py` rewrites `results.json` wholesale**, so every key the deck reads
  must be produced there — not patched in afterwards. `lc_overfit_val_final`,
  `rf_default_ops` and `best_C_str` were all added for this reason.
* **Consolas has no U+2500**, so a `─────` separator in a `codeBox` renders as blank.
  Use ASCII hyphens.
* **Never derive a slide number from another one by a made-up factor.** The untuned
  forest's op count was briefly `ops["random forest"] * 7`; it is now measured.
* Same pptxgenjs/LibreOffice traps as Lecture 8: `defineLayout` for 13.333 × 7.5,
  bullet boxes at `h: 0.46` with `valign: "top"`, `box()` bodies also `valign: "top"`,
  and a dark-background variant of the workflow strip for the summary slide.
---
 
## Hooks into later lectures
 
* **Lecture 10** is set up on the Lab 9 sheet and in the slide 12 notes: accuracy was
  the wrong score (confusion matrix, precision/recall, cost asymmetry), and the
  dataset's perfectly balanced fault labels are a fiction no factory has — which opens
  anomaly detection.
* **Lecture 11** consumes `lecture9_model.json` directly. The 63 numbers and the
  m2cgen sizing on slide 9 are deliberate setup; exercise 8 asks students to write the
  pure-Python scorer, which is the first cell of Lecture 11's device code.
* The **speed sweep** and the interpolated-peak feature are reusable if Lecture 12
  wants a second quantity to publish to NETPIE alongside the fault label.
 
# Lecture 9 slide notes

## Slide 1

Open by connecting to last week. Lecture 8 ended with a table - 2928 rows, twelve features, one label per row, and a run id. Building it was most of the work; today we spend it. Set the destination early: the model that wins today has to run on an ESP32 in Lecture 11, so we will not only ask which model is most accurate but how many bytes it occupies and how much arithmetic one decision costs. Tell them the punchline is genuinely surprising - the two smallest models turn out to be the two most accurate, and the random forest a student writes by default is a thousand times larger and worse. Do not give away why yet; that is slide 8. Also flag the shape of the session: five slides of method - protocol, overfitting, learning curves, regularisation - then the comparison, then a short regression thread building a virtual tachometer, then the lab. Ask the room a warm-up question: if I gave you this dataset and said 'get the best accuracy', which model would you reach for first? Note the answers on the board and come back to them on slide 8 - most rooms say random forest or a neural network.

## Slide 2
Keep this slide short - it is framing, not content. The left box is what they built last week. The two right boxes are the two things you can ask of it. Point out that the mechanics are identical: same windows, same features, same split-by-run rule; only the target column and the scoring change. Then spend the time on the callout, because it is the part students skip. A number like 'RMSE 1.9 Hz' or 'accuracy 0.85' means nothing on its own - you have to know what doing nothing would have scored. For three balanced classes, guessing gives 0.333. For regression, predicting the mean every time gives the standard deviation of the target. Make them write both down now, because in section 8 the soft sensor scores 1.90 Hz and the only way to know that is good is that the baseline was 4.47. Worth noting where the labels come from: classification labels had to be recorded by a human who knew what state the machine was in, which is why labelled fault data is scarce in industry. The regression target came free from the drive's speed setpoint - that asymmetry is why Lecture 10 spends time on anomaly detection, which needs no fault labels at all.

## Slide 3
Walk the five panels left to right, naming the mechanism each time. The decision tree asks 'is feature j above t?', so its boundary is made of axis-aligned steps - you can see the corners. Logistic regression and the linear SVM both compute a weighted sum, so each gets one straight cut per class pair; the difference is what they optimise, log-likelihood versus the margin, and here it barely matters. k-NN has no equation at all - the boundary wanders wherever the training points happen to be. The random forest votes over many trees, so you get steps again, but softened by averaging. Say clearly that being restricted is not a weakness: a model that can only draw straight lines cannot chase noise, which is exactly what we want with 48 runs. Note these are trained on two features only so the boundary can be drawn - the real models use all twelve. Then set up slide 9 with the callout: four of the five compress the data into a few numbers, k-NN keeps all of it. Ask the room which of these five they would find easiest to explain to a maintenance engineer who has to trust the alarm.

## Slide 4
This is the slide that separates a student who can run scikit-learn from one you would trust with a result. Start with the failure, concretely. You try nine tree depths. You score each on the test set. You keep the best. The number you now report is the maximum of nine noisy measurements, and the maximum of noise is biased upward - the more values you tried, the worse the bias. Nothing about that is dishonest in intent, and it is what almost everyone does the first time. The fix is a third pile: fit on train, choose on validation, report on test exactly once. Walk the strip: 48 runs split 28 / 10 / 20 percent - read the actual counts off the figure. Emphasise that the split is still by RUN, not by row; Lecture 8's rule has not been relaxed, it has been extended. Point at the orange warning: score the test set more than once and it quietly becomes a second validation set, and you no longer have an honest estimate of anything. The question students ask here: 'what if I get an unlucky split?' Good question - the answer is to repeat the whole procedure over several splits and average, which is what every number in this lecture does, eight times.

## Slide 5
Two textbook curves, and then one observation specific to this rig. Left: the tree. Training accuracy climbs to 1.000 at depth 16 while validation peaks at 0.820 at depth 2 and then falls away to 0.709. That is the overfitting scissors - name it. Right: k-NN. At k = 1 training accuracy is a perfect 1.000, and ask the room why before telling them - because the nearest neighbour of a training point is itself. Its validation accuracy climbs all the way to k = 401. Now the observation. Both models are asking to be made far simpler than anyone would guess from 2928 rows. The reason is that 2928 is not the number of independent observations. Windows from one run are near-duplicates and share that run's speed, gain and noise floor, so the effective sample size is closer to the 28 training runs. Any capacity beyond what 28 observations support gets spent memorising which run the model is looking at. Then a moment of honesty worth making explicit: Lecture 8 used depth 6 throughout, which scores 0.734 here against 0.820 for depth 2. Last week was demonstrating leakage, not tuning - but it shows why you tune.

## Slide 6
Frame the difference first, because students conflate the two plots. The previous slide varied model complexity at fixed data. This one fixes the model and varies how much data it gets, and it answers a question a manager will genuinely ask: should we spend another week collecting data? Two shapes, two different answers. Left, the depth-2 model we chose: the curves are 0.059 apart and validation gained 0.262 over these 24 runs and is still climbing. That model is data-limited, and more runs would pay. Right, depth 12: training pinned at 1.000, validation at 0.716, a gap of 0.28 that is not closing. That model is not short of data, it is short of discipline - a simpler model helps immediately, more data barely at all. Now the detail that matters most and is easy to miss: the x-axis counts RUNS, not rows. Adding more windows from a machine you have already recorded adds almost no information. That is the same insight as the previous slide, drawn differently, and it is the practical advice to give a student planning data collection - twenty machines for an hour each beats one machine for twenty hours. Expect the objection: 'but overlap gave us more rows for free in Lecture 8.' It did, and they were nearly free of information too.

## Slide 7
Say the direction out loud, twice, because everyone gets it wrong once: small C means MORE regularisation. C is the inverse of the penalty strength. Left panel is the regularisation path - total coefficient size falls from 40.2 at C = 100 to 5.5 at the chosen C. Explain what large weights mean physically: the model is leaning hard on small differences between features, and on this rig those small differences are mostly run-specific noise - gain, noise floor, frame resonance. The penalty makes it earn every unit of weight. Right panel is the payoff, and the two curves must be read together. Training accuracy is essentially flat across four decades of C. If you had only ever looked at training accuracy you would have concluded regularisation does nothing here. Validation is not flat at all - it peaks at 0.0032 and loses about 0.075 by C = 100. Only the validation runs, machines the model has never seen, reveal the cost. Close with the bonus that matters for this course: the well-regularised model is also the smaller, better-conditioned model, and in Lecture 11 those coefficients become constants in a MicroPython file, where small stable numbers quantise far more gracefully than large ones.

## Slide 8
The anchor slide. Come back to the show of hands from slide 1 - most rooms predicted the random forest. Left panel: the five tuned models, scored once each on the test runs, averaged over eight splits. Read the numbers aloud. Then the small print under each bar, because it is the better statistic: because every model saw the SAME splits, we can subtract per split, which cancels the run-to-run variance that dominates the individual spreads. The standard error of the paired difference is about 0.015, five times smaller than the raw sd. On that measure the linear models are ahead of the tree by roughly three standard errors - a real effect, not an accident of splitting. Teach that as a transferable habit: always compare models on shared splits and difference the results, it is free precision. Right panel is the surprise. The two smallest models are the two most accurate. Give the three reasons: the data is small in the way that counts, 48 runs; the features already did the hard work, so once e_1x and e_hi exist the classes are close to linearly separable; and capacity beyond the data buys memorisation. Then guard against over-generalising - this is not 'linear models always win'. Give the same pipeline 5000 runs from 200 real machines and the forest very likely takes the lead. The rule is that capacity must match the number of independent observations.

## Slide 9
This slide converts accuracy into engineering. Walk the table column by column rather than row by row. The bytes column was not estimated - each model was actually exported with m2cgen, which is the tool Lecture 11 uses to turn a scikit-learn model into plain Python for the device, so these are the real numbers they will see in eight weeks. The ops column is arithmetic per decision, counted rather than timed, so it is hardware-independent. Now the k-NN box on the right, because it is the subtle one. At 109 KB it would technically fit in the ESP32's RAM - size is not what rules it out. What rules it out is 27,816 operations per decision against 36, and worse, that number grows every time you record another run. A model whose inference cost scales with your dataset cannot live on a device that must run unattended for years. That is a structural objection, not a benchmark. Then the two lower boxes: the entire trained linear model is 63 numbers - 36 coefficients, 3 intercepts, 24 scaler constants - about 252 bytes of data plus a double loop. Tell them plainly that this is why Lecture 11 is a short lecture, and that anyone expecting TensorFlow Lite and quantisation-aware training is going to be disappointed in a good way.

## Slide 10
Short thread, but it carries one of the two most useful diagnostics in the course. Set the problem: the rig has no tachometer, and shaft speed matters because it sets the 1x line, the bearing defect frequencies and the expected vibration level. So compute it instead of installing it - that is a soft sensor, and the process industry runs on them. Data is a separate campaign, 40 healthy runs across 22 to 40 Hz with the true speed from the drive setpoint. Read the bars left to right. Doing nothing scores 4.47 Hz. Ridge on the twelve features gets to 1.90 - so the soft sensor works, more than twice as good as nothing. Now the interesting part: try a random forest and you get 2.15, essentially the same. Two very different model families landing in the same place is a signal. Give them the rule: when several model families plateau at the same error, the limit is not in the models, it is in the features. Here it is the 7.81 Hz FFT bin - dom_freq can take only 3 distinct values across an 18 Hz range, so the resolution was destroyed back in Lecture 8, before any model existed. Parabolic interpolation of the peak costs about ten operations and gets to 0.35 Hz. In the scatter, blue is the twelve features shrinking toward the mean; green hugs the diagonal. Tie it back: this is the positive counterpart to e_bpfo last week, which looked essential and carried nothing. Features are hypotheses in both directions.

## Slide 11
Hand over to the lab half. Part A is reproduction, and it should be quick - the point is that they see the curves appear on their own machine rather than taking the slides on trust. Part B is the real work. Two requirements worth stressing. First, tuning min_samples_leaf instead of max_depth: it reaches similar accuracy by a different route, and it forces them to think about what the knob actually controls rather than turning the one they were shown. Second, adding a model family of their own choice - gradient boosting, naive Bayes, an MLP - and reporting it on the SAME splits with paired differences. If they report it on a fresh split the comparison is worthless, and that mistake is worth making here rather than in a report. Part C is the deliverable that matters: pick one model and defend it in a paragraph on all three axes together. A student who writes 'random forest, because it scored highest' without mentioning 1.5 MB has missed the entire lecture. Insist on one line stating how many times they scored the test set; the honest answer is once, and asking for it in writing makes the discipline real. Finally, remind them the JSON file is not a throwaway - Lecture 11 turns those 63 numbers into MicroPython and runs them on the ESP32 that produced the features in Lab 8.

## Slide 12
Close by walking the strip: Lecture 8's table, five candidates, fit, choose, report, size it, and Lecture 11 exports it. Point at the dashed box - everything inside it happened today, and the test runs were opened exactly once. Then read the six rules, spending most of the time on three, five and six because those are the ones that transfer beyond this dataset. Rule three is the one that will save them on their own projects: when the tuned model comes back far simpler than you expected, that is information about your data, not a bug. Rule five is free precision and almost nobody does it. Rule six is what makes this an engineering course rather than a machine-learning course - accuracy alone would have chosen the random forest and the project would have failed at the device. Set up next week honestly: today every model scored above 0.82 and we compared them on accuracy, but accuracy is a poor measure when a missed bearing fault costs a gearbox and a false alarm costs an hour. Lecture 10 replaces accuracy with the confusion matrix, precision and recall, and then asks the harder industrial question: what do you do when you have no labelled faults at all, which is the normal situation in a real plant.





