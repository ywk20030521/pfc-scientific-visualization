# Open-source readiness and three-Skill standards alignment

**Repository:** `ywk20030521/pfc-scientific-visualization`
**Date:** 2026-11-27
**Standard sources:** PFC-SRA-ARCH-001 / ARCH-002 / REM-001 and the overall
three-step plan.
**Status key:** `PASS` on `main`; `ADDED IN THIS PR`; `PARTIAL`; `GAP`.

## 1. GitHub repository configuration

| # | Requirement | Standard source | Current compliance | Gap / action | Priority |
|---|---|---|---|---|---|
| 1 | MIT LICENSE | GitHub OSS baseline | `PASS` | None | — |
| 2 | README with scope and non-goals | ARCH-002 §1.3 | `PASS` | Add contributing/CoC/release links | P2 |
| 3 | CONTRIBUTING guide | GitHub OSS baseline | `ADDED IN THIS PR` | Includes scientific-integrity rules | — |
| 4 | Code of Conduct | GitHub OSS baseline | `ADDED IN THIS PR` | None | — |
| 5 | Security policy | GitHub OSS baseline | `ADDED IN THIS PR` | None | — |
| 6 | Issue templates | GitHub OSS baseline | `ADDED IN THIS PR` | None | — |
| 7 | PR template | GitHub OSS baseline | `ADDED IN THIS PR` | None | — |
| 8 | CHANGELOG | GitHub OSS baseline | `ADDED IN THIS PR` | Keep updated each PR | P1 |
| 9 | Release config + draft notes | GitHub OSS baseline | `ADDED IN THIS PR` | Must not be published while blocked | P0 |
| 10 | Tag + public Release | GitHub OSS baseline | `GAP` — no tags or Releases | Propose `v2.1.0`; block until P0 rows close; none created here | P0 |

## 2. Three-Skill standard alignment

| Standard item | Requirement | Current compliance | Gap / action | Priority |
|---|---|---|---|---|
| ARCH-002 §1.3 — analysis boundary | No PFC control, no RAW modification, no scientific verdict | `PASS` in scope text | Keep enforcement in PR review | — |
| ARCH-002 §2.1 — Analysis ownership | Viz owns DERIVED / Analysis / charts | `PASS` | Do not add Finding objects | — |
| ARCH-002 §3 rule 7 — verification honesty | No `NOT_RUN/UNKNOWN/WARNING → PASS` | `PARTIAL` — documented but not uniformly enforced in outputs | Add explicit status mapping to analysis output | P1 |
| ARCH-002 §5.3 — canonical layers | `RAW / STANDARDIZED / DERIVED` | `GAP` on `main`; `layer_contract.py` in remediation worktree | Merge REM-001 R06 and coordinate with Headless | **P0** |
| REM-001 R05 — analysis-findings naming | Mark as `ANALYSIS_FEEDBACK_NOT_SCIENTIFIC_FINDING` / `NOT_RE_FINDING` | `GAP` on `main`; fixed in remediation worktree | Merge; treat unmarked historical data as analysis feedback | **P0** |
| REM-001 R06 — layer vocabulary | Canonical layers with legacy mapping | `GAP` on `main` | Merge in same release window as Headless | **P0** |
| REM-001 R12 — hard-coded paths | `project_root` / `owner` / `artifact_root` from caller | `GAP` | Parameterize; keep compatibility period | P2 |
| REM-001 R11 — invocation envelope | `request_id` + `idempotency_key` | `GAP` | Define `pfc.skill-invocation@1.0.0` | P1 |
| Acceptance integrity | Fresh worktree test suite must be green | `GAP` — 1 CRLF-related ERROR reported | Re-run in main workspace; normalize line endings before tag | **P0** |
| Capability status vocabulary | Six exact tokens, TESTED ≠ REAL_ENV_VERIFIED | `PARTIAL` — reports use prose levels | Add a status mapping table | P1 |

## 3. Release decision

**Do not tag or publish from `main` yet.** The naming and layer remediation
changes are unmerged, and a fresh-worktree acceptance test is not green. This
PR adds repository configuration only; it does not change runtime behavior.

## 4. Verification of this PR

```text
PYTHONPATH=scripts python -m unittest discover -s tests -p "test_*.py"
# Ran 76 tests in 8.390s — FAILED (errors=1)
# test_standard_contract_boundary: experiment.json hash does not match the contract
```

The error is the known fresh-worktree line-ending issue described in REM-001 §4;
it occurs on unmodified `main` in this worktree and is **not** caused by this
documentation PR. No runtime module, schema or test was modified. Do not tag
until it is resolved in the main workspace.
