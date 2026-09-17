# Lab 11 — The Edge Pipeline on the ESP32

**01211271 Industrial AI and IoT** · Lecture 11 · Electromechanical Manufacturing Engineering

**Time:** 180 minutes (the second half of today's session)
**Files:** `iaiiot26_Lect11_nb.ipynb`, `Lecture11_Wokwi.zip`
**Platform:** Wokwi ESP32 — https://wokwi.com/ — no hardware required

---

## What you are building

A microcontroller that decides by itself.

By the end of this lab the ESP32 in your browser reads a vibration signal, computes all
twelve features including a 256-point FFT, runs the Lecture 9 classifier and the
Lecture 10 alarm, and drives an output — with no network connection of any kind.

You are also going to find out whether it *fits*, and you are going to find out by
measuring rather than by hoping.

Three parts, and part A must come first. Everything in parts B and C is an argument
about numbers you have not measured yet.

---

## Setting up (10 min)

1. Open https://wokwi.com/ and start a new **MicroPython on ESP32** project.
2. Unzip `Lecture11_Wokwi.zip`. Copy every `.py` file into the project (use the
   *New file* button, one per file).
3. Replace the project's `diagram.json` with the one from the zip.
4. Check the file list. You should have:

| file | what it is |
|---|---|
| `features.py` | all twelve features, including the FFT |
| `features_lite.py` | the fallback: nine features, no FFT |
| `model.py` | the Lecture 9 classifier, scaler folded in |
| `alarm.py` | the Lecture 10 alarm |
| `main.py` | the device loop |
| `bench.py` | the timing harness |
| `wave_normal.py`, `wave_imbalance.py`, `wave_bearing.py`, `wave_unknown.py` | 2 s recordings, int16, base64 |
| `expected_features.csv` | the NumPy reference values for every window |

The four waveforms are **fresh runs** (seed 41). Neither model has seen them.

---

## Part A — Measure (45 min)

Nothing in this lab means anything until you know what your board costs.

**A1. Run `bench.py`.** Rename it to `main.py` temporarily, or add
`import bench; bench.main()` to the top of `main.py`. Record every row of the table:

| stage | your µs | % of the 128 ms window |
|---|---|---|
| 7 time-domain features | | |
| 256-point FFT | | |
| 5 frequency features | | |
| all 12 features | | |
| 9 lite features (no FFT) | | |
| classifier | | |
| alarm | | |
| **total per window** | | |

**A2. Compute your two ratios.**

```
FFT / time-domain features       = ______
whole pipeline / time-domain     = ______
```

The lecture measured 8.5× and 10.2× on a desktop MicroPython build. Your absolute
microseconds will be *tens of times larger*; that is expected and not a problem. Your
**ratios** should be close. If they are not, say in your report which stage moved and
propose a reason — the ESP32's FPU, the flash cache, and the way MicroPython indexes
`array('f')` are all fair suspects.

**A3. The verdict.** Does the full twelve-feature pipeline fit the 128 ms window on your
board? State the margin as a percentage of the budget. If it does not fit, you are on
the part C fallback branch and should say so now.

**A4. Heap.** `bench.py` prints the heap used by one pass and the free heap. Record
both. Then answer in one sentence: if the FFT work buffers were allocated *inside*
`_fft` instead of at import, which of those two numbers would change, and what would
happen to the device after a fortnight of running?

---

## Part B — Deploy and verify (75 min)

**B1. Verify before you trust.** Set `WAVE = "wave_bearing"` in `main.py` and run it.
Take the twelve features printed for window 0 and compare them, by hand, with row
`bearing, 0` of `expected_features.csv`.

> **They must agree to at least three decimal places.** Not eight — the ESP32 computes
> in float32 and the reference is float64, and section 7 of the notebook shows the
> disagreement is in the seventh significant figure.

A device that computes the wrong features will still print confident labels. This check
is the only thing standing between you and a plausible wrong answer. Do not skip it,
and record in your report that you did it.

**B2. The three known states.** Run `wave_normal`, `wave_imbalance` and `wave_bearing`
in turn. For each, record:

| wave | label | median margin | median anomaly score | driver | windows raised |
|---|---|---|---|---|---|
| normal | | | | | |
| imbalance | | | | | |
| bearing | | | | | |

**B3. The budget under real conditions.** `main.py` prints the mean microseconds per
window and the percentage of the budget used. Compare with your A1 total. If they
differ by more than about 10 %, find out why before continuing — printing over the
serial port is not free.

**B4. The actuator.** The on-board LED (GPIO 2) is driven by `set_actuator`. Watch it
during the bearing run and describe, in one sentence, the relationship between the LED
and the `raised` column. Then explain why the code writes the pin only when the state
*changes* rather than every window.

---

## Part C — Break it (60 min)

**C1. The fault nobody trained on.** Set `WAVE = "wave_unknown"`. It is a loose mounting
bolt: a large structural resonance at 330 Hz. No training set in this course contains
it. Record the same row as in B2.

Then answer, in a short paragraph each:

* **What did the classifier say, and how confident was it?** Compare its margin with its
  margin on `wave_normal`. Explain the result — and note that "the model is broken" is
  not the explanation.
* **What did the alarm say, and which feature drove it?** The score will be very large.
  Explain why that magnitude is *not* a measure of severity, using the healthy standard
  deviation of the driver feature.
* **What should the device actually do?** There is no single correct answer. A good one
  says what goes to the actuator, what goes in the log, and what a technician arriving
  at the machine is told. A very good one says what should be kept for retraining.

**C2. The design decision.** Choose one and defend it in half a page.

*Option 1 — keep the FFT.* You measured that it fits. Say by what margin, and say what
you would do if the customer later asked for a 500 Hz sample rate instead of 2000 Hz.

*Option 2 — take the lite path.* Your board could not fit the full pipeline, or you
judged the headroom too thin. Switch `main.py` to `features_lite`, measure again, and
state clearly in the report that **the deployed model would have to be retrained and
re-validated on the nine lite features**, because the exported `model.py` and `alarm.py`
were fitted on the twelve. Estimate what that work would cost.

Either answer earns full marks. An undefended answer earns none.

**C3. Fail-safe, on purpose.** Break something and watch the device survive it. Pick one:

* corrupt a few samples in the waveform so a feature returns `inf` or `nan`;
* raise an exception inside `model.predict`;
* comment out the `Pin` import so the actuator write fails.

Record what the device printed and what the actuator did. Confirm that it kept running
and that the failure appears in the log.

---

## What to hand in

A short report, three to four pages:

1. **The measured stage table** from A1, with your two ratios and the fit verdict.
2. **The verification evidence** from B1 — the two rows of numbers, side by side.
3. **The three-state table** from B2 and the unknown-fault row from C1.
4. **The three paragraphs** from C1.
5. **Your design decision** from C2, defended.
6. **One screenshot** of the serial output during the run you are proudest of.

---

## Marking

| | weight |
|---|---|
| A — measurement complete, ratios correct, verdict stated | 25 % |
| B — verification done and evidenced; three states correct | 30 % |
| C1 — the three explanations, especially the z-score caveat | 25 % |
| C2 — design decision defended with your own numbers | 15 % |
| C3 — fail-safe demonstrated | 5 % |

Marks are lost for: quoting the lecture's microseconds instead of your own; reporting
labels without the B1 verification; and claiming the alarm score is a severity.

---

## If you get stuck

**`MemoryError` on import.** The FFT buffers need about 4.5 KB. Run `gc.collect()`
before importing `features`, and do not import both `features` and `features_lite` in
the same program unless you need to.

**Features disagree in the third decimal.** Check that `SCALE` is being applied to the
raw int16 counts, and that your window start indices step by 128 and not by 256.

**Wokwi runs very slowly.** The simulator is slower than real silicon and varies with
your browser. Run `bench.py` three times and take the median — and say in your report
that you did.

**The device never raises on `wave_bearing`.** That is the correct behaviour for part of
the run: the alarm needs 3 of the last 5 windows over threshold. Look at the `raised`
column over the whole run rather than at window 0.

---

## Looking ahead

The device now produces, every 64 ms, a label, a margin, an anomaly score, a driver name
and a raised flag — and it has no idea anyone is listening. Next week it starts talking
to NETPIE, and the first question will be how little of that stream actually needs to be
sent. Exercise 8 in the notebook is the warm-up; attempt it before Lecture 12.
