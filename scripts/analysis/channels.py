"""Physical-variable registry.

Names alone are not sufficient to identify a physical History.  ``classify_history``
therefore only classifies explicit, user-declared meanings; unknown names stay
unknown and cannot become stress or strain by convention.
"""
from __future__ import annotations

from typing import Any

CHANNEL_REGISTRY: dict[str, dict[str, Any]] = {
    "ball.position": {
        "entity": "ball",
        "unit": "m",
        "requirements": ["Ball ID", "XYZ"],
        "derived": False,
    },
    "ball.radius": {
        "entity": "ball",
        "unit": "m",
        "requirements": ["Ball radius or observed size"],
        "derived": False,
    },
    "ball.contact_force": {
        "entity": "ball",
        "unit": "N",
        "requirements": ["declared per-Ball contact-force magnitude"],
        "derived": False,
    },
    "ball.orientation": {
        "entity": "ball",
        "unit": "degree",
        "requirements": ["declared per-Ball orientation angle"],
        "derived": False,
    },
    "ball.local_strain": {
        "entity": "ball",
        "unit": "1",
        "requirements": ["declared per-Ball local strain"],
        "derived": False,
    },
    "ball.velocity": {
        "entity": "ball",
        "unit": "m/s",
        "requirements": ["consecutive same-ID positions", "non-zero time interval"],
        "derived": True,
    },
    "ball.acceleration": {
        "entity": "ball",
        "unit": "m/s^2",
        "requirements": ["at least three same-ID positions", "two time intervals"],
        "derived": True,
    },
    "wall.vertex_position": {
        "entity": "wall",
        "unit": "m",
        "requirements": ["Wall ID", "vertex ID", "XYZ"],
        "derived": False,
    },
    "contact.network": {
        "entity": "contact",
        "unit": None,
        "requirements": ["contact IDs", "endpoint Ball IDs", "same-Cycle state"],
        "derived": False,
    },
    "contact.force": {
        "entity": "contact",
        "unit": "N",
        "requirements": ["contact IDs", "normal/tangential force vectors"],
        "derived": False,
    },
    "bond.break_event": {
        "entity": "bond",
        "unit": "event",
        "requirements": ["bond/contact ID", "break Cycle", "break mode"],
        "derived": False,
    },
    "bond.force": {
        "entity": "bond",
        "unit": "N",
        "requirements": ["bond IDs", "force vector or declared scalar"],
        "derived": False,
    },
    "fracture.event": {
        "entity": "fracture",
        "unit": "event",
        "requirements": ["event ID", "Cycle", "time", "mode"],
        "derived": False,
    },
    "fracture.orientation": {
        "entity": "fracture",
        "unit": "degree",
        "requirements": ["captured normal or dip/dip-direction"],
        "derived": False,
    },
    "sample.axial_strain": {
        "entity": "sample",
        "unit": "1",
        "requirements": ["initial height", "same-frame platen distance"],
        "derived": True,
    },
    "sample.axial_stress": {
        "entity": "sample",
        "unit": "Pa",
        "requirements": ["platen contact forces", "initial cross-section area"],
        "derived": True,
    },
}

SEMANTIC_DETAILS = {
    "ball.position": {
        "meaning": "Ball centroid position in real model coordinates",
        "dimensions": ["frame", "ball", "xyz"],
        "color_token": "slate",
        "display_unit": "m",
    },
    "ball.radius": {
        "meaning": "Captured or first-observed Ball radius",
        "dimensions": ["frame", "ball"],
        "color_token": "tan",
        "display_unit": "m",
    },
    "ball.contact_force": {
        "meaning": "Declared per-Ball contact-force magnitude (MOCK extension channel)",
        "dimensions": ["frame", "ball"],
        "color_token": "tan",
        "display_unit": "N",
    },
    "ball.orientation": {
        "meaning": "Declared per-Ball orientation angle (MOCK extension channel)",
        "dimensions": ["frame", "ball", "angle"],
        "color_token": "slate",
        "display_unit": "degree",
    },
    "ball.local_strain": {
        "meaning": "Declared per-Ball local axial strain (MOCK extension channel)",
        "dimensions": ["frame", "ball"],
        "color_token": "primary",
        "display_unit": "1",
    },
    "ball.velocity": {
        "meaning": "Finite-difference Ball velocity from real same-ID observations",
        "dimensions": ["frame", "ball", "xyz"],
        "color_token": "slate",
        "display_unit": "m/s",
    },
    "ball.acceleration": {
        "meaning": "Finite-difference Ball acceleration from real observations",
        "dimensions": ["frame", "ball", "xyz"],
        "color_token": "accent",
        "display_unit": "m/s^2",
    },
    "wall.vertex_position": {
        "meaning": "Captured Wall vertex position in real model coordinates",
        "dimensions": ["frame", "wall", "vertex", "xyz"],
        "color_token": "slate",
        "display_unit": "m",
    },
    "contact.network": {
        "meaning": "Contact ID and endpoint topology; unavailable in the preserved baseline",
        "dimensions": ["frame", "contact"],
        "color_token": "tan",
        "display_unit": None,
    },
    "contact.force": {
        "meaning": "Contact force vector; unavailable in the preserved baseline",
        "dimensions": ["frame", "contact", "xyz"],
        "color_token": "tan",
        "display_unit": "N",
    },
    "bond.break_event": {
        "meaning": "Captured Bond break event; unavailable unless explicitly captured",
        "dimensions": ["event"],
        "color_token": "fracture",
        "display_unit": "event",
    },
    "bond.force": {
        "meaning": "Bond force with a declared vector or scalar basis",
        "dimensions": ["frame", "bond"],
        "color_token": "tan",
        "display_unit": "N",
    },
    "fracture.event": {
        "meaning": "Captured Bond-break or fracture event",
        "dimensions": ["event"],
        "color_token": "fracture",
        "display_unit": "event",
    },
    "fracture.orientation": {
        "meaning": "Fracture direction derived from a captured normal",
        "dimensions": ["event", "angle"],
        "color_token": "fracture",
        "display_unit": "degree",
    },
    "sample.axial_strain": {
        "meaning": "Compression-positive engineering axial strain",
        "dimensions": ["frame"],
        "color_token": "slate",
        "display_unit": "1",
    },
    "sample.axial_stress": {
        "meaning": "Nominal engineering stress with a declared force and area basis",
        "dimensions": ["frame"],
        "color_token": "primary",
        "display_unit": "Pa",
    },
}
for _channel_id, _details in SEMANTIC_DETAILS.items():
    if _channel_id in CHANNEL_REGISTRY:
        CHANNEL_REGISTRY[_channel_id].update(_details)


def channel_definition(variable: str) -> dict[str, Any] | None:
    return CHANNEL_REGISTRY.get(variable)


def classify_history(
    name: str,
    declared_meaning: str | None = None,
    declared_unit: str | None = None,
) -> dict[str, Any]:
    """Return a conservative History classification.

    A caller must provide the meaning from the model or experiment metadata.
    Matching words in a name alone is explicitly insufficient.
    """
    if not declared_meaning:
        return {
            "name": name,
            "meaning": None,
            "physical_quantity": None,
            "unit": None,
            "classification": "UNCONFIRMED",
            "reason": "No declared History meaning was supplied.",
        }
    return {
        "name": name,
        "meaning": declared_meaning,
        "physical_quantity": declared_meaning,
        "unit": declared_unit,
        "classification": "DECLARED",
        "reason": "Classification uses explicit experiment metadata, not the History name.",
    }
