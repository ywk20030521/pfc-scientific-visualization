# Skill Module Evaluation — 2026-11-24

Scope: `pfc-headless` and `pfc-scientific-visualization`, evaluated through the complete real-data case `run_case17_confined_break_6k_r1`.

Evidence case: `examples/reference_3d_case/confined_break_6k/`.

## 1. Summary

| Area | Status | Evidence |
|---|---|---|
| Environment discovery | PASS | PFC3D 9.0 Console verified; bridge dependency 0.6.11; console-only accepted |
| Engine/connection lifecycle | PASS | Registered instance `pfc3d_9001case17`, 4-layer evidence READY |
| Project/case/run management | PASS | case_17 registered; `run_case17_confined_break_6k_r1` prepared, attached, completed, finalized |
| Simulation execution | PASS | 6379 balls, 6 walls, 9330 cycles, 0.03 s mechanical time |
| Raw capture | PASS | 19 real frames; 3721 fracture events with endpoint Ball IDs |
| Standardization | PASS | `data verify PASS []`; immutable delivery manifest |
| Analysis engine | PASS | channels resolved; particle displacement/speed/acceleration, nominal stress, fracture events supported |
| Chart intelligence | PASS with explicit omissions | unsupported/missing candidates recorded with reasons; no fabricated values |
| Viewer generation | PASS | light-only viewer, local assets, 72 wall triangles, 3407 cracks visible at cycle 4500 |
| Payload verification | PASS | `verify_payload.py PASS []` |
| Browser runtime | PASS | no pageerror; wallFaces=72; cracks=3407 |
| Publication figures | NOT_VERIFIED | composed SVG/PNG require Viewer browser exports not run here |
| Feedback loop | NOT_VERIFIED | not exercised in this case |
| Full physics calibration | NOT_VERIFIED | case prioritizes observable fracture; UCS 150 MPa not calibrated |

## 2. Measured performance

- Headless tests: **63 OK** in 12.0 s
- Visualization tests: **75 OK** in 15.0 s
- Case 17 simulation + capture: **116.57 s** for 6379 balls / 6 walls / 19 frames
- Raw run tree: 18 files, 15,534,372 bytes
- Standardized delivery: 57 files, 24,232,931 bytes
- Analysis + viewer output: 169 files, 32,941,111 bytes
- Browser frame 8 (cycle 4500): `wallFaces=72`, `cracksVisible=3407`, no pageerror

## 3. Bottlenecks found

1. **FISH frame writing is the dominant cost.** case_15 with ~10k balls, contact capture enabled and a 200-cycle stride could not keep up; bridge requests timed out. Reducing to 6379 balls, disabling contact capture and using a 500-cycle stride completed in under two minutes.
2. **High bond strength + rigid confinement suppresses breakage.** Parameter scan showed `pb_ten=5e6–4e7` produced no bond breaks within 10k cycles; `pb_ten=5e5` produced progressive fracture. Strong-rock calibration and visible fracture are not yet unified.
3. **Publication export path remains unexercised.** The viewer supports export APIs, but SVG/PNG composition was not run in this acceptance case.
4. **Contact channel was not captured in case 17.** Viewer correctly reports `NOT_CAPTURED`; no zero-filling occurred.

## 4. Module verdicts

### pfc-headless

- Core workflow is stable: environment, instance, connection, project, run, capture, standardization all produced contract-compliant artifacts.
- The capture script was hardened earlier in the session to derive a one-to-one fracture catalog from authoritative FISH bond-break events when the DFN catalog is empty.
- `run rebind` import bug was fixed.
- Remaining limitation: FISH frame write throughput must be considered when sizing particle count and sampling stride.

### pfc-scientific-visualization

- Analysis and viewer path is stable on real 3D data with fracture events.
- Viewer honors real wall vertices and real fracture endpoints; no fabricated wall scaling or interpolated frames.
- `verify_payload.py` history stride bug was fixed and verified.
- Wall material now uses bright blue `#2F6FD0`, with thin fill and edge outline.
- Remaining limitation: publication export and feedback loop are implemented but not verified in this real-data case.

## 5. Reference case decision

`examples/reference_3d_case/confined_break_6k/` replaces the mock showcase as the primary case to read. The legacy mock directories remain as regression fixtures only.

The new reference case is complete: raw run, standardized delivery, analysis and viewer output, plus a README documenting evidence and limits.
