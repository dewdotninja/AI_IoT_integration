"""
rig.py — the rotor-rig simulator shared by Lectures 8-14
01211271 Industrial AI and IoT

Synthetic but physics-motivated vibration data for a small motor-driven rotor rig.

Rig model
---------
A 3-phase induction motor drives a rotor disc supported by two rolling-element
bearings.  A MEMS accelerometer is mounted radially on the drive-end bearing
housing and sampled at fs = 2000 Hz.

Three machine states are simulated:

  normal    : residual unbalance only -> modest 1x shaft-rate component
  imbalance : added trial mass on the disc -> large 1x component
  bearing   : outer-race spall -> periodic impulses at BPFO that ring the
              bearing housing resonance

Outer-race defect frequency, for a bearing with n = 9 balls, ball/pitch
diameter ratio d/D = 0.2 and contact angle 0:

    BPFO = (n/2) * (1 - (d/D) cos(phi)) * f_r = 4.5 * 0.8 * f_r = 3.6 * f_r

so at a nominal 30 Hz shaft rate (1800 rpm) the impulses arrive at 108 Hz.

Every run carries its own nuisance variation -- shaft speed, sensor gain,
broadband noise floor, DC bias and a structural tone.  This is what makes a
random train/test split across overlapping windows dishonest: the model can
memorise the run, not the fault.

Lecture 8 built the classification dataset from make_dataset().  Lecture 9 adds
make_speed_sweep(), a separate acquisition campaign used for the soft-sensor
thread: the rig is run across its speed range in the healthy state so that a
regression model can learn to read shaft speed off the vibration alone.
"""

import numpy as np

# ----------------------------------------------------------------- constants
FS = 2000.0                 # sampling rate, Hz
RUN_SECONDS = 4.0           # length of one acquisition run
RUNS_PER_CLASS = 16
CLASSES = ("normal", "imbalance", "bearing")

WIN = 256                   # default window length, samples (128 ms)
HOP = 128                   # 50 % overlap

F_RESONANCE = 600.0         # bearing housing resonance, Hz
TAU_RING = 0.0012           # impulse ring-down time constant, s
BPFO_RATIO = 3.6            # outer-race defect order

# Fixed analysis bands, Hz.  Shaft speed wanders over 28-32 Hz, so the bands
# are wide enough to hold the order they are named for without a tachometer.
BANDS = {
    "e_1x":   (20.0, 42.0),     # shaft rate
    "e_2x":   (48.0, 78.0),     # twice shaft rate
    "e_bpfo": (90.0, 132.0),    # outer-race defect order
    "e_hi":   (400.0, 900.0),   # housing resonance region
}

FEATURE_NAMES = [
    "mean", "rms", "std", "ptp", "crest", "kurt", "zcr",
    "dom_freq", "e_1x", "e_2x", "e_bpfo", "e_hi",
]


# ------------------------------------------------------------ signal synthesis
def _run_params(rng, state):
    """Nuisance parameters that vary from one acquisition run to the next."""
    return dict(
        f_r=rng.uniform(28.0, 32.0),          # shaft rate, Hz
        gain=rng.uniform(0.85, 1.25),         # sensor / mounting gain
        noise=rng.uniform(0.04, 0.20),        # broadband floor, g rms
        bias=rng.uniform(-0.06, 0.06),        # accelerometer DC offset, g
        f_struct=rng.uniform(150.0, 700.0),   # frame resonance -- a confounder
        a_struct=rng.uniform(0.03, 0.15),
        a_1x=(rng.uniform(0.20, 0.38) if state != "imbalance"
              else rng.uniform(0.58, 1.10)),
        a_imp=(rng.uniform(0.45, 1.40) if state == "bearing" else 0.0),
    )


