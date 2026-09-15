# Lecture 8, Supplement 1 — code

**01211271 Industrial AI and IoT**

Unzip beside `Lecture8_Supplement1_Frequency_Features.ipynb` and it will run.

| file | what it is |
|---|---|
| `week8_common.py` | exactly the Lab 8 file: the rotor rig, the framing, the twelve features |
| `spectral.py` | new: the DFT, a radix-2 FFT, Goertzel, the band arithmetic, and an operation counter |

`spectral.py` writes both transforms as **plain loops with no NumPy inside the
algorithm**, because the point of the comparison is the operation count and NumPy hides
it. It is slower than `numpy.fft` by a large factor and that is deliberate.

## The three things worth reading

* `band_bins()` — which DFT bins each named band actually covers. Count them before you
  choose an algorithm; it is the whole decision.
* `prepare()` — de-mean, then window. Two lines, and they change a band feature by more
  than the choice of transform does.
* `crossover()` — instruments both routes and finds where the multiply counts cross.
  Nothing here is asserted; run it and see.

## Check it yourself

```python
import numpy as np, spectral as sp, week8_common as w8

rng = np.random.default_rng(11)
x, p = w8.make_run(rng, "bearing", seconds=1.0)
a = sp.prepare(x[:sp.WIN], "hann")

P = sp.fft_power(list(a))
bins = sp.band_bins()
print(sp.normalise(sp.band_power_from_spectrum(P, bins), P))
print({k: v / sum(P[1:]) for k, v in sp.goertzel_bands(list(a), bins).items()})
print(w8.freq_features(x[:sp.WIN][None, :])[0][1:])
```

Three routes, one answer.
