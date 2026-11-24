# A1-A4 Acceptance Report

## Decision

Scope for this round was limited to A1-A4. No A5-A15 item was modified.

| Item | Result | Evidence |
|---|---|---|
| A1 missing-value semantics | `PASS` | `null`, `undefined`, `NaN`, empty and invalid strings display as `—`/`未采集`; numeric `0` remains `0`. |
| A2 sampled-frame consistency | `PASS` | A real PFC3D Case with 352 source frames sampled to 8 preserves source indices `0,50,100,150,201,251,301,351` in every temporal chart. |
| A3 Ball history linkage | `PASS` | A physical Ball click selected Ball `316`; all 8 history points map to the same source indices, Viewer indices `0-7`, and captured Cycles. Frame and Case switching were verified. |
| A4 chart SVG download | `PASS` | The actual `图表 SVG` button generated 10 unique real-PFC3D files with valid roots and matching titles. |

The A1-A4 implementation is ready for source review. This report does not accept
the entire PR because A5-A15 remain outside this round.

## Root causes and fixes

### A1

`Number(null)` and similar coercions converted missing values to numeric zero.
The Viewer now uses one finite-number gate that distinguishes missing/invalid
values from real zero. Metrics, tooltip values, heatmaps, comparisons, chart
data and formatter probes share that rule. Missing chart points remain `null`.

### A2

`_slice_chart` checked the outer `x`/`y` objects instead of their `data` arrays,
so lengths did not equal the source count and time-series arrays were not
actually sliced. Charts also lacked an explicit source-frame index.

Case-attached charts now carry `source_indices`. Slicing builds a source-index
position map and applies the same positions to `x`, `y`, every series and
display metadata. Derived time series retain missing first points instead of
removing or zero-filling them.

### A3

History rows stored the source frame index but the Viewer treated it as a
Viewer frame position. History rows now contain both indices:

```text
source_frame_index
viewer_frame_index
x
y
z
displacement
speed
acceleration
```

The payload version is `2.2.0`; history stride is explicitly `8`. The Viewer
validates each source/Viewer pair against the Case frame map before drawing.
Chart interaction resolves source indices through the same map.

### A4

`setTimeout` callbacks read the loop's shared index after the loop had ended,
so every chart could request the same filename. Each callback now captures its
own chart number, entry and filename. Export completion is reported only after
all scheduled downloads have been requested.

SVG titles are inserted deterministically into each vector payload, including
current-frame histograms, correlation charts and Ball history. Verification
clicks the real user download button; it no longer substitutes the internal
Data URL API for the download test.

## Modified files

- `assets/viewer/scientific-viewer.js`
- `scripts/analysis/intelligence.py`
- `scripts/viewer/payload_builder.py`
- `scripts/viewer/external_builder.py`
- `scripts/verify_lazy_viewer.mjs`
- `scripts/verify_real_frame_contract.mjs`
- `tests/test_viewer_frame_index_regressions.py`
- `TEST_REPORT.md`
- `tests/TEST_PLAN.md`
- `tests/COVERAGE_MATRIX.md`
- `tests/UNVERIFIED_ITEMS.md`

## Verification

### Automated

- Scientific suite: `44 PASS, 0 FAIL`
- Python source compilation: `PASS`
- JavaScript syntax checks: `PASS`
- 351-source-frame Mock integration and strict browser scenario: `PASS`
- `REAL_PFC` PFC3D browser/download scenario: `PASS`

### Real PFC3D data

The acceptance input was the existing Soft Bonded PFC3D capture, labeled
`REAL_PFC`, PFC3D `9.7.49`. The 23 Cases were converted read-only by
`pfc-headless` into the `pfc.standardized-experiment@1.0.0` contract. Scientific
analysis used a separate output root.

The reviewed default Case was Case 22:

```text
source frames: 352
Viewer frames: 8
source indices: 0,50,100,150,201,251,301,351
Cycles: 30586,55586,80586,105586,131086,156086,181086,205900
selected Ball: 316
history points: 8
```

No new PFC solve was started. The source capture predates this repair and has
`execution_mode: UNKNOWN`; it is valid `REAL_PFC` data but is not evidence of a
new Console run or hardware performance.

### Evidence

Strict Mock Viewer:

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a1-a4-e2e-final\04_viewer\scientific_viewer.html
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a1-a4-browser-final\report.json
```

Real PFC3D:

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\real-pfc3d-a1-a4\standardized
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\real-pfc3d-a1-a4\analysis-final
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\real-pfc3d-a1-a4\browser-source-final
```

Actual SVG files:

```text
pfc_case_22_chart_01.svg
pfc_case_22_chart_02.svg
pfc_case_22_chart_03.svg
pfc_case_22_chart_04.svg
pfc_case_22_chart_05.svg
pfc_case_22_chart_06.svg
pfc_case_22_chart_07.svg
pfc_case_22_chart_08.svg
pfc_case_22_chart_09.svg
pfc_case_22_chart_10.svg
```

## Remaining limits

- A5-A15 were not changed or claimed as fixed.
- No new PFC2D/PFC3D solve was executed.
- Hardware-GPU performance was not re-benchmarked.
- Browser validation used local Edge in headless mode with the offline Viewer.
