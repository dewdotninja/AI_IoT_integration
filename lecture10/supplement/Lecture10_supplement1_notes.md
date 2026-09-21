# Lecture 10, Supplement 1 — build notes and reuse guide
 
**Topic:** Three ways to say "that is not normal" — mean ± kσ, isolation forest, PCA reconstruction error
**Course:** 01211271 Industrial AI and IoT
**Status:** supplementary background for Lecture 10's anomaly-detection section. **Not new
examinable material**; the title slide says so.
**Built:** September 2026. Second in the per-lecture supplement series (after Lecture 8, Supplement 1).
 
---
 
## Scope decisions (from the instructor)
 
* **Depth:** from "what is normal" up — z-scores and quantile thresholds first, no linear
  algebra assumed, PCA introduced geometrically.
* **Examples:** every method shown first on a 2-D toy (`rms` vs `ptp`), then on all 12 rig
  features.
* **Extras:** Mahalanobis distance as the bridge between the box and PCA; contaminated
  training data.
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture10_Supplement1_Anomaly_Detection.pptx` | 15 slides (dark title, 13 light, dark summary), notes 965–1112 chars on every slide |
| `Lecture10_Supplement1_Anomaly_Detection.ipynb` | 50 cells, executed, zero errors, zero stderr, ~20 s; 8 exercises + references |
| `Lecture10_Supplement1_Code.zip` | `rig.py` (**Lecture 10's file, unchanged**) + `detectors.py` (new) + README |
| `source/` | `rig.py`, `detectors.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `results.json`, `figs/` |
 
Also written to the instructor's `~/Downloads`, beside the Lecture 10 files.
 
Rebuild order: `make_figs.py` → `build_notebook.py` (then execute) → `build_deck.js`.
 
---
 
## Where `rig.py` came from — read this before rebuilding
 
The build workspace had been reset, so the Lecture 10 source was gone. A generator rebuilt
from the project notes matched the fleet's **shape** exactly (8052 / 732 / 366 windows, 7 PCA
components) but drew different machines, and the detector AUCs came out ≈ 0.89 instead of
0.96. **Numbers from a rebuilt generator do not match the slides.**
 
The fix: the instructor copied the Lecture 10 deliverables to `~/Downloads`. The Lecture 10
notebook (`iaiiot26_Lect10_nb.ipynb`) inlines the complete `rig.py` in **code cell 3**, and
cell 24 holds the exact detector protocol. Extracting both reproduced the Lecture 10 table
to the third decimal. **For any future supplement, extract `rig.py` from that lecture's
notebook rather than rebuilding it from notes.**
 
---
 
## `detectors.py`
 
Four classes with the same `fit(H)` / `score(X)` shape, written to be read:
 
* `ZScore` — max |z|; `driver()` returns the feature name.
* `Mahalanobis` — `sqrt(z · pinv(C) · z)`. **Must use the pseudo-inverse**: `rms` and `std`
  are identical after de-meaning (differ by 1e-16), so C has rank 11 of 12.
