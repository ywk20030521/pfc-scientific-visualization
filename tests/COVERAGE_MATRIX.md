# Scientific Test Coverage Matrix

The split scientific suite was executed on 2026-11-16:
`61 PASS, 0 FAIL`. Capture/standardization adds `25 PASS` in `pfc-headless`.

| Requirement | Test location | Environment | Status |
|---|---|---|---|
| External standardized parent + Analysis/Display lineage | `test_data_layers_formatting_units.py` | Mock/unit | `PASS` |
| Read-only contract and output separation | `test_standard_contract_boundary.py` | Mock/integration | `PASS` |
| Number formatting | `test_data_layers_formatting_units.py` | Mock/unit | `PASS` |
| Unit conversion | `test_data_layers_formatting_units.py` | Mock/unit | `PASS` |
| Missing values preserved | `test_data_layers_formatting_units.py` | Mock/unit | `PASS` |
| Chart candidate reasons | `test_chart_intelligence_decisions.py` | Mock/unit | `PASS` |
| Constant chart rejection | `test_chart_intelligence_decisions.py` | Mock/unit | `PASS` |
| Manual chart override | `test_chart_intelligence_decisions.py` | Mock/unit | `PASS` |
| Odd panel layouts | `test_publication_composition.py` | Mock/unit | `PASS` |
| Even panel layouts | `test_publication_composition.py` | Mock/unit | `PASS` |
| Six/eight panel orientation | `test_publication_composition.py` | Mock/unit | `PASS` |
| Variable panel sizes | `test_publication_composition.py` | Mock/unit | `PASS` |
| SVG title/composition | `test_publication_composition.py` | Mock/unit | `PASS` |
| 2D/3D rendering contract | `test_scientific_visual_console_boundary.py` | Static contract | `PASS` |
| Shadow/auto-focus contract | `test_scientific_visual_console_boundary.py` | Static contract | `PASS` |
| Acceleration and optional networks | `test_scientific_visual_console_boundary.py` | Static contract | `PASS` |
| Adaptive Viewer composite export | `test_scientific_visual_console_boundary.py` | Static contract | `PASS` |
| Dynamic entities | `pfc-headless/tests/test_standardization_dynamic.py` | Mock/unit | `PASS` |
| Multi-Case payload | `test_viewer_chunked_payload.py` | Mock/integration | `PASS` |
| A1 missing values and real zero | `verify_lazy_viewer.mjs` | Real browser/Mock data | `PASS` |
| A2 351-to-8 frame mapping | `test_viewer_frame_index_regressions.py` | Mock/integration | `PASS` |
| A3 Ball history source/Viewer mapping | `test_viewer_frame_index_regressions.py`, `verify_lazy_viewer.mjs` | Mock + browser | `PASS` |
| A4 real SVG download button | `verify_lazy_viewer.mjs`, `verify_real_frame_contract.mjs` | Browser download events | `PASS` |
| A5 robust P05/P95 overflow bins | `test_histogram_robust_binning.py`, real browser | Unit + real PFC3D | `PASS` |
| A6 shared axis notation/range | `test_axis_contract_formatting.py`, real browser | Unit + real PFC3D | `PASS` |
| A8 multi-Case availability | `test_multicase_availability_contract.py`, real browser | Unit + real PFC3D | `PASS` |
| A9 legacy compatibility/identity | `test_legacy_artifact_compatibility.py`, publication tests | Unit + real SVG compose | `PASS` |
| A7 publication presentation | `test_publication_composition.py`, browser/vector inspection | Unit + real SVG/PNG | `PASS` |
| Missing channel handling | `test_analysis_chart_semantics.py` | Mock/unit | `PASS` |
| Offline Viewer assets | `test_viewer_offline_contract.py` | Static contract | `PASS` |
| PNG/SVG export API | `verify_lazy_viewer.mjs`, `verify_real_frame_contract.mjs` | Real browser | `PASS`, A1-A4 real PFC3D Case |
| Timeline/chart/particle/range linkage | `verify_lazy_viewer.mjs` | Real browser | `PASS`, reviewed PFC3D Case |
| Real PFC capture | `pfc-headless` Console procedure | Real Console | `NOT_EXECUTED` in this split |
| Real PFC3D A1-A4 Viewer | `verify_real_frame_contract.mjs` | Real browser | `PASS` |
| PFC2D upgraded Viewer | Pending end-to-end run | Real browser | `NOT_VERIFIED` |
| Hardware performance | `benchmark_viewer.mjs` | Hardware GPU | `NOT_EXECUTED` |
| Contact/Bond scene data | Optional array contract tests | Real capture | `NOT_AVAILABLE_IN_REVIEWED_CASE` |
