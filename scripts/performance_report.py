"""Create a baseline/optimized Viewer performance comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mib(value: float | int | None) -> str:
    return "—" if value is None else f"{value / (1024 * 1024):.2f} MiB"


def _pct(before: float | int | None, after: float | int | None) -> str:
    if before in (None, 0) or after is None:
        return "—"
    return f"{(after - before) / before * 100:+.1f}%"


def build_report(
    baseline: dict[str, Any],
    optimized: dict[str, Any],
    timing: dict[str, Any],
    long_playback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_final = baseline["final"]["frameIndex"]
    opt_final = optimized["final"]["frameIndex"]
    report = {
        "status": "GENERATED",
        "scope": "Same real SoftBonded_PFC3D experiment, headless Edge SwiftShader, 1600x1000",
        "environment_note": (
            "FPS values are relative browser-automation measurements under software WebGL; "
            "they are not hardware-GPU acceptance claims."
        ),
        "baseline": {
            "label": baseline["label"],
            "file_bytes": baseline["fileBytes"],
            "ready_ms": baseline["readyMs"],
            "js_heap_bytes": baseline["peakJsHeapBytes"],
            "median_fps": baseline["medianFps"],
            "frames_advanced_in_benchmark": base_final,
            "max_draw_calls": baseline["maxDrawCalls"],
            "max_geometries": baseline["maxGeometries"],
        },
        "optimized": {
            "label": optimized["label"],
            "file_bytes": optimized["fileBytes"],
            "ready_ms": optimized["readyMs"],
            "js_heap_bytes": optimized["peakJsHeapBytes"],
            "median_fps": optimized["medianFps"],
            "frames_advanced_in_benchmark": opt_final,
            "max_loaded_chunks": optimized["maxLoadedChunks"],
            "max_draw_calls": optimized["maxDrawCalls"],
            "max_geometries": optimized["maxGeometries"],
            "payload_reused": timing["payload_reused"],
            "payload_elapsed_seconds": timing["payload_elapsed_seconds"],
            "viewer_build_elapsed_seconds": timing["viewer_build_elapsed_seconds"],
            "payload_total_bytes": timing["payload_total_bytes"],
        },
        "comparison": {
            "html_or_single_file_size": _pct(baseline["fileBytes"], optimized["fileBytes"]),
            "ready_time": _pct(baseline["readyMs"], optimized["readyMs"]),
            "peak_js_heap": _pct(baseline["peakJsHeapBytes"], optimized["peakJsHeapBytes"]),
            "median_fps": _pct(baseline["medianFps"], optimized["medianFps"]),
            "frames_advanced": _pct(base_final, opt_final),
        },
    }
    if long_playback is not None:
        report["long_playback"] = {
            "seconds": long_playback["playbackSeconds"],
            "frames_advanced": long_playback["final"]["frameIndex"],
            "max_loaded_chunks": long_playback["maxLoadedChunks"],
            "initial_js_heap_bytes": long_playback["initial"]["memory"],
            "peak_js_heap_bytes": long_playback["peakJsHeapBytes"],
            "final_js_heap_bytes": long_playback["finalJsHeapBytes"],
            "max_draw_calls": long_playback["maxDrawCalls"],
            "max_geometries": long_playback["maxGeometries"],
        }
    return report


def markdown(report: dict[str, Any]) -> str:
    base = report["baseline"]
    opt = report["optimized"]
    cmp = report["comparison"]
    lines = [
            "# Scientific Viewer Performance Report",
            "",
            f"- Scope: {report['scope']}",
            f"- Environment: {report['environment_note']}",
            "",
            "| Metric | Baseline single HTML | Chunked Viewer | Change |",
            "|---|---:|---:|---:|",
            f"| HTML / page shell | {_mib(base['file_bytes'])} | {_mib(opt['file_bytes'])} | {cmp['html_or_single_file_size']} |",
            f"| Payload on disk | embedded | {_mib(opt['payload_total_bytes'])} | externalized |",
            f"| Page ready | {base['ready_ms']} ms | {opt['ready_ms']} ms | {cmp['ready_time']} |",
            f"| Peak JS heap | {_mib(base['js_heap_bytes'])} | {_mib(opt['js_heap_bytes'])} | {cmp['peak_js_heap']} |",
            f"| Median software-WebGL FPS | {base['median_fps']} | {opt['median_fps']} | {cmp['median_fps']} |",
            f"| Frames advanced in 8 s | {base['frames_advanced_in_benchmark']} | {opt['frames_advanced_in_benchmark']} | {cmp['frames_advanced']} |",
            f"| Max loaded frame chunks | all embedded | {opt['max_loaded_chunks']} | bounded LRU |",
            f"| Max draw calls | {base['max_draw_calls']} | {opt['max_draw_calls']} | — |",
            f"| Max geometries | {base['max_geometries']} | {opt['max_geometries']} | — |",
            "",
            "## Build time",
            "",
            f"- Payload reused: `{opt['payload_reused']}`",
            f"- Payload elapsed: `{opt['payload_elapsed_seconds']}` s",
            f"- Viewer style/bundle elapsed: `{opt['viewer_build_elapsed_seconds']}` s",
            "",
            "## Reading",
            "",
            "- The single-file HTML drops from tens of MiB to a few KiB. Data remains available in local chunk files and is loaded on demand.",
            "- Browser JS heap is the primary measured memory win. GPU memory is not directly exposed by this benchmark.",
            "- The software-WebGL FPS result is noisy and is not evidence of failure or success on a hardware GPU. Interaction correctness is separately acceptance-tested.",
            "- A payload rebuild preserves every real frame by default. Style-only rebuilds reuse the existing payload.",
            "",
        ]
    if "long_playback" in report:
        long_run = report["long_playback"]
        lines.extend(
            [
                "## Long playback",
                "",
                f"- Duration: `{long_run['seconds']}` s",
                f"- Frames advanced: `{long_run['frames_advanced']}`",
                f"- Maximum loaded chunks: `{long_run['max_loaded_chunks']}`",
                f"- Peak JS heap: {_mib(long_run['peak_js_heap_bytes'])}",
                f"- Final JS heap: {_mib(long_run['final_js_heap_bytes'])}",
                "",
            ]
        )
    return "\n".join(lines)


def build_single_report(optimized: dict[str, Any]) -> dict[str, Any]:
    """Report one measured Viewer run when no baseline artifact is supplied."""
    return {
        "status": "GENERATED",
        "scope": "One real Console experiment, headless Edge SwiftShader, 1600x1000",
        "environment_note": (
            "FPS is a software-WebGL measurement and is not a hardware-GPU claim."
        ),
        "optimized": {
            "label": optimized["label"],
            "file_bytes": optimized["fileBytes"],
            "ready_ms": optimized["readyMs"],
            "js_heap_bytes": optimized["peakJsHeapBytes"],
            "median_fps": optimized["medianFps"],
            "playback_seconds": optimized["playbackSeconds"],
            "max_loaded_chunks": optimized["maxLoadedChunks"],
            "max_draw_calls": optimized["maxDrawCalls"],
            "max_geometries": optimized["maxGeometries"],
            "final_js_heap_bytes": optimized["finalJsHeapBytes"],
        },
        "comparison": {
            "status": "NOT_APPLICABLE",
            "reason": "No pre-optimization baseline artifact was supplied.",
        },
    }


def single_markdown(report: dict[str, Any]) -> str:
    item = report["optimized"]
    return "\n".join(
        [
            "# Scientific Viewer Performance Report",
            "",
            f"- Scope: {report['scope']}",
            f"- Environment: {report['environment_note']}",
            f"- Label: `{item['label']}`",
            "",
            "| Metric | Measured value |",
            "|---|---:|",
            f"| HTML page shell | {_mib(item['file_bytes'])} |",
            f"| Ready time | {item['ready_ms']} ms |",
            f"| Peak JS heap | {_mib(item['js_heap_bytes'])} |",
            f"| Final JS heap | {_mib(item['final_js_heap_bytes'])} |",
            f"| Median software-WebGL FPS | {item['median_fps']} |",
            f"| Playback duration | {item['playback_seconds']} s |",
            f"| Maximum loaded chunks | {item['max_loaded_chunks']} |",
            f"| Maximum draw calls | {item['max_draw_calls']} |",
            f"| Maximum geometries | {item['max_geometries']} |",
            "",
            "## Boundary",
            "",
            "- The benchmark uses headless Edge with SwiftShader.",
            "- FPS is noisy and must not be interpreted as target-workstation GPU performance.",
            "- Interaction correctness and offline integrity are reported separately.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline")
    parser.add_argument("--optimized", required=True)
    parser.add_argument("--timing", required=True)
    parser.add_argument("--long-playback")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()
    optimized = _read(Path(args.optimized))
    if args.baseline:
        report = build_report(
            _read(Path(args.baseline)),
            optimized,
            _read(Path(args.timing)),
            _read(Path(args.long_playback)) if args.long_playback else None,
        )
        report_text = markdown(report)
    else:
        report = build_single_report(optimized)
        report_text = single_markdown(report)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(report_text, encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
