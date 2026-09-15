# Lecture 8, Supplement 1 — build notes and reuse guide
 
**Topic:** How a band feature is actually computed — sampling → DFT → bins → window → FFT vs Goertzel
**Course:** 01211271 Industrial AI and IoT
**Status:** supplementary background for Lecture 8. **Not new examinable material**, and the
deck says so on the title slide.
**Built:** September 2026. First of a planned series of per-lecture supplements.
 
---
 
## Why it exists
 
Students asked four questions the main lecture skipped, and all four are in the deck's
opening notes:
 
1. Why 2000 Hz? Why 256 samples?
2. What is a bin, and why can I not ask for the power at 30.0 Hz?
3. Why does my ESP32 give a different `e_1x` from the notebook on the same window?
4. What is the unused `goertzel()` in Lab 8's `features.py` for?
Question 3 turns out to be a **real bug in the material I shipped**, not a student error —
see "The correction" below.
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture8_Supplement1_Frequency_Features.pptx` | 13 slides (dark title, 11 light, dark summary), 13.333 × 7.5 in, speaker notes 932–1257 chars on every slide |
| `Lecture8_Supplement1_Frequency_Features.ipynb` | 34 cells, executed, zero errors, zero stderr, ~3 s runtime; 8 exercises + references |
| `Lecture8_Supplement1_Code.zip` | `week8_common.py` (unchanged from Lab 8) + `spectral.py` (new) + README |
| `source/` | `spectral.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `results.json`, `figs/` |
 
Rebuild order: `make_figs.py` → `build_notebook.py` (then execute) → `build_deck.js`.
`make_figs.py` writes `results.json` including figure aspect ratios.
 
---
 
## `spectral.py` — the one new file
 
Both transforms are written as **plain loops with no NumPy inside the algorithm**, because
the whole point is the operation count and NumPy hides it. Contents:
 
* `band_bins()` — which DFT bins each named band covers. This is the decision.
* `Counter` + `dft_naive`, `fft_radix2`, `fft_power`, `goertzel_power` — every multiply
  counted, with `twiddles="recurrence"|"table"` so the twiddle question is honest.
* `prepare(x, window)` — de-mean, then Hanning. The two steps students omit.
* `band_power_from_spectrum`, `normalise`, `goertzel_bands`, `crossover()`.
---
 
## Headline numbers (all from `results.json`)
 
| quantity | value |
|---|---|
| fs / N / window | 2000 Hz / 256 / 128 ms |
| **bin width Δf = fs/N** | **7.8125 Hz** |
| bins per band — `e_1x` / `e_2x` / `e_bpfo` / `e_hi` | 3 / 3 / 5 / **64** |
| **total band bins** | **75** (11 without `e_hi`) |
| naive DFT, N = 256 | **132,096** real multiplies |
| radix-2 FFT (twiddles by recurrence) | **8,450** — 16× fewer |
| radix-2 FFT (twiddles from a table) | 4,354 |
| Goertzel, per bin | **260** |
| **crossover** | **33 bins** (17 with a twiddle table); Goertzel wins up to 32 |
| FFT vs numpy.fft | 9.7e-14 relative |
| **Goertzel vs FFT, every bin** | **5.1e-12 relative** |
| alias demo | 1700 Hz at fs = 2000 → reads as **300 Hz** |
| leakage: pure 30 Hz tone into `e_bpfo`, no window | **0.2182 %** |
| the same with a Hanning window | 9.2e-6 % — **23,627× less** |
| forgetting the window moves `e_bpfo` by | **16 %** |
 
### The two arguments the supplement makes
 
1. **The window matters more than the algorithm.** Choosing between FFT and Goertzel is
   worth 5e-12; remembering to window is worth 16 % — comparable to Lecture 8's own
   healthy-vs-faulty change in `crest` (2.54 → 3.29). Slide 11 states this directly.
2. **`e_hi` is what forces the FFT, and only `e_hi`.** The three narrow bands need 11 bins,
   where Goertzel is 3.0× cheaper and needs a fraction of the RAM. Adding `e_hi`
   (64 bins) or `dom_freq` (an argmax over every bin) settles it the other way. The
   conclusion is therefore *"count your bins"*, not *"FFTs are better"*.
