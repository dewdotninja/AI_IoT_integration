# Lab 10 — Build the Alarm, Not the Model

**01211271 Industrial AI and IoT** · Lecture 10 · Electromechanical Manufacturing Engineering

**Time:** 180 minutes (the second half of today's session)
**Files:** `Lecture10_Evaluation_and_Anomaly_Detection.ipynb`

---

## What you are building

One JSON file: `lecture10_alarm.json`. Twenty-five numbers, a persistence rule, a
false-alarm rate you have chosen on purpose, and a date on which it expires.

No model is trained today. That is the point. Lecture 9 spent three hours choosing a
classifier and gained 0.053 of accuracy over a depth-2 tree. Today you will cut
nuisance alarms twenty-five-fold with a five-window rule and no machine learning at
all — and the difference between those two afternoons is worth thinking about.

Laptop only, as in Lab 9. Lecture 11 puts both artefacts on the device.

---

## Part A — See it fail (45 min)

Run the notebook to the end of section 5. For each of the three diagnostics below,
write **one sentence** saying what it told you that accuracy did not. Not what the
number was — what it told you.

**A1. The majority baseline.** `always normal` scores 0.880 on this fleet. What is the
majority-class accuracy of a fleet with 1 % faults? At what prevalence does accuracy
stop being able to distinguish a working detector from a broken one?

**A2. The confusion matrix.** Accuracy 0.983, bearing recall 0.577. Which cell of the
matrix would you show a maintenance manager, and which one would you show a plant
director? They are different cells, and the reason is not cynicism.

**A3. The fold spread.** Grouped cross-validation gives a bearing recall of 0.59 with
a standard deviation of 0.34. Write the sentence you would put in a report. It must
contain the mean, the spread, and the number of machines the estimate rests on.

---

## Part B — Choose the operating point (90 min)

**B1. The cost ratio.** Pick one and defend it in two or three sentences. There is no
correct answer; there is only a defended one.

A defensible answer looks like: *"I assumed 50:1. A destroyed gearbox on this rig is
roughly a week of lost production plus the part; an unnecessary inspection is about an
hour of a technician's time. 50:1 is the low end of that."*

An indefensible answer looks like: *"I used 100:1 because it gave the best recall."*

**B2. The threshold.** Using the isolation forest scores from section 7, find the
threshold that minimises expected cost at your ratio. Then find the threshold at the
99th percentile of healthy scores. Report both, and say which one you would ship and
why.

You should find they disagree, and the reason matters: the cost-optimal threshold
assumes your cost ratio and your fault prevalence are correct, while the quantile
threshold only assumes you know what a healthy machine looks like. On a new machine
with no failure history, only one of those assumptions is safe.

**B3. Persistence.** Sweep *m* and *n* over `m in 1..5`, `n in 1..9`, `m <= n`. For each
pair record: false alarms per window, bearing recall, the fraction of healthy machines
raising at least one alarm, and the added detection delay in milliseconds.

Choose one pair. Your justification must mention the delay — a rule that never false
alarms because it needs thirty seconds of agreement is not a bargain.

**B4. Drift.** Re-run section 9 with `n_months=72`. How many months does your chosen
threshold survive before the false-alarm rate exceeds what you decided in B1 was
tolerable? That number is your `review_after_months`.

---

## Part C — Write the specification (45 min)

Export `lecture10_alarm.json`. It must contain, at minimum:

| field | why it is there |
|---|---|
| `scaler_mean`, `scaler_scale` | the baseline, twelve numbers each |
| `threshold`, `threshold_quantile` | the operating point and how it was chosen |
| `persistence` | your *m* and *n* |
| `expected_false_alarm_rate_per_window` | what you are buying |
| `expected_bearing_recall` | and what it costs you |
| `recall_uncertainty_note` | how many spalls that estimate rests on |
| `fitted_on_healthy_windows` | how much healthy data the baseline saw |
| `review_after_months` | from B4 |

Then write the **one-page alarm specification** that would accompany it — the document
a maintenance engineer reads, not the JSON. It answers, in plain language:

1. What is measured, and how often?
2. What triggers an alarm?
3. How often will it be wrong, and in which direction?
4. What should the person receiving the alarm do?
5. When does this document expire, and who re-estimates it?

Question 4 is the one students skip and the one that decides whether the system is
used. An alarm nobody knows how to act on is worse than no alarm.

---

## Deliverables

1. Your A1–A3 sentences
2. The cost-ratio justification from B1
3. Both thresholds from B2 and your choice, with reasoning
4. The persistence sweep table and your chosen *m*, *n*
5. The `review_after_months` figure from B4, with the evidence
6. `lecture10_alarm.json`
7. The one-page alarm specification

## Marking

| | |
|---|---|
| A1–A3, reasoning rather than restated numbers | 20 % |
| B1 — a cost ratio defended in engineering terms | 15 % |
| B2 — both thresholds, and a defended choice between them | 20 % |
| B3 — persistence sweep complete, with the delay accounted for | 20 % |
| B4 — review interval derived from evidence | 10 % |
| C — the specification, especially questions 3 and 4 | 15 % |

A specification that honestly reports a poor recall scores above one that quotes a
good recall without saying it rests on six machines.

---

## Traps to avoid

| symptom | what happened |
|---|---|
| your detector's false-alarm rate is far below the quantile you set | you fitted the quantile on windows the detector trained on |
| recall is suspiciously high | check you have not accidentally included fault runs in the healthy baseline |
| the persistence rule kills recall entirely | *n* is longer than the fault lasts in your test runs; check the run length |
| the drift experiment shows no drift | you re-fitted the scaler each month — the fixed-threshold arm must use the year-one scaler |
| alarm rate is exactly 0.000 | you may be below the resolution of the data: 8052 healthy windows cannot measure a rate below about 1 in 8000 |

---

## Looking ahead

Lecture 11 is where the course converges. You will arrive with two files:

* `lecture9_model.json` — 63 numbers. Names the fault, but only faults it was trained on.
* `lecture10_alarm.json` — 25 numbers and a persistence rule. Needs no labels, but
  cannot say what is wrong.

Both fit on an ESP32 with room to spare. Lecture 11 exports them to MicroPython,
measures inference time against the 128 ms window budget you established in Lab 8, and
runs them on the device that produced the features in the first place.

Bring both files.
