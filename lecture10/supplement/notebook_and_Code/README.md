# Lecture 10, Supplement 1 — code

**01211271 Industrial AI and IoT**

Unzip beside `Lecture10_Supplement1_Anomaly_Detection.ipynb` and it will run (about 20 s).

| file | what it is |
|---|---|
| `rig.py` | exactly Lecture 10's rig: the rotor, the twelve features, `make_fleet(seed=23)` |
| `detectors.py` | new: the four anomaly scores as short readable classes, and Lecture 10's evaluation protocol |

`detectors.py` contains:

* `ZScore` — mean ± kσ, scored as max |z|. The detector Lecture 11 deploys.
* `Mahalanobis` — the same question asked of all features together. Uses the
  pseudo-inverse, because `rms` and `std` are the same number and the correlation matrix
  is singular.
* `IForest` — scikit-learn's isolation forest with Lecture 10's settings.
* `PCAResidual` — reconstruction error, plus `t2()`, the half Lecture 10 did not use.
* `oof_scores()` and `summary()` — Lecture 10's five grouped folds, unchanged, so

```python
import rig, detectors as D
X, y, g = rig.build_table(rig.make_fleet(seed=23))
print(D.summary(D.oof_scores(X, y, g)["S"], y))
```

reproduces the Lecture 10 table to the third decimal. `oof_scores(..., contamination=0.02)`
slips 2 % faulty windows into the training set, as in section 8 of the notebook.
