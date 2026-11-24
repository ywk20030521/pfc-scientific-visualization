"""Static capability inspection for real PFC2D/PFC3D standardized data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _case_path(root: Path, case: dict[str, Any]) -> Path:
    path = Path(case["arrays_path"])
    return path if path.is_absolute() else root / path


def _finite(array: np.ndarray) -> int:
    return int(np.isfinite(array).sum()) if array.size else 0


def inspect_experiment_capabilities(
    experiment_root: Path,
    analysis_root: Path | None = None,
) -> dict[str, Any]:
    experiment_root = experiment_root.resolve()
    analysis_root = analysis_root.resolve() if analysis_root else None
    experiment = json.loads(
        (experiment_root / "experiment.json").read_text(encoding="utf-8")
    )
    cases = {}
    common: dict[str, str] | None = None
    for case in experiment["cases"]:
        case_id = int(case["case_id"])
        with np.load(_case_path(experiment_root, case), allow_pickle=False) as arrays:
            fracture = "fracture_event_id" in arrays.files and len(arrays["fracture_event_id"]) > 0
            contact_keys = sorted(key for key in arrays.files if key.startswith("contact_"))
            bond_keys = sorted(key for key in arrays.files if key.startswith("bond_"))
            ball_xyz = arrays["ball_xyz"] if "ball_xyz" in arrays.files else np.asarray([])
            wall_xyz = (
                arrays["wall_vertex_xyz"]
                if "wall_vertex_xyz" in arrays.files
                else np.asarray([])
            )
            capabilities = {
                "ball_position": "SUPPORTED" if _finite(ball_xyz) else "NOT_CAPTURED",
                "ball_radius": "SUPPORTED" if "ball_radius" in arrays.files else "NOT_CAPTURED",
                "wall_geometry": "SUPPORTED" if _finite(wall_xyz) else "NOT_CAPTURED",
                "fracture_event": "SUPPORTED" if fracture else "NOT_CAPTURED",
                "contact_network": "SUPPORTED" if contact_keys else "NOT_CAPTURED",
                "bond_network": "SUPPORTED" if bond_keys else "NOT_CAPTURED",
                "particle_displacement": "NOT_VERIFIED",
                "particle_speed": "NOT_VERIFIED",
                "particle_acceleration": "NOT_VERIFIED",
                "nominal_stress": "NOT_VERIFIED",
                "line_load": "NOT_VERIFIED",
            }
        if analysis_root:
            analysis_path = (
                analysis_root / f"case_{case_id}" / "analysis_arrays.npz"
            )
            if analysis_path.is_file():
                with np.load(analysis_path, allow_pickle=False) as analysis:
                    checks = {
                        "particle_displacement": "ball_displacement_magnitude",
                        "particle_speed": "ball_speed_m_s",
                        "particle_acceleration": "ball_acceleration_xyz",
                        "nominal_stress": "axial_stress_pa",
                        "line_load": "axial_load_per_unit_thickness_n_m",
                    }
                    for capability, key in checks.items():
                        if key in analysis.files:
                            capabilities[capability] = (
                                "SUPPORTED" if _finite(analysis[key]) else "INVALID"
                            )
                        else:
                            capabilities[capability] = "NOT_CAPTURED"
        cases[str(case_id)] = {
            "status": "GENERATED",
            "dimension": int(case["dimension"]),
            "capabilities": capabilities,
        }
        if common is None:
            common = dict(capabilities)
        else:
            for key, value in capabilities.items():
                if common[key] != value:
                    common[key] = "MIXED"
    return {
        "status": "GENERATED",
        "policy": (
            "Capabilities are inspected per Case. A missing optional field in one "
            "Case does not prevent other Cases from being processed."
        ),
        "cases": cases,
        "common": common or {},
        "runtime_verification": "NOT_VERIFIED",
    }
