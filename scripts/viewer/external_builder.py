"""Bundle the lightweight external-resource scientific Viewer.

Frame data is prepared separately by :mod:`payload_builder`. Re-running this
module after a CSS or JavaScript-only change reuses the chunked payload.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import time
from pathlib import Path
from typing import Any

from .payload_builder import PAYLOAD_VERSION, prepare_payload
from .linkage import evaluate_linkage_decisions


SKILL_ROOT = Path(__file__).resolve().parents[2]
ASSETS = SKILL_ROOT / "assets"
SHELL = ASSETS / "scientific-viewer-shell.html"
WEB_ASSETS = ASSETS / "viewer"
VENDOR = ASSETS / "vendor"
VISUAL_SEMANTICS = ASSETS / "styles" / "scientific-visual-semantics.json"
HTML_LIMIT_BYTES = 5 * 1024 * 1024


class ViewerBuildError(RuntimeError):
    pass


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ViewerBuildError(f"Required Viewer asset missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _write_shell(output: Path, title: str) -> None:
    text = SHELL.read_text(encoding="utf-8")
    if "__TITLE__" not in text:
        raise ViewerBuildError("Viewer shell has no __TITLE__ placeholder")
    text = text.replace("__TITLE__", html.escape(title))
    if "__TITLE__" in text:
        raise ViewerBuildError("Viewer shell title placeholder was not replaced")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")


def build_viewer(
    experiment_root: Path,
    output: Path,
    *,
    analysis_root: Path | None = None,
    max_frames: int | None = 0,
    title: str | None = None,
    cases: list[int] | None = None,
    rebuild_payload: bool = False,
    linkage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    experiment_root = experiment_root.resolve()
    output = output.resolve()
    viewer_root = output.parent
    analysis_root = (analysis_root or experiment_root / "analysis").resolve()
    experiment = json.loads((experiment_root / "experiment.json").read_text(encoding="utf-8"))
    viewer_title = title or experiment["title"]
    data_root = viewer_root / "data"
    payload = prepare_payload(
        experiment_root,
        analysis_root,
        data_root,
        max_frames=max_frames,
        reuse=not rebuild_payload,
        force=rebuild_payload,
    )

    runtime_root = viewer_root / "viewer"
    runtime_root.mkdir(parents=True, exist_ok=True)
    _copy_file(WEB_ASSETS / "scientific-viewer.js", runtime_root / "scientific-viewer.js")
    _copy_file(WEB_ASSETS / "scientific-viewer.css", runtime_root / "scientific-viewer.css")
    if not VISUAL_SEMANTICS.is_file():
        raise ViewerBuildError(f"Required visual semantics missing: {VISUAL_SEMANTICS}")
    semantics = json.loads(VISUAL_SEMANTICS.read_text(encoding="utf-8"))
    # Wire the published Nature design tokens into the runtime semantics so
    # ECharts/Three.js actually consume the same palette and typography.
    nature_path = VISUAL_SEMANTICS.parent / "nature-theme.json"
    if nature_path.is_file():
        nature = json.loads(nature_path.read_text(encoding="utf-8"))
        semantics["nature_design_tokens"] = nature
        light = semantics.get("themes", {}).get("light", {})
        light.update({
            "scene_background": nature.get("background", light.get("scene_background")),
            "chart_background": nature.get("background", light.get("chart_background")),
            "axis": nature.get("axis", light.get("axis")),
            "typography": nature.get("typography", light.get("typography")),
            "numeric_display": nature.get("numeric_display", light.get("numeric_display")),
        })
        semantics["themes"]["light"] = light
    (runtime_root / "visual-semantics.js").write_text(
        "window.PFC_VISUAL_SEMANTICS = "
        + json.dumps(semantics, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    for name in ("three.min.js", "OrbitControls.js", "echarts.min.js"):
        _copy_file(VENDOR / name, runtime_root / "vendor" / name)
    (runtime_root / ".pfc-generated").write_text(
        PAYLOAD_VERSION + "\n", encoding="utf-8", newline="\n"
    )
    _write_shell(output, viewer_title)

    html_bytes = output.stat().st_size
    if html_bytes >= HTML_LIMIT_BYTES:
        raise ViewerBuildError(
            f"HTML shell exceeds the 5 MiB target: {html_bytes} bytes"
        )
    case_ids = [int(case["id"]) for case in payload["cases"]]
    filtered_cases = None
    visible_case_ids = case_ids
    if cases is not None:
        requested = {int(case_id) for case_id in cases}
        filtered_cases = [case_id for case_id in case_ids if case_id in requested]
        if not filtered_cases:
            raise ViewerBuildError("No requested Cases exist in the Viewer payload")
        visible_case_ids = filtered_cases
        _json_dump(
            data_root / "view_filter.json",
            {
                "status": "CONFIG",
                "requested_case_ids": sorted(requested),
                "available_case_ids": case_ids,
                "note": "The current shell displays the full payload; this file records the requested build filter.",
            },
        )
    (data_root / "view-filter.js").write_text(
        "window.PFC_VIEWER_CASE_FILTER = "
        + json.dumps(visible_case_ids, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
        newline="\n",
    )

    if linkage is None:
        metric_status = {
            metric: (
                "SUPPORTED"
                if any(
                    case.get("metricStatus", {}).get(metric) == "SUPPORTED"
                    for case in payload["cases"]
                )
                else "NOT_CAPTURED"
            )
            for metric in ("displacement", "speed", "acceleration")
        }
        entity_contact = (
            "SUPPORTED"
            if any(
                case.get("entityStatus", {}).get("contact") == "SUPPORTED"
                for case in payload["cases"]
            )
            else "NOT_CAPTURED"
        )
        linkage = evaluate_linkage_decisions(
            contact_network=entity_contact,
            particle_metrics=tuple(
                metric for metric, status in metric_status.items() if status == "SUPPORTED"
            ),
        )
    _json_dump(viewer_root / "linkage_decisions.json", linkage)
    analysis_contract = {
        name: "GENERATED" if (analysis_root / name).is_file() else "NOT_GENERATED"
        for name in (
            "chart_decisions.json",
            "display_data.json",
            "data_layers.json",
        )
    }
    _json_dump(
        viewer_root / "viewer_output_contract.json",
        {
            "status": "GENERATED",
            "scope": "VIEWER_BUNDLE_ONLY",
            "verification": "NOT_VERIFIED",
            "items": [
                {
                    "id": "offline_viewer",
                    "status": "GENERATED",
                    "path": output.name,
                    "verification": "NOT_VERIFIED",
                },
                {
                    "id": "linking_decision_record",
                    "status": linkage.get("status", "NOT_GENERATED"),
                    "path": "linkage_decisions.json",
                },
            ],
            "analysis_contract_artifacts": analysis_contract,
            "note": (
                "This path rebuilds only the Viewer bundle. Use run_pipeline.py "
                "to regenerate the complete experiment output contract."
            ),
        },
    )
    viewer_bytes = _directory_bytes(viewer_root)
    payload_sizes = dict(payload["sizes"])
    payload_sizes.setdefault("total_bytes", _directory_bytes(data_root))
    manifest = {
        "status": "GENERATED",
        "verification_status": "NOT_VERIFIED",
        "architecture": "small-html-local-dependencies-chunked-data",
        "viewer": str(output),
        "html_bytes": html_bytes,
        "html_target_bytes": HTML_LIMIT_BYTES,
        "html_target_met": html_bytes < HTML_LIMIT_BYTES,
        "viewer_total_bytes": viewer_bytes,
        "offline": True,
        "external_network_requests": False,
        "single_html": False,
        "dependencies": [
            "viewer/vendor/three.min.js",
            "viewer/vendor/OrbitControls.js",
            "viewer/vendor/echarts.min.js",
            "viewer/visual-semantics.js",
        ],
        "payload": {
            "path": str(data_root),
            "version": payload["payload_version"],
            "reused": bool(payload.get("reused")),
            "frame_policy": payload["frame_policy"],
            "sizes": payload_sizes,
            "cases": payload["cases"],
        },
        "state_contract": {
            "currentCase": "integer Case ID",
            "currentFrame": "zero-based index in the real-frame sequence",
            "currentCycle": "captured PFC Cycle",
            "currentTime": "captured mechanical time in seconds",
            "selectedBallIds": "real PFC Ball IDs",
            "selectedMetric": "displacement | speed | acceleration",
            "selectedRange": "inclusive numeric range for the selected particle metric",
        },
        "linking": {
            "timeline_to_scene": True,
            "chart_drag_to_frame": True,
            "scene_ball_to_history": True,
            "current_distribution_brush_to_particles": True,
            "multi_ball_selection": True,
            "particle_force_history": "NOT_CAPTURED_UNLESS_SOURCE_FIELD_EXISTS",
            "decision_record": "linkage_decisions.json",
            "decision_summary": {
                "implemented": sum(
                    1 for item in linkage.get("decisions", []) if item.get("implemented")
                ),
                "not_implemented": sum(
                    1 for item in linkage.get("decisions", []) if not item.get("implemented")
                ),
            },
        },
        "design_system": {
            "path": "viewer/visual-semantics.js",
            "source": "assets/styles/scientific-visual-semantics.json",
            "version": semantics.get("version"),
            "sha256": _sha256(runtime_root / "visual-semantics.js"),
        },
        "publication_export_api": {
            "png_current": "window.PFCViewer.exportPNG()",
            "png_specified_frame": "window.PFCViewer.exportFramePNG(frameIndex, width)",
            "chart_svg": "window.PFCViewer.exportChartSVGs()",
            "composite_png": "window.PFCViewer.exportCompositePanels()",
        },
        "requested_cases": filtered_cases,
        "viewer_output_contract": "viewer_output_contract.json",
        "build_elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    _json_dump(viewer_root / "viewer_manifest.json", manifest)
    _json_dump(
        viewer_root / "publication_export_spec.json",
        {
            "viewer": output.name,
            "fixed_view": True,
            "png_supported": True,
            "transparent_background_supported": True,
            "chart_vector_format": "SVG",
            "composite_raster_export": "PNG",
            "panel_letters": True,
            "adaptive_composite_layout": True,
            "composite_titles": True,
            "all_panels_exported": True,
            "uniform_color_tokens": {
                "primary": "#3C5488",
                "fracture": "#E64B35",
                "slate": "#8491B4",
                "tan": "#B09C85",
                "accent": "#F39B7F",
            },
            "verification": "NOT_VERIFIED",
        },
    )
    _json_dump(
        viewer_root / "viewer_build_timing.json",
        {
            "status": "GENERATED",
            "payload_reused": bool(payload.get("reused")),
            "payload_elapsed_seconds": payload.get("elapsed_seconds"),
            "viewer_build_elapsed_seconds": manifest["build_elapsed_seconds"],
            "html_bytes": html_bytes,
            "payload_total_bytes": manifest["payload"]["sizes"].get("total_bytes"),
        },
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", required=True)
    parser.add_argument("--analysis-root")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="0 preserves all real frames; a positive value is disclosed as explicit sampling",
    )
    parser.add_argument("--title")
    parser.add_argument("--cases", type=int, nargs="+")
    parser.add_argument("--rebuild-payload", action="store_true")
    args = parser.parse_args()
    result = build_viewer(
        Path(args.experiment_root),
        Path(args.out),
        analysis_root=Path(args.analysis_root) if args.analysis_root else None,
        max_frames=args.max_frames,
        title=args.title,
        cases=args.cases,
        rebuild_payload=args.rebuild_payload,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
