# Deliverables

> Historical integrated-build inventory. Raw capture and standardized delivery
> are now owned by `pfc-headless`.

| Requirement | Location | Current status |
|---|---|---|
| Complete Skill source | `SKILL.md`, `scripts/`, `assets/`, `schema/`, `references/`, `tests/` | `GENERATED` |
| Three.js scientific design system | `assets/styles/scientific-visual-semantics.json`, `references/threejs-rendering.md` | `GENERATED`, browser-reviewed |
| Nature-inspired ECharts system | `assets/styles/nature-theme.json`, `references/echarts-chart-system.md` | `GENERATED`, browser-reviewed |
| RAW/ANALYSIS/DISPLAY layers | `scripts/schema/layers.py`, `schema/data_layer.schema.json`, `references/data-layers.md` | `GENERATED`, tests `PASS` |
| Unit and number formatting | `scripts/analysis/units.py`, `formatting.py` | `GENERATED`, tests `PASS` |
| Chart Intelligence Engine | `scripts/analysis/intelligence.py`, `references/chart-intelligence.md` | `GENERATED`, tests and real-data review `PASS` |
| Adaptive figure composition | `scripts/charts/publication.py`, `references/figure-composition.md` | `GENERATED`, tests and visual QA `PASS` |
| 2D/3D linkage decisions | `scripts/viewer/linkage.py`, `references/linkage-decisions.md` | `GENERATED`, browser-reviewed |
| Tests and plan | `tests/`, `tests/TEST_PLAN.md`, `tests/COVERAGE_MATRIX.md` | `PASS`, 57 tests |
| PR1-PR8 report | `IMPLEMENTATION_REPORT.md`, `PR_DEPENDENCIES.md` | `GENERATED` |
| Capability and unverified lists | `CAPABILITY_MATRIX.md`, `tests/UNVERIFIED_ITEMS.md` | `GENERATED` |
| Installation and usage | `README.md`, `references/installation.md`, `references/usage.md` | `GENERATED` |
| Example config/data/Viewer | `examples/` | existing mock assets preserved; not revalidated |
| Output Contract | `SKILL.md`, `references/output-contract.md`, `07_metadata/output_contract.json` generated per experiment | `GENERATED` |
| Installable Skill ZIP | `../pfc-scientific-visualization-v2.1-2026-11-15.zip` | `GENERATED` |

The experiment result package and the Skill software package are separate
deliverables. This directory is the Skill software package.

The maintenance run did not start PFC, Console or Bridge. It used an existing
real PFC3D capture for post-processing and browser review. Hardware performance
remains unmeasured.
