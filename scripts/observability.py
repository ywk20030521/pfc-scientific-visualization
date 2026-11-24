"""Runtime stage timing and dual-memory measurement for the pipeline.

RSS is measured with ctypes/psapi on Windows (no third-party dependency);
tracemalloc tracks Python-object allocations only. The two are reported side
by side and must never be added together.
"""
from __future__ import annotations

import ctypes
import json
import platform
import sys
import time
import tracemalloc
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def rss_mb() -> float | None:
    """Current process RSS in MiB, or None when the platform API is absent."""
    if sys.platform != "win32":
        return None
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = _PMC()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.WorkingSetSize / 1048576, 3)
    except (OSError, AttributeError):
        return None


def peak_rss_mb() -> float | None:
    """Peak working set in MiB since process start, or None if unavailable."""
    if sys.platform != "win32":
        return None
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = _PMC()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.PeakWorkingSetSize / 1048576, 3)
    except (OSError, AttributeError):
        return None


def environment_record() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "rss_source": "ctypes/psapi GetProcessMemoryInfo" if sys.platform == "win32" else "unavailable",
        "python_alloc_source": "tracemalloc",
    }


def _directory_bytes(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        if path.is_file():
            total += path.stat().st_size
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
    return total


class StageRecorder:
    """Measure each pipeline stage with wall time, RSS and file deltas."""

    def __init__(self, *, warm: bool = False) -> None:
        self.warm = warm
        self.stages: list[dict[str, Any]] = []
        self._active: dict[str, tuple[float, float | None, float | None, int]] | None = None
        self.tracemalloc_started = False

    def __enter__(self) -> "StageRecorder":
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self.tracemalloc_started = True
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self.tracemalloc_started and tracemalloc.is_tracing():
            tracemalloc.stop()
            self.tracemalloc_started = False

    def begin(self, stage: str, inputs: list[Path] | None = None) -> None:
        self._active = (
            time.perf_counter(),
            rss_mb(),
            peak_rss_mb(),
            _directory_bytes(inputs or []),
        )
        self._stage_name = stage

    def end(self, outputs: list[Path] | None = None, *, status: str = "success") -> None:
        if self._active is None:
            return
        started, rss_before, peak_before, input_bytes = self._active
        elapsed = time.perf_counter() - started
        _, python_peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
        self.stages.append(
            {
                "stage": self._stage_name,
                "duration_seconds": round(elapsed, 4),
                "status": status,
                "input_bytes": input_bytes,
                "output_bytes": _directory_bytes(outputs or []),
                "rss_mb_before": rss_before,
                "rss_mb_after": rss_mb(),
                "peak_rss_mb_observed": peak_before,
                "python_alloc_peak_mb": round(python_peak / 1048576, 3)
                if python_peak
                else None,
            }
        )
        self._active = None

    def run(self, stage: str, fn: Callable[[], Any], *,
            inputs: list[Path] | None = None,
            outputs: list[Path] | None = None) -> Any:
        self.begin(stage, inputs)
        try:
            result = fn()
        except BaseException:
            self.end(outputs, status="failed")
            raise
        self.end(outputs)
        return result

    def report(self, *, input_hash: str | None = None) -> dict[str, Any]:
        return {
            "status": "GENERATED",
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "measurement": {
                "mode": "warm" if self.warm else "cold",
                "environment": environment_record(),
                "note": (
                    "RSS (process working set) and tracemalloc (Python objects) "
                    "are different scopes; do not sum them."
                ),
            },
            "input_manifest_sha256": input_hash,
            "stages": self.stages,
            "total_duration_seconds": round(
                sum(s["duration_seconds"] for s in self.stages), 4
            ),
            "process_peak_rss_mb": peak_rss_mb(),
        }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
