"""Aggregate real PFC, integrity, browser and performance evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from packaging import materialize_output_contract


def _read(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _gate(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"name": name, "status": status, "evidence": evidence}


def finalize_acceptance(
    result_root: Path,
    *,
    pfc_result: Path,
    capture_validation: Path | None,
    payload_integrity: Path,
    browser_acceptance: Path,
    force_report: Path | None = None,
    console_run: Path | None = None,
    benchmark: Path | None = None,
    cleanup_plan: Path | None = None,
) -> dict[str, Any]:
    """Mark PASS only when every mandatory runtime gate has real evidence."""
    result_root = result_root.resolve()
    pfc = _read(pfc_result) or {}
    execution = _read(console_run)
    validation = _read(capture_validation) or (execution or {}).get("validation") or {}
    payload = _read(payload_integrity) or {}
    browser = _read(browser_acceptance) or {}
    performance = _read(benchmark)
    cleanup = _read(cleanup_plan)

    engine = pfc.get("engine") or {}
    pfc_pass = (
        pfc.get("status") == "COMPLETE"
        and pfc.get("data_boundary") == "REAL_PFC"
        and str(engine.get("runtime_mode", "")).upper() == "CONSOLE"
    )
    capture_pass = validation.get("status") == "PASS"
    payload_pass = payload.get("status") == "PASS"
    browser_pass = bool(browser.get("pass"))
    checks = [
        _gate("PFC CONSOLE EXECUTION", "PASS" if pfc_pass else "FAIL", str(pfc_result)),
        _gate(
            "CAPTURE INTEGRITY",
            "PASS" if capture_pass else "FAIL",
            str(capture_validation) if capture_validation else str(console_run),
        ),
        _gate("PAYLOAD INTEGRITY", "PASS" if payload_pass else "FAIL", str(payload_integrity)),
        _gate("BROWSER INTERACTION", "PASS" if browser_pass else "FAIL", str(browser_acceptance)),
        _gate(
            "FORCE REPORT",
            "GENERATED" if force_report and force_report.is_file() else "NOT_GENERATED",
            str(force_report) if force_report else "not supplied",
        ),
        _gate(
            "PERFORMANCE MEASUREMENT",
            "GENERATED" if performance else "NOT_GENERATED",
            str(benchmark) if benchmark else "not supplied",
        ),
        _gate(
            "CLEANUP PLAN",
            "GENERATED" if cleanup else "NOT_GENERATED",
            str(cleanup_plan) if cleanup_plan else "not supplied",
        ),
    ]
    mandatory_pass = all((pfc_pass, capture_pass, payload_pass, browser_pass))
    verification = {
        "status": "PASS" if mandatory_pass else "FAIL",
        "verified_utc": (
            browser.get("verified_utc")
            or validation.get("verified_utc")
            or pfc.get("ended_utc")
        ),
        "official_execution_mode": "CONSOLE",
        "checks": checks,
        "console_run": execution,
        "pfc_result": {
            "path": str(pfc_result),
            "status": pfc.get("status"),
            "engine": engine,
            "run_id": pfc.get("run_id"),
            "frame_count": (pfc.get("capture") or {}).get("frame_count"),
            "mechanical_time_run": (pfc.get("capture") or {}).get("mechanical_time_run"),
        },
        "capture_integrity": validation,
        "payload_integrity": payload,
        "browser_acceptance": browser,
        "benchmark": performance,
        "cleanup": cleanup,
    }
    metadata = result_root / "07_metadata"
    _dump(metadata / "verification_report.json", verification)

    report_path = result_root / "report" / "experiment_report.md"
    if report_path.is_file():
        current = report_path.read_text(encoding="utf-8").rstrip()
        current += (
            "\n\n## Final acceptance\n\n"
            f"- Status: `{verification['status']}`\n"
            "- Execution: independent PFC Console process\n"
            "- Evidence: `07_metadata/verification_report.json`\n"
            "- Browser and payload gates are reported separately from generation.\n"
        )
        report_path.write_text(current + "\n", encoding="utf-8", newline="\n")

    output_index = materialize_output_contract(
        result_root,
        title=result_root.name,
        data_boundary="REAL_PFC",
    )
    output_index["verification"] = {
        "status": verification["status"],
        "checks": checks,
        "evidence_file": "07_metadata/verification_report.json",
    }
    _dump(metadata / "output_index.json", output_index)
    contract_path = metadata / "output_contract.json"
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["verification"] = verification["status"]
        for item in contract.get("items", []):
            if item.get("id") == "offline_viewer":
                item["verification"] = verification["status"]
        contract["verified"] = [
            item["name"] for item in checks if item.get("status") == "PASS"
        ]
        contract["unverified"] = [
            item["name"] for item in checks if item.get("status") != "PASS"
        ]
        _dump(contract_path, contract)

    console_lines = [
        "# Console Acceptance Report",
        "",
        f"- Overall: `{verification['status']}`",
        f"- Execution mode: `CONSOLE`",
        f"- Engine: `{engine.get('executable')}`",
        f"- Run ID: `{pfc.get('run_id')}`",
        f"- Frames: `{(pfc.get('capture') or {}).get('frame_count')}`",
        f"- Mechanical time run: `{(pfc.get('capture') or {}).get('mechanical_time_run')}` s",
        "",
    ]
    if execution:
        console_lines.extend(
            [
                f"- Transport: `{execution.get('transport')}`",
                f"- Console PID: `{execution.get('pid') or (execution.get('runtime') or {}).get('pid')}`",
                f"- Task ID: `{execution.get('task_id')}`",
                f"- Task status: `{execution.get('task_status')}`",
                "",
            ]
        )
    console_lines.extend(
        [
            "## Dynamic entity evidence",
            "",
            f"- Added Ball IDs: `{validation.get('added_ball_ids')}`",
            f"- Removed Ball IDs: `{validation.get('removed_ball_ids')}`",
            "",
        ]
    )
    (metadata / "CONSOLE_ACCEPTANCE.md").write_text(
        "\n".join(console_lines), encoding="utf-8", newline="\n"
    )

    integrity_lines = [
        "# Data Integrity Report",
        "",
        f"- Upstream capture validation referenced read-only: `{validation.get('status')}`",
        f"- Frame count: `{validation.get('frames')}`",
        f"- Cycle range: `{validation.get('cycle_start')}..{validation.get('cycle_end')}`",
        f"- Strict Cycle increase: `{validation.get('strictly_increasing_cycles')}`",
        f"- Strict mechanical-time increase: `{validation.get('strictly_increasing_time')}`",
        f"- All Ball values finite: `{validation.get('all_ball_values_finite')}`",
        f"- Hash errors: `{validation.get('hash_errors')}`",
        f"- Payload integrity: `{payload.get('status')}`",
        f"- Viewer frames: `{sum(int(case.get('viewer_frames', 0)) for case in payload.get('cases', []))}`",
        "",
        "Raw capture, quality evidence and standardized arrays remain owned by pfc-headless and were not modified by scientific post-processing.",
        "",
    ]
    (metadata / "DATA_INTEGRITY_REPORT.md").write_text(
        "\n".join(integrity_lines), encoding="utf-8", newline="\n"
    )

    browser_lines = [
        "# Browser Acceptance Report",
        "",
        f"- Result: `{'PASS' if browser_pass else 'FAIL'}`",
        f"- Browser: `{browser.get('browser')}`",
        f"- Failures: `{browser.get('failures')}`",
        f"- External requests: `{browser.get('externalRequests')}`",
        f"- Timeline frame: `{(browser.get('middle') or {}).get('frameIndex')}`",
        f"- Scene-click Ball ID: `{browser.get('sceneClickSelected')}`",
        f"- PNG export length: `{(browser.get('exports') or {}).get('pngLength')}`",
        f"- SVG exports: `{(browser.get('exports') or {}).get('svgCount')}`",
        f"- Case switch: `{browser.get('caseSwitchStatus')}`",
        "",
    ]
    (metadata / "BROWSER_ACCEPTANCE_REPORT.md").write_text(
        "\n".join(browser_lines), encoding="utf-8", newline="\n"
    )

    cleanup_lines = [
        "# Security Cleanup Report",
        "",
        "- Cleanup tool defaults to dry-run.",
        "- Apply mode requires the exact `CLEAN_INTERMEDIATE` token.",
        "- The pfc-headless standardized contract is rejected as a cleanup root.",
        "- Local analysis, Viewer, publication figures, metadata and reports are protected.",
        "- PFC source/save suffixes are protected recursively.",
        "",
        f"- Cleanup plan evidence: `{cleanup_plan}`",
        f"- Candidates: `{len((cleanup or {}).get('accepted', []))}`",
        f"- Skipped/protected: `{len((cleanup or {}).get('skipped', []))}`",
        "",
    ]
    (metadata / "SECURITY_CLEANUP_REPORT.md").write_text(
        "\n".join(cleanup_lines), encoding="utf-8", newline="\n"
    )
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--pfc-result", required=True)
    parser.add_argument("--capture-validation")
    parser.add_argument("--payload-integrity", required=True)
    parser.add_argument("--browser-acceptance", required=True)
    parser.add_argument("--force-report")
    parser.add_argument("--console-run")
    parser.add_argument("--benchmark")
    parser.add_argument("--cleanup-plan")
    args = parser.parse_args()
    result = finalize_acceptance(
        Path(args.result_root),
        pfc_result=Path(args.pfc_result),
        capture_validation=(
            Path(args.capture_validation) if args.capture_validation else None
        ),
        payload_integrity=Path(args.payload_integrity),
        browser_acceptance=Path(args.browser_acceptance),
        force_report=Path(args.force_report) if args.force_report else None,
        console_run=Path(args.console_run) if args.console_run else None,
        benchmark=Path(args.benchmark) if args.benchmark else None,
        cleanup_plan=Path(args.cleanup_plan) if args.cleanup_plan else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
