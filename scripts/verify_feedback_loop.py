"""Verify the analysis → findings → headless feedback loop end to end.

Uses an isolated copy of a headless project; never modifies the source project
or its immutable Run artifacts. Proves:
  1. findings can be emitted with portable artifact hashes
  2. headless ingest/approve/prepare-run accepts them
  3. the new Run ID differs from the source Run
  4. the source Run files remain byte-identical
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr[-1200:]}")
    return json.loads(result.stdout)


def verify_loop(
    *,
    source_project: Path,
    analysis_root: Path,
    run_id: str,
    new_run_id: str,
    work_root: Path,
    headless_scripts: Path,
    viz_scripts: Path,
) -> dict[str, Any]:
    source_project = source_project.resolve()
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    run_source = source_project / "runs" / run_id
    delivery_source = source_project / "deliveries" / run_id
    if not run_source.is_dir() or not delivery_source.is_dir():
        raise FileNotFoundError(f"Run {run_id} missing in {source_project}")

    # Isolated copy with only what feedback ingest needs.
    shutil.copy2(source_project / "project.json", work_root / "project.json")
    project = json.loads((work_root / "project.json").read_text(encoding="utf-8"))
    project["project_root"] = str(work_root)
    (work_root / "project.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name in ("cases", "audit"):
        src = source_project / name
        if src.exists():
            shutil.copytree(src, work_root / name, dirs_exist_ok=True)
    (work_root / "runs").mkdir(exist_ok=True)
    (work_root / "deliveries").mkdir(exist_ok=True)
    (work_root / "analysis").mkdir(exist_ok=True)
    shutil.copytree(run_source, work_root / "runs" / run_id)
    shutil.copytree(delivery_source, work_root / "deliveries" / run_id)

    original_hash = _tree_hash(run_source)
    original_project_hash = original_hash
    findings_path = work_root / "findings.json"
    _run([
        sys.executable, str(viz_scripts / "emit_findings.py"),
        "--analysis-root", str(analysis_root),
        "--project-root", str(work_root),
        "--output", str(findings_path),
    ])
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    if findings.get("run_id") != run_id:
        raise AssertionError(f"findings run_id mismatch: {findings.get('run_id')}")

    headless_cli = headless_scripts / "headless.py"
    feedback_id = findings["feedback_id"]
    _run([
        sys.executable, str(headless_cli), "feedback", "ingest",
        "--project", str(work_root), "--file", str(findings_path),
    ])
    _run([
        sys.executable, str(headless_cli), "feedback", "approve",
        "--project", str(work_root), "--feedback-id", feedback_id,
        "--approved-by", "feedback-loop-verifier",
        "--rationale", "E2E verification of the analysis feedback contract",
    ])
    _run([
        sys.executable, str(headless_cli), "feedback", "prepare-run",
        "--project", str(work_root), "--feedback-id", feedback_id,
        "--run-id", new_run_id,
    ])

    feedback_path = work_root / "analysis" / "feedback" / f"{feedback_id}.json"
    state = json.loads(feedback_path.read_text(encoding="utf-8"))
    new_run = work_root / "runs" / new_run_id
    checks = {
        "findings_contract": findings.get("contract") == "pfc.analysis-findings@1.0.0",
        "source_run_id_match": findings.get("run_id") == run_id,
        "new_run_created": new_run.is_dir(),
        "new_run_differs": new_run_id != run_id,
        "feedback_active_attempt": state.get("active_attempt_run_id") == new_run_id,
        "feedback_status_proposed": state.get("status") == "PROPOSED",
        "attempt_recorded": any(
            item.get("run_id") == new_run_id for item in state.get("attempts", [])
        ),
        "source_run_unchanged": _tree_hash(work_root / "runs" / run_id) == original_hash,
        "original_project_unchanged": _tree_hash(run_source) == original_project_hash,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_run_id": run_id,
        "new_run_id": new_run_id,
        "feedback_id": feedback_id,
        "work_root": str(work_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project", required=True)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--new-run-id", default="run_feedback_loop_verify")
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--headless-scripts", required=True)
    parser.add_argument("--viz-scripts", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    result = verify_loop(
        source_project=Path(args.source_project),
        analysis_root=Path(args.analysis_root),
        run_id=args.run_id,
        new_run_id=args.new_run_id,
        work_root=Path(args.work_root),
        headless_scripts=Path(args.headless_scripts),
        viz_scripts=Path(args.viz_scripts),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
