# Lecture 14 — build notes and reuse guide
 
**Topic:** The integrated system, and what we did not teach you
**Course:** 01211271 Industrial AI and IoT, lectures 8–14 (AI and integration half)
**Session format:** 5 hours — ~2 h lecture + debrief, ~3 h lab (each group runs its own chain)
**Built:** September 2026. **This is the last lecture of the course.**
 
---
 
## Deliverables
 
| file | shape |
|---|---|
| `Lecture14_The_Integrated_System.pptx`, renamed to `iaiiot26_Lect14.pptx` | 12 slides (dark title, 10 light, dark summary), 13.333 × 7.5 in, speaker notes 1001–1270 chars on every slide |
| `Lecture14_The_Integrated_System.ipynb`, renamed to `iaiiot26_Lect14_nb.ipynb` | 28 cells, executed end to end, zero errors, zero stderr, ~60 s runtime; 8 exercises + references |
| `Lecture14_Run_Sheet.md` | **instructor only** — minute-by-minute script, what to watch for, reference results, a five-question debrief, troubleshooting (not included in github) |
| `Lecture14_Observation_Sheet.md` | the groups' deliverable: 12 checkpoints + 3 reason strings + own numbers + 4 questions + marking scheme (not included in github) |
| `Lecture14_Exam_Bank.md` | **46 questions with model answers and `[MARKING]` notes**, Lectures 8–14 only, 233 marks total (not included in github) |
| `Lecture14_Chain.zip` | `Lecture14_Chain/` — rig, sensors, netpie, cloud, downlink, chain, build_chain, both model JSONs, results.json, README |
| `source/` | `chain.py`, `build_chain.py`, `make_figs.py`, `build_notebook.py`, `build_deck.js`, `results.json`, `figs/` |
 
**Rebuild order:** `build_chain.py` (writes `results.json`) → `make_figs.py` (re-runs the
chain, appends `aspects`, rewrites `results.json`) → `build_notebook.py` + execute →
`build_deck.js`. `make_figs.py` rewrites `results.json`, so it must run before the
notebook and the deck.
 
---
 
## The one new file
 
`chain.py` (481 lines) contains **no new method**. It is the wiring, the scripted session
and the checkpoint list — an integration test, and it is presented to students as one.
 
```
SEG = 4.0  HEARTBEAT_S = 60  SMOOTH = 32  DWELL_S = 15  MIN_MARGIN = 0.25
ALERT_K, ALERT_WINDOW = 3, 120     KEEP_QUIET, KEEP_ALARM = 1200, 400
SESSION_MIN = 22.0
SCRIPT   = [(0,6,normal), (6,9,loaded), (9,11,normal),
            (11,13,clipped), (13,15,normal), (15,22,bearing)]
INJECTS  = [(18, network down), (20, network up)]
UPDATE_TIMES = {"good": 3.0, "over-tight": 5.0, "deaf": 17.5}
a_imp during the spall = 0.55 + 1.30 * frac        # frac over minutes 15 -> 22
```
 
