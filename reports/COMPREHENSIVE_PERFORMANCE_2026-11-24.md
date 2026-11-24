# Comprehensive performance assessment after both upgrades (2026-11-24)

Two skills were upgraded this session:
- `pfc-headless` PR-1..PR-4 (cleaning pipeline), commit `718d019`
- `pfc-scientific-visualization` V0..V3 (observability/packaging/feedback), commit `e96609d`

This report separates **speed**, **memory**, and **capability**. conflating them
is the main source of misleading upgrade claims.

## 1. pfc-headless cleaning: large, real speed and memory gains

Measured end-to-end with exact `git HEAD` baseline code restored via
`git archive`; synthetic 200 frames × 1000 balls = 200,000 ball rows.

| Variant | Wall time | Peak Python memory | vs baseline |
|---|---:|---:|---|
| Original HEAD | 15.16 s | 283.1 MB | 1.00× / 1.00× |
| PR-1 preallocation (default) | 15.87 s | 283.1 MB | 0.95× / 1.00× |
| PR-1 `--fast-reader` | 15.41 s | 163.3 MB | 0.98× / **1.73×** |
| **PR-2 `--columnar`** | **9.90 s** | **29.4 MB** | **1.53× / 9.6×** |
| PR-4 `--auto` | selects columnar for this case | same as columnar | same |

Key point: preallocation alone changed nothing end-to-end; the win came from
eliminating the `ball_frames` dict-of-dicts layer. `--auto` picks the fast path.

Validated on real experiments (re-converted in `--auto` mode, every channel
byte-identical to shipped deliveries):
- `run_case14_realistic_ratio_break_r1`: 599,830 ball rows + 1,211,213 contact
  rows, 40/40 identical
- case16 29/29, case13 40/40, 2D case10 32/32, 2D case08 20/20
- 35/35 shipped deliveries PASS `verify_delivery`; 39/47 raw runs convertible,
  8 correctly rejected (failed/incomplete attempts with no delivery)

## 2. visualization pipeline: no speed gain by design; earlier "27.55 s" was measurement overhead

The V0..V3 upgrade added observability, baseline checks, feedback verification
and packaging. It did **not** set out to make the analysis faster, and it does not.

Fair A/B on the real reference case (`confined_break_6k`, 6,379 balls / 19 frames
/ 3,721 fractures), both runs without tracemalloc or `--measure`:

| Variant | Inner wall time | Peak process RSS | ratio |
|---|---:|---:|---|
| Pre-upgrade (`bbefe42`) | 10.184 s | 84.3 MB | 1.00× |
| Post-upgrade (`e96609d`) | 9.994 s | 84.0 MB | 1.02× faster, 0.4% less RSS |

**Correction of an earlier number**: the first skill-generated stage report
showed 27.55 s and 108.75 MB peak RSS. That run had tracemalloc active. Measured
overhead on the same upgraded code:

| Condition | Inner wall time | vs pre-upgrade |
|---|---:|---|
| upgraded, no instrumentation | 9.99 s | 1.02× faster |
| upgraded + external tracemalloc | 22.09 s | 0.46× (2.2× slower) |
| upgraded + `--measure` (tracemalloc + stage work) | 30.42 s | 0.33× (3.0× slower) |

So: the upgrade itself is ~2% faster; the apparent 2.7× slowdown was entirely
tracemalloc's cost. This is why `--measure` is opt-in and why the report records
both RSS and tracemalloc with an explicit "do not sum" note.

The stage report is still valuable because it revealed the true stage split:
analysis 16.86 s, viewer payload 6.48 s, packaging 3.91 s **under tracemalloc**.
Those ratios differ from uninstrumented runs because tracemalloc taxes Python
object allocation unevenly; use the frozen baseline for regression decisions.

## 3. Capability gains (not speed, but they change what the tools can do)

| Capability | Before | After |
|---|---|---|
| Per-stage pipeline timing | none | 7 stages, RSS + tracemalloc, indexed in output manifest |
| Performance regression detection | none | env-tagged baseline, +20% warn / +50% fail, verified by simulated regression |
| Findings → next Run loop | producer and state machine existed, never E2E verified | 9/9 checks PASS on isolated project copy, source Run hash unchanged |
| Packaging | single manifest, no atomic publish | scientific 24.8 MB / display 8.0 MB packages, hash-verified, atomic |
| Cleanup safety | dry-run + confirmation + protected names | also protects files claimed by output index; idempotent |
| NumPy 2.x contact `-1` endpoints | `OverflowError`, real case14 unconvertible | explicit uint64 sentinel, byte-identical output |

## 4. Honest scoring

| Dimension | Before | After | Evidence |
|---|---|---|---|
| Cleaning throughput (large runs) | 5/10 | **9/10** | 1.53× faster, 9.6× less memory, 5 real experiments identical |
| Cleaning correctness/compatibility | 7/10 | **9/10** | sentinel fix; 35 deliveries PASS; 8 correct rejections |
| Visualization analysis speed | 8/10 | **8/10** | 9.99 s vs 10.18 s, no material change |
| Visualization observability | 4/10 | **9/10** | skill-generated stage report + regression gate |
| Visualization feedback closure | 5/10 | **8/10** | 9/9 E2E checks; final VALIDATED still needs real Console run |
| Packaging/storage hygiene | 7/10 | **9/10** | atomic publish, display package 3.1× smaller, in-use cleanup guard |

Overall: **the performance-limited part (cleaning) improved dramatically; the
visualization side gained engineering robustness rather than raw speed, and
its pipeline stayed flat.** Any claim that visualization became 2.7× slower or
faster would be a measurement artifact.

## 5. Reproduce

- headless cleaning: `run_standardization.py --input <run> --output <new> --auto`
- viz fair run: `run_pipeline.py --input <standardized> --output <result>` (no flags)
- viz measured run: add `--measure` (expect ~3× slower by design)
- regression check: `performance_baseline.py check --timing <result>/07_metadata/stage_timings.json --baseline references/baselines/confined_break_6k_cold.json --output <check.json>`
- feedback loop: `verify_feedback_loop.py` with `--source-project`, `--analysis-root`, `--run-id`, `--work-root`, `--headless-scripts`, `--viz-scripts`
