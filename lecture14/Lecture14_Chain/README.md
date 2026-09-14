# Lecture14_Chain — the whole system in one folder

**01211271 Industrial AI and IoT** · Lecture 14

Unzip this beside `Lecture14_The_Integrated_System.ipynb` and the notebook will run.
Nothing here is new: every file is the one built in its own lecture.

| file | what it is | lecture |
|---|---|---|
| `rig.py` | the rotor rig, the framing, the twelve features | 8 |
| `lecture9_model.json` | the linear SVM, scaler folded in (39 numbers) | 9, 11 |
| `lecture10_alarm.json` | the max \|z\| baseline and 3-of-5 rule (25 numbers) | 10, 11 |
| `sensors.py` | the validity gate: five comparisons, one pass | 13 |
| `netpie.py` | the mock broker, topics, wildcards, retained, shadow, byte count | 12 |
| `cloud.py` | the message schema, the publish policies, the subscriber | 12 |
| `downlink.py` | validate → stage → verify → commit → rollback | 13 |
| `chain.py` | **the only new file**: the wiring, the scripted session, the checkpoints | 14 |
| `build_chain.py` | drives `chain.py` once and writes `results.json` | 14 |
| `results.json` | every number the deck, the notebook and the sheets quote | 14 |

## Run it

```
python build_chain.py
```

prints the event log and the twelve checkpoints. It takes about ten seconds and it
should print `12 of 12`. If it does not, that is a bug and I want to know.

## Where to start reading

`chain.py`, from `SESSION_MIN` downwards. It is an integration test, and the comments
say why each moment in the script is where it is — in particular why the third model
update arrives at minute 17.5 and not earlier.
