# Module performance evaluation — pfc-scientific-visualization (2026-11-24)

Evidence-based evaluation of every module. All numbers measured on the active
skill at `C:\Users\L\.workbuddy\skills\pfc-scientific-visualization`.

## Measurement setup

- Tests: `run_tests.py` → **75 tests OK in 12.25 s**
- End-to-end pipeline: `run_pipeline.py` on the real reference case
  `examples/reference_3d_case/confined_break_6k/02_standardized_data`
  (6,379 balls / 6 walls / 19 frames / 3,721 fracture events)
  → **21.98 s wall, 34.8 MB peak Python memory** (`tracemalloc`), exit 0
- Stage timing on the same case: `load_standardized_case` **0.075 s**,
  `_derive_case` **2.599 s** → analysis math is ~12% of total; the rest is
  chart intelligence, viewer payload chunking and JSON/file I/O
- `verify_payload.py --experiment-root ... --data-root .../04_viewer/data`
  → failures `[]`
- Output sizes: `03_analysis` 17 MB, `04_viewer` 15 MB (138 data chunks, 13 MB),
  `05_charts` 172 KB, `06_publication_figures` 68 KB, `07_metadata` 116 KB
- 438 files / 112 MB total skill (includes reference case + vendored JS)

## Module-by-module verdict

| Module | Files / lines | Score | Verdict and evidence |
|---|---|---|---|
| Standard contract & read-only adapter | `standard_contract.py` 170, `adapters/capabilities.py` 96 | **9** | Manifest hash + contract `pfc.standardized-experiment@1.0.0` verified before any work; 3 boundary tests; output root must be separate from input |
| Analysis engine | `analysis/engine.py` 893 + channels/physics/statistics/units/formatting (~700) | **9** | 50 analysis keys, 16 derived arrays, 7 recorded issues on real case; per-frame positions, velocity, acceleration, nominal stress, histograms, correlations, spatial heatmaps; 2.6 s for 6k balls |
| Chart intelligence | `analysis/intelligence.py` 1,515 | **9** | 13 candidate generators; on real case 3 unsupported candidates rejected with exact reasons (`line_load` `NOT_CAPTURED`, single-case comparison `NOT_GENERATED`) and `missing_values_treated_as_zero: false`; 6 dedicated decision tests |
| Viewer payload builder | `viewer/payload_builder.py` 1,102 | **9** | 138 chunk files / 13 MB for 19 frames; u32/f32 base64 encoding; crack records rebuilt from real endpoint Ball IDs; 3 chunked-payload + 2 frame-index regression tests |
| Viewer runtime (JS) | `assets/viewer/scientific-viewer.js` 4,066 lines / 168 KB | **9** | three.js r160 offline, InstancedMesh, real wall vertices (72 triangles), 3,407 visible cracks in browser, no pageerror; local assets only, light-only theme by explicit design |
| Payload verification | `verify_payload.py` 197 | **10** | Independently re-reads chunk data against standardized NPZ; `failures: []` on the benchmarked output; strongest correctness gate in this skill |
| Publication figures | `charts/publication.py` 706 | **8** | 10 composition tests; figure_plan + ECharts SVG/PNG export path exists and was exercised in earlier acceptance (A7), but the pipeline explicitly reports composed SVG/PNG `not_generated` when browser export is not run — implemented, not automatic |
| Findings producer | `emit_findings.py` 274 | **7** | Stable `pfc.analysis-findings@1.0.0` with source manifest and artifact lineage; real producer runs verified; feedback loop itself not exercised end-to-end in the reference case |
| Performance reporting | `performance_report.py` 234 | **7** | CLI exists and records scale metrics; no automated regression threshold or CI gate — numbers must be interpreted manually |
| Linkage decisions | `viewer/linkage.py` 149 | **8** | Timeline/case/particle/range linkage verified in real browser; camera↔2D bidirectional sync intentionally not implemented |
| External viewer builder | `viewer/external_builder.py` 367 | **8** | Offline shell assembled with local vendor JS; offline contract tests PASS; GPU performance explicitly `NOT_MEASURED` (software WebGL is not GPU evidence) |
| Cleanup / packaging | `maintenance/cleanup_delivery.py` 202, `packaging/experiment_output.py` 116 | **8** | 3 cleanup-safety tests; protects immutable deliveries; packaging scripts present and used in release history |

## Honest limitations

1. **Not measured: GPU frame rate.** Browser checks used software WebGL; the
   capability matrix correctly marks hardware-GPU performance `NOT_MEASURED`.
2. **Publication export is manual.** SVG/PNG composition requires browser
   export; the CLI reports it as `not_generated` rather than silently faking it.
3. **Contact/bond networks untested on real endpoint arrays.** Renderers exist
   and pass static checks, but the reviewed cases have contact `NOT_CAPTURED`.
4. **Clump, PDF converter, 2D/3D camera sync** are explicitly not implemented —
   consistent with the honesty policy, not hidden gaps.
5. **Feedback loop not exercised in the reference case.** State machine exists
   in producer tests, but full analyze→findings→headless-rerun loop is untested.

## Overall

This skill mirrors headless: **deep and narrow, correctness-first**. Its strongest
properties are the independent payload verifier (10/10), chart intelligence that
records *why* a chart was rejected instead of inventing data, and a viewer bound
to real wall vertices and fracture endpoints. Performance is no longer a concern
at the 6k-ball/19-frame scale — 22 s end-to-end, 35 MB peak — and the remaining
gaps are coverage/measurement gaps (GPU, publication automation, feedback E2E),
not architectural defects.

Recommended positioning: downstream scientific analysis and offline viewing of
`pfc-headless` standardized deliveries; treat publication export and GPU
throughput as opt-in/manual until measured in your target environment.