---
 
## The correction to Lab 8
 
`wokwi/features.py` ships `goertzel(buf, k, n)` with a docstring reading *"a rectangular
window is assumed here, so the value will not match the Hanning-windowed notebook
exactly."*
 
That is a statement about **that code**, not about the algorithm, and students have read it
as the latter. Goertzel has no opinion about windows: multiply the buffer by the Hanning
window before the loop and it matches `week8_common.freq_features` to 1.3e-14. The notebook
shows the three-way agreement (FFT / Goertzel / `week8_common`) and **exercise 3 asks them
to fix the file.**
 
If Lab 8 is ever rebuilt, either apply the window inside `goertzel()` or reword the
docstring to say the function does not window, rather than that the algorithm cannot.
 
---
 
## Deck outline (13 slides)
 
1. dark title — background, not examinable
2. A sample is a number; a rate is a promise — `fig_sampling`
3. The one mistake no software can undo — `fig_alias`
4. The DFT is a bank of correlations — `fig_dft` ← two probes per bin
5. The bins are not yours to choose — `fig_bins`
6. A finer ruler is a slower one — `fig_res`
7. Leakage, and the line that fixes it — `fig_leak` ← the money slide
8. The FFT: the same answer, fewer operations — `codeBox` + two boxes
9. Goertzel: one bin, two variables — `codeBox` + two boxes + the correction
10. So which one? Count the bins — `fig_cost` ← the decision
11. They agree; the window changes the answer — `fig_compare`
12. What this means for your device code — `fig_decide` + two boxes
13. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
1. A sample is a number, and a rate is a promise (+ aliasing)
2. The DFT as a bank of correlations (cos sum, sin sum, magnitude)
3. The bins are not yours to choose (+ the resolution–latency table)
4. Leakage and the window function (+ `prepare()` source)
5. The FFT (+ `fft_radix2` source, checked against numpy)
6. Goertzel (+ source, checked against the FFT) — and the Lab 8 correction
7. So which one? Count the bins (+ the three-way agreement table)
8. What this means for your device code (MicroPython Goertzel, as markdown)
9. What to remember (7 rules) · 10. 8 exercises · 11. references
---
 
## Reuse notes / gotchas hit
 
* **`fig_dft` was wrong on the first build.** The demo signal was a *sine* and the probe a
  *cosine*, so the matching bin summed to zero and the figure taught the opposite of the
  point. Fixed by using `cos(2πkt/N + 0.8)` and printing **both** sums plus the magnitude —
  which is a better figure anyway, because it shows why the DFT is complex.
* **`\'\'\'` inside an `r'''...'''` cell source** breaks `build_notebook.py`. The device-code
  cell became a markdown fenced block instead, which is right anyway since it is not meant
  to run under CPython.
* **`crossover_bins` is a ceiling, so it is the first bin count at which the FFT wins** —
  Goertzel wins *up to* 32. The notebook and the deck have to say this consistently or
  students spot the off-by-one.
* **Band-label collisions** in `fig_bins`: three narrow bands overlap at full scale. Split
  into two panels (0–150 Hz and 0–Nyquist) — and the left panel is better pedagogy because
  the individual bins are countable.
* **`save()` must not pass `bbox_inches="tight"` to a constrained-layout figure.** Same
  helper as Lecture 14.
* **pptxgenjs multi-run text needs `breakLine: true`** or LibreOffice merges the summary
  rules into one paragraph. Same gotcha as Lecture 14.
* The demo window is `make_run(default_rng(11), "bearing", seconds=1.0)[:256]`, shaft at
  28.51 Hz, BPFO 102.7 Hz. Pinned in `make_figs.demo_window()` and reproduced in the
  notebook; if it changes, every band number in the deck changes with it.
---
 
## Teaching notes
 
* **Slide 7 is the one that pays.** It answers "why does my device disagree with the
  notebook" and the answer is a missing line of code manufacturing a 0.22 % bearing
  signature on a healthy machine.
