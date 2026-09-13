"""
bench.py  --  Lecture 11
01211271 Industrial AI and IoT

Times every stage of the edge pipeline under the MicroPython interpreter it is
actually running on, and prints the result as a table.

Run it on the ESP32 in Wokwi to get the number that matters.  Run it on a
desktop MicroPython build to get a number that is 20-40x too fast but lets you
compare stages against each other, which is the part that transfers.
"""
import gc
import math
import time

import features
import features_lite
import model
import alarm

WIN = features.WIN
REPS = 60


def _ticks_us():
    try:
        return time.ticks_us()
    except AttributeError:              # desktop builds may not have ticks_us
        return int(time.time() * 1000000)


def _diff(a, b):
    try:
        return time.ticks_diff(a, b)
    except AttributeError:
        return a - b


def make_window(n=WIN):
    """A deterministic test window: 30 Hz shaft line plus a little noise."""
    buf = []
    s = 12345
    for i in range(n):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        noise = (s / 0x7FFFFFFF - 0.5) * 0.2
        buf.append(0.35 * math.sin(2.0 * math.pi * 30.0 * i / features.FS)
                   + noise)
    return buf


def timeit(fn, reps=REPS):
    fn()                                # warm up: first call may allocate
    gc.collect()
    t0 = _ticks_us()
    for _ in range(reps):
        fn()
    return _diff(_ticks_us(), t0) / reps


def main():
    buf = make_window()
    gc.collect()
    free0 = gc.mem_free()

    t_mean = timeit(lambda: features.time_features(buf))
    tf = features.time_features(buf)
    t_fft = timeit(lambda: features._fft(buf, tf[0]))
    t_freq = timeit(lambda: features.freq_features(buf, tf[0]))
    t_all = timeit(lambda: features.all_features(buf))
    t_lite = timeit(lambda: features_lite.all_features(buf))
    x = features.all_features(buf)
    t_clf = timeit(lambda: model.predict(x))
    t_alm = timeit(lambda: alarm.score(x))

    gc.collect()
    used = free0 - gc.mem_free()
    budget = 1000000.0 * WIN / features.FS

    print("stage                       us      %% of window")
    print("-" * 48)
    for name, us in (("7 time-domain features", t_mean),
                     ("256-point FFT", t_fft),
                     ("5 frequency features", t_freq),
                     ("all 12 features", t_all),
                     ("9 lite features (no FFT)", t_lite),
                     ("classifier (36 MACs)", t_clf),
                     ("alarm (12 z-scores)", t_alm)):
        print("%-24s %8.1f %10.2f" % (name, us, 100.0 * us / budget))
    total = t_all + t_clf + t_alm
    print("-" * 48)
    print("%-24s %8.1f %10.2f" % ("TOTAL per window", total, 100.0 * total / budget))
    print()
    print("window duration          %8.1f us" % budget)
    print("FFT / time-features ratio %7.1f x" % (t_fft / t_mean))
    print("full pipeline / time-feat %7.1f x" % (total / t_mean))
    print("lite pipeline / time-feat %7.1f x" % ((t_lite + t_clf + t_alm) / t_mean))
    print("MACHINE-READABLE %s" % repr({
        "t_time": t_mean, "t_fft": t_fft, "t_freq": t_freq, "t_all": t_all,
        "t_lite": t_lite, "t_clf": t_clf, "t_alm": t_alm, "total": total,
        "budget_us": budget, "heap_used": used, "heap_free": gc.mem_free()}))
    print("heap used by one pass    %8d bytes" % used)
    print("free heap                %8d bytes" % gc.mem_free())


if __name__ == "__main__":
    main()