Classes: `Device` (re-reads its models from `SpecStore`, so a commit takes effect
mid-run), `Uplink` (counting heartbeat + debounce/dwell events + an offline queue that
drains on reconnect), `Cloud` (Lecture 12's subscriber, alerts once), plus `make_session`,
`fit_alarm`, `run_session` and `checkpoints`.
 
`build_chain.py` drives it once and writes every number the deck, notebook and sheets
quote. **`baseline_specs(rig_seed=101)` fits the boot alarm on the session's own rig** —
`rig._run_params` is re-drawn from the same seed so shaft speed, gain and mounting match,
only the noise realisation differs. Fitting on a different rig seed makes the alarm raise
on 82 % of the quiet start, which is Lecture 10's opening mistake and a good demo but a
broken baseline.
 
---
 
## Headline numbers (all from `results.json`)
 
| quantity | value |
|---|---|
| session | 22.0 min, 20 130 windows, 15.625 windows/s |
| **checkpoints passed** | **12 of 12** |
| messages published | 31 |
| bytes on the wire | 3 485 → 0.228 MB/day |
| raw samples for the same session | 5.28 MB (**1 515×** more) |
| alarm raised — normal / loaded / clipped / bearing | 0.02 % / 99.9 % / 0 % / 86.6 % |
| gate rejection — normal / loaded / clipped / bearing | 0 / 0 / **100 %** / 0.08 % |
| actuator transitions during the clipped stretch | **0** |
| driver: heavy cut / spall | `rms` / `e_hi` |
| cloud alert | minute 16.0 (**1 min** after onset) |
| windows decided with no network | 1 830 |
| reports queued and later delivered | 3 |
| alarm threshold / version at the end | 4.029 / v4 |
 
### The three updates
 
| t | spec | outcome |
|---|---|---|
| 3.0 | good (refit on fresh healthy) | `accepted: committed` |
| 5.0 | over-tight (`scaler_scale × 0.25`) | `refused: shadow test: would raise on 100% of a quiet stretch` |
| 17.5 | deaf (`scaler_scale × 3.0`) | `refused: shadow test: deaf: raises on only 0% of the windows that alarmed last time` |
 
**Both bad specs are arithmetically perfect** — twelve finite features, no zero standard
deviation, threshold inside `THRESHOLD_RANGE = (2.0, 12.0)`, good checksum, fresh
timestamp, monotonic version. `validate()` has nothing to object to; only `verify()`
catches them. **Do not make the bad specs bad by moving the threshold** — that is caught
by the range check and the lesson evaporates. Corrupt the *scale* instead.
 
---
 
## The centrepiece result: the shadow test has a boundary
 
The same deaf spec pushed at different minutes of the same run:
 
| pushed at | outcome |
|---|---|
| 12.0 – **16.0** min | **ACCEPTED** |
| **16.5** – 19.0 min | refused |
 
Nothing about the spec changed. What changed is the device's retained-`alarmed` buffer:
before ~16 min it holds heavy-cut windows (amplitude), on which a deaf spec still raises;
after, it has turned over to spall windows (impulsive), on which it does not.
 
**The general statement — this is the lecture's argument:** the shadow test can only
defend against faults the device has *already seen and raised on*. On a new machine, a new
fault type, or the first unit of a fleet, that set is empty. The mitigations are
organisational, not arithmetic: stage on a few machines, keep a cloud-side regression set
containing faults from *other* machines, and make the approving human read detection
numbers rather than only false-alarm numbers. Notebook §6 sweeps this; deck slide 8 is
built on it; exam question G4 (7 marks) asks for it.
 
---
 
## Deck outline (12 slides)
 
1. dark title — "The integrated system"
2. Seven weeks, one system — `fig_arc` (the dashed line is the whole argument)
3. Today's run, minute by minute — `fig_timeline` ← **centrepiece**
4. What you have to observe — `fig_checks` (doubles as the observation sheet)
5. The five ways this can be wrong — `fig_failures`
6. The numbers, seven weeks on — `fig_numbers`
7. Every decision, and what it cost — `fig_decisions` (the examinable slide)
8. Where the shadow test stops working — `codeBox` + two boxes ← **the honest finish**
9. What would change in a real plant — four boxes (run as discussion first)
10. What we did not teach you — `fig_notcovered`
11. The exam, and this afternoon — three boxes
12. dark summary — `fig_workflow_dark`, six rules
## Notebook sections
 
1. The seven pieces (module inventory, line counts)
2. The session (script table, raw rms plot — deliberately uninformative)
3. One window all the way through (four labelled windows, ring pre-filled)
4. The whole chain (`run_session`, the three acks, the timeline reproduced)
5. The checkpoints (source of `checkpoints()` shown, then run)
6. **Where the shadow test stops working** (the push-time sweep)
7. What being careful cost (the trade table + byte arithmetic)
8. The protocol (10 rules)
9. 8 exercises · 10. references
---
 
## Reuse notes / gotchas hit
 
* **`make_figs.py` rewrites `results.json`** (it appends `aspects`). Run it before
  `build_notebook.py` and `build_deck.js`, as in Lecture 8's notes.
* **`save()` must not pass `bbox_inches="tight"` to a constrained-layout figure** — it
  fights the layout engine. `fig_numbers` uses `constrained_layout=True`; the helper now
  checks `fig.get_constrained_layout()`.
* **pptxgenjs multi-run text needs `breakLine: true`** on each run, or LibreOffice renders
  the six summary rules as one paragraph. Lecture 13's `options: {}` form silently merged.
* **Figure aspect drives slide legibility.** `fig_timeline` at figsize (11.4, 6.8) is
  aspect 1.66 and fits only 7.2 in wide in the available band; at (11.4, 5.0) it is 2.17
  and fills 11.6 in. Table figures likewise: row pitch 0.34 in, not 0.44.
* **Spall growth rate is load-bearing in two directions.** `0.55 + 1.30·frac`: slower and
  the retained-alarm buffer never turns over, so the deaf spec at 17.5 gets in; faster
  (try 1.90) and past minute 20 the impulses hit the ±2 g rail, the gate calls the sensor
  clipped, and it refuses 3.6 % of the very windows you want. The fast case is shipped as
  notebook **exercise 4**, which is a better home for it than the live demo.
* **`chain.py` hands `validate()` the argument `msg["t"] + now`**, so the age it computes
  is `now`. `make_update(..., issued_at=-2.0)` keeps the apparent age at a couple of
  seconds; `issued_at=0.0` would make it the whole session (harmless at `MAX_AGE_S` = 30
  days, but confusing to read).
* **Checkpoints must be keyed by update tag, not by position.** The first draft tested
  `len(accepted) == 1` and broke the moment an extra spec was accepted for the wrong
  reason — it hid the real failure instead of reporting it.
* **The notebook's one-window demo must pre-fill the persistence ring** (step windows
  *i−5…i−1* first), or every row prints `raised=0` and the demo teaches the wrong thing.
