"""Analyze a read-only pfc-headless standardized experiment.

This command verifies the standardized delivery manifest, then writes analysis,
Viewer and publication products to a separate output root. It never starts PFC,
connects to the Bridge, captures raw data or standardizes arrays.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from adapters import inspect_experiment_capabilities
from analysis import analyze_experiment
from analysis.physics import (
    infer_physics_context, redundancy_analysis, coverage_analysis,
)
from analysis.physics import (
    infer_physics_context, redundancy_analysis, coverage_analysis,
)
from charts import write_publication_plan
from packaging import materialize_output_contract
from schema import (
    make_analysis_data_layer,
    make_display_data_layer,
    make_provenance,
)
from standard_contract import verify_standard_contract
from viewer import build_viewer
from viewer.linkage import evaluate_linkage_decisions


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _report(output_root: Path, pipeline: dict[str, Any]) -> None:
    generated = pipeline["generated"]
    lines = [
        "# PFC 科研可视化实验结果",
        "",
        f"- 实验：{pipeline['title']}",
        f"- 数据边界：`{pipeline['data_boundary']}`",
        f"- 标准化输入契约：`{pipeline['source_contract']['name']}@{pipeline['source_contract']['version']}`",
        f"- 输入契约 SHA-256：`{pipeline['source_contract']['manifest_sha256']}`",
        f"- 验证状态：`NOT_VERIFIED`",
        f"- 生成时间：{pipeline['generated_utc']}",
        "",
        "## 实际生成",
        "",
    ]
    lines.extend(f"- `{value}`" for value in generated)
    lines.extend(
        [
            "",
            "## 未生成或未验证",
            "",
            "- Viewer 未进行浏览器运行验收。",
            "- 本章节不包含真实 PFC 求解或实验验证结果。",
            "- 没有输入数据的物理量、图表和图片不会被补齐或伪造。",
            "- 本次没有执行单元测试、集成测试或性能测试。",
            "",
            "## 真实性与边界",
            "",
            "- 原始采集、质量检查和标准化由 pfc-headless 管理。",
            "- 本结果只读消费标准化契约，不复制或修改其原始数据与数组。",
            "- 本结果只在独立输出目录写分析、图表和视觉产物。",
            "- 标准化数组使用变长实体偏移，不假设固定颗粒数。",
            "- 派生量记录公式、输入、单位、来源和适用条件。",
            "- 播放与时间轴只切换真实采样帧，不插值。",
            "",
            "## 文件索引",
            "",
            "参见 `07_metadata/output_index.json`。",
            "",
        ]
    )
    if pipeline.get("rejected"):
        lines.extend(["## 图表未生成原因", ""])
        lines.extend(
            f"- `{item['id']}`: `{item['status']}` — {item['reason']}"
            for item in pipeline["rejected"]
        )
        lines.append("")
    if pipeline.get("capability_summary"):
        lines.extend(["## 数据能力摘要", ""])
        lines.extend(
            f"- `{key}`: `{value}`"
            for key, value in pipeline["capability_summary"].items()
        )
        lines.append("")
    (output_root / "report" / "experiment_report.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_records(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    records = []
    for path in paths:
        if not path.is_file():
            continue
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def _write_data_layers(
    output_root: Path,
    source_contract: dict[str, Any],
    experiment: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    analysis_root = output_root / "03_analysis"
    source_root = Path(source_contract["root"])
    source_case_map = {
        int(item["case_id"]): item for item in source_contract["cases"]
    }
    display_data = {
        "status": "GENERATED",
        "policy": (
            "Display formatting is derived from chart values at render time. "
            "Per-point formatted strings are not used as analysis inputs."
        ),
        "charts": [
            {
                "chart_id": chart["id"],
                "display": chart.get("display", {}),
                "conversions": chart.get("conversions", []),
            }
            for chart in analysis.get("charts", [])
        ],
        "verification": "NOT_VERIFIED",
    }
    _dump(analysis_root / "display_data.json", display_data)
    layers = []
    for case in experiment["cases"]:
        case_id = int(case["case_id"])
        source_case = source_case_map[case_id]
        source_arrays_path = source_root / source_case["arrays_path"]
        analysis_files = _file_records(
            output_root,
            [
                analysis_root / f"case_{case_id}" / "analysis_arrays.npz",
                analysis_root / f"case_{case_id}" / "analysis.json",
            ],
        )
        operations = [
            {
                "method": item.get("formula") or item.get("applicability") or item["id"],
                "outputs": [item["id"]],
                "unit": item.get("unit"),
                "source": item.get("source"),
            }
            for item in next(
                (
                    case_result.get("channels", [])
                    for case_result in analysis["cases"]
                    if int(case_result["case_id"]) == case_id
                ),
                [],
            )
        ]
        analysis_layer = make_analysis_data_layer(
            case_id,
            analysis_files,
            parent_layer_id=(
                f"pfc-headless:{source_contract['manifest_sha256']}:case_{case_id}"
            ),
            operations=operations,
            provenance=make_provenance(
                source="DERIVED",
                input_files=[
                    {
                        "path": str(source_root / "experiment.json"),
                        "sha256": source_contract["manifest"]["experiment"]["sha256"],
                        "size_bytes": source_contract["manifest"]["experiment"][
                            "size_bytes"
                        ],
                    },
                    {
                        "path": str(source_arrays_path),
                        "sha256": source_case["arrays_sha256"],
                        "size_bytes": source_arrays_path.stat().st_size,
                    },
                ],
                method="Formula-gated analysis over standardized arrays.",
                applicability="Only fields with complete declared inputs are derived.",
            ),
        )
        display_layer = make_display_data_layer(
            case_id,
            _file_records(
                output_root,
                [
                    analysis_root / "chart_specs.json",
                    analysis_root / "display_data.json",
                ],
            ),
            parent_layer_ids=[analysis_layer["layer_id"]],
            formatting={
                "method": "AUTO_SCIENTIFIC_OR_DECIMAL_DISPLAY_ONLY",
                "significant_digits": 4,
                "tooltip_digits": 8,
                "rules": (
                    "Display strings and unit scaling are metadata; chart values "
                    "retain the declared numerical transform and never feed analysis."
                ),
            },
        )
        layers.extend([analysis_layer, display_layer])
    manifest = {
        "status": "GENERATED",
        "layers": ["ANALYSIS_DATA", "DISPLAY_DATA"],
        "records": layers,
        "external_parent": {
            "owner": "pfc-headless",
            "contract": source_contract["contract"],
            "manifest_sha256": source_contract["manifest_sha256"],
            "read_only": True,
        },
        "policy": {
            "standardized_input_immutable": True,
            "raw_owned_by_pfc_headless": True,
            "derived_requires_formula_and_inputs": True,
            "display_never_used_as_analysis_input": True,
        },
        "verification": "NOT_VERIFIED",
    }
    _dump(analysis_root / "data_layers.json", manifest)
    return manifest


def _write_source_contract(
    output_root: Path,
    source_contract: dict[str, Any],
) -> None:
    _dump(
        output_root / "07_metadata" / "source_contract.json",
        {
            "status": "VERIFIED_READ_ONLY",
            "owner": "pfc-headless",
            "root": source_contract["root"],
            "contract": source_contract["contract"],
            "manifest_sha256": source_contract["manifest_sha256"],
            "experiment_id": source_contract["experiment"]["experiment_id"],
            "case_count": len(source_contract["cases"]),
            "cases": source_contract["cases"],
            "consumer_policy": {
                "read_only": True,
                "may_write_inside_contract": False,
            },
        },
    )


def run_pipeline(
    input_root: Path,
    output_root: Path,
    *,
    title: str | None = None,
    max_frames: int = 0,
    chart_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    if (
        output_root == input_root
        or output_root in input_root.parents
        or input_root in output_root.parents
    ):
        raise ValueError(
            "Analysis output must be separate from the standardized input contract"
        )
    source_contract = verify_standard_contract(input_root)
    experiment = source_contract["experiment"]
    title = title or str(experiment["title"])
    materialize_output_contract(
        output_root,
        title=title,
        data_boundary=experiment.get("data_boundary", "UNKNOWN"),
    )
    analysis_root = output_root / "03_analysis"
    viewer_root = output_root / "04_viewer"
    chart_root = output_root / "05_charts"
    publication_root = output_root / "06_publication_figures"

    analysis = analyze_experiment(
        input_root,
        analysis_root,
        chart_overrides=chart_overrides,
    )
    _write_source_contract(output_root, source_contract)
    data_layers = _write_data_layers(
        output_root,
        source_contract,
        experiment,
        analysis,
    )
    capabilities = inspect_experiment_capabilities(
        input_root,
        analysis_root,
    )
    supported_metrics = tuple(
        metric
        for metric, key in (
            ("displacement", "particle_displacement"),
            ("speed", "particle_speed"),
        )
        if capabilities.get("common", {}).get(key) == "SUPPORTED"
    )
    linkage = evaluate_linkage_decisions(
        contact_network=capabilities.get("common", {}).get(
            "contact_network", "NOT_CAPTURED"
        ),
        particle_metrics=supported_metrics,
    )
    viewer_manifest = build_viewer(
        input_root,
        viewer_root / "scientific_viewer.html",
        analysis_root=analysis_root,
        max_frames=max_frames,
        title=title,
        linkage=linkage,
    )
    _dump(
        chart_root / "chart_specs.json",
        json.loads((analysis_root / "chart_specs.json").read_text(encoding="utf-8")),
    )
    figure_plan = write_publication_plan(
        analysis["charts"],
        publication_root / "figure_plan.json",
        max_panels_per_figure=6,
    )
    chart_decisions = json.loads(
        (analysis_root / "chart_decisions.json").read_text(encoding="utf-8")
    )
    # Physics-aware decision record: intent, coverage and redundancy are
    # auditable; charts themselves are still selected by the data gates.
    try:
        _source_cases = source_contract.get("cases", [])
        _default_case = next(iter(_source_cases), {}) if isinstance(_source_cases, list) else {}
        _ctx = infer_physics_context({
            "case_name": " ".join(str(_default_case.get(k, "")) for k in ("case_name", "name", "title", "label")),
            "run_id": str(experiment.get("title", "") or experiment.get("experiment_id", "")),
            "physics_context": _default_case.get("physics_context", {}),
        })
        _redundancy = redundancy_analysis(analysis.get("charts", []))
        _coverage = coverage_analysis(analysis.get("charts", []), _ctx)
        _dump(
            analysis_root / "chart_decision_record.json",
            {
                "status": "GENERATED",
                "case_id": _default_case.get("case_id"),
                "physics_context": _ctx,
                "data_inventory": list(capabilities.get("common", {}).keys()),
                "selected_charts": [c.get("chart_id") for c in analysis.get("charts", [])],
                "rejected_charts": [r.get("id") for r in chart_decisions.get("rejected", [])],
                "redundancy_analysis": _redundancy,
                "coverage_analysis": _coverage,
                "limitations": [
                    "Physics context is inferred from case name unless explicitly declared.",
                    "Coverage reflects chart intent only; all selected charts passed real-data gates."
                ],
            },
        )
    except Exception as _exc:  # never break the main pipeline for metadata
        _dump(analysis_root / "chart_decision_record.json",
              {"status": "NOT_GENERATED", "error": str(_exc)})
    output_contract = {
        "status": "GENERATED",
        "verification": "NOT_VERIFIED",
        "items": [
            {
                "id": "source_standardized_contract",
                "status": "VERIFIED_READ_ONLY",
                "path": source_contract["root"],
                "owner": "pfc-headless",
                "manifest_sha256": source_contract["manifest_sha256"],
            },
            {
                "id": "analysis_data",
                "status": "GENERATED",
                "path": "03_analysis/",
            },
            {
                "id": "offline_viewer",
                "status": "GENERATED",
                "path": "04_viewer/scientific_viewer.html",
                "verification": "NOT_VERIFIED",
            },
            {
                "id": "charts",
                "status": "GENERATED" if analysis["charts"] else "NOT_GENERATED",
                "path": "03_analysis/chart_specs.json",
                "rejected": chart_decisions.get("rejected", []),
            },
            {
                "id": "publication_figure_plan",
                "status": (
                    "GENERATED"
                    if figure_plan.get("figures")
                    else "NOT_GENERATED"
                ),
                "path": "06_publication_figures/figure_plan.json",
                "verification": "NOT_VERIFIED",
            },
            {
                "id": "publication_composed_svg",
                "status": "NOT_GENERATED",
                "reason": "Viewer SVG exports are required.",
            },
            {
                "id": "publication_pdf",
                "status": "NOT_SUPPORTED",
                "reason": "Use a local vector converter on composed SVG; no PDF backend is bundled.",
            },
            {
                "id": "experiment_report",
                "status": "GENERATED",
                "path": "report/experiment_report.md",
                "verification": "NOT_VERIFIED",
            },
        ],
        "unverified": [
            "browser rendering and interaction",
            "PNG/SVG export",
            "test suite execution",
            "performance measurement",
        ],
    }
    _dump(output_root / "07_metadata" / "experiment_capabilities.json", capabilities)
    _dump(output_root / "07_metadata" / "output_contract.json", output_contract)
    _dump(
        output_root / "07_metadata" / "pipeline_manifest.json",
        {
            "status": "GENERATED",
            "verification": "NOT_VERIFIED",
            "source_contract": source_contract["contract"],
            "source_manifest_sha256": source_contract["manifest_sha256"],
            "experiment": experiment,
            "data_layers": data_layers,
            "capabilities": capabilities,
            "linkage": linkage,
            "viewer": viewer_manifest,
            "analysis_chart_count": len(analysis["charts"]),
            "figure_plan": figure_plan,
            "output_contract": output_contract,
        },
    )
    generated = [
        "03_analysis/analysis.json",
        "03_analysis/chart_specs.json",
        "03_analysis/chart_decisions.json",
        "03_analysis/chart_decision_record.json",
        "03_analysis/display_data.json",
        "03_analysis/data_layers.json",
        "04_viewer/scientific_viewer.html",
        "04_viewer/viewer/",
        "04_viewer/data/",
        "04_viewer/linkage_decisions.json",
        "04_viewer/viewer_manifest.json",
        "05_charts/chart_specs.json",
        "06_publication_figures/figure_plan.json",
        "07_metadata/source_contract.json",
        "07_metadata/experiment_capabilities.json",
        "07_metadata/output_contract.json",
        "07_metadata/output_index.json",
        "report/experiment_report.md",
    ]
    pipeline = {
        "status": "GENERATED",
        "verification": "NOT_VERIFIED",
        "title": title,
        "data_boundary": experiment["data_boundary"],
        "source_contract": {
            **source_contract["contract"],
            "manifest_sha256": source_contract["manifest_sha256"],
        },
        "generated_utc": analysis.get(
            "generated_utc", experiment["generated_utc"]
        ),
        "generated": generated,
        "rejected": chart_decisions.get("rejected", []),
        "capability_summary": capabilities.get("common", {}),
        "not_generated": [
            "06_publication_figures/composed_figure.svg (requires Viewer SVG exports)",
            "publication PNG (requires Viewer browser capture)",
        ],
    }
    _report(output_root, pipeline)
    materialize_output_contract(
        output_root,
        title=title,
        data_boundary=experiment["data_boundary"],
    )
    return pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="Read-only standardized contract produced by pfc-headless.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="New analysis-result directory; must be separate from --input.",
    )
    parser.add_argument("--title")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="0 preserves every real frame; a positive value is disclosed as explicit sampling",
    )
    parser.add_argument(
        "--chart-overrides",
        help="Optional JSON object keyed by chart ID; overrides are validated against data structure.",
    )
    args = parser.parse_args()
    chart_overrides = (
        json.loads(Path(args.chart_overrides).read_text(encoding="utf-8"))
        if args.chart_overrides
        else None
    )
    result = run_pipeline(
        Path(args.input),
        Path(args.output),
        title=args.title,
        max_frames=args.max_frames,
        chart_overrides=chart_overrides,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