* **Slide 10 is the one to photograph.** The decision is one comparison and the step people
  skip is counting the bins.
* Expect the question on slide 8: *"if the FFT is exact and cheap, why use anything else?"*
  Let it sit — the answer is the 512 floats of scratch space, and it arrives on slide 9.
* Exercise 8 (name a real industrial task where Goertzel is clearly right) is the one worth
  discussing the following week.
---
 
## Planned siblings
 
The user intends supplements for other points where background is thin. Keep the
conventions established here: `LectureN_SupplementM_<Topic>` naming, the same palette and
slide grammar as the main decks, "background, not examinable" stated on the title slide,
notebook-only with device code shown to read, and every number from a `results.json` that
both builders import.

# Slide Notes

## Slide 1
Open by saying why this session exists: Lecture 8 used four frequency features and told you what they mean, and several of you asked where the numbers come from. That is a fair question and the answer is not hard - it is arithmetic you can check by hand, and there is nothing in this hour you have to take on trust. Say clearly that this is background, not new examinable material, so nobody spends the week memorising it instead of the main lecture. Then set the four questions the hour answers, because they are the ones actually asked: why two thousand hertz and two hundred and fifty-six samples; what a bin is and why you cannot just ask for the power at thirty hertz; why a student's ESP32 gives a different e_1x from the notebook on the same window - which is a real bug and we will find it; and what that unused goertzel function in the Lab 8 file is for. Promise them one concrete outcome: by the end they will choose between an FFT and Goertzel with a number, not a preference, and the number is how many bins they need.


## Slide 2
Left panel: the grey line is the real vibration and the blue dots are all that survives. At thirty hertz with a two kilohertz sample rate there are sixty-seven samples per revolution, so the dots trace the curve and sampling looks free. That is the wrong intuition and the next slide breaks it. Make the point about WHY two thousand: not the shaft, which would be satisfied by a tenth of that, but the bearing housing resonance at six hundred hertz, which is where a spall's energy actually lands. You need comfortable headroom above twice six hundred. Right panel: the actual buffer the device holds - two hundred and fifty-six samples, a hundred and twenty-eight milliseconds, and it looks like noise, because it is a healthy-ish machine with a small spall and you cannot see a spall in a time trace. Ask the room: what would you have to do to that trace to see the bearing? Somebody will say 'look at the frequencies', and that is the rest of the hour.


## Slide 3
This is the slide to slow down on, because it is the only irreversible decision in the whole pipeline. Left panel: the grey seventeen-hundred-hertz signal and the red three-hundred-hertz one pass through EVERY blue dot. Make them check one or two by eye. The samples are consistent with both, so no algorithm downstream can prefer one - the information that would separate them was never recorded. Right panel: run those samples through an FFT and you get a clean peak at three hundred hertz. Not a smeared one, not a suspicious one - a clean, confident, completely wrong peak. Then the practical consequence: this is why a data acquisition front end has an ANALOGUE low-pass filter before the converter. Ask the room what would alias on a real machine at two kilohertz. Good answers: an inverter switching frequency, a gear mesh on a high-speed stage, electrical pickup at a multiple of fifty hertz. On our rig nothing does, because the generator has nothing above nine hundred hertz - and say that plainly, because it is the simulation being kind to us.


## Slide 4
Walk one row at a time. Row one, bin three: the test wave does not match, the product swings above and below zero, and the sum is nothing. Row two, bin five: the test wave matches what is in the signal, the product sits mostly above zero and the sum is large. That is the entire idea of a Fourier transform and it needs no complex analysis to state. Now the part that catches people. Look at the numbers in row two: the cosine sum is twenty-two point three and the sine sum is minus twenty-three. Neither is the answer. I chose the signal's phase arbitrarily and those two numbers moved; the magnitude, thirty-two, did not. That is why the DFT is complex and why every feature in this course uses the magnitude squared and never the real part. Expect the question 'why not just use the real part, it is half the work' - the answer is that you would get a feature that changes when the machine's phase relative to your trigger changes, which is every window. If there is time, ask what the sum at bin five would be for a signal at bin five with amplitude one: N over two, exactly, and it is on the slide.


