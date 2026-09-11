# Lab 8 — Wokwi package

## What is in here

| file | where it runs | what it does |
|---|---|---|
| `main.py` | ESP32 | streams the stored waveform, windows it, prints one CSV row per window |
| `features.py` | ESP32 | the seven time-domain features, in plain MicroPython |
| `wave_normal.py` | ESP32 | 2 s of recorded vibration, int16 + base64 |
| `wave_imbalance.py` | ESP32 | the same, with a trial mass on the disc |
| `wave_bearing.py` | ESP32 | the same, with an outer-race spall |
| `expected_features.csv` | laptop | the reference values your device must reproduce |
| `diagram.json` | Wokwi | a bare ESP32 with the serial monitor attached |

## Setting it up in Wokwi

1. Open <https://wokwi.com/projects/new/micropython-esp32>.
2. Replace `diagram.json` with the one in this folder.
3. Add `features.py` and **one** of the `wave_*.py` files with the green **+**
   button in the file tab bar, then paste the contents in.
   Add one waveform at a time — all three together will not fit comfortably in RAM.
4. Paste `main.py` over the default `main.py`.
5. Press the green play button and watch the serial monitor.

## What you should see

```
# device: wave_normal, 4000 samples at 2000 Hz
# window=256 hop=128
win,mean,rms,std,ptp,crest,kurt,zcr
0,...
...
# 30 windows
# feature time: ... us per window
# window duration: 128000 us -- compare the two numbers
```

Those last two numbers matter. The feature computation has to finish well
inside one window duration, or the device cannot keep up with its own sensor.
Write both down; Week 11 adds model inference on top of this budget.

## The acceptance test

Copy the serial output into a text file and compare it against
`expected_features.csv`, which was computed in the notebook from **the same
quantised samples** your device is reading.

Agreement to **three decimal places** is a pass. The fourth decimal will
usually differ, and that is not a bug: MicroPython on the ESP32 uses
single-precision floats, while NumPy on your laptop uses double precision.
Accumulating 256 squares — and 256 fourth powers for the kurtosis — makes that
difference visible. Expect `kurt` to be the worst agreement of the seven, for
exactly that reason.

If a feature is off in the **second** decimal or worse, it is a bug, not
precision. The usual causes, in order of frequency:

1. the DC component was not removed before computing `crest`, `kurt` or `zcr`
2. `peak` was measured on the raw samples instead of the AC part
3. `zcr` divided by `n` instead of `n - 1`
4. the window or hop length does not match the notebook
