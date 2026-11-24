# Automated Test Report

## Current maintenance run

- Command: bundled Python 3 execution of `scripts/run_tests.py`
- Result: `PASS`
- Tests: `66`
- Failures/errors: `0`
- Execution date: 2026-11-16
- Scope: Mock/unit and static Viewer contracts only; no PFC process started
- Browser review: `PASS` for A1-A9 on an existing `REAL_PFC` PFC3D capture

The suite covers data layers, numerical formatting, unit conversion, chart
reasoning and constant-channel rejection, odd/even composition, payload
generation, dynamic entities, multi-Case behavior, missing channels, offline
assets, acceleration wiring, optional network rendering contracts and the
Console-only boundary. The A1-A4 regression additions cover missing-value
semantics, 351/352-to-8 frame sampling, first-point-missing derived series,
source/Viewer frame mapping, Ball history, Case switching and real browser SVG
downloads. A5-A9 add robust histogram tails, shared-exponent axes, Case
availability contracts, legacy temporal compatibility, stable SVG identities,
Case-aware publication selection and visual clipping checks.

The PR9-PR14 maintenance pass adds automated `pfc.analysis-findings@1.0.0`
producer coverage and re-runs all 66 tests after a clean installation audit.

Real PFC execution and hardware-GPU performance remain separate acceptance
items and were not executed by this test command.
