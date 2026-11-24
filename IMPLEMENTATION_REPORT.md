# PR1-PR8 Implementation Report

> Historical integrated-build report. The current responsibility split moves
> capture and standardization to `pfc-headless`; use `CAPABILITY_MATRIX.md` and
> the post-split test reports for current status.

## Delivery status

- Static code and documentation implementation: `GENERATED`.
- Tests: `PASS`, 57 Mock/unit/static checks.
- PFC/Console execution in this delivery: not performed, `NOT_VERIFIED`.
- Browser/Viewer acceptance: `PASS` for the reviewed real PFC3D Case.
- Image export and visual inspection: `PASS` for the reviewed real PFC3D Case.
- Performance measurement: not performed, `NOT_VERIFIED`.
- Skill ZIP packaging: `GENERATED`.

The Skill remains Console-only. GUI actions, paths and acceptance are outside
the supported boundary.

| PR | Implemented in this upgrade | Static status |
|---|---|---|
| PR1 | RAW/ANALYSIS/DISPLAY layer builders; enriched variable semantics; versioned Three.js/ECharts token config; data-layer JSON Schema | `GENERATED` |
| PR2 | Unit registry and conversion records; automatic scientific/decimal formatting; axis/tooltip display separation | `GENERATED` |
| PR3 | Chart Intelligence Engine with features, candidate generation, scores, reasons, alternatives, overrides and rejection records | `GENERATED` |
| PR4 | PFC2D planar circles versus PFC3D spheres; local scientific materials; real-ball auto fit; view presets; capability-gated metrics and entity controls | `GENERATED`, browser-reviewed |
| PR4.1 | InstancedMesh/BufferGeometry reuse; sRGB/no-tone-map quantitative color path; controlled soft shadows; chunk/history LRU; PNG export API; acceleration coloring | `GENERATED`, browser-reviewed |
| PR5 | Nature-inspired ECharts styles, single-column readability, SVG titles, odd/even adaptive Viewer composite | `GENERATED`, browser-reviewed |
| PR6 | Per-Case capability inspection; PFC2D/PFC3D declarations; Console preservation; mixed-Case input does not fail on an optional missing field | `GENERATED` |
| PR7 | Mock/unit/static-contract tests, coverage matrix and unverified inventory | `PASS`, 57 tests |
| PR8 | SKILL/references/agent metadata/README/capability/output contract and ZIP packaging updates | `GENERATED`, `NOT_VERIFIED` |

## Important modules

| File | Role |
|---|---|
| `scripts/schema/layers.py` | Three-layer lineage records |
| `scripts/analysis/units.py` | Compatible-unit conversion |
| `scripts/analysis/formatting.py` | Display-only numerical formatting |
| `scripts/analysis/intelligence.py` | Explainable chart selection |
| `scripts/viewer/linkage.py` | 2D/3D linkage value decisions |
| `scripts/adapters/capabilities.py` | Per-Case field/entity capability scan |
| `scripts/charts/publication.py` | Adaptive multipanel composition |
| `scripts/run_pipeline.py` | Offline integration of data, charts, Viewer and contract |

## Boundaries not changed

- Existing script-embedded FISH capture remains the acquisition engine.
- No interpolation, zero fill or synthetic frame was added.
- Contact endpoints and particle force/stress histories are not synthesized.
- Contact and Bond network renderers activate only when endpoint arrays exist.
- PFC2D N/m line load is not reported as Pa stress.
- No new network/CDN dependency was introduced.
- No GUI execution entrypoint was added.