* `IForest` — sklearn, 200 trees, `random_state=0`, standardised features (Lecture 10's settings).
* `PCAResidual` — residual (SPE) as `score()`, and `t2()` for the half Lecture 10 did not use.
`oof_scores()` is Lecture 10's `StratifiedGroupKFold(5, shuffle=True, random_state=0)`,
fitted on each fold's healthy training windows only. `contamination=p` adds that fraction
of faulty training windows and also returns the threshold an engineer would set from the
contaminated set.
 
---
 
## Headline numbers (all from `results.json`)
 
### On the rig — Lecture 10's protocol, reproduced exactly
 
| detector | AUC | bearing | imbalance |
|---|---|---|---|
| mean ± kσ | 0.959 | 0.514 | 0.993 |
| **Mahalanobis** (new) | **0.972** | **0.631** | **1.000** |
| isolation forest | 0.963 | 0.577 | 0.954 |
| PCA residual (7 of 12) | 0.943 | 0.637 | 0.557 |
| PCA T² (new) | 0.959 | 0.486 | 0.992 |
 
**Mahalanobis beats all three Lecture 10 methods on this rig.** Explained on slide 12 without
undermining Lecture 11: the box is 25 numbers vs 168, it names the tripping feature, and the
bearing gap (0.514 vs 0.631) is inside the ~0.3 fold-to-fold spread Lecture 10 measured.
 
### Thresholds
 
| | value |
|---|---|
| healthy windows beyond ±3σ: `rms` / `e_bpfo` | 0.00 % / 1.60 % (Gaussian: 0.27 %) |
| max\|z\| > 3 on healthy (out of fold) | **4.1 %** = a false alarm every **1.6 s** |
| Gaussian, 12 independent features | 3.2 % |
| **99th-percentile k** | **4.04** — exactly Lecture 10's alarm-spec threshold |
 
### 2-D toy (`rms` vs `ptp`, corr 0.88, fitted on all healthy windows, 99th-pct threshold)
 
| | bearing | imbalance |
|---|---|---|
| box, k = 2.55 | 43 % | 100 % |
| ellipse (Mahalanobis) | 54 % | 100 % |
| isolation forest | 25 % | 91 % |
| PCA, 1 axis kept (94 % of variance) | 43 % | 98 % |
 
### Isolation forest — two honest limits
 
* **It saturates.** Walking straight up the ptp axis, the score flattens at a ceiling. In 2-D
  the healthy 99th percentile (0.677) is already at the ceiling (0.680), so only 25 % of
  bearing windows get above it. "It knows *outside*, not *how far outside*."
* **One-feature faults slip through in 12-D.** Push `kurt` 50σ out, leave eleven features
  at the healthy mean: max|z| = 50, the forest scores **0.78×** its threshold (healthy).
  Reason: each cut picks one feature, trees are 8 deep, (11/12)⁸ ≈ 50 % of trees never test
  it. Real bearing windows move several features and score a median 1.09×.
* The cutting game by hand (61 points): **3.3** cuts for the odd point vs **9.7** for an
  ordinary one, averaged over 400 trees.
### PCA's blind spot, explained
 
| | bearing | imbalance |
|---|---|---|
| residual (Lecture 10's score) | 0.637 | 0.557 |
| T² (inside the 7 kept directions) | 0.486 | **0.992** |
 
Median imbalance window: residual **1.04×** its threshold (on the line), T² **1.46×**.
Imbalance moves *along* the healthy directions. In 2-D (1 axis) PCA does catch imbalance
(98 %) — the blind spot only appears in 12-D, which the deck states explicitly.
 
### Contamination (threshold set from the contaminated training set)
 
| % faulty | ±kσ B / I | Mahalanobis B / I | iForest B / I | PCA B / I |
|---|---|---|---|---|
| 0 | 0.53 / 1.00 | 0.63 / 1.00 | 0.60 / 0.98 | 0.64 / 0.58 |
| 1 | 0.42 / 0.81 | 0.56 / 0.79 | 0.52 / 0.92 | 0.61 / 0.17 |
| **2** | **0.31 / 0.47** | 0.43 / 0.46 | 0.31 / 0.64 | 0.57 / 0.10 |
| 5 | 0.26 / 0.20 | 0.32 / 0.16 | 0.25 / 0.20 | 0.44 / 0.00 |
| 10 | 0.24 / 0.02 | 0.29 / 0.07 | 0.24 / 0.09 | 0.29 / 0.00 |
 
* **The threshold is the first casualty:** once > 1 % of training data is faulty, the 99th
  percentile is set by the faults. ±kσ threshold: k 3.92 → **5.42** at 2 %.
* **False alarms FALL** (1.1 % → 0.2 % for ±kσ) while detection collapses — the same trap as
  Lecture 12's "refit on everything recent".
* Split at 2 %: with a *clean* threshold, ±kσ is 0.464 / 0.831; PCA's imbalance is still
  0.113 (the fault pulls a principal direction and starts to reconstruct); the forest's
  model is most robust (0.936).
---
 
## Deck outline (15 slides)
 
1. dark title
2. The job: score, then threshold — `fig_scatter`
3. "Beyond 3σ" is a promise only a Gaussian keeps — `fig_normal`
4. With twelve features, k is not 3 — `fig_k`
5. The box, and the ellipse that leans with the data — `fig_box_maha`
6. Mahalanobis: all features together — code box + the rank-11 trap
7. The isolation forest plays a game of random cuts — `fig_iso_cuts`
8. The forest knows "outside", not "how far outside" — `fig_iso_score` + two limit boxes
9. PCA: keep the directions healthy data uses — `fig_pca_geo`
10. PCA's blind spot — and the half Lecture 10 did not use — `fig_pca_two`
11. Four shapes of "normal" — `fig_shapes` ← the slide to photograph
12. On the rig: Lecture 10's table, plus the two it did not have — `fig_rig`
13. When "healthy" is not quite healthy — `fig_contam`
14. Which one? — four boxes + a default architecture
15. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
0 the job · 1 one feature · 2 mean ± kσ · 3 Mahalanobis · 4 isolation forest (hand-played
cutting game, ceiling, one-feature test) · 5 PCA (strip, T² vs residual) · 6 four shapes ·
7 on the rig · 8 contamination (sweep + clean-vs-contaminated threshold split) · 9 which
one · 10 what to remember · 11 eight exercises · 12 references (Liu 2008 ICDM; Mahalanobis
1936; Jackson & Mudholkar 1979; MacGregor & Kourti 1995; Chandola 2009; Montgomery; sklearn).
 
---
 
## Gotchas hit
 
* **LaTeX braces inside `rf"""` markdown** — `\text{residual}` becomes a format field.
  Double every brace: `\text{{residual}}`.
* **PCA with the 95 % rule in 2-D keeps both directions** and every residual is zero. The
  toy fixes k = 1 and the notebook says why.
* **Isolation-forest threshold contour in 2-D is noise** (threshold ≈ ceiling). Dropped from
  the score map; the four-shapes figure keeps it and the notes explain the cross shape.
* **Uppercase kicker turns σ into Σ** ("MEAN ± KΣ"). Kickers avoid Greek letters.
* Two-line bullets collide with figures that start at y ≈ 2.0 in; bullets were cut to one line.

# Slide Notes

## Slide 1
Open by pointing back at the table in section seven of Lecture 10: three detectors, three AUCs between 0.94 and 0.96, fitted in a single cell. That table is correct and almost impossible to understand if you have never met the methods, which is why this hour exists. Say plainly that this is background, not new examinable material. Then give them the one skill the hour is designed to build: for each method, be able to say what SHAPE it thinks normal is. A box, an ellipse, whatever random cuts carve out, a strip. Once you know the shape you can predict which faults a method will catch and which it will miss before you run it - and that is worth more than memorising any of the four. Mention the two additions this supplement makes: the Mahalanobis distance as a bridge between the box and PCA, and what happens when the healthy training data is not quite healthy. Both earn their place: Mahalanobis turns out to beat all three Lecture 10 methods on this rig, and contamination turns out to be the thing that actually breaks detectors in practice.


## Slide 2
Left panel is all the training data any of these methods ever sees: 8,052 healthy windows, plotted in just two features so we can look at them - rms, the overall level, and ptp, peak to peak. Both are in healthy standard deviations, so zero is the healthy average. Point out the shape: a tilted cigar, correlation 0.88, because a machine that vibrates more overall also swings further. Hold that in mind; the first half of the hour turns on it. Right panel is what arrives in service. The two faults leave the cloud in different ways. Imbalance walks far out along rms - a big shaft line makes everything bigger. Bearing stays at an ordinary rms, but its ptp is too high FOR that rms, because a spall adds sharp impulses that raise the peaks without adding much energy. Ask the room which one will be harder to catch. Then land the callout: every method in the next hour produces a score; none of them produces a decision. The decision is a threshold, and choosing it is the engineering.


## Slide 3
Start from the one idea everything else is built on: the z-score. Subtract the healthy mean, divide by the healthy standard deviation, and every feature is on the same ruler. Then break the rule of thumb they have all heard. 'Beyond three sigma happens 0.27 per cent of the time' is a property of the Gaussian distribution and of nothing else. Left: rms is symmetric with light tails, and NO healthy window in eight thousand lies beyond three sigma. Right: e_bpfo is skewed, with a long tail on one side, and 1.6 per cent do - six times the Gaussian figure. Same k, completely different false-alarm rate. Ask the room why e_bpfo might be skewed: it is an energy fraction, so it cannot go below zero but can occasionally be large. The conclusion is the callout, and it holds for every method in the hour: you never pick k from a textbook. You pick a false-alarm rate, and read the threshold off the healthy data as a quantile. That works whatever shape the data has.


## Slide 4
This is the first method, and it is the simplest: compute twelve z-scores and keep the worst one. Mean plus or minus k sigma, applied to every feature, alarm if any feature is out. Now the histogram: those are the out-of-fold max-z scores of every healthy window in Lecture 10. The red line is k equals three. It flags 4.1 per cent of healthy windows - at fifteen and a half windows a second, that is a false alarm every 1.6 seconds, forever. Two reasons, both general. First, twelve chances: even twelve perfectly Gaussian independent features would give 3.2 per cent. Second, skew, as on the last slide. The green line is the 99th percentile of healthy scores, 4.04, and that number should look familiar: it is the threshold in lecture10_alarm.json, the file the ESP32 carries in Lecture 11. Ask the room: if we added eight more features next year, would k go up or down? Up - more chances - and the quantile rule handles it automatically, which is the whole point.


## Slide 5
Left: the box, at its own 99th-percentile threshold of 2.55 in two dimensions. Filled violet dots are bearing windows it catches; red rings are the ones it misses. Ask them to find where the misses are: inside the box, in the upper part, at ordinary rms but high ptp. Each feature separately is within range, so the box calls them healthy. The box judges features one at a time and cannot see that two features are wrong TOGETHER. Right: the Mahalanobis distance draws an ellipse instead, tilted the same way the data is. Being far along the cigar is cheap; being far across it is expensive. Those same bearing windows are across the cigar, so they fall outside. Emphasise that both thresholds give the same one per cent false-alarm rate, so this is a fair comparison - 43 against 54 per cent is bought purely by changing the shape. The objection to expect: then why did Lecture 11 put the box on the device? Answer on slide 12 - it names the feature, and it is 25 numbers.


## Slide 6
No algebra is required to use this, and I would not examine it. Read the three lines of the code box: the same z-scores as the box method, the healthy correlation matrix, and a distance that uses the inverse of it. What the inverse does, in words: it divides each direction by how much healthy data spreads along it. Along the cigar the spread is big, so moving there is cheap. Across it the spread is small, so moving there is expensive. That is the ellipse. Then the trap, because every student who tries this on all twelve features will hit it: rms and std are literally the same number after the mean is removed. The correlation matrix has two identical rows, rank eleven, and np.linalg.inv either throws or returns enormous nonsense. The pseudo-inverse is the fix. Finish on the result, which surprised me: on the full rig Mahalanobis beats the box, the forest and PCA - AUC 0.972, bearing 0.631, imbalance 1.000. It is 168 numbers, still small enough for the ESP32.


## Slide 7
This one is best explained as a game, and the notebook plays it by hand in a dozen lines. Sixty ordinary points and one odd one. Pick a feature at random, pick a cut value at random between the smallest and largest values still in play, throw away the side that does not contain the point you care about, and repeat until the point is alone. Left: the odd point, fenced off in three cuts - there is nobody near it, so almost any cut separates it. Right: an ordinary point in the middle, and it takes ten, each cut shaving off a few neighbours. Over four hundred random trees the averages are 3.3 and 9.7. The real IsolationForest does exactly this with two hundred trees, each on a random sample of 256 healthy windows, and converts the average cut count into a score between zero and one. Say what is attractive about it: no mean, no standard deviation, no assumption that the data is a cigar or a ball. Then say 'which sounds like it must be better' - and turn the slide, because it has two properties the others do not.


## Slide 8
Left is the forest's score map in our two features. Darker means fewer cuts. Notice the grid pattern: every cut is horizontal or vertical, so the forest's idea of normal is built from rectangles. Right is the important plot. Walk straight up out of the healthy cloud and plot each score divided by its own threshold. The box and the ellipse keep climbing - further out, bigger score. The forest flattens, because once you are outside the data one cut isolates you and one cut is the minimum. It knows outside, not how far. Two consequences, in the boxes. In two dimensions the healthy fringe is already isolated almost as fast as possible, so the threshold sits at the ceiling and the forest catches a quarter of bearing windows. In twelve dimensions there is room, but each cut picks one feature, a tree is only eight cuts deep, and in half the trees a single odd feature is never tested. So a window fifty sigma out on kurtosis alone is called healthy. Which real fault looks like that? A single broken sensor channel.


## Slide 9
Principal component analysis, without the linear algebra. Step one: find the direction along which healthy data varies most. In our two features that is obvious - the diagonal, the long axis of the cigar, carrying 94 per cent of the variance. Step two: to score a window, find the nearest point a healthy machine could have produced using only that direction - drop a perpendicular onto the line - and measure the length of that perpendicular. That red line is the residual. Left panel: a bearing window, off to the upper left of the line, residual 1.61; an imbalance window, residual 2.15. Both above the threshold of 0.89 here. Right panel: the consequence. Normal is every point within a fixed distance of the line - a strip - and the strip never ends. A window a hundred sigma out along the diagonal reconstructs perfectly and is called healthy. Ask the room what kind of fault would move along the diagonal: one that is just more of what a healthy machine already does. Hold that - it is the next slide.


## Slide 10
This explains the most puzzling number in Lecture 10's table: PCA catches only 0.557 of imbalance windows, while the plain box catches 0.993. The x-axis is new. PCA gives you two numbers for free. The residual, on the y-axis, is how far a window is OFF the seven healthy directions - that is what Lecture 10 used. T-squared, on the x-axis, is how far it is ALONG them, measured in their own standard deviations - which is exactly the Mahalanobis distance from slide six, computed inside the kept directions. Now find the orange cloud: far to the right, far along the healthy directions, but sitting on the residual threshold, half above and half below. Imbalance is not doing anything new; it is doing something ordinary, far too much. The residual cannot see that. T² catches 0.992 of it. The violet bearing windows are the opposite: high residual, moderate T². The two halves are complementary, and that is why process-monitoring practice, since MacGregor in the nineties, watches both with a threshold on each. Exercise five asks them to build the combined detector.


## Slide 11
This is the slide to photograph, because it is the whole hour in four pictures. Box: judges each feature separately, so it misses faults that are wrong only together - the bearing windows in the empty corner. Ellipse: assumes healthy data is one tilted, roughly elliptical cloud; it would fail on a machine with two operating modes, where healthy data is two clouds and the ellipse covers the empty gap between them. Random cuts: assumes no shape, which sounds ideal, but it saturates and it is weak on single-feature faults. Its odd cross shape here is the ceiling from slide eight made visible - where the score has flattened out it hovers at the threshold and noise decides. Strip: sees anything that leaves the healthy directions and nothing that moves along them. Put a question to the room: suppose our rig ran at two different speeds, so healthy data formed two clouds. Which shape would you distrust first? The ellipse and the box - both assume one cloud. The forest copes best with two clusters, and that is its genuine advantage.


## Slide 12
Now all twelve features, with Lecture 10's exact evaluation - the same folds, the same seeds - and the three Lecture 10 detectors reproduce its table to the third decimal: 0.959, 0.963, 0.943. Solid bars are bearing recall, hatched are imbalance, all at one per cent false alarms. Two new columns. Mahalanobis wins outright on this rig. PCA's T² and residual are mirror images: T² is excellent on imbalance and weaker on bearing, the residual the reverse. The objection a sharp student will raise: then Lecture 11 deployed the wrong detector. Answer honestly in three parts. The box is twenty-five numbers against a hundred and sixty-eight. It tells the technician WHICH feature tripped - kurtosis, rms - and Mahalanobis gives one distance with no name attached. And the gap, 0.514 against 0.631 on bearing, is inside the fold-to-fold spread Lecture 10 measured, about 0.3. The sensible architecture is both: the box on the device for a named, local decision, and Mahalanobis or PCA with T² in the cloud, where the extra numbers cost nothing.


## Slide 13
Every method in this hour learns from windows you BELIEVE are healthy, and in a real plant you never know that. A bearing may already be degrading while you collect your baseline. So we slipped a few per cent of faulty windows into the training set and did everything else exactly as an engineer would. Left and middle: recall collapses, and fast. Two per cent contamination - two faulty windows in every hundred - roughly halves imbalance detection for three of the four methods, and PCA's drops to 0.1, because the faults pull a principal direction towards themselves and start to reconstruct. At five per cent nothing catches more than a fifth of imbalance. The mechanism is in the left box: a 99th percentile is decided by the top one per cent of the data, so once more than one per cent is faulty the faults set the threshold. Then the right-hand panel, which is the dangerous part: the false-alarm rate goes DOWN. The number you would watch to check your detector improves while the detector goes deaf. Same trap as Lecture 12's 'refit on everything recent'.


## Slide 14
Put the four side by side on the things an engineer actually cares about: does it fit on the device, does it tell the technician anything, what shape does it assume, and what does it miss. Walk each box briefly - they have seen every line of these by now. Then the default, and be clear that it is a default for THIS kind of machine, not a law: the box on the device, because it is cheap, it runs with the WiFi unplugged, and it names the feature; something that handles correlation in the cloud, where memory is free and the extra detection is worth having. That is the hybrid architecture the course committed to, justified from the detector side. Close on the callout, because slide thirteen showed that it matters more than the choice of method. A clever detector trained on contaminated data is worse than a simple one trained on data you checked. Exclude what alarmed before it joins the baseline - the exact rule Lecture 10's drift fix used - and every time you refit, measure whether it still catches faults, not just whether it is quiet.


## Slide 15
Walk the strip first, and point out that the choice of score is one box out of six. The other five - collecting data you believe healthy, checking it, setting the threshold as a quantile, applying persistence, and reporting the driver - decide whether a detector works in a plant far more than the choice between a box and a forest. Then the six rules. Spend the time on one and six, the bookends. Rule one: every score is useless until you choose a threshold, and the threshold is a quantile of healthy scores because real features are not Gaussian. Rule six: the failure that actually happens in industry is not a poor choice of method, it is a baseline that already contained the fault, and it hides itself by making the false-alarm rate look better. Point them at the notebook - eight exercises; exercise five builds the combined PCA detector and exercise seven fixes contamination with a median instead of a mean. Finish by putting this back in its place: background, not new examinable material. The reason to know it is so that when a detector misses something, you can say which shape it assumed and why.


