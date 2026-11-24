"""Display-only number formatting for axes, tooltips and statistical labels."""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _round_significant(value: float, digits: int) -> str:
    if value == 0:
        return "0"
    exponent = math.floor(math.log10(abs(value)))
    decimal_places = max(0, int(digits) - exponent - 1)
    rounded = Decimal(str(value)).quantize(
        Decimal(1).scaleb(-decimal_places), rounding=ROUND_HALF_UP
    )
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def choose_scientific(value: float, *, low: float = 1.0e-3, high: float = 1.0e5) -> bool:
    magnitude = abs(value)
    return magnitude != 0 and (magnitude < low or magnitude >= high)


def format_number(
    value: Any,
    *,
    significant_digits: int = 4,
    decimals: int | None = None,
    scientific: bool | None = None,
) -> str:
    number = _finite(value)
    if number is None:
        return "—"
    if scientific is None:
        scientific = choose_scientific(number)
    if scientific:
        rendered = f"{number:.{max(1, significant_digits - 1)}e}"
        mantissa, exponent = rendered.split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa} × 10{str(int(exponent)).translate(SUPERSCRIPT)}"
    if decimals is not None:
        quantum = Decimal(1).scaleb(-max(0, int(decimals)))
        text = format(
            Decimal(str(number)).quantize(quantum, rounding=ROUND_HALF_UP), "f"
        )
        if decimals <= 0:
            return text
        return text
    return _round_significant(number, significant_digits)


def formatting_spec(
    unit: str | None,
    values: Iterable[Any] = (),
    *,
    significant_digits: int = 4,
    tooltip_digits: int = 8,
) -> dict[str, Any]:
    finite = [abs(float(value)) for value in values if _finite(value) is not None]
    nonzero = [value for value in finite if value > 0]
    smallest = min(nonzero) if nonzero else None
    largest = max(nonzero) if nonzero else None
    scientific = bool(
        smallest is not None
        and (smallest < 1.0e-3 or (largest is not None and largest >= 1.0e5))
    )
    decimals = None
    axis_exponent = None
    axis_scale = 1.0
    axis_scale_label = None
    if not scientific and smallest is not None:
        magnitude = math.floor(math.log10(smallest))
        decimals = max(0, min(8, significant_digits - magnitude - 1))
    elif scientific and largest is not None:
        axis_exponent = math.floor(math.log10(largest))
        axis_scale = 10.0**axis_exponent
        axis_scale_label = (
            "× 10"
            + str(axis_exponent).translate(SUPERSCRIPT)
        )
        decimals = max(0, min(8, significant_digits - 1))
    return {
        "method": "AUTO_SCIENTIFIC_OR_DECIMAL_DISPLAY_ONLY",
        "unit": unit,
        "scientific": scientific,
        "axis_notation": (
            "SCIENTIFIC_SHARED_EXPONENT" if scientific else "DECIMAL"
        ),
        "axis_exponent": axis_exponent,
        "axis_scale": axis_scale,
        "axis_scale_label": axis_scale_label,
        "significant_digits": int(significant_digits),
        "decimals": decimals,
        "axis_formatter": "number",
        "tooltip_digits": int(tooltip_digits),
        "missing_text": "—",
        "rule": (
            "Axis values prioritize readability; tooltips retain higher precision. "
            "Formatted strings never replace analysis values."
        ),
    }


def format_display_series(
    values: Iterable[Any],
    *,
    unit: str | None,
    significant_digits: int = 4,
    tooltip_digits: int = 8,
) -> dict[str, Any]:
    source = [None if _finite(value) is None else float(value) for value in values]
    spec = formatting_spec(
        unit,
        source,
        significant_digits=significant_digits,
        tooltip_digits=tooltip_digits,
    )
    display = [
        format_number(
            value,
            significant_digits=significant_digits,
            decimals=spec["decimals"],
            scientific=spec["scientific"],
        )
        for value in source
    ]
    tooltip = [
        format_number(
            value,
            significant_digits=tooltip_digits,
            scientific=spec["scientific"],
        )
        for value in source
    ]
    return {
        "status": "GENERATED",
        "unit": unit,
        "values": display,
        "tooltip_values": tooltip,
        "formatting": spec,
    }
