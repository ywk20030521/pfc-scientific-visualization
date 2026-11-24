# Capability Matrix

Two evidence levels are distinguished:

- `Implemented` means code/config exists and contract or unit tests pass.
- `Acceptance evidence` records whether the capability was exercised against a
  real PFC capture or a real browser during the 2026-11-16 acceptance round.

A `NOT_VERIFIED` entry has code but no recorded acceptance evidence. It is not
a claim that the capability is broken, and it must not be upgraded without a
new acceptance run.

## Current evidence (2026-11-16)

Sources: `tests/COVERAGE_MATRIX.md` (61 PASS), `tests/UNVERIFIED_ITEMS.md`,
`A5-A9_FINAL_ACCEPTANCE_REPORT_2026-11-16.md`, `A1-A4_ACCEPTANCE_REPORT_2026-11-16.md`
and `BROWSER_ACCEPTANCE_REPORT.md`.

| Capability | Implemented | Acceptance evidence |
|---|---:|---|
| Read-only standardized contract verification | Yes | Mock contract test, PASS |
| External RAW + local ANALYSIS/DISPLAY lineage | Yes | Mock contract test, PASS |
| Analysis output separation from standardized input | Yes | Mock smoke test, PASS |
| Unit conversion and display formatting | Yes | Unit PASS; A6 axis contract PASS on real PFC3D |
| Chart Intelligence scores/reasons | Yes | Unit PASS; decisions recorded in real PFC2D/PFC3D outputs |
| Chart rejection for missing data | Yes | Unit PASS; A8 reported 21 missing Cases with exact IDs on real PFC3D |
| Manual chart override | Yes | Unit PASS; no real-case override was run |
| PFC2D planar `CircleGeometry` | Yes | PASS, real PFC2D capture reviewed (A1-A4) |
| PFC3D `SphereGeometry` | Yes | PASS, real PFC3D browser A1-A9 |
| InstancedMesh and reused buffers | Yes | Static contract PASS; real-browser buffer reuse not instrumented |
| Fit/isometric/front/top/side views | Yes | Static contract PASS; real PFC3D camera controls reviewed |
| Real-ball-volume auto fit | Yes | PASS, reviewed PFC3D Case |
| Scientific self-shadowing | Yes | PASS, reviewed PFC3D Case |
| Particle metric/entity capability gates | Yes | PASS, reviewed PFC3D Case |
| Displacement/speed/acceleration coloring | Yes | Contract PASS; displacement/speed reviewed, acceleration UI wired only |
| Contact network renderer | Yes, with captured endpoint arrays | Code PASS static; `NOT_AVAILABLE_IN_REVIEWED_CASE` — no real endpoint array |
| Bond network renderer | Yes, with captured endpoint arrays | Code PASS static; `NOT_AVAILABLE_IN_REVIEWED_CASE` |
| Clump membership | No | `NOT_CAPTURED` by pfc-headless |
| Nature-inspired ECharts | Yes | A7 publication presentation PASS on real PFC3D SVG/PNG |
| Axis scientific formatting and high-precision tooltip | Yes | A6 PASS on real PFC3D; tooltip digits recorded in display metadata |
| Odd/even adaptive figure layout | Yes | Unit PASS and Viewer export |
| SVG vector composition | Yes | Unit PASS; real SVG download produced 10 unique files |
| Composed PNG with titles | Yes | PASS, reviewed PFC3D Case / A7 |
| PDF publication output | No bundled converter | `NOT_SUPPORTED`; supply a local SVG vector converter |
| Timeline/Case/particle/range linkage | Yes | PASS, reviewed real PFC3D browser |
| 3D Ball/crack 2D projection | No | intentionally omitted, `NOT_IMPLEMENTED` |
| Camera/2D bidirectional sync | No | intentionally omitted |
| Offline Viewer with local assets | Yes | PASS, real PFC2D/PFC3D Cases |
| Centralized theme tokens (historical dual-theme) | Yes | 2026-11-16 dark/light browser PASS; current runtime is light-only (see 2026-11-23 section) |
| Hardware-GPU performance | No measurement | `NOT_MEASURED`; software-WebGL automation is not GPU evidence |
| Automated scientific test suite | Yes | 61 PASS, 0 FAIL |
| Stable `pfc.analysis-findings@1.0.0` producer | Yes | Real PFC2D and PFC3D outputs, PASS |
| Findings source-manifest and artifact lineage | Yes | Unit PASS and real producer runs |

