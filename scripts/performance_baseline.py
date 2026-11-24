"""Freeze and check pipeline performance baselines with explicit thresholds.

Baselines are per-stage, per-mode (cold/warm) and tagged with the environment.
Never compare numbers across different hardware or Python/numpy versions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WARN_RATIO = 0.20
FAIL_RATIO = 0.50
RSS_BUDGET_FACTOR = 2.0
STAGES = (
    "input_validation", "analysis", "data_layers", "capabilities",
    "viewer_payload", "publication_plan", "packaging",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _environment() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def freeze(timing_path: Path, output: Path, *, label: str = "reference") -> dict[str, Any]:
    report = _read(timing_path)
    stages = {s["stage"]: s for s in report.get("stages", [])}
    missing = [name for name in STAGES if name not in stages]
    if missing:
        raise ValueError(f"Timing report missing stages: {missing}")
    baseline = {
        "status": "FROZEN",
        "label": label,
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": _environment(),
        "mode": report["measurement"]["mode"],
        "input_manifest_sha256": report.get("input_manifest_sha256"),
        "stages": {
            name: {
                "duration_seconds": stages[name]["duration_seconds"],
                "output_bytes": stages[name].get("output_bytes"),
            }
            for name in STAGES
        },
        "process_peak_rss_mb": report.get("process_peak_rss_mb"),
        "thresholds": {
            "warn_ratio": WARN_RATIO,
            "fail_ratio": FAIL_RATIO,
            "rss_budget_factor": RSS_BUDGET_FACTOR,
        },
    }
    _write(output, baseline)
    return baseline


def check(timing_path: Path, baseline_path: Path, output: Path) -> dict[str, Any]:
    actual = _read(timing_path)
    base = _read(baseline_path)
    failures: list[str] = []
    warnings: list[str] = []
    ae = _environment()
    be = base.get("environment", {})
    if ae != be:
        failures.append(
            f"environment mismatch: baseline={be} actual={ae}"
        )
    if actual["measurement"]["mode"] != base.get("mode"):
        failures.append(
            f"mode mismatch: baseline={base.get('mode')} actual={actual['measurement']['mode']}"
        )
    if actual.get("input_manifest_sha256") != base.get("input_manifest_sha256"):
        failures.append("input manifest hash changed; baseline is not comparable")

    stages = {s["stage"]: s for s in actual.get("stages", [])}
    checks: dict[str, Any] = {}
    for name in STAGES:
        if name not in stages:
            failures.append(f"missing stage: {name}")
            continue
        b = base["stages"][name]["duration_seconds"]
        a = stages[name]["duration_seconds"]
        ratio = (a - b) / b if b else 0.0
        status = "PASS"
        if ratio > FAIL_RATIO:
            status = "FAIL"
            failures.append(f"{name}: duration regression {ratio:+.1%}")
        elif ratio > WARN_RATIO:
            status = "WARN"
            warnings.append(f"{name}: duration regression {ratio:+.1%}")
        checks[name] = {
            "baseline_seconds": b,
            "actual_seconds": a,
            "ratio": round(ratio, 4),
            "status": status,
        }

    rss_baseline = base.get("process_peak_rss_mb")
    rss_actual = actual.get("process_peak_rss_mb")
    if rss_baseline and rss_actual:
        if rss_actual > rss_baseline * RSS_BUDGET_FACTOR:
            failures.append(
                f"peak RSS exceeded budget: {rss_actual} MB > "
                f"{rss_baseline * RSS_BUDGET_FACTOR:.1f} MB"
            )

    result = {
        "status": "FAIL" if failures else ("WARN" if warnings else "PASS"),
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
        "baseline_label": base.get("label"),
        "actual_peak_rss_mb": rss_actual,
        "baseline_peak_rss_mb": rss_baseline,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--timing", required=True)
    f.add_argument("--output", required=True)
    f.add_argument("--label", default="reference")
    c = sub.add_parser("check")
    c.add_argument("--timing", required=True)
    c.add_argument("--baseline", required=True)
    c.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(Path(args.timing), Path(args.output), label=args.label)
    else:
        result = check(Path(args.timing), Path(args.baseline), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
