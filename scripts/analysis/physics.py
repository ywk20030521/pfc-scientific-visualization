"""Physics-aware context inference for chart decision records.

The chart intelligence module gates candidates on data availability, but the
scientific value of a chart depends on the physical question of the
experiment.  This module infers a *declared or name-derived* physics context
and computes redundancy between selected charts.  It never invents measured
data and never changes which charts are generated; it only records intent,
coverage and duplication so a reviewer can audit the decisions.
"""
from __future__ import annotations

import re
from typing import Any


# Ordered: the first matching pattern wins.  Keys are stable experiment types.
_PHYSICS_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("balls_in_box", "granular_packing", "堆积结构、粒径分布与孔隙特征"),
    ("bonded_assembly", "bonded_assembly", "键结网络与结构连通性"),
    ("restitution", "collision_restitution", "碰撞前后速度与恢复系数、能量损失"),
    ("measure_porosity", "porosity_measurement", "孔隙率结果与测量区域一致性"),
    ("wave_propagation", "wave_propagation", "波前时序、空间响应与衰减"),
    ("rock_ucs", "uniaxial_compression", "应力-应变响应、轴向变形与局部化"),
    ("fragmentation", "fracture_fragmentation", "裂纹起裂、扩展与破坏阶段"),
    ("hopper_discharge", "granular_discharge", "流动速度、流量时程与卸料区"),
    ("slip_on_fault", "fault_slip", "相对位移、剪切响应与滑移演化"),
    ("table_tennis", "projectile_collision", "运动轨迹、速度与反弹响应"),
]

# Which chart ids most directly answer each physics question.  Used only for
# a coverage score in the decision record, never to force chart generation.
_PREFERRED: dict[str, set[str]] = {
    "granular_packing": {"particle_size", "particle_density", "correlation"},
    "bonded_assembly": {"particle_density", "correlation", "motion"},
    "collision_restitution": {"speed_time", "motion", "acceleration_time"},
    "porosity_measurement": {"particle_size", "particle_density"},
    "wave_propagation": {"speed_time", "displacement_hist", "acceleration_time"},
    "uniaxial_compression": {"stress_strain", "stress_time", "displacement_hist"},
    "fracture_fragmentation": {"motion_cracks", "fracture_rose", "speed_time"},
    "granular_discharge": {"speed_time", "motion", "displacement_hist"},
    "fault_slip": {"displacement_hist", "speed_time", "correlation"},
    "projectile_collision": {"motion", "speed_time", "acceleration_time"},
}


def infer_physics_context(case: dict[str, Any]) -> dict[str, Any]:
    """Infer experiment type from an explicit declaration or case name."""
    declared = case.get("physics_context") or {}
    if isinstance(declared, dict) and declared.get("experiment_type"):
        return {
            "experiment_type": str(declared["experiment_type"]),
            "primary_process": str(declared.get("primary_process", "declared")),
            "research_questions": list(declared.get("research_questions", [])),
            "source": "declared_in_case_config",
        }
    name = " ".join(
        str(case.get(key) or "")
        for key in ("case_name", "run_id", "title", "label")
    ).lower()
    for slug, experiment, question in _PHYSICS_PATTERNS:
        if slug in name:
            return {
                "experiment_type": experiment,
                "primary_process": experiment,
                "research_questions": [question],
                "source": "inferred_from_case_name",
            }
    return {
        "experiment_type": "unspecified",
        "primary_process": "unspecified",
        "research_questions": [],
        "source": "not_inferred",
    }


def redundancy_analysis(charts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag chart pairs that express the same information via the same family.

    This is intentionally conservative: only charts of the same type whose
    source variables overlap are flagged.  Charts with different variables
    are kept even if the type is the same (e.g. two histograms of different
    physical quantities answer different questions).
    """
    findings: list[dict[str, Any]] = []
    for i, first in enumerate(charts):
        for second in charts[i + 1:]:
            if first.get("type") != second.get("type"):
                continue
            a = set(str(v) for v in (first.get("source_variables") or []))
            b = set(str(v) for v in (second.get("source_variables") or []))
            if not a or not b:
                continue
            overlap = a & b
            if len(overlap) / max(len(a | b), 1) >= 0.6:
                findings.append({
                    "chart_ids": [first.get("chart_id"), second.get("chart_id")],
                    "chart_type": first.get("type"),
                    "shared_variables": sorted(overlap),
                    "jaccard": round(len(overlap) / len(a | b), 3),
                    "recommendation": "review_for_merge_or_distinct_purpose",
                })
    return findings


def coverage_analysis(
    charts: list[dict[str, Any]], context: dict[str, Any]
) -> dict[str, Any]:
    preferred = _PREFERRED.get(context.get("experiment_type"), set())
    selected = {str(c.get("chart_id", "")).split(":")[-1] for c in charts}
    covered = sorted(preferred & selected)
    gaps = sorted(preferred - selected)
    return {
        "experiment_type": context.get("experiment_type"),
        "preferred_chart_ids": sorted(preferred),
        "covered": covered,
        "gaps": gaps,
        "coverage_ratio": round(len(covered) / len(preferred), 3) if preferred else None,
        "note": (
            "Gaps reflect missing data/derivation, not a defect, when the "
            "chart was explicitly rejected with a data-quality reason."
        ),
    }