---
 
## What the course ends on
 
Three deliberate choices worth preserving if this is ever rebuilt:
 
1. **The last technical slide is a negative result** (slide 8). The strongest safety
   mechanism in the course has a boundary, it is found by measurement, and the fix is
   organisational. This is the tone the whole second half has been building.
2. **The observation sheet is the deliverable, not the code.** Marks go to recorded
   observations; an honest FAIL with a number beats a PASS with an empty box. The closing
   line of the debrief is that the transferable habit is asking *what would I have to see
   to believe this works*.
3. **Two events in the live run are unannounced** (the sensor fault at 11:00, the network
   at 18:00). A rehearsed reaction is not evidence.
## Pedagogical traps that fire every year
 
* **At 6:00 the heavy cut raises the alarm on a healthy machine.** Roughly a third of the
  room marks it a failure. It is a pass. Do not correct it during the run — it is debrief
  question 1, and it is the most valuable ten minutes of the session.
* **At 11:00 the LED changes state** on any group that wrote `raised = False` in the gate
  branch instead of holding. This is the most common implementation bug in the course.
* **At 18:00 the serial output stops** on any group whose `check_msg()` or publish blocks.
  Lecture 11 exists to prevent exactly this.
 
# Lecture Slides

## Slide 1
Say at the start that there is nothing new today, and then say why that is the hardest kind of session rather than the easiest. Every component in this system passed its own test, in its own lecture, on data chosen to show that component working. None of them has ever had to work while another one was failing. The interesting failures in an industrial system are almost never inside a component; they are in the joins - the assumption one piece makes about another that nobody ever wrote down. Give them the three examples early because they will meet all three today: the gate refuses a window, so what does the ACTUATOR do - nothing in Lecture 13 says. A model update commits mid-run, and the persistence ring still holds five scores computed against the old baseline. The link drops while a report is half-composed - Lecture 12 assumed the network was there and Lecture 11 assumed it was not, and both are in the same loop now. Then set the shape of the day: first half is this deck and the run, second half is the groups running their own chain against a checkpoint sheet. Tell them the exam is on weeks 8 to 14 and that the bank is already published, so the questions in this session are the ones worth arguing about, not the ones worth memorising.


## Slide 2
Walk it left to right along the top row first, naming the lecture under each box, and let them notice how little of it is machine learning: one box out of five, and thirty-nine numbers inside it. Then the bottom row, and the two lanes crossing the dashed line - features and events going down, a model specification coming up. Now spend the time on the line itself. Ask the room: which of these boxes may fail without anyone getting hurt? They will get it quickly, and the answer is everything below the line plus the reporting lane. Then the harder question: what does a system that respects this line actually cost you? The honest answer is that the cloud sees a fraction of what it could, your model has to fit in 200 kB, and you cannot use anything you cannot run on the device. That is the trade this whole course has been making. One objection to expect: 'why not put the model in the cloud and keep a simple threshold on the device as a backup?' It is a real architecture and it is defensible - the answer is that you then maintain and validate two detectors, and the simple one is the one that will actually fire.