## Slide 5
Start with the constraint, because it is the bit that feels arbitrary until you see why. A test wave has to be periodic in the window or the transform is answering a question about a signal you do not have, so only whole numbers of cycles are allowed, so the available frequencies are spaced by sample rate over window length. Seven point eight one two five hertz here, and it is arithmetic, not a setting. Left panel: zoomed in, and they can literally count the dots inside each band - three, three, five. Right panel: the same spectrum to Nyquist, and e_hi is sixty-four bins on its own. Have them write down seventy-five, the total, because slide ten turns on it. Then the payoff sentence: this is the real reason Lecture 8 used BANDS rather than lines. The shaft wanders between twenty-eight and thirty-two hertz depending on load, we have no tachometer, and at seven point eight hertz resolution a single bin would sometimes contain the shaft line and sometimes not. Ask what hardware would let you use a single bin - a tacho and order tracking, and that is a genuinely better instrument.


## Slide 6
Left panel: two lines that are really one fact. Bin width falls as you lengthen the window and latency rises, in exact proportion, because they are both sample rate over window length read in different units. Right panel: what that buys - at N of sixty-four, e_1x is a single bin; at two thousand and forty-eight it is twenty-three. Now make the connection back to Lecture 8, and be honest about it: the window sweep in the main lecture showed accuracy still RISING at a thousand and twenty-four samples, and we chose two hundred and fifty-six anyway. That was not a modelling decision. A hundred and twenty-eight milliseconds is the latency the contactor can live with, five hundred and twelve bytes is the buffer the device can spare, and both of those outrank one accuracy point. Say the general rule out loud: accuracy does not choose the window; latency and memory do. Ask what would change on a slow machine - a gearbox output shaft at two hertz needs a much longer window, and then the latency argument goes the other way because nothing on that machine changes in a second.


## Slide 7
This is the slide that answers 'why does my device disagree with the notebook', so do not rush it. The mechanism first: the DFT assumes your window repeats forever. If the tone does not complete a whole number of cycles, the end does not join the beginning, and that discontinuity is a step - which contains energy at every frequency. Left panel: a tone sitting exactly on bin four, where the red un-windowed spectrum is a single clean line. Right panel: the same tone at thirty hertz, three point eight four bins, and the red curve smears across the whole spectrum. Then the number in the callout, and let it land: a healthy machine, with no bearing fault of any kind, manufactures zero point two two per cent of its energy into the outer-race defect band purely because somebody forgot one line of code. Twenty-three thousand times more than with a window. That is not a rounding difference, it is an invented fault. Two rules follow and they are worth more than any algorithm choice: de-mean, then window, then transform. Ask why de-meaning matters too - because the dc offset is mounting and amplifier bias, and left in it inflates the total that every normalised band is divided by.


## Slide 8
Set the problem first: the definition is order N squared, which at two hundred and fifty-six samples is a hundred and thirty-two thousand real multiplies per window, and we need fifteen point six windows a second. That is not happening in interpreted MicroPython. The FFT exploits one observation - the even-indexed and odd-indexed samples share almost all of their work - and recurses, giving order N log N. Walk the code box for shape only, not indices: a bit-reversal permutation, which is pure addressing and costs no arithmetic at all, then eight passes of butterflies. Labour the word EXACT. Students often think the F in FFT means an approximation is being made; it does not. Our hundred-line plain-Python version agrees with numpy to one part in ten to the thirteen, which is floating-point noise. The question to put to the room: if it is free and exact, why would anyone use anything else? Let them sit with that for a moment, then turn the slide - the answer is on the next one, and it is the five hundred and twelve floats of scratch space in the left-hand box.


## Slide 9
Introduce it as a filter rather than as a transform, because that is what it is: a second-order resonant IIR tuned to the frequency of one bin. Feed the window through and the two state variables you are left with contain the real and imaginary parts, up to a rotation you do not care about because you only want the magnitude. Walk the code box line by line - there are seven lines, one multiply per sample, no complex numbers, no array of twiddle factors and no output buffer. On a microcontroller that is a different class of program from an FFT, and the difference that matters most is not the multiplies, it is the five hundred and twelve floats of scratch space you no longer need. Then the correction, and it is a real bug in material I gave them: the goertzel function shipped in Lab 8's features.py has a docstring saying a rectangular window is assumed, and students have read that as a property of the ALGORITHM. It is not - it is a property of that code, which simply does not apply a window. Multiply by the Hanning window before the loop and it matches the notebook to ten to the minus fourteen. Fixing it is exercise three, and it is a five-line change.