## Genuinely unverified or unsupported

These remain open after the 2026-11-16 round and need a new acceptance run:

- Contact/Bond rendering with real captured endpoint arrays.
- Clump membership rendering (upstream `NOT_CAPTURED`).

## 2026-11-23 light-scientific upgrade (implemented)

Implemented and verified against real PFC3D/PFC2D viewer copies in
`_practice/viz_upgrade_proposal/verify_3d` and `verify_2d`:

| Capability | Status | Evidence |
|---|---|---|
| three.js r160 offline vendor with global `THREE.OrbitControls` | Implemented | `THREE.REVISION=160` in browser; no page errors |
| Light-only viewer (dark theme toggle removed) | Implemented | shell has no `themeToggle`; CSS dark token block removed |
| Golden-ratio split (render:chart = 1.618:1) | Implemented | CSS grid contract test PASS |
| Bottom horizontal control dock, collapsed by default | Implemented | Browser: `data-dock=collapsed` → `open` → `collapsed`, display toggles |
| Simulation summary moved to stage header | Implemented | Browser: `#stageHead #summaryBody` present |
| Chart-only right rail | Implemented | Browser: 0 buttons/selects/inputs in `#panel` |
| Nature-light ramp + optional high-contrast palette | Implemented | Theme ramp updated; `#colorPalette` switch updates CSS ramp |
| Light scientific PBR preset (ACES + physical material + rim/env/glint) | Implemented | ACES, `MeshPhysicalMaterial`, `envMapIntensity=1.4` in runtime |
| Real-frame 2D insets with smart choice | Implemented | Browser: `insetChoice=section` (PFC3D), `top` (PFC2D) |
| View-shift compensation while dock expanded | Implemented | Expanded-state screenshot reviewed; shift removed on collapse |
| Wall solid rods + outline + vertex points | Implemented | Each captured wall segment is extruded as an instanced semi-transparent rod; true facets still require upstream payload change |
| Shareable viewer ZIP | Implemented | `scripts/viewer/package_viewer.py`; 36.6 MB → 19.1 MB ZIP |
| Headless contact-field compatibility | Implemented | `_network_frame_payload()` reads real `contact_offsets`/`contact_end1_id`/`contact_end2_id`/`contact_force_xyz` (vector→magnitude) plus legacy `*_ball_id_a/b` + `*_force_n`; browser: 120 contact segments |
| Dynamic cracks via endpoint Ball IDs | Extension | 11-field crack rows with ball A/B re-anchor the break midpoint per frame; real headless events (no endpoint IDs) stay static; browser: 37 cracks at late frame |
| 2D hides clipping + all insets | Implemented | `body[data-dimension=2]` hides `.dim3-only` + `.scene-inset`; browser verified hidden |
| Summary shown expanded (no toggle) | Implemented | `<div>` summary block with `#summaryBody`, no `<details>/<summary>` |
| Automated suite | PASS | 75 tests, 0 failures (with `PYTHONPATH=scripts`) |

Note: wall facets, bond networks and fracture endpoint Ball IDs are NOT in the
real headless converter payload. Contact networks ARE real (headless field names
now supported). Bond rendering and dynamic cracks are Viewer capabilities
verified with a labeled MOCK extension dataset; wall is rendered as solid rods
from real vertex polylines. Nothing is silently fabricated: unsupported states
remain explicitly disabled/“未采集”.
- Hardware-GPU performance benchmarking.
- PDF output without a local vector converter.
- PFC2D upgraded Viewer as an independent post-split run: a real PFC2D capture
  was reviewed, but no new PFC2D solve was executed in this round.

## Note on earlier reports

`IMPLEMENTATION_REPORT.md` and the PR1-PR8 era reports describe the earlier
integrated build. The post-split unit and browser acceptance is recorded in
`A5-A9_FINAL_ACCEPTANCE_REPORT_2026-11-16.md`, `UNVERIFIED_ITEMS.md` and
`COVERAGE_MATRIX.md`. Do not treat the older reports as the sole evidence, and
do not treat them as proof that nothing was accepted after the split.