def _synth(rng, p, seconds=RUN_SECONDS, fs=FS):
    """Turn a parameter dict into a waveform.  Shared by every campaign."""
    n = int(seconds * fs)
    t = np.arange(n) / fs

    ph = rng.uniform(0, 2 * np.pi, 4)
    x = (p["a_1x"] * np.sin(2 * np.pi * p["f_r"] * t + ph[0])
         + 0.32 * p["a_1x"] * np.sin(2 * np.pi * 2 * p["f_r"] * t + ph[1])
         + 0.12 * p["a_1x"] * np.sin(2 * np.pi * 3 * p["f_r"] * t + ph[2])
         + p["a_struct"] * np.sin(2 * np.pi * p["f_struct"] * t + ph[3]))

    if p["a_imp"] > 0:
        f_bpfo = BPFO_RATIO * p["f_r"]
        period = fs / f_bpfo
        k = 0
        while True:
            # 1 % random slip, as real rolling elements do
            idx = int(k * period * (1.0 + rng.normal(0, 0.01)))
            if idx >= n:
                break
            tail = np.arange(n - idx) / fs
            ring = (p["a_imp"] * rng.uniform(0.75, 1.25)
                    * np.exp(-tail / TAU_RING)
                    * np.sin(2 * np.pi * F_RESONANCE * tail))
            x[idx:] += ring
            k += 1

    x = p["gain"] * (x + rng.normal(0, p["noise"], n)) + p["bias"]
    return x.astype(np.float64)


def make_run(rng, state, seconds=RUN_SECONDS, fs=FS):
    """Synthesise one acquisition run.  Returns (signal, params)."""
    p = _run_params(rng, state)
    return _synth(rng, p, seconds, fs), p


def make_dataset(seed=7, runs_per_class=RUNS_PER_CLASS):
    """All runs.  Returns list of dicts with signal, label and run id."""
    rng = np.random.default_rng(seed)
    runs, rid = [], 0
    for state in CLASSES:
        for _ in range(runs_per_class):
            x, p = make_run(rng, state)
            runs.append({"x": x, "label": state, "run": rid, "params": p})
            rid += 1
    return runs


# ------------------------------------------------------------------- features
def frame(x, win=WIN, hop=HOP):
    """Slice a 1-D signal into overlapping windows -> (n_windows, win)."""
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def time_features(w):
    """Seven time-domain features for each row of w."""
    mean = w.mean(axis=1)
    ac = w - mean[:, None]                      # remove DC before anything else
    rms = np.sqrt((ac ** 2).mean(axis=1))
    std = ac.std(axis=1)
    ptp = np.ptp(w, axis=1)
    peak = np.abs(ac).max(axis=1)
    crest = peak / np.maximum(rms, 1e-12)
    m4 = (ac ** 4).mean(axis=1)
    kurt = m4 / np.maximum(rms, 1e-12) ** 4     # non-excess kurtosis; 3.0 = Gaussian
    zc = np.diff(np.signbit(ac).astype(np.int8), axis=1)
    zcr = np.abs(zc).sum(axis=1) / (w.shape[1] - 1)
    return np.column_stack([mean, rms, std, ptp, crest, kurt, zcr])