## Slide 10
Left panel establishes the three complexity classes on one log-log axis - order N squared for the definition, N log N for the FFT, N per bin for Goertzel - and the annotation gives the concrete comparison at our window length. Right panel is the decision. The green curve is Goertzel's cost as you ask for more bins; the blue line is the FFT, flat because it does not care. They cross at thirty-three. Now the part that makes this a real engineering answer rather than a slogan: count OUR bins. Seventy-five, so the FFT wins - but look WHERE the seventy-five comes from. Sixty-four of them are e_hi, because the housing resonance is a wide physical phenomenon spanning four hundred to nine hundred hertz. The other three bands together are eleven bins, and for those Goertzel is three times cheaper and needs a fraction of the RAM. So the honest conclusion is not 'FFTs are better'. It is: a simple imbalance monitor wanting e_1x and e_2x should use Goertzel, and the moment you want e_hi - or a dom_freq feature, which needs an argmax over every bin - you are past the crossover before you start. Footnote worth giving: precompute the twiddles into a table and the FFT drops to four thousand three hundred and fifty-four, moving the crossover to seventeen.


## Slide 11
Left panel is the reassurance: FFT and Goertzel, same window, same Hanning window, and the four band features agree to one part in ten to the fourteen. If a student's two implementations disagree by more than that, they have changed the window function or forgotten the de-mean - not discovered a difference between the algorithms, because there is not one. Right panel is the lesson. Same FFT both times; the only difference is whether the Hanning window was applied. e_bpfo moves by sixteen per cent. Put that next to something they know: in Lecture 8's own numbers, crest goes from two point five to three point three between a healthy and a spalled machine. A sixteen per cent shift from a missing line of code is the same order as the fault you are trying to detect. State the moral directly, because it is the single most useful thing in this supplement: arguing about FFT versus Goertzel is worth about ten to the minus fourteen, and remembering to window is worth sixteen per cent. Spend your attention accordingly. In the notebook there is a third column - week8_common's own NumPy one-liner - and all three match, which is worth showing if the projector allows.


## Slide 12
This is the slide to photograph. The decision is a single comparison with an arithmetic answer, and the step people skip is the first one - counting the bins. Band width divided by seven point eight one two five hertz, and you have your number before you have written any code. Give them the two concrete cases in the boxes. Then connect forward: Lecture 11 puts the FFT path on a real ESP32 and measures nine hundred and twenty-three microseconds against a hundred and twenty-eight millisecond budget, so on THAT board the argument is about elegance and RAM rather than feasibility. On a smaller part, or with a control loop sharing the CPU, it would not be. Close on the callout, which is the practical instruction they will actually use in Lab 8: de-mean, window, transform, in that order. Ask them, before they leave, to go and look at their own features.py and say which of those two lines is missing. In most years it is both.


## Slide 13
Walk the strip and name the two boxes that get left out - de-mean and window - then read the six rules. Spend what time remains on four and five together, because they are the pair that changes behaviour: the window function is worth sixteen per cent and the choice of algorithm is worth ten to the minus fourteen, so anybody who spent this hour worrying about which transform to use and walks out still not windowing has taken the wrong lesson. Rule six is the transferable engineering habit: a design choice that feels like taste usually has an arithmetic answer hiding behind one countable quantity, and here the quantity is bins. Point them at the notebook - eight exercises, and exercise three is the one that fixes the real bug in their own Lab 8 file, while exercise eight asks them to name an industrial task where Goertzel would clearly be right, which is the one worth discussing next week. Finish by putting this back in its place: none of this is new examinable material. It is the floor underneath Lecture 8, and the reason to know it is so that when a number looks wrong you can work out why instead of guessing.


