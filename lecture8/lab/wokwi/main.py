"""
main.py  --  Week 8, Lab 8
01211271 Industrial AI and IoT

Streams a stored waveform from the device file system as if it were arriving
from an accelerometer, cuts it into windows, computes the seven time-domain
features of each window and prints one CSV row per window.

Wokwi cannot shake a real rotor, so the "sensor" is a recording.  Everything
downstream of read_sample() is exactly what you would run against a live
MPU6050.

Change WAVE below to try the other two machine states.
"""
import time
import ubinascii
import struct

import features

WAVE = "wave_normal"       # wave_normal | wave_imbalance | wave_bearing
WIN = 256                  # window length, samples
HOP = 128                  # 50 % overlap

mod = __import__(WAVE)
RAW = ubinascii.a2b_base64(mod.B64)     # int16 little-endian, 2 bytes/sample
SCALE = mod.SCALE                       # counts -> g
FS = mod.FS
N_SAMPLES = len(RAW) // 2

print("# device: %s, %d samples at %d Hz" % (WAVE, N_SAMPLES, FS))
print("# window=%d hop=%d" % (WIN, HOP))
print("win,mean,rms,std,ptp,crest,kurt,zcr")


def read_sample(i):
    """One accelerometer reading, in g.

    On real hardware this is an I2C transaction with the MPU6050.  Here it is
    a lookup into the recording -- same units, same scale.
    """
    return struct.unpack_from("<h", RAW, 2 * i)[0] * SCALE


n_win = 1 + (N_SAMPLES - WIN) // HOP
t_total = 0

for w in range(n_win):
    start = w * HOP
    buf = [read_sample(start + j) for j in range(WIN)]

    t0 = time.ticks_us()
    f = features.time_features(buf)
    t_total += time.ticks_diff(time.ticks_us(), t0)

    print("%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f"
          % (w, f[0], f[1], f[2], f[3], f[4], f[5], f[6]))

print("# %d windows" % n_win)
print("# feature time: %d us per window" % (t_total // n_win))
print("# window duration: %d us -- compare the two numbers"
      % (1000000 * WIN // FS))