## Slide 3
This is the centrepiece and it deserves four or five minutes. Top panel is the alarm score on a log axis - log because by minute twenty-two the spall is an order of magnitude above threshold and a linear axis flattens everything before it into one band. Point at the heavy cut first: the score goes to about twenty-six, the alarm raises on a hundred per cent of windows, and the machine is completely healthy. That is not a bug; an anomaly detector is telling you truthfully that the machine is outside its baseline. The driver name says rms, and that is the piece of information a person can act on. Then the clipped stretch: notice the score line simply STOPS - the gate refused every window, there is no score, and look at the second panel, the actuator held its previous state rather than dropping out. Then the spall from fifteen, where the driver becomes e_hi and kurt. Bottom panel: bytes, and it is a staircase, not a ramp - each step is an event or a minute summary. Show the flat stretch between eighteen and twenty where the link is down and the device is still deciding. Question for the room: which single moment on this chart would you want an operator to be told about, and in what words?


## Slide 4
Make the point that 'it looked fine' is not evidence, and that the difference between a demo and an engineering test is a list written BEFORE the run. Read three lines aloud and let them hear the shape: each one names a thing that could have gone wrong and a number that settles it. Then count the refusals with them - two updates refused, the actuator held, nothing published while the link was down. Four of twelve checkpoints are the system choosing not to act, and in a protection system most of the engineering is in the refusals. Warn them about the trap in checkpoint five, the heavy cut: the expected observation is that the alarm DOES raise, with an amplitude driver. Half the groups will mark that as a failure because the machine is healthy. It is a pass, and the discussion about why is the most valuable ten minutes of the afternoon. Tell them the observation sheet has the same rows in the same order so they can fill it in live, and that a checkpoint with no observation recorded scores zero even if the system did the right thing.


## Slide 5
This slide is the one to photograph. Go row by row and ask, for each, which lecture's tool applies and what happens if you use the wrong one. Row two is worth labouring: a broken sensor is not a noisy input, it is a confident wrong one - Lecture 13's clipped accelerometer made a spalled bearing look calmer than health, kurtosis one-point-eight against two-point-two. No amount of model quality fixes that, because the fault information is gone before the model sees it. Row three is today's: two well-formed specs refused, and neither of them could have been caught by arithmetic. Row five is the one engineers underestimate. Ask the room how many alarms a machine can raise in a week before the operator tapes over the light, and then point out that the answer in most plants is about two. Persistence, dwell and the driver name exist for that reason, not for statistical tidiness. Expect the objection: 'surely you would rather have a false alarm than a missed fault?' Answer: yes, once. Not twice a shift.


## Slide 6
Left: how much goes over the wire. Raw samples would be three hundred and forty-six megabytes a day; a JSON feature message every window is actually WORSE, four hundred and ninety, because protocol overhead exceeds the samples it replaces - that surprises people and it is worth a pause. What we sent is nought-point-two-three, two thousand times less, and the mechanism was on-change reporting plus a heartbeat that carries a count. Middle: the device budget, log scale. The FFT is nine hundred and twenty-three microseconds, eight times the time features, and the whole pipeline is under one per cent of the hundred and twenty-eight millisecond window. Remind them of Lecture 11's honest result - the FFT bought about one accuracy point for that eight times, and we deployed it anyway for fidelity to the validated model, not because the number justified it. Right: three time scales in one system - a quarter of a second to open a contactor, a minute for the cloud to raise an alert, six months of warning from a fleet trend. Ask which of those three a maintenance planner actually wants. The answer is the six months, and it is the only one that needs the cloud.


## Slide 7
This is the examinable slide and they should be told so. Every row is a decision that could reasonably have gone the other way, and the right-hand column is the part students skip. Pick three rows at random and put them to the room as 'when would you choose differently?' Good answers exist for all of them: twelve features loses whatever nobody thought of, so on a machine with an unknown failure mode you might log raw windows on alarm; a linear model cannot bend, so with a large labelled fleet a gradient-boosted model in the cloud is a better detector; max-|z| cannot name the fault, so with good labels a classifier tells the technician what to bring. The row to dwell on is the last but one: two of two bad specs refused today, and one that is deaf to a fault the device has never seen still gets in - that is the next slide. Close by telling them the exam asks them to defend a decision, not to recall it, and that an answer which names only the benefit and not the cost cannot get full marks.


