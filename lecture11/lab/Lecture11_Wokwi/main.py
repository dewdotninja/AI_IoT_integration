"""
main.py  --  Lecture 11, Lab 11
01211271 Industrial AI and IoT

The whole edge pipeline, on the device:

    sample -> window -> 12 features -> classifier -> alarm -> actuate

Two models run side by side and they are not redundant.

  * The CLASSIFIER (Lecture 9) names the fault, and is blind to any fault it
    was not trained on.
  * The ALARM (Lecture 10) needs no fault labels and notices anything unusual,
    but cannot say what it is.

Where they disagree, the alarm wins the actuator and the classifier only
annotates it.  The alarm has a measured false-alarm rate; the classifier's
confidence on an unfamiliar input is not measured and not trustworthy.

Change WAVE to try the other machine states.
"""
import gc
import struct
import time

import ubinascii

import features
import model
import alarm

WAVE = "wave_bearing"        # wave_normal | wave_imbalance | wave_bearing
                             #          | wave_unknown  <- a fault nobody trained on

MIN_MARGIN = 0.25            # below this the classifier is not believed
LED_PIN = 2                  # on-board LED on most ESP32 dev boards

mod = __import__(WAVE)
RAW = ubinascii.a2b_base64(mod.B64)
SCALE = mod.SCALE
N_SAMPLES = len(RAW) // 2
WINDOW_US = 1000000 * features.WIN // features.FS

try:
    from machine import Pin
    _led = Pin(LED_PIN, Pin.OUT)
except (ImportError, ValueError):
    _led = None


def set_actuator(on):
    """The only place the outside world is touched.  Fails safe to OFF."""
    try:
        if _led is not None:
            _led.value(1 if on else 0)
    except Exception:
        pass


def read_sample(i):
    """One accelerometer reading, in g.  On real hardware this is I2C."""
    return struct.unpack_from("<h", RAW, 2 * i)[0] * SCALE


def classify(x):
    """Name the fault, or admit you cannot.  Never raises."""
    try:
        label, margin = model.predict(x)
        if margin < MIN_MARGIN:
            return "uncertain", margin
        return label, margin
    except Exception:
        return "model-error", 0.0


def main():
    print("# device: %s, %d samples at %d Hz" % (WAVE, N_SAMPLES, int(features.FS)))
    print("# window %d, hop %d, budget %d us" % (features.WIN, features.HOP
                                                 if hasattr(features, "HOP")
                                                 else 128, WINDOW_US))
    print("win,label,margin,anom_score,driver,raised,us")

    alarm.reset()
    n_win = 1 + (N_SAMPLES - features.WIN) // 128
    t_total = 0
    raised_any = False

    for w in range(n_win):
        start = w * 128
        buf = [read_sample(start + j) for j in range(features.WIN)]

        t0 = time.ticks_us()
        try:
            x = features.all_features(buf)
        except Exception:
            # No features, no decision.  Hold the actuator and say so.
            print("%d,feature-error,0,0,-,%d,0" % (w, 1 if raised_any else 0))
            continue
        label, margin = classify(x)
        raised, score = alarm.update(x)
        _, driver = alarm.worst_feature(x)
        t_total += time.ticks_diff(time.ticks_us(), t0)

        # the alarm owns the actuator; the classifier only annotates it
        if raised != raised_any:
            set_actuator(raised)
            raised_any = raised

        print("%d,%s,%.3f,%.3f,%s,%d,%d"
              % (w, label, margin, score, driver, 1 if raised else 0,
                 time.ticks_diff(time.ticks_us(), t0)))

    gc.collect()
    per = t_total // n_win
    print("# %d windows" % n_win)
    print("# mean %d us per window, budget %d us, %d %% used"
          % (per, WINDOW_US, 100 * per // WINDOW_US))
    print("# free heap %d bytes" % gc.mem_free())
    if per > WINDOW_US:
        print("# OVER BUDGET -- the device cannot keep up with its own sensor")


if __name__ == "__main__":
    main()
