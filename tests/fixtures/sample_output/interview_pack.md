# Interview prep — tesla-adas-validation-2026-07

Positioning: **adas-av-validation**

## Format forecast
- **phone screen** — Validate Smart Cruise Control (SCC) and Adaptive Cruise Control behavior
- **technical: HIL/validation deep-dive** — Build and run Hardware-in-the-Loop (HIL) and Model-in-the-Loop (MIL) test benches

## Likely topics
- [deep] EKF / Kalman sensor fusion for road-radius (predicted by `scc`)
- [deep] HIL vs MIL bench architecture (predicted by `hil`)
- [deep] false-positive/negative triage via log replay (predicted by `log-replay`)
- [skim] ISO 26262 functional-safety vocabulary (predicted by `scc`)

## Resume deep-dive
### Independently developed and validated SCC emergency-stop behavior.
- Q: Walk through the safe-stop state machine.
- Q: How did you validate driver-incapacitated handover?
- A: Grounded in the SCC emergency-stop behavior I independently developed; describe the stop-state transitions without exposing internal thresholds.

### Reduced repeated real-bus road-test loops using log replay.
- Q: How did the BEV replay workflow cut trips?
- A: Replayed production logs through TOS/ODP target-selection logic to reproduce false detections offline before real-vehicle confirmation.

## Project walkthroughs (STAR)
### BEV replay validation studio
- **Situation:** Rare bus-only-lane false detections needed many long road tests.
- **Task:** Reproduce and debug them without repeated real-bus trips.
- **Action:** Built a BEV replay workflow through production TOS/ODP logic.
- **Result:** Cut repeated bus-only-lane road-test loops from about 10 trips to about 5, each roughly 4-5 hours.

## System design
- Design a regression-validation pipeline for a commercial-vehicle ADAS stack.
  - skeleton: log ingest -> replay through target-selection -> scenario diff -> triage

## Behavioral
- Tell me about a time you caught a production issue before release. — <HUMAN FILLS>

## Questions to ask
- How is HIL coverage measured on the validation team?

## Honest gaps to prep
- ISO 26262 is exposure-level for me — prepare the vocabulary honestly.

## Refreshers plan
- EKF derivation + bicycle model (~2h)
- CAN-FD / XCP recap (~1h)
