"""Emit a stable analysis-findings contract from Visualization outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT = "pfc.analysis-findings@1.0.0"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _display_path(path: Path, project_root: Path | None) -> str:
    if project_root is not None:
        try:
            return path.relative_to(project_root).as_posix()
        except ValueError:
            pass
    return str(path.resolve())


def _portable_artifacts(
    paths: list[Path],
    *,
    analysis_root: Path,
    project_root: Path,
    feedback_id: str,
) -> tuple[list[str], dict[str, str]]:
    """Copy referenced evidence inside the headless project and return paths.

    pfc-headless validates feedback artifacts against its own managed roots,
    while this Skill intentionally keeps analysis output outside that root.
    Copying the small, referenced JSON evidence into the feedback payload
    directory reconciles both contracts without weakening either boundary.
    """
    target_root = (
        project_root / "analysis" / "findings" / feedback_id / "artifacts"
    )
    hashes: dict[str, str] = {}
    display: list[str] = []
    for path in paths:
        try:
            relative = path.relative_to(analysis_root)
        except ValueError:
            raise ValueError(
                f"Feedback artifact {path} is outside the analysis root {analysis_root}"
            )
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        hashes[destination.relative_to(project_root).as_posix()] = digest
        display.append(destination.relative_to(project_root).as_posix())
    return display, hashes


def build_findings(
    analysis_root: Path,
    *,
    project_root: Path | None = None,
    copy_artifacts: bool | None = None,
) -> dict[str, Any]:
    analysis_root = analysis_root.resolve()
    analysis_path = analysis_root / "03_analysis" / "analysis.json"
    capabilities_path = (
        analysis_root / "07_metadata" / "experiment_capabilities.json"
    )
    source_contract_path = analysis_root / "07_metadata" / "source_contract.json"
    for path in (analysis_path, capabilities_path, source_contract_path):
        if not path.is_file():
            raise FileNotFoundError(f"Visualization artifact is missing: {path}")
    analysis = _read(analysis_path)
    capabilities = _read(capabilities_path)
    source_contract = _read(source_contract_path)
    source_root = Path(str(source_contract["root"]))
    experiment_path = source_root / "experiment.json"
    experiment = _read(experiment_path) if experiment_path.is_file() else {"cases": []}

    unavailable: list[str] = []
    for case in experiment.get("cases", []):
        for channel in case.get("channels", []):
            status = str(channel.get("status") or channel.get("source") or "")
            if status in {"NOT_CAPTURED", "NOT_SUPPORTED", "INVALID", "UNKNOWN"}:
                channel_id = str(channel.get("id") or "")
                if channel_id and channel_id not in unavailable:
                    unavailable.append(channel_id)

    artifact_paths = [analysis_path, capabilities_path, source_contract_path]
    experiment_id = str(
        source_contract.get("experiment_id") or analysis_root.name
    )
    feedback_id = f"feedback_{experiment_id}"
    artifact_hashes: dict[str, str] = {}
    should_copy = copy_artifacts
    if should_copy is None:
        should_copy = bool(
            project_root is not None
            and any(
                _display_path(path, project_root).startswith("/")
                or ":" in _display_path(path, project_root).split("/")[0]
                for path in artifact_paths
            )
        )
    if should_copy:
        if project_root is None:
            raise ValueError("--project-root is required when copying feedback artifacts")
        referenced, artifact_hashes = _portable_artifacts(
            artifact_paths,
            analysis_root=analysis_root,
            project_root=project_root.resolve(),
            feedback_id=feedback_id,
        )
    else:
        referenced = [
            _display_path(path, project_root) for path in artifact_paths
        ]
    findings = []
    for case in analysis.get("cases", []):
        case_id = int(case.get("case_id", -1))
        generated = [
            str(item.get("id"))
            for item in case.get("channels", [])
            if item.get("status") == "GENERATED"
        ]
        findings.append(
            {
                "finding_id": f"analysis_case_{case_id}",
                "statement": (
                    f"Case {case_id} analysis generated {len(generated)} "
                    "documented channels without fabricating unavailable data."
                ),
                "evidence": referenced,
            }
        )
    if unavailable:
        findings.append(
            {
                "finding_id": "missing_channel_evidence",
                "statement": (
                    "Unavailable source channels remain explicitly marked and "
                    "are not substituted with inferred values."
                ),
                "evidence": referenced,
            }
        )

    channels = [
        {"id": "ball.position", "enabled": True, "required": True},
        {"id": "ball.radius", "enabled": True, "required": True},
        {"id": "wall.geometry", "enabled": True, "required": True},
    ]
    events: list[str] = []
    if any(item.startswith("contact_") for item in unavailable):
        for channel_id in ("contact.id", "contact.endpoints", "contact.force"):
            channels.append(
                {"id": channel_id, "enabled": True, "required": False}
            )
    if any(item.startswith("fracture_") for item in unavailable):
        channels.append(
            {"id": "fracture.event", "enabled": True, "required": False}
        )
        events.append("fracture")
    sampling = {
        "mode": "event" if events else "cycle",
        "interval": 1,
        "capture_contacts": any(
            item.startswith("contact_") for item in unavailable
        ),
        "collection_plan": {
            "plan_version": "1.0.0",
            "mode": "event" if events else "cycle",
            "interval": 1,
            "channels": channels,
            "events": events,
            "dimension": int(
                next(iter(capabilities.get("cases", {}).values()), {}).get(
                    "dimension", 2
                )
            ),
        },
    }
    payload = {
        "schema_version": "1.0.0",
        "contract": CONTRACT,
        "feedback_id": f"feedback_{experiment_id}",
        "run_id": experiment_id,
        "source": "pfc-scientific-visualization",
        "referenced_artifacts": referenced,
        "findings": findings,
        "missing_data": unavailable,
        "recommended_sampling": sampling,
        "recommended_parameters": {},
        "recommended_actions": (
            [
                "Rerun with the recommended collection plan and preserve the "
                "new Run as a separate immutable attempt."
            ]
            if unavailable
            else []
        ),
        "status": "RECEIVED",
        "attempts": [],
        "active_attempt_run_id": None,
        "review": None,
        "produced_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_contract": {
            "manifest_sha256": str(source_contract["manifest_sha256"]),
            "experiment_id": experiment_id,
            "artifact_sha256": artifact_hashes,
        },
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root")
    parser.add_argument(
        "--copy-artifacts",
        action="store_true",
        default=None,
        help="Copy referenced evidence into the headless project (auto by default when outside project root)",
    )
    parser.add_argument(
        "--no-copy-artifacts",
        dest="copy_artifacts",
        action="store_false",
        help="Keep referenced artifact paths as-is",
    )
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else None
    payload = build_findings(
        Path(args.analysis_root),
        project_root=project_root,
        copy_artifacts=args.copy_artifacts,
    )
    output = Path(args.output).resolve()
    _write(output, payload)
    print(
        json.dumps(
            {
                "status": "GENERATED",
                "contract": CONTRACT,
                "output": str(output),
                "run_id": payload["run_id"],
                "missing_data": payload["missing_data"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
