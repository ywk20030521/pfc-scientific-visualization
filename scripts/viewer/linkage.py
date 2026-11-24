"""Explicit value assessment for 2D/3D linkage features."""
from __future__ import annotations

from typing import Any


def evaluate_linkage_decisions(
    *,
    contact_network: str = "NOT_CAPTURED",
    particle_metrics: tuple[str, ...] = ("displacement", "speed"),
) -> dict[str, Any]:
    metric_text = ", ".join(particle_metrics) if particle_metrics else "none"
    decisions = [
        {
            "id": "timeline_sync",
            "implemented": True,
            "status": "SUPPORTED",
            "scientific_need": "high",
            "interaction_value": "high",
            "technical_complexity": "low",
            "coordinate_conversion_complexity": "none",
            "data_sync_complexity": "low",
            "performance_cost": "low",
            "maintenance_cost": "low",
            "decision_reason": "All temporal views index the same real captured frame.",
        },
        {
            "id": "case_switch_sync",
            "implemented": True,
            "status": "SUPPORTED",
            "scientific_need": "high",
            "interaction_value": "high",
            "technical_complexity": "low",
            "coordinate_conversion_complexity": "none",
            "data_sync_complexity": "medium",
            "performance_cost": "low",
            "maintenance_cost": "low",
            "decision_reason": "Case changes reset selection, range and frame before loading new data.",
        },
        {
            "id": "particle_selection_attribute_panel",
            "implemented": True,
            "status": "PARTIAL",
            "scientific_need": "high",
            "interaction_value": "high",
            "technical_complexity": "medium",
            "coordinate_conversion_complexity": "none",
            "data_sync_complexity": "medium",
            "performance_cost": "low",
            "maintenance_cost": "medium",
            "decision_reason": (
                f"Implemented for real Ball IDs with these particle histories: {metric_text}; "
                "force and stress histories remain unavailable unless captured."
            ),
            "available_metrics": list(particle_metrics),
            "unavailable_metrics": ["contact_force", "particle_stress"],
        },
        {
            "id": "particle_3d_to_2d_projection",
            "implemented": False,
            "status": "NOT_IMPLEMENTED",
            "scientific_need": "medium",
            "interaction_value": "medium",
            "technical_complexity": "high",
            "coordinate_conversion_complexity": "medium",
            "data_sync_complexity": "high",
            "performance_cost": "medium",
            "maintenance_cost": "high",
            "decision_reason": (
                "The existing distribution view answers aggregate spatial questions; "
                "a projected particle marker would add synchronization complexity with "
                "limited additional evidence. Independent views are retained."
            ),
        },
        {
            "id": "crack_3d_to_2d_projection",
            "implemented": False,
            "status": "NOT_IMPLEMENTED",
            "scientific_need": "medium",
            "interaction_value": "medium",
            "technical_complexity": "high",
            "coordinate_conversion_complexity": "high",
            "data_sync_complexity": "high",
            "performance_cost": "medium",
            "maintenance_cost": "high",
            "decision_reason": (
                "Captured crack direction is already represented by a rose chart and "
                "3D lines; projection is only valuable for an explicit shared slice."
            ),
        },
        {
            "id": "camera_to_2d_view_sync",
            "implemented": False,
            "status": "NOT_IMPLEMENTED",
            "scientific_need": "low",
            "interaction_value": "low",
            "technical_complexity": "high",
            "coordinate_conversion_complexity": "high",
            "data_sync_complexity": "high",
            "performance_cost": "high",
            "maintenance_cost": "high",
            "decision_reason": "Camera rotation is exploratory navigation, not a shared physical state.",
        },
        {
            "id": "all_charts_bidirectional_3d",
            "implemented": False,
            "status": "NOT_IMPLEMENTED",
            "scientific_need": "low",
            "interaction_value": "low",
            "technical_complexity": "high",
            "coordinate_conversion_complexity": "medium",
            "data_sync_complexity": "high",
            "performance_cost": "high",
            "maintenance_cost": "high",
            "decision_reason": (
                "Many aggregate charts have no particle-level correspondence. Forcing "
                "bidirectional linkage would imply a mapping the data does not contain."
            ),
        },
    ]
    if contact_network == "SUPPORTED":
        decisions.append(
            {
                "id": "contact_network_scene_layer",
                "implemented": False,
                "status": "NOT_IMPLEMENTED",
                "scientific_need": "high",
                "interaction_value": "high",
                "technical_complexity": "medium",
                "coordinate_conversion_complexity": "low",
                "data_sync_complexity": "medium",
                "performance_cost": "medium",
                "maintenance_cost": "medium",
                "decision_reason": (
                    "Contact endpoints exist in this experiment, but this delivery has "
                    "not added a dedicated contact renderer or acceptance run."
                ),
            }
        )
    return {
        "status": "GENERATED",
        "verification": "NOT_VERIFIED",
        "shared_state": ["currentCase", "currentFrame", "currentCycle", "currentTime"],
        "policy": (
            "Shared time and Case state does not imply full bidirectional linkage. "
            "A view remains independent when it has no physical ID correspondence."
        ),
        "decisions": decisions,
    }
