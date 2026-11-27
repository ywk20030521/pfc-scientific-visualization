# Contributing to PFC Scientific Visualization

Thanks for contributing. This repository is the analysis and presentation
engine of the PFC Scientific Research Agent. Please keep changes inside that
boundary.

## Scope boundary

This Skill owns:

- consumption of the immutable `pfc.standardized-experiment@1.0.0` contract;
- cleaning, derived quantities, statistics, curve and spatial analysis;
- Chart Intelligence, ECharts charts, Three.js offline Viewer and publication
  figures;
- analysis provenance (formula, algorithm version, parameters, units, inputs)
  and DERIVED outputs.

This Skill does **not** own PFC/Console control (Execution), user discussion,
decisions or authorization (Interaction), or scientific validation, Evidence
and Finding (Research Evidence Skill). A computed peak strength is a number,
not a scientific conclusion.

## Before you start

- Python 3.10+; Node tooling is only needed if you rebuild vendored Viewer
  assets.
- Read `SKILL.md`, `README.md`, `CAPABILITY_MATRIX.md` and
  `docs/OPEN_SOURCE_READINESS.md` first.
- Never modify RAW data. Corrections and filters produce new DERIVED objects.

## Development and tests

```bash
PYTHONPATH=scripts python -m unittest discover -s tests -p "test_*.py"
```

Browser and Viewer checks are recorded in `BROWSER_ACCEPTANCE_REPORT.md` and
the acceptance reports in the repository root. A green unit suite is not a
substitute for a real-data review.

## Scientific integrity rules

1. Use the capability vocabulary exactly: `IMPLEMENTED`, `TESTED`,
   `REAL_ENV_VERIFIED`, `NOT_VERIFIED`, `NOT_IMPLEMENTED`, `DEPRECATED`.
2. Do not decide that a model is physically valid. Report numbers, formulas,
   units, algorithm versions and limitations; leave validation to RE.
3. Never name an analysis result a `Finding`. Analysis feedback is explicitly
   `ANALYSIS_FEEDBACK_NOT_SCIENTIFIC_FINDING` / `NOT_RE_FINDING`.
4. Use the canonical data layers `RAW / STANDARDIZED / DERIVED`; legacy
   `RAW_DATA / ANALYSIS_DATA / DISPLAY_DATA` labels must be normalized through
   the layer contract, never silently mixed.
5. Visual quality is not scientific correctness. Record renderer performance,
   scientific fidelity and publication output as separate checks.
6. Report memory and size measurements separately: ZIP size is not runtime
   memory, and local offline verification is not public deployment.

## Pull requests

- Fork and open a PR against `main`; use `fix/...`, `docs/...` or `feat/...`.
- Fill in `.github/PULL_REQUEST_TEMPLATE.md`.
- Add tests for behavioral changes; update `CHANGELOG.md` and the relevant
  acceptance/capability document in the same PR.
- If you change an output schema, check Headless compatibility together.
- State exactly which verification was real data, browser-based or simulated.
- Do not mix security/contract fixes with cosmetic changes.

## Issues

Use the bug or feature templates. Include the input contract version, PFC
dimension (2D/3D), dataset size, and whether the result was produced from real
PFC data. Do not attach proprietary datasets.

## Security

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
