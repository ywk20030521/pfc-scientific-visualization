# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); tags
use [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Open-source repository configuration: contributing guide, code of conduct,
  security policy, issue and pull-request templates, release-note configuration,
  versioning policy and a three-Skill standards alignment matrix.

### Planned / not in this PR

- `analysis-findings` → `analysis-feedback` naming and explicit
  `NOT_RE_FINDING` markers (REM-001 R05) exist in a remediation worktree, not
  on `main`.
- Canonical `RAW / STANDARDIZED / DERIVED` layer contract (REM-001 R06) exists
  in a remediation worktree, not on `main`.
- Project-root / owner decoupling (REM-001 R12) is still a plan.

## [2.1.0] — PROPOSED, NOT TAGGED

> Draft target for the first public tag. Do not treat this as a published
> release. Historical packaging mentioned a `v2.1` ZIP, but no Git tag exists.

### Capabilities on the current baseline

- Offline Three.js / ECharts scientific Viewer with local assets.
- Derived quantities, unit-aware statistics and formula lineage.
- Chart Intelligence, publication figure composition, 2D/3D linkage decisions.
- Consumption of `pfc.standardized-experiment@1.0.0` from `pfc-headless`.

### Verification evidence

- `TEST_REPORT.md`, `VALIDATION_REPORT.md`, `BROWSER_ACCEPTANCE_REPORT.md`,
  `A5-A9_FINAL_ACCEPTANCE_REPORT_2026-11-16.md`.

### Known limitations

- No tag or GitHub Release has been created.
- A fresh worktree produced one `test_standard_contract_boundary` ERROR caused
  by CRLF checkout under `core.autocrlf=true`; the installed directory passed.
  Confirm after merging before tagging.
- The 6,379-particle viewer ZIP was verified offline on the development
  machine only; independent-machine and static hosting remain `NOT_VERIFIED`.
- Scientific validation and Finding belong to the Research Evidence Skill.
