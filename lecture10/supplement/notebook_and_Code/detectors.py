"""
detectors.py  --  Lecture 10, Supplement 1

The four anomaly scores, written so that each one is a handful of readable lines
rather than a library call, plus the exact evaluation protocol Lecture 10 used.

Every detector has the same two-step shape:

    fit(H)      learn what "healthy" looks like from healthy windows only
    score(X)    one number per window: how unlike healthy is this?

and then, separately, a THRESHOLD: a quantile of the healthy scores.  Keeping the
score and the threshold apart is the whole design -- the score says "how odd",
the threshold says "odd enough to act on", and only the second one is a policy.

    mean +- k sigma     how many standard deviations is the worst feature out?
    Mahalanobis         the same question, asked of all features together,
                        allowing for the fact that they move together
    isolation forest    how few random cuts does it take to fence this window off?
    PCA residual        how much of this window can the healthy directions NOT
                        explain?  (+ its other half, T^2: how far along them)
"""
import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler


# ============================================================ mean +- k sigma
class ZScore:
    """max |z| over features.  25 numbers on the device: 12 means, 12 sigmas,
    one threshold -- which is why it is the detector Lecture 11 deploys."""

    def fit(self, H):
        self.mu = H.mean(axis=0)
        self.sd = H.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        return self

    def z(self, X):
        return (X - self.mu) / self.sd

    def score(self, X):
        return np.abs(self.z(X)).max(axis=1)

    def driver(self, X, names):
        """Which feature is furthest out -- the name an engineer can act on."""
        return [names[i] for i in np.abs(self.z(X)).argmax(axis=1)]


# ================================================================ Mahalanobis
class Mahalanobis:
    """sqrt( z^T  C^-1  z ) with C the healthy correlation matrix.

    Where max|z| draws a BOX around the healthy data, this draws an ELLIPSE
    that leans the same way the data does.  The price: C must be invertible,
    and on this rig it is not -- `rms` and `std` are the same number once the
    mean is removed -- so we use the pseudo-inverse, which quietly ignores any
    direction the healthy data never moves in.
    """

    def fit(self, H):
        self.mu = H.mean(axis=0)
        self.sd = H.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        Z = (H - self.mu) / self.sd
        self.C = np.cov(Z, rowvar=False)
        self.P = np.linalg.pinv(self.C, rcond=1e-10)
        self.rank = int(np.linalg.matrix_rank(self.C, tol=1e-10))
        return self

    def score(self, X):
        Z = (X - self.mu) / self.sd
        return np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", Z, self.P, Z), 0.0))


# =========================================================== isolation forest
class IForest:
    """Mean path length to isolate a point, over 200 random trees, turned into
    a score in (0, 1).  Nothing is assumed about the SHAPE of healthy data.

    Lecture 10's settings: standardised features, 200 trees, random_state=0.
    """

    def __init__(self, n_estimators=200, random_state=0, max_samples="auto"):
        self.kw = dict(n_estimators=n_estimators, random_state=random_state,
                       max_samples=max_samples, n_jobs=-1)

    def fit(self, H):
        self.sc = StandardScaler().fit(H)
        self.m = IsolationForest(**self.kw).fit(self.sc.transform(H))
        return self

    def score(self, X):
        return -self.m.score_samples(self.sc.transform(X))


# ============================================================== PCA residual
class PCAResidual:
    """Project onto the k directions that carry 95 % of healthy variance,
    reconstruct, and measure what is left over.

    `score` is the residual (the "reconstruction error", or SPE / Q statistic).
    `t2` is the other half PCA offers for free: how far the window sits ALONG
    the kept directions, in units of their own spread.  Lecture 10 used only
    the first, and that is where its blind spot comes from.
    """

    def __init__(self, var=0.95, k=None):
        self.var, self.k_fixed = var, k

    def fit(self, H):
        self.sc = StandardScaler().fit(H)
        A = self.sc.transform(H)
        if self.k_fixed is None:
            cum = np.cumsum(PCA().fit(A).explained_variance_ratio_)
            self.k = int(np.searchsorted(cum, self.var) + 1)
        else:
            self.k = self.k_fixed
        self.pca = PCA(n_components=self.k, random_state=0).fit(A)
        return self

    def score(self, X):
        A = self.sc.transform(X)
        R = A - self.pca.inverse_transform(self.pca.transform(A))
        return np.sqrt((R ** 2).sum(axis=1))

    def t2(self, X):
        T = self.pca.transform(self.sc.transform(X))
        return np.sqrt((T ** 2 / self.pca.explained_variance_).sum(axis=1))


DETECTORS = {
    "mean ± kσ": ZScore,
    "Mahalanobis": Mahalanobis,
    "isolation forest": IForest,
    "PCA residual": PCAResidual,
}
ORDER = list(DETECTORS)


# ================================================================ protocol
def folds(X, y, groups):
    """Lecture 10's splitter, unchanged -- so the numbers line up exactly."""
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
    return list(cv.split(X, y, groups))


def oof_scores(X, y, groups, cols=None, which=ORDER, contamination=0.0,
               seed=0, extra=False):
    """Out-of-fold scores: every window is scored by detectors fitted on
    OTHER runs' healthy windows only.

    contamination > 0 slips that fraction of faulty windows (from the training
    folds) into the "healthy" fitting set, and ALSO returns the threshold an
    engineer would set from that contaminated set -- believing it clean.
    """
    Xc = X if cols is None else X[:, cols]
    S = {k: np.zeros(len(y)) for k in which}
    T2 = np.zeros(len(y))
    thr = {k: [] for k in which}
    rng = np.random.default_rng(seed)
    for tr, te in folds(X, y, groups):
        h = tr[y[tr] == "normal"]
        if contamination > 0:
            bad = tr[y[tr] != "normal"]
            n_bad = int(round(contamination * len(h) / (1 - contamination)))
            h = np.concatenate([h, rng.choice(bad, size=n_bad, replace=False)])
        for k in which:
            d = DETECTORS[k]().fit(Xc[h])
            S[k][te] = d.score(Xc[te])
            thr[k].append(np.quantile(d.score(Xc[h]), 0.99))
            if extra and k == "PCA residual":
                T2[te] = d.t2(Xc[te])
    out = {"S": S, "fit_threshold": {k: float(np.mean(v)) for k, v in thr.items()}}
    if extra:
        out["T2"] = T2
    return out


def summary(S, y, thr=None, q=0.99):
    """AUC and recall at the q-quantile of HEALTHY scores (Lecture 10's rule),
    or at a supplied threshold."""
    f = (y != "normal").astype(int)
    rows = {}
    for k, v in S.items():
        t = np.quantile(v[y == "normal"], q) if thr is None else thr[k]
        rows[k] = {"auc": float(roc_auc_score(f, v)),
                   "threshold": float(t),
                   "false_alarms": float((v[y == "normal"] > t).mean()),
                   "bearing": float((v[y == "bearing"] > t).mean()),
                   "imbalance": float((v[y == "imbalance"] > t).mean())}
    return rows
