"""Validate the read-only standardized-data contract produced by pfc-headless."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


CONTRACT_NAME = "pfc.standardized-experiment"
CONTRACT_VERSION = "1.0.0"


class StandardContractError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StandardContractError(
            f"Contract artifact escapes standardized root: {relative}"
        ) from exc
    return path


def verify_standard_contract(root: Path) -> dict[str, Any]:
    """Verify hashes and core array invariants without modifying the input."""
    root = root.resolve()
    manifest_path = root / "delivery_manifest.json"
    if not manifest_path.is_file():
        raise StandardContractError(
            "Missing delivery_manifest.json. Produce the input with "
            "pfc-headless/run_standardization.py."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = manifest.get("contract") or {}
    if contract.get("name") != CONTRACT_NAME:
        raise StandardContractError(
            f"Unsupported contract name: {contract.get('name')!r}"
        )
    if contract.get("version") != CONTRACT_VERSION:
        raise StandardContractError(
            f"Unsupported contract version: {contract.get('version')!r}"
        )
    if contract.get("immutable") is not True:
        raise StandardContractError("Standardized contract must be immutable")
    consumer_policy = manifest.get("consumer_policy") or {}
    if consumer_policy.get("read_only") is not True:
        raise StandardContractError("Contract does not declare read-only consumption")
    if consumer_policy.get("may_write_inside_contract") is not False:
        raise StandardContractError("Contract permits writes inside its root")

    experiment_record = manifest.get("experiment") or {}
    experiment_relative = experiment_record.get("path")
    if not experiment_relative:
        raise StandardContractError("Contract experiment path is missing")
    experiment_path = _inside(root, str(experiment_relative))
    if not experiment_path.is_file():
        raise StandardContractError("Contract experiment.json is missing")
    expected_experiment_hash = experiment_record.get("sha256")
    if sha256_file(experiment_path) != expected_experiment_hash:
        raise StandardContractError("experiment.json hash does not match the contract")

    for artifact in manifest.get("artifacts", []):
        path = _inside(root, str(artifact.get("path")))
        if not path.is_file():
            raise StandardContractError(f"Contract artifact is missing: {path}")
        if int(path.stat().st_size) != int(artifact.get("size_bytes", -1)):
            raise StandardContractError(f"Contract artifact size differs: {path}")
        if sha256_file(path) != artifact.get("sha256"):
            raise StandardContractError(f"Contract artifact hash differs: {path}")

    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment_id = experiment.get("experiment_id")
    if not experiment_id:
        raise StandardContractError("Standardized experiment has no experiment_id")
    if not experiment.get("cases"):
        raise StandardContractError("Standardized experiment has no Cases")
    contract_cases = {
        int(item["case_id"]): item for item in manifest.get("cases", [])
    }
    case_records = []
    for case in experiment["cases"]:
        case_id = int(case["case_id"])
        contract_case = contract_cases.get(case_id)
        if contract_case is None:
            raise StandardContractError(
                f"Case {case_id} is absent from the delivery manifest"
            )
        arrays_path = Path(case["arrays_path"])
        arrays_path = (
            arrays_path.resolve()
            if arrays_path.is_absolute()
            else (root / arrays_path).resolve()
        )
        try:
            arrays_path.relative_to(root)
        except ValueError as exc:
            raise StandardContractError(
                f"Case {case_id} arrays escape standardized root"
            ) from exc
        if not arrays_path.is_file():
            raise StandardContractError(
                f"Case {case_id} standardized arrays are missing"
            )
        if sha256_file(arrays_path) != contract_case.get("arrays_sha256"):
            raise StandardContractError(
                f"Case {case_id} standardized array hash differs from the contract"
            )
        with np.load(arrays_path, allow_pickle=False) as arrays:
            required = {
                "cycle",
                "mechanical_time_total",
                "frame_offsets",
                "ball_id",
                "ball_xyz",
                "ball_frame_index",
            }
            missing = sorted(required - set(arrays.files))
            if missing:
                raise StandardContractError(
                    f"Case {case_id} arrays are missing: {missing}"
                )
            frame_count = int(case["frame_count"])
            if len(arrays["cycle"]) != frame_count:
                raise StandardContractError(
                    f"Case {case_id} Cycle length does not match frame_count"
                )
            if len(arrays["frame_offsets"]) != frame_count + 1:
                raise StandardContractError(
                    f"Case {case_id} frame offsets do not match frame_count"
                )
            if int(arrays["frame_offsets"][-1]) != len(arrays["ball_id"]):
                raise StandardContractError(
                    f"Case {case_id} final Ball offset is inconsistent"
                )
        case_records.append(
            {
                "case_id": case_id,
                "arrays_path": arrays_path.relative_to(root).as_posix(),
                "arrays_sha256": contract_case["arrays_sha256"],
                "frame_count": int(case["frame_count"]),
            }
        )
    return {
        "status": "PASS",
        "root": str(root),
        "manifest": manifest,
        "manifest_sha256": sha256_file(manifest_path),
        "experiment": experiment,
        "cases": case_records,
        "contract": {
            "name": CONTRACT_NAME,
            "version": CONTRACT_VERSION,
            "read_only": True,
        },
    }