## Slide 8
Slow down here; this is the intellectual high point of the session and it is a negative result. Re-run the same deaf specification at different moments in the same session and it flips from accepted to refused at a specific minute - not because the specification changed, but because what the device had KEPT changed. Before that minute the retained alarmed buffer is full of heavy-cut windows, which are amplitude events, and a deaf specification still raises on those. After it, the buffer has turned over to spall, which is impulsive, and the specification is caught. Let that sit, then generalise it: the shadow test is the best defence in this course and it can only ever test against faults the device has already seen. Ask the room what that means for the first machine of a new type on a new site. Then give them the mitigations, because a negative result without a response is just pessimism: stage updates on a few machines first; keep a labelled regression set in the cloud containing faults from OTHER machines; and make the named human who approved the refit look at detection numbers, not just false-alarm numbers, before the fleet gets it. Exercise six in the notebook asks them to design that regression set, and it is the hardest exercise in the course.


## Slide 9
Run this as discussion, not lecture - they were given the question a week ago. Take answers first and put them on the board before showing the boxes; most years the room produces three of the four. The one they miss is labels, so if it does not come up, prompt for it: where would the word 'bearing' come from on a real machine? The answer is a work order in a maintenance system, written by a fitter, possibly weeks after the event, possibly naming the wrong component. Every supervised method in Lecture 9 assumed that label was free and correct, and it is neither - which is also the strongest practical argument for the anomaly detector of Lecture 10, which needs no labels at all. On the security box, be precise rather than alarming: our sha256 checksum is a corruption check, not a signature, and we said so when we built it. Anybody who can publish to your topic can push a specification. Finish by asking which of these four they would do first with a fixed budget, and make them justify the order.


## Slide 10
Be straight with them here; overclaiming is how graduates get into trouble in their first job. Left column is what a fourteen-week course can genuinely give: the shape of the problem, one worked example of every stage, and the habit of measuring rather than asserting. Right column is what they will meet in week one of a real project. Draw out two of them. Deep models and quantisation: we banned C and TFLite Micro deliberately so that every number in the system stayed readable, and that was a teaching decision, not an engineering one - on a real product with a real dataset, a quantised convolutional model on the same chip is a serious option and they should not be afraid of it. And the last bullet, somebody on call at three in the morning: ask who in the room has ever been that person, and what they would want the system to have printed. Usually one mature student has a story and it is worth more than the slide. Close the slide by telling them that everything in the right-hand column is learnable, and that nothing in it is harder than what they did in Lecture 13.


## Slide 11
Keep this short and unambiguous; they will remember the rules better than the theory. On the exam: the bank is published with model answers because the point is not to catch them out - there are forty-six questions and the paper is drawn from them, so preparation is reading and arguing rather than guessing scope. Emphasise the right-hand box: nobody has to memorise a kurtosis formula, and anyone who spends the week doing that has misread the course. On the lab: every group runs its own chain on its own hardware, which means twelve slightly different systems and that is the point - the checkpoints are written so that any correct implementation passes them. Say clearly that two events are unannounced, because a rehearsed reaction is not evidence of anything. Remind them that the observation sheet is the deliverable, not the code, and that an honest FAIL with a recorded number and a one-line explanation scores more than a PASS with an empty box. Finally, tell them to bring the list from notebook exercise eight of Lecture 13 - what they would have to SEE to believe each step worked - because we will run the afternoon against it.


## Slide 12
Walk the strip once more and point out that only the last two boxes need a network - that is the same line as slide two, drawn a different way, and repetition is deliberate. Then the six rules. Spend the remaining time on rules two, three and five, because those are the ones that separate a demo from something you would put on a machine. Rule two is the cheapest insurance in the course: about ninety-nine microseconds a window, eight per cent of the pipeline, and students delete it every year because it appears to do nothing - it does nothing on ninety-nine-point-nine-nine per cent of windows, which is exactly what a working gate looks like. Rule three is the one that will be got wrong in industry if it is not got right here. Rule five is Lecture 13 in one line, and slide eight is its limit. Finish personally rather than administratively: tell them the most valuable thing they have is not the model, it is the habit of asking what they would have to SEE to believe a system works - and that habit transfers to every controls, process and reliability job they will ever have. Then send them to lunch and set up the rig.


