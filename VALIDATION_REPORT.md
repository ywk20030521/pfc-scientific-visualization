# Validation Report

> Historical integrated-build report. It is not evidence for the current split
> contract and must be re-run from a pfc-headless standardized delivery.

## Current PR1-PR8 upgrade

| Gate | Current status |
|---|---|
| Static code/document implementation | `GENERATED` |
| Unit/integration tests | `PASS`, 57 tests |
| PFC2D Console execution | `NOT_VERIFIED` |
| PFC3D Console execution | `NOT_VERIFIED` |
| Capture integrity execution | `NOT_VERIFIED` |
| Browser rendering/interaction | `PASS` for reviewed real PFC2D and PFC3D Cases |
| PNG/SVG export | `PASS` for reviewed real PFC2D and PFC3D Cases |
| PDF export | `NOT_SUPPORTED` without a local vector converter |
| Visual figure inspection | `PASS` for reviewed PFC2D and PFC3D Cases |
| Performance measurement | `NOT_VERIFIED` |
| Skill ZIP creation | `GENERATED` after final installation packaging |

This report does not inherit PASS status from an earlier build. Historical
evidence remains in `HISTORICAL_VALIDATION_2026-11-08.md` and the acceptance
files marked as historical snapshots; those artifacts do not validate the new
CircleGeometry, chart-formatting, data-layer, capability-gate or adaptive-layout
changes.

## Known unsupported or unimplemented

- GUI execution is forbidden.
- PDF conversion requires an external local vector converter.
- Contact/Bond network renderers require captured endpoint arrays; the reviewed
  case does not contain them.
- Clump membership is not captured.
- 3D-to-2D projected particle/crack linkage is intentionally not implemented.
- Hardware-GPU performance is not claimed.
