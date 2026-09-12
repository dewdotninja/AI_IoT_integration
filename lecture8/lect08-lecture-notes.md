# Week 8 — build notes and reuse guide

**Topic:** From Sensor Data to a Dataset
**Course:** 01211271 Industrial AI and IoT, weeks 8–14 (AI and integration half)
**Session format:** 5 hours — ~2 h lecture, ~3 h lab
**Built:** September 2026

---

## Deliverables

| file | shape |
|---|---|
| `Week8_From_Sensor_Data_to_a_Dataset.pptx` renamed to `iaiiot26_Lect08.pptx` | 12 slides (dark title, 10 light content, dark summary), 13.333 × 7.5 in, speaker notes 1085–1268 chars on every slide |
| `Week8_From_Sensor_Data_to_a_Dataset.ipynb` renamed to `iaiiot26_Lect08_nb.pptx` | 34 cells, executed end to end, zero errors, zero stderr; ~10 s runtime; 8 exercises + real references |
| `Week8_Lab_Sheet.md` renamed to `iaiiot26_Lect08_Lab_Sheet.pptx`| Parts A/B/C with timings, deliverables, marking scheme, troubleshooting table, stretch task |
| `wokwi/` | `features.py`, `main.py`, three `wave_*.py` waveforms, `expected_features.csv`, `diagram.json`, `README.md` |
| `source/` | `week8_common.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `make_wokwi.py`, `results.json`, `figs/` |

Rebuild order: `make_figs.py` → `build_notebook.py` (then execute) → `make_wokwi.py` → `build_deck.js`.
`results.json` is the single source of every number; the deck and notebook both read from it.

---

## The running example

Motor-driven rotor rig. Accelerometer on the drive-end bearing housing, `fs = 2000` Hz.
Three states: `normal`, `imbalance` (trial mass on the disc), `bearing` (outer-race spall).

BPFO = (n/2)(1 − (d/D)cos φ)·f_r with n = 9, d/D = 0.2, φ = 0 → **3.6 f_r = 108 Hz** at 1800 rpm.

### Generator constants that matter (`week8_common.py`)

| constant | value | why |
|---|---|---|
| `FS` | 2000 Hz | headroom over the 600 Hz housing resonance |
| `WIN` / `HOP` | 256 / 128 | 128 ms window, Δf = 7.81 Hz, 50 % overlap |
| `RUNS_PER_CLASS` | 16 | 48 runs total; fewer makes the grouped-split variance too large to teach with |
| `F_RESONANCE` | 600 Hz | where the impulse energy actually lands |
| `TAU_RING` | 1.2 ms | shorter ring = higher kurtosis; 2.2 ms was too blunt to separate the classes |
| `noise` | U(0.04, 0.20) | run-to-run load variation, the main honest confounder |
| `f_struct` | U(150, 700) Hz | frame resonance; deliberately overlaps `e_hi` so the bearing class is not trivially separable |
| `a_1x` | normal U(0.20, 0.38), imbalance U(0.58, 1.10) | tuned so honest accuracy lands near 0.81, leaving room for Weeks 9–10 to improve |

**Tuning history, so it is not re-derived.** With narrow per-run variation the leakage
gap was only +0.05 — too small to see on a projector. With wide variation (a_struct up
to 0.26, noise to 0.22) honest accuracy collapsed to 0.66 — too discouraging. The values
above are the balance point.

### Bands

`e_1x` 20–42 · `e_2x` 48–78 · `e_bpfo` 90–132 · `e_hi` 400–900 Hz.
Wide enough to hold their order without a tachometer, since f_r wanders 28–32 Hz.

---

## Headline numbers (all from `results.json`)

| quantity | value |
|---|---|
| runs / windows / features | 48 / 2928 / 12 |
| window | 256 samples = 128 ms, Δf = 7.81 Hz, 1024-byte buffer |
| **raw samples, random split** | 0.616 |
| **raw samples, split by run** | 0.537 |
| **12 features, random split** | 0.933 |
| **12 features, split by run** | **0.810** |
| leakage inflation | **+0.123** |
| gain from features (honest) | **+0.273** |
| window sweep (64/128/256/512/1024) | 0.754 / 0.750 / 0.795 / 0.815 / 0.854, sd ≈ 0.045 |
| k-NN, normalised bands: as-is → standardised | 0.854 → 0.835 (**−0.019**) |
| k-NN, absolute band power: as-is → standardised | 0.765 → 0.841 (**+0.076**) |
| feature range ratio, normalised / absolute | 121× / 40 973× |
| `e_bpfo` normal vs bearing | 0.012 vs 0.014 (**carries nothing**) |
| `e_hi` normal vs bearing | 0.146 vs 0.289 |
| `crest` normal vs bearing | 2.537 vs 3.294 |
| `rms` normal vs imbalance | 0.277 vs 0.658 g |

Model throughout: `DecisionTreeClassifier(max_depth=6)`, scores averaged over 8 splits
(10 for the window sweep).

---

## Three teaching points that came out of the data, not the plan

1. **`e_bpfo` is worthless and that is the lesson.** A band designed on the whiteboard to
   catch the outer-race defect frequency does nothing, because impulse energy lands in
   the housing resonance rather than at the repetition rate. Envelope analysis is named
   as the correct technique and explicitly left out of scope. This became the anchor for
   "a feature you invented is a hypothesis, not a fact", and it sets up feature
   importance in Week 9.

2. **Scaling had to be demonstrated honestly.** The first version of the scaling slide
   showed standardising *hurting* k-NN (−0.019), because the normalised band features
   already share a scale. Rather than drop it, the notebook builds a second feature set
   with absolute band power (range ratio 41 000×) where scaling recovers +0.076. The
   slide is now "scaling is not a ritual — it fixes one specific problem", which is a
   better lesson than "always standardise".

3. **Accuracy does not choose the window length.** The sweep rises monotonically to
   N = 1024, so the slide had to be reframed around latency and RAM rather than a fake
   optimum. Error bars (sd ≈ 0.045) were added so the 64→128 dip is visibly noise; this
   doubles as the course's first lesson in reporting spread.

---

## The Wokwi lab

- **Scope:** the **seven time-domain features only** on the device. The frequency
  features stay on the laptop this week.
  Reason: `e_hi` spans 64 FFT bins (52–115), so Goertzel is not viable for it, and a
  full 256-point FFT in interpreted MicroPython is a Week 11 conversation. `goertzel()`
  is shipped in `features.py` but uncalled, as a stretch task for `e_1x` (bins 3, 4, 5).
- **Waveforms:** 2 s each (4000 samples → 30 windows), int16 + base64, ~12 KB per file.
  One at a time — three together risk `MemoryError`.
  Generated with `LAB_SEED = 21`, separate from the notebook's `seed=7` dataset.
- **The reference must be quantised.** `expected_features.csv` is computed from the
  *int16-quantised* samples, not the float originals, or the acceptance test fails for
  the wrong reason.
- **Acceptance test is three decimals, not four.** MicroPython on ESP32 uses
  single-precision floats; accumulating 256 fourth powers for the kurtosis makes the
  fourth digit differ. Saying this up front prevents an hour of false bug-hunting.
  `make_wokwi.py` verifies the device code against the reference in CPython —
  agreement is ~1e-15 in double precision, so any device disagreement is precision or a
  student bug, never a broken lab.

---

## Build gotchas hit and fixed

- **pptxgenjs `LAYOUT_16x9` is 10 in wide.** `defineLayout` at 13.333 × 7.5 is mandatory.
- **Figure aspects are ~2.3–2.5, not 2.9.** Hardcoded widths overflowed the slide.
  `build_deck.js` now uses `figureFit(slide, file, yTop, yBottom, maxW)`, reading aspects
  that `make_figs.py` writes into `results.json`.
- **LibreOffice vertically centres text boxes.** A one-line bullet in an `h: 0.95` box
  rendered at y ≈ 1.90 and collided with the figure. Bullet boxes are now `h: 0.46` with
  explicit `valign: "top"`; `box()` bodies likewise.
- **The workflow strip needs a dark variant.** The light-background PNG rendered as a
  white slab on the dark summary slide — `fig_workflow_dark.png` is generated alongside.
- **numpy 2.x:** `np.ptp(a)`, not `a.ptp()`.
- **`results.json` is rewritten by `make_figs.py`.** `make_wokwi.py` must read-modify-write
  it (it adds `lab_rows`, `lab_windows`) and must run *after* `make_figs.py`.
- Overlapping spectra are unreadable when all three classes peak at 30 Hz — the states
  figure offsets them by decades in log space and hides the y ticks.

---

## Hooks into later weeks

- `week8_dataset.csv` (2928 × 14) is the direct input to Week 9.
- `features.py` on the device is the front end that Week 11 attaches a m2cgen-exported
  decision tree to.
- The timing measurement in Lab 8 B3 establishes the latency budget that Week 11's
  inference has to fit inside.
- The message schema discussion in Week 12 builds on "publish features, not waveforms",
  which is foreshadowed on the workflow strip.
- Exercise 8 (a pure-Python feature function, no NumPy) is deliberately the first cell of
  next week's device work.

## Slides note

### Page 1

Set the frame for the whole second half. In weeks 1-7 every decision in their pipeline was a threshold they typed in by hand. From this week on, thresholds get learned - but a learning algorithm will not accept a stream of samples. It wants a table. Say plainly that building that table correctly is most of the work of industrial ML, and that the most common failure mode in this field is not a bad model but a dataset that was assembled or split wrongly, producing a number that looks excellent and does not survive contact with a real machine. Introduce the rig: motor, rotor disc, two bearings, accelerometer on the drive-end housing at 2000 Hz. Three states - normal, imbalance, outer-race bearing spall. Tell them the data is synthetic and why: we have no rig, and a synthetic rig gives us exact ground truth, which is what a teaching dataset needs. Point out the notebook filename and say the whole lecture is reproducible line by line; the five-hour session is lecture in the first half, this notebook plus the Wokwi lab in the second. Ask the room: who has recorded vibration from a real machine before? It calibrates how much mechanical background to assume.

### Page 2

Left panel first. Walk down the three traces. Normal: a modest 30 Hz wave in noise. Imbalance: obviously bigger, same shape - a student can see this one without any machine learning, and a plain RMS threshold would catch it. Bearing fault: this is the important one. Ask the room to point at the fault. They will struggle, which is the point - the impulses arrive every 9.3 ms and are buried under the 1x component and the noise floor. Now move to the right panel. The spectra are offset vertically so they do not cover each other; say so explicitly or someone will read the y-axis as absolute. Point at the 30 Hz line, common to all three. Then the bearing trace: the comb near 108 Hz, and the broad hump around 600 Hz where the housing rings. Connect it to the BPFO formula from the notebook - 3.6 times shaft rate, 108 Hz at 1800 rpm. The engineering message: two different faults announce themselves in two different frequency regions, so one threshold on one number cannot cover both. Expected objection: why not just look at the spectrum by eye? Answer: you can, for one machine; you cannot for two hundred machines reporting every minute.

### Page 3

This is Week 3 material returning with consequences. Left panel: the grey curve is the true 600 Hz ring from the bearing housing. The red dots are what you get sampling at 800 Hz. Trace the dots with your finger - they lie exactly on the dashed 200 Hz wave. Read the arithmetic aloud: 800 minus 600 is 200. That 200 Hz component is not in the machine and no amount of clever software will remove it afterwards, because the information was destroyed at the ADC. Right panel: at 2000 Hz the resonance is recovered honestly. Now the decision rule. A student who sizes fs from the shaft speed - 30 Hz, so a few hundred hertz should do - builds a system that sees imbalance perfectly and is structurally blind to bearing damage. So the question is never 'how fast does the shaft turn' but 'what is the highest frequency that carries the fault I care about'. Stress the analogue filter: aliasing must be stopped in hardware before the ADC, not in MicroPython afterwards. Ask: what would you have to change if the housing resonance were at 3 kHz? Exercise 1 in the notebook makes them work it out.


### Page 4

This slide is the mechanical heart of the week. A classifier needs a fixed-length input, so the continuous stream has to be cut up. Walk it top to bottom. One run is four seconds at 2000 Hz, eight thousand samples. The window is 256 samples, 128 milliseconds. The hop is 128, so each window starts halfway through the last one - that is the 50 percent overlap, and you can see the coloured boxes interleaving. Sixty-one windows come out of one run. For each window we compute twelve numbers and write one row. The table at the bottom is real output from the notebook, not a mock-up - these are the first three windows of run zero. Point at the run column and say it looks like bookkeeping but is the most important column in the table; slide 8 will explain why. Then deliver the warning in orange at the bottom: because of the overlap, row 1 and row 2 are not independent observations. They share 128 samples. Let that sit, because in three slides it becomes a twelve-point accuracy illusion. Someone will ask why overlap at all: it multiplies training rows and smooths the decision stream. It is not free.



### Page 5

Seven numbers, and the table in the notebook shows what each one buys. Start with the DC rule: an accelerometer bias drifts with temperature and mounting, so subtract the window mean before computing anything else. Leave it in and zero-crossing rate measures your bias instead of your machine. Now the two panels. Left: crest factor, peak over RMS, by class. Normal sits near 2.5, imbalance slightly lower - a bigger sine is still a sine - and the bearing fault jumps to 3.3 with a long upper whisker. Impulses raise the peak faster than they raise the RMS; that ratio is the whole idea. Right: RMS against kurtosis. The orange imbalance cluster separates on RMS alone. The blue and violet clusters sit on top of each other in RMS and separate vertically, on kurtosis. Read the headline numbers off the callout. The sentence to leave them with: RMS answers how much, crest and kurtosis answer what shape, and a diagnosis needs both. Note that neither panel gives clean separation - the clusters overlap - which is exactly why we will need a classifier rather than a pair of thresholds.


### Page 6

Five more features: the dominant frequency, and four band energies expressed as a fraction of the window's total power. Justify both design choices out loud. Fixed hertz bands rather than shaft orders, because order tracking needs a tachometer we do not have. Fractions rather than absolute power, because a loose accelerometer halves every absolute number and barely touches a ratio - the feature becomes gain-invariant for free. Left panel: the four shaded bands over the mean spectrum of each class. Right panel: the same information as bars. Imbalance loads e_1x to 0.83. The bearing fault loads e_hi from 0.146 to 0.289. Now spend real time on the third bar group. We designed e_bpfo specifically to catch the outer-race defect, and it does nothing - 0.012 healthy against 0.014 damaged. This is not a coding error, it is mechanics: an impulse excites whatever likes to ring nearby, so the energy lands in the 600 Hz resonance and not at the 108 Hz repetition rate. Two lessons. First, check your features against data instead of trusting the whiteboard. Second, the technique that does recover that periodicity is envelope analysis - name it, say it is outside our scope, and point anyone interested at the Randall and Antoni tutorial in the notebook references.


### Page 7

Left panel: honest accuracy against window length, with error bars over ten splits. Before reading the trend, make them look at the error bars - about 0.045. The apparent dip from 64 to 128 is smaller than one standard deviation, so it is noise, not a finding, and saying so out loud teaches more scepticism than any lecture on statistics. The rise from 256 to 1024 is about 0.06, just over one standard deviation: a weak but real trend. Now the key point. Accuracy never stops improving over this range, so it cannot be the thing that decides N. Right panel shows what actually decides it: frequency resolution falls as fs over N while decision latency rises as N over fs. They cross at 256. At N = 64 the bins are 31 Hz wide and the 1x and 2x lines land in neighbouring bins - the spectral features have nothing left to work with. At N = 1024 the accuracy is best but every decision lags the machine by half a second and the buffer alone is 4 KB of ESP32 RAM before any FFT workspace. We take 256. Ask the room: what if this were a protective trip rather than a maintenance alert? Then 128 ms may already be too slow and you would trade accuracy for speed. That is an engineering decision, not a machine-learning one.


### Page 8

The most important slide of the week. Start by writing the wrong line on the board: X_train, X_test = train_test_split(X, y). Everyone has typed it. It is correct when rows are independent draws, and ours are not, for two separate reasons. One, overlap: window k and k+1 share half their samples, so a test row sits between two of its own training neighbours. Two, run identity: every run has its own shaft speed, gain, noise floor and frame resonance, and every row of that run carries the same label - so a model that learns 'this is run 23' can read the answer off it. Left schematic shows both schemes. Right bars show the damage: with twelve features, 0.933 under a random split against 0.810 when whole runs are held out. Say the two questions aloud, because the numbers are answers to different questions, not a good and a bad estimate of one thing. Also point at the left pair: on raw samples the honest number is 0.537, barely above the 0.333 of guessing, because sample 40 of a window means nothing at a random phase. Twelve features buy +0.273. Generalise the rule: if rows share a source - same run, machine, shift, patient - split on that source. Someone will ask whether overlap alone causes this; exercise 5 has them measure it.



### Page 9

Push back gently on the textbook advice 'always standardise'. It is a fine default and a poor explanation, and students who follow rules without conditions cannot debug anything. Standardising matters when a model measures distance, as k-NN and SVM do, or when it regularises coefficients. A decision tree only ever asks whether one feature exceeds a threshold, so scaling is literally irrelevant to it - and the tree is what we will deploy in Week 11. Now the experiment. With band energy as a fraction of total power, our twelve features already share a scale within a factor of 121, and standardising changes k-NN by minus 0.019, which is noise. Rebuild the same features with absolute band power and the ratio explodes to about forty-one thousand, e_1x dominates every distance, k-NN drops to 0.765, and standardising hands 0.076 straight back. So the condition is incomparable magnitudes, not superstition. Two takeaways. First, good feature design can remove the problem before scaling has to fix it. Second, fit the scaler on training rows only - use a pipeline so you cannot get it wrong by hand. Flag forward: whatever you choose becomes twelve constants that must be copied into the ESP32 firmware.


### Page 10

Bridge from laptop to device, so the week lands in the hardware they actually use. Everything on the left of the workflow - window, features - has to run on the ESP32 in MicroPython, with no NumPy and no SciPy. Walk the code slowly. Note the mean subtraction on line four; note that we accumulate sum of squares, running peak and zero crossings in a single pass over the buffer, because a second pass costs another 256 iterations of interpreted Python. Right-hand boxes. The FFT one: a 256-point radix-2 FFT is about 2048 butterfly operations in interpreted Python, which is slow and memory-hungry; since we only need four band energies, the Goertzel algorithm computes a single bin with two state variables and a short loop. Mention it now and they will not be surprised in Lab 8. The second box is the one that bites people: the device must compute identically, not similarly. Same window length, same feature order, same scaler constants. A transposed feature order produces a model that is confidently wrong and very hard to debug. Then set up the lab: the acceptance test is that the device's CSV rows match the notebook to three decimal places - the fourth digit differs because the ESP32 computes in single precision, and saying so up front pre-empts an hour of false bug-hunting. If they match, the week's work is verified end to end.


### Page 11

Hand over to the lab half of the five-hour session. Read the three blocks in order. The laptop half is mostly running the notebook and reading it, but insist they actually verify the feature code against NumPy rather than assuming - that habit is what makes the device comparison meaningful later. The Wokwi half is the new work: Wokwi cannot produce realistic vibration, so we store a generated waveform on the device file system and stream it as if it were the accelerometer. Say clearly that this is a deliberate simulation choice, not a fudge - it gives every student identical data and exact ground truth. The acceptance test is the part to emphasise: three decimal places between device and notebook. Say out loud that the fourth digit will differ, because MicroPython on the ESP32 uses single-precision floats, or the room will lose an hour to false bug-hunting. A disagreement in the second decimal is a real bug, almost always the DC removal or the order of operations, and finding it today is far cheaper than finding it in Week 11 with a trained model on top. Remind them the CSV is not a throwaway - Week 9 trains on this exact file and Week 11 puts the resulting model back on the device. Anyone who loses it repeats today. Finally, the one-paragraph note: it costs them five minutes and gives you a reading on whether the feature discussion landed.


### Page 12

Close by walking the strip left to right and naming each stage: sense, window, features, label, split, scale, and then Week 9 trains the classifier. Point at the dashed box under the first four stages - that whole front end runs on the ESP32 in MicroPython, and it is what Lab 8 builds today. Then read the six rules. Spend the most time on rules four and five, because they are the two that separate a student who can run scikit-learn from an engineer who can be trusted with a maintenance decision. Rule four: e_bpfo was a reasonable, physics-motivated guess and it carried nothing, so check rather than assume. Rule five: the 0.123 inflation was not a subtle statistical effect, it was the difference between answering a question nobody asked and answering the one the maintenance engineer actually has. Remind them the notebook has eight exercises and real references, and that exercise 8 - a pure-Python feature function with no NumPy - is literally the first cell of next week's device code. Finish by naming next week: training classifiers on week8_dataset.csv, comparing decision trees, logistic regression and k-NN, and asking which of them could possibly fit in 200 KB of RAM.




