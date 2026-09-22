# Lab 8 — From Sensor Data to a Dataset

**01211271 Industrial AI and IoT** · Lecture 8 · Electromechanical Manufacturing Engineering

* **Time:** 180 minutes (the second half of today's session)
* **Files:** `iaiiot26_Lect08_nb.ipynb`, `wokwi/`

---

## What you are building

By the end of today the same twelve-feature calculation exists in two places — in
Python on your laptop, and in MicroPython on an ESP32 — and you will have proved
they agree. Every remaining week of this course is built on that foundation:

- **Lecture 9** trains classifiers on the CSV you export today.
- **Lecture 11** compiles one of those classifiers back onto the device that produced
  the features.
- **Lecture 12–13** publish these same feature vectors to NETPIE.

If your feature code is wrong today, everything after it is wrong and you will not
find out until Lecture 11.

---

## Part A — On the laptop (60 min)

Work through `iaiiot26_lect08_nb.ipynb` from the top. Run every
cell; do not skim the markdown.

**A1.** Run sections 1–4. Stop at the class summary table in §2 and answer, in your
notes: which single feature separates `imbalance` best, and which separates
`bearing` best? They are not the same feature, and understanding why is the point
of the week.

**A2.** Section 5 is the one to slow down on. Before you run the comparison cell,
write down what accuracy you *expect* from each of the four cells in the table.
Then run it. The gap between the random split and the grouped split is the number
you must be able to explain to someone else by the end of the lab.

**A3.** Run sections 6–8 and confirm `lect08_dataset.csv` is written.
**Back it up somewhere you will still have it in three weeks.**

**A4.** Pick any two of exercises 1–7. Exercise 8 is Part B, so you get it free.

---

## Part B — On the ESP32, in Wokwi (90 min)

Everything you need is in the `wokwi/` folder, and `wokwi/README.md` has the
click-by-click setup.

**B1. Set up the project.** Open a new MicroPython ESP32 project in Wokwi, replace
`diagram.json`, and add `features.py` plus **one** waveform file. Add only one
waveform at a time — all three at once will not fit comfortably in RAM, and
diagnosing a `MemoryError` is not today's lesson.

**B2. Read `main.py` before you run it.** In particular, understand `read_sample()`.
On real hardware that function is an I²C transaction with an MPU6050; here it is a
lookup into a stored recording. Everything downstream of it is production code.
Wokwi cannot shake a rotor, so the sensor is a recording — this is a deliberate
simulation choice, and it has the useful side effect of giving the whole class
identical data with exact ground truth.

**B3. Run it.** You should see 30 CSV rows and three comment lines. Record the last
two numbers: the time your feature code takes per window, and the 128 000 µs the
window itself lasts. Your computation must finish comfortably inside that budget,
or a real device could not keep up with its own sensor. Week 11 adds model
inference on top of the same budget, so note how much headroom you have.

**B4. Repeat for the other two waveforms.** Change `WAVE` in `main.py`, swap the
waveform file, and run again. Eyeball the `crest` and `kurt` columns across the
three states. Do they move the way §2 of the notebook said they would?

---

## Part C — The acceptance test (30 min)

**C1.** Copy the serial output for each waveform into a text file.

**C2.** Compare against `wokwi/expected_features.csv`. That file was computed in
Python **from the same quantised int16 samples your device is reading**, so the
comparison is exact in principle.

**C3. Agreement to three decimal places is a pass.**

The fourth decimal will usually differ and that is not a bug. MicroPython on the
ESP32 uses single-precision floats; NumPy on your laptop uses double precision.
Summing 256 squares — and 256 fourth powers for the kurtosis — makes that
difference visible. Expect `kurt` to be the worst of the seven, for exactly that
reason.

A disagreement in the **second** decimal or worse *is* a bug. In order of how often
it happens:

| symptom | almost always |
|---|---|
| `crest`, `kurt` or `zcr` wrong, `rms` right | DC component not removed first |
| `crest` too large | peak measured on raw samples instead of the AC part |
| `zcr` off by a constant factor | divided by `n` instead of `n − 1` |
| everything wrong from window 1 onwards | window or hop length does not match |

**C4.** Write the one-paragraph note: *which two of the twelve features do you expect
to matter most to a classifier, and why?* Five minutes. Week 9 will tell you whether
you were right.

---

## Deliverables

Submit one zip containing:

1. `features.py` and `main.py` as they ran in Wokwi, plus your Wokwi project link
2. A screenshot of the serial monitor for **one** of the three waveforms
3. Your comparison against `expected_features.csv`, with the worst per-feature
   difference stated
4. The two timing numbers from B3, and one sentence on the headroom you have
5. `lect08_dataset.csv`
6. Your Part A notes (A1, A2) and the Part C paragraph

## Marking

| | |
|---|---|
| Notebook run through, A1 and A2 answered | 25 % |
| Device code runs and produces 30 well-formed rows | 25 % |
| Acceptance test passes at three decimals, differences reported honestly | 30 % |
| Timing measured and interpreted | 10 % |
| Part C paragraph | 10 % |

An acceptance test that fails, **reported accurately with a diagnosis of why**,
scores better than one claimed to pass without evidence.

---

## Stretch task — one FFT bin without an FFT

`features.py` contains a `goertzel()` function that is written but never called.

A 256-point FFT in interpreted MicroPython costs about 2048 butterfly operations
and a workspace you do not have. But we only need a handful of bins. The Goertzel
algorithm gets **one** bin with two state variables and a single pass — and bin *k*
sits at frequency *k · f_s / N*.

At `fs = 2000` Hz and `N = 256`, the bins are 7.8125 Hz apart, so the `e_1x` band
(20–42 Hz) is bins 3, 4 and 5.

1. Call `goertzel()` for bins 3, 4 and 5 and sum the results.
2. Divide by the total AC power, which you already have as `s2` inside
   `time_features`.
3. Compare against the `e_1x` column in the notebook.

It will be close but not equal — `goertzel()` assumes a rectangular window while
the notebook applies a Hanning window. Explaining that difference is worth as much
as getting the number.

4. Time it. How many bins could you afford before a full FFT becomes the cheaper
   option? That is the calculation that decides the Week 11 architecture.

___
Generated by Claude and customized by

<div align="center">
<img src="https://raw.githubusercontent.com/dewdotninja/sharing-github/refs/heads/master/dewninja_logo50.jpg" alt="dewninja"/>
</div>
<div align="center">dew.ninja 2026</div>