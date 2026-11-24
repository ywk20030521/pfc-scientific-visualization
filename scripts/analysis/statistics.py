"""Statistical helpers shared by analysis and chart selection."""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def finite_summary(values: Iterable[float]) -> dict[str, float | int | str]:
    array = np.asarray(list(values), dtype=np.float64)
    array = array[np.isfinite(array)]
    if not len(array):
        return {"status": "NOT_CAPTURED", "count": 0}
    return {
        "status": "GENERATED",
        "count": int(len(array)),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
        "median": float(np.median(array)),
    }


def bin_hellinger(left: Iterable[float], right: Iterable[float], bins: int = 24) -> float | None:
    """Return a distribution distance without aligning or interpolating times."""
    a = np.asarray(list(left), dtype=np.float64)
    b = np.asarray(list(right), dtype=np.float64)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    lo = min(float(a.min()), float(b.min()))
    hi = max(float(a.max()), float(b.max()))
    if hi <= lo:
        return 0.0
    ha, _ = np.histogram(a, bins=bins, range=(lo, hi), density=True)
    hb, _ = np.histogram(b, bins=bins, range=(lo, hi), density=True)
    width = (hi - lo) / bins
    pa = ha * width
    pb = hb * width
    pa /= pa.sum() or 1.0
    pb /= pb.sum() or 1.0
    return float(math.sqrt(max(0.0, 1.0 - float(np.sqrt(pa * pb).sum()))))