def freq_features(w, fs=FS, normalise=True):
    """Dominant frequency plus four band energies.

    normalise=True gives each band as a fraction of the window's total power,
    which makes the feature independent of sensor gain.  normalise=False gives
    the absolute band power, whose units and magnitude differ wildly from the
    time-domain features -- useful for showing when feature scaling matters.
    """
    n = w.shape[1]
    win = np.hanning(n)
    ac = w - w.mean(axis=1, keepdims=True)
    spec = np.abs(np.fft.rfft(ac * win, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1.0 / fs)
    spec[:, 0] = 0.0                            # DC carries no information here
    total = np.maximum(spec.sum(axis=1), 1e-20)

    dom = f[spec.argmax(axis=1)]
    cols = [dom]
    for lo, hi in BANDS.values():
        m = (f >= lo) & (f < hi)
        band = spec[:, m].sum(axis=1)
        cols.append(band / total if normalise else band)
    return np.column_stack(cols)


def features_of(w, fs=FS, normalise=True):
    """Full 12-feature vector for each row of w."""
    return np.column_stack([time_features(w), freq_features(w, fs, normalise)])


def build_table(runs, win=WIN, hop=HOP, fs=FS, normalise=True):
    """Turn the raw runs into the (X, y, groups) learning problem."""
    X, y, g = [], [], []
    for r in runs:
        w = frame(r["x"], win, hop)
        X.append(features_of(w, fs, normalise))
        y += [r["label"]] * w.shape[0]
        g += [r["run"]] * w.shape[0]
    return np.vstack(X), np.array(y), np.array(g)


def raw_table(runs, win=WIN, hop=HOP):
    """The naive alternative: the raw samples of each window as the features."""
    X, y, g = [], [], []
    for r in runs:
        w = frame(r["x"], win, hop)
        X.append(w)
        y += [r["label"]] * w.shape[0]
        g += [r["run"]] * w.shape[0]
    return np.vstack(X), np.array(y), np.array(g)


# ------------------------------------------------- Lecture 9: the speed sweep
SWEEP_RUNS = 40
SWEEP_FR = (22.0, 40.0)     # stays inside the e_1x band (20-42 Hz)


def make_speed_sweep(seed=11, n_runs=SWEEP_RUNS, seconds=RUN_SECONDS):
    """A healthy-machine speed sweep, for the virtual tachometer.

    The rig has no tachometer.  To build one in software you run the machine
    across its speed range in a known-good state and record the true shaft
    speed from the drive's own setpoint.  Each run still carries its own gain,
    noise floor, bias and frame resonance -- the soft sensor has to work in
    spite of those, not because of them.

    Returns a list of dicts with the signal, the true shaft speed and a run id.
    """
    rng = np.random.default_rng(seed)
    runs = []
    for rid in range(n_runs):
        p = _run_params(rng, "normal")
        p["f_r"] = float(rng.uniform(*SWEEP_FR))
        x = _synth(rng, p, seconds, FS)
        runs.append({"x": x, "f_r": p["f_r"],
                     "run": rid, "params": p})
    return runs


def build_speed_table(runs, win=WIN, hop=HOP, fs=FS):
    """(X, y, groups) for the soft sensor.  y is the true shaft speed in Hz."""
    X, y, g = [], [], []
    for r in runs:
        w = frame(r["x"], win, hop)
        X.append(features_of(w, fs))
        y += [r["f_r"]] * w.shape[0]
        g += [r["run"]] * w.shape[0]
    return np.vstack(X), np.array(y), np.array(g)


# =========================================== Lecture 10: the fleet campaign
# A year of monitoring across a fleet of nominally identical rigs.  Faults are
# RARE, and the ones you catch early are mild -- which is the whole point of
# catching them early, and the reason recall is hard.
FLEET_N = {"normal": 132, "imbalance": 12, "bearing": 6}


def _fleet_params(rng, state):
    """Run parameters for the fleet.  Fault severity spans incipient to severe."""
    p = _run_params(rng, state)
    if state == "imbalance":
        # a light trial mass barely shifts 1x; a thrown blade is unmistakable
        p["a_1x"] = float(rng.uniform(0.42, 1.10))
    if state == "bearing":
        # an early spall rings faintly; a spalled race is loud
        p["a_imp"] = float(rng.uniform(0.22, 1.40))
    return p


def make_fleet(seed=23, counts=None, seconds=RUN_SECONDS, fs=FS):
    """One acquisition per machine per month, across a fleet.

    Returns runs in a shuffled order with a 'label' and a 'severity' field.
    Prevalence is industrial, not academic: most machines are fine, a few have
    imbalance, and bearing spalls are rarer still.
    """
    counts = counts or FLEET_N
    rng = np.random.default_rng(seed)
    runs, rid = [], 0
    for state, n in counts.items():
        for _ in range(n):
            p = _fleet_params(rng, state)
            x = _synth(rng, p, seconds, fs)
            sev = (p["a_1x"] if state == "imbalance"
                   else p["a_imp"] if state == "bearing" else 0.0)
            runs.append({"x": x, "label": state, "run": rid,
                         "severity": float(sev), "params": p})
            rid += 1
    order = rng.permutation(len(runs))
    return [runs[i] for i in order]


# ============================================ Lecture 10: the drift campaign
# The same healthy machine, measured monthly for four years.  Nothing breaks --
# but the sensor mount relaxes, the ambient noise floor rises and the frame
# resonance walks.  A threshold set in the first year will not survive.
def make_drift_campaign(seed=31, n_months=48, fault_from=42, seconds=RUN_SECONDS,
                        fs=FS):
    """Healthy runs in time order with a slow baseline drift, then a real fault.

    Each run carries 'month'.  Runs from `fault_from` onward are a genuine
    bearing spall, so the last months contain something a detector SHOULD fire
    on -- everything before that is a healthy machine that merely looks
    different from how it looked in month 0.
    """
    rng = np.random.default_rng(seed)
    runs = []
    for m in range(n_months):
        t = m / (n_months - 1)                       # 0 -> 1 over the campaign
        faulty = m >= fault_from
        p = _run_params(rng, "bearing" if faulty else "normal")
        p["noise"] = float(0.06 + 0.050 * t + rng.normal(0, 0.005))
        p["a_struct"] = float(0.04 + 0.045 * t + rng.normal(0, 0.004))
        p["f_struct"] = float(180.0 + 110.0 * t + rng.normal(0, 8.0))
        p["gain"] = float(1.0 + 0.10 * t + rng.normal(0, 0.015))
        if faulty:
            p["a_imp"] = 1.10
        x = _synth(rng, p, seconds, fs)
        runs.append({"x": x, "label": "bearing" if faulty else "normal",
                     "run": m, "month": m, "params": p})
    return runs


# ======================================== Lecture 12: one shift, continuously
# Lectures 8-11 worked in 4-second acquisitions.  A device that is deployed does
# not take acquisitions -- it runs.  This campaign is one machine monitored
# without interruption through a shift, so that "how often should it publish?"
# becomes a question with a measurable answer.
#
# Two things happen during the shift and only one of them is a fault:
#
#   * a LOAD CHANGE at `load_at_min` -- the operator takes a heavier cut.  The
#     machine is fine.  Vibration amplitude rises anyway, which is exactly what
#     a fixed dashboard threshold on rms will fire on.
#   * a BEARING SPALL from `fault_at_min`, growing in severity.  This is the
#     thing worth telling anybody about.
SHIFT_SEG = 4.0             # seconds of signal synthesised at a time


def make_shift(seed=53, minutes=20.0, load_at_min=5.0, load_until_min=9.0,
               fault_at_min=12.0, fs=FS, win=WIN, hop=HOP):
    """A continuous run of one machine.  Returns the FEATURE STREAM, not samples.

    Returns a dict with:
        X          (n_windows, 12) features, in FEATURE_NAMES order
        t          window start time, seconds from the start of the shift
        state      per-window ground truth: 'normal' | 'loaded' | 'bearing'
        fault_at   seconds at which the spall begins
        load_at    (start, end) seconds of the heavy cut
        hop_s      seconds between consecutive windows
    """
    rng = np.random.default_rng(seed)
    n_seg = int(round(minutes * 60.0 / SHIFT_SEG))
    base = _run_params(rng, "normal")

    X, tt, st = [], [], []
    for k in range(n_seg):
        t0 = k * SHIFT_SEG
        p = dict(base)
        # slow wander that a real machine has and a 4-second acquisition hides
        p["f_r"] = base["f_r"] + 0.6 * np.sin(2 * np.pi * t0 / 420.0) + rng.normal(0, 0.05)
        p["noise"] = base["noise"] * float(rng.uniform(0.94, 1.06))

        loaded = load_at_min * 60.0 <= t0 < load_until_min * 60.0
        if loaded:
            p["a_1x"] = base["a_1x"] * 1.85       # heavier cut, healthy machine
            p["gain"] = base["gain"] * 1.10

        sev = 0.0
        if t0 >= fault_at_min * 60.0:
            # the spall grows: barely audible at onset, unmistakable by the end
            frac = (t0 - fault_at_min * 60.0) / max(
                1e-9, minutes * 60.0 - fault_at_min * 60.0)
            sev = 0.18 + 1.05 * frac
            p["a_imp"] = float(sev)

        x = _synth(rng, p, SHIFT_SEG, fs)
        w = frame(x, win, hop)
        f = features_of(w, fs)
        X.append(f)
        tt.append(t0 + np.arange(len(f)) * hop / fs)
        st += [("bearing" if sev > 0 else "loaded" if loaded else "normal")] * len(f)

    return {"X": np.vstack(X), "t": np.concatenate(tt), "state": np.array(st),
            "fault_at": fault_at_min * 60.0,
            "load_at": (load_at_min * 60.0, load_until_min * 60.0),
            "hop_s": hop / fs, "minutes": minutes}


# ==================================== Lecture 12: a fleet, measured for 2 years
# One acquisition per machine per month.  Two effects are superimposed and
# telling them apart is the whole cloud-side argument:
#
#   * a PLANT-WIDE ambient change -- every machine's noise floor creeps up as
#     the building fills with new equipment.  Common mode.  Nothing is wrong.
#   * ONE machine developing a bearing spall so slowly that no single monthly
#     acquisition looks alarming until it is nearly too late.
MONTH_MACHINES = 12
MONTH_MONTHS = 24


def make_month_campaign(seed=61, n_machines=MONTH_MACHINES, n_months=MONTH_MONTHS,
                        degrader=7, degrade_from=8, seconds=RUN_SECONDS, fs=FS):
    """Monthly acquisitions from a small fleet.  Returns a list of run dicts.

    Each run carries 'machine', 'month', 'label' and 'severity'.
    """
    rng = np.random.default_rng(seed)
    # every machine has its own fixed personality: mounting, gain, resonance
    ident = []
    for m in range(n_machines):
        q = _run_params(rng, "normal")
        ident.append(q)

    runs = []
    for month in range(n_months):
        u = month / (n_months - 1)
        ambient = 1.0 + 0.38 * u                 # common mode, plant-wide
        for m in range(n_machines):
            p = dict(ident[m])
            p["noise"] = float(ident[m]["noise"] * ambient
                               * rng.uniform(0.96, 1.04))
            p["f_r"] = float(ident[m]["f_r"] + rng.normal(0, 0.25))
            p["gain"] = float(ident[m]["gain"] * rng.uniform(0.97, 1.03))
            p["a_1x"] = float(ident[m]["a_1x"] * rng.uniform(0.94, 1.06))

            sev = 0.0
            if m == degrader and month >= degrade_from:
                frac = (month - degrade_from) / max(1, n_months - 1 - degrade_from)
                sev = 0.15 + 1.35 * frac
                p["a_imp"] = float(sev)
            x = _synth(rng, p, seconds, fs)
            runs.append({"x": x, "machine": m, "month": month,
                         "label": "bearing" if sev > 0 else "normal",
                         "severity": float(sev), "params": p})
    return runs


def build_month_table(runs, win=WIN, hop=HOP, fs=FS):
    """One row per window, with machine and month carried alongside."""
    X, mach, mon, lab, sev = [], [], [], [], []
    for r in runs:
        f = features_of(frame(r["x"], win, hop), fs)
        X.append(f)
        mach += [r["machine"]] * len(f)
        mon += [r["month"]] * len(f)
        lab += [r["label"]] * len(f)
        sev += [r["severity"]] * len(f)
    return (np.vstack(X), np.array(mach), np.array(mon), np.array(lab),
            np.array(sev))
