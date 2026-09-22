# Lab 9 — Choose a Model and Defend the Choice

**01211271 Industrial AI and IoT** · Lecture 9 · Electromechanical Manufacturing Engineering

* **Time:** 180 minutes (the second half of today's session)
* **Files:** `iaiiot26_Lect9_nb.ipynb`

---

## What you are building

One trained model, exported as `lecture9_model.json`, and one paragraph that justifies
it on three axes at once: accuracy, deployed size, and inference cost.

That file is not a throwaway. **Lecture 11 turns those numbers into MicroPython and
runs them on the ESP32 that produced your features in Lab 8.** If you pick a model
that cannot be exported, you will have nothing to deploy.

There is no Wokwi work this week. Everything is on the laptop — but every decision you
make today is constrained by a device you will not touch until Lecture 11, and that is
the point.

---

## Part A — Reproduce (60 min)

Work through the notebook from the top. Run every cell.

**A1.** Stop at §4 and write down two numbers: the tree depth the validation curve
picks, and the *k* that k-NN picks. Both are far more conservative than most people
guess. In one sentence, say why — the answer is not "the model is bad".

**A2.** In §5, look at the two learning curves and answer the question a manager would
actually ask: *should we spend another week collecting data?* Give a different answer
for each panel and say what distinguishes them.

**A3.** In §7, cover the right-hand column of the cost table with your hand and pick a
model on accuracy alone. Uncover it. Did your choice survive?

---

## Part B — Your own comparison (90 min)

**B1. A different knob.** The notebook tunes `max_depth`. Instead, set
`max_depth=None` and tune `min_samples_leaf` over `[1, 5, 20, 50, 200, 500]` on the
validation runs.

Report the test accuracy and the value chosen. Does it reach the same place as tuning
depth? Which of the two knobs would you rather explain to a maintenance engineer, and
why?

**B2. A sixth model.** Add one model family the notebook does not cover. Reasonable
choices: `GaussianNB`, `GradientBoostingClassifier`, `MLPClassifier`,
`ExtraTreesClassifier`, an SVM with an RBF kernel.

Three rules, and the first is the one that gets broken:

1. **Evaluate it on the same eight splits** as everything else, and report the paired
   difference against the decision tree. A number from a fresh split is not comparable
   and is worth nothing.
2. Tune exactly one hyperparameter, on the validation runs.
3. Measure its exported size with `m2cgen` — or, if it cannot be exported, say so and
   explain what it would have to carry instead.

**B3. Extend the cost table.** Rebuild the §7 table with your two additions. Keep all
four columns: chosen knob, bytes, operations per decision, accuracy.

---

## Part C — Commit (30 min)

**C1.** Choose one model. Run the §9 cell to export `lecture9_model.json`.

**C2.** Write the justification. One paragraph, and it must mention all three axes.

A paragraph that says *"I chose the random forest because it scored highest"* has
missed the entire lecture. So has one that says *"I chose the linear SVM because it is
smallest"*. The point is the trade, made explicitly.

**C3.** State, in one line, **how many times you scored the test set.** The honest
answer is once. Writing it down is what makes the discipline real.

---

## Deliverables

1. Your extended comparison table from B3, with paired differences and their standard
   errors
2. Your answers to A1, A2 and A3 — three short paragraphs
3. `lecture9_model.json`
4. The Part C justification paragraph
5. The line stating how many times the test set was scored
6. Your notebook, run end to end

## Marking

| | |
|---|---|
| Part A answered, with reasoning rather than restated numbers | 20 % |
| B1 — second knob tuned correctly on validation | 15 % |
| B2 — sixth model evaluated on **shared splits** with paired differences | 25 % |
| B3 — cost table complete, including size and operation count | 15 % |
| Part C — justification covering all three axes | 20 % |
| The test-set line, answered honestly | 5 % |

A student who reports a worse model with a correct protocol scores above one who
reports a better model with a broken one. In this field the protocol is the skill;
the model is a library call.

---

## Traps to avoid

| symptom | what happened |
|---|---|
| your new model beats everything by a wide margin | it was evaluated on a different split, or on the validation set |
| accuracy jumps when you use `train_test_split` | you have gone back to splitting by row — Lecture 8, slide 8 |
| `LinearSVC` warns about convergence | raise `max_iter`; do not ignore it, the coefficients are not final |
| k-NN scores 1.000 on training data | it will, always — the nearest neighbour of a training point is itself |
| the tuned model is far simpler than you expected | that is not a bug. It is your data telling you it has 48 independent observations |

---

## Looking ahead

Lecture 10 will make two uncomfortable observations about today's results.

The first is that **accuracy was the wrong score all along.** Every model here landed
between 0.82 and 0.88, but that single number hides which state is being confused with
which — and a missed bearing fault costs a gearbox while a false alarm costs an hour.
Those are not equally bad, and accuracy treats them as if they were.

The second is harder. Our dataset has sixteen labelled runs of each fault, balanced
perfectly. **No real factory has that.** Faults are rare, and nobody runs a machine to
destruction to build you a training set. Lecture 10 asks what you do when you have
plenty of healthy data and almost no labelled faults at all.

Bring `lecture9_model.json` and your comparison table.
