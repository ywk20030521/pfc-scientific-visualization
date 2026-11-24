"""Adaptive multipanel composition for exported scientific charts.

The Viewer exports vector SVG panels and an optional scene PNG. Layout depends
on panel count, content priority and page aspect; absent panels are never
replaced with blank placeholders.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

COLOR_TOKENS = {
    "primary": "#3C5488",
    "fracture": "#E64B35",
    "slate": "#8491B4",
    "tan": "#B09C85",
    "accent": "#F39B7F",
}


def _natural_sort_key(value: str) -> tuple[Any, ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
    )


def _panel_label(index: int) -> str:
    label = ""
    value = int(index) + 1
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        label = chr(ord("a") + remainder) + label
    return label


def _wrap_text(value: str, max_characters: int) -> list[str]:
    text = " ".join(str(value or "").split())
    if not text:
        return [""]
    if len(text) <= max_characters:
        return [text]
    lines = []
    remaining = text
    while remaining:
        if len(remaining) <= max_characters:
            lines.append(remaining)
            break
        split_at = -1
        for delimiter in (" ", "–", "-", "，", ","):
            candidate = remaining.rfind(delimiter, 0, max_characters + 1)
            split_at = max(split_at, candidate)
        if split_at <= 0:
            split_at = max_characters
        lines.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip(" –-，,")
    return lines


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _chunks(count: int, columns: int) -> list[int]:
    rows = []
    remaining = count
    while remaining > 0:
        rows.append(min(columns, remaining))
        remaining -= rows[-1]
    return rows


def _row_recipe(
    count: int,
    *,
    aspect_ratio: float,
    columns: int | None,
    primary_index: int | None,
) -> tuple[str, list[dict[str, Any]]]:
    if count <= 0:
        return "empty", []
    if columns is not None:
        widths = _chunks(count, max(1, int(columns)))
        return "manual_columns", [
            {"count": row_count, "weights": [1.0] * row_count, "height": 1.0}
            for row_count in widths
        ]
    if count == 1:
        return "single", [{"count": 1, "weights": [1.0], "height": 1.0}]
    if count == 2:
        return "two_columns", [{"count": 2, "weights": [1.0, 1.0], "height": 1.0}]
    if count == 3:
        return "featured_plus_two", [
            {"count": 1, "weights": [1.0], "height": 1.25, "featured": True},
            {"count": 2, "weights": [1.0, 1.0], "height": 1.0},
        ]
    if count == 4:
        return "two_by_two", [
            {"count": 2, "weights": [1.0, 1.0], "height": 1.0},
            {"count": 2, "weights": [1.0, 1.0], "height": 1.0},
        ]
    if count == 5:
        return "featured_plus_four", [
            {"count": 2, "weights": [2.0, 1.0], "height": 1.15, "featured": True},
            {"count": 3, "weights": [1.0, 1.0, 1.0], "height": 1.0},
        ]
    if count == 6:
        column_count = 2
        rows = _chunks(count, column_count)
        return (
            f"{rows[0]}_by_{len(rows)}",
            [
                {"count": row_count, "weights": [1.0] * row_count, "height": 1.0}
                for row_count in rows
            ],
        )
    if count == 7:
        return "featured_plus_six", [
            {"count": 1, "weights": [1.0], "height": 1.15, "featured": True},
            {"count": 3, "weights": [1.0, 1.0, 1.0], "height": 1.0},
            {"count": 3, "weights": [1.0, 1.0, 1.0], "height": 1.0},
        ]
    if count == 8:
        column_count = 2
        rows = _chunks(count, column_count)
        return (
            f"{column_count}_by_{len(rows)}",
            [
                {"count": row_count, "weights": [1.0] * row_count, "height": 1.0}
                for row_count in rows
            ],
        )
    column_count = max(2, min(5, round(math.sqrt(count * max(aspect_ratio, 0.75)))))
    rows = _chunks(count, column_count)
    if primary_index is not None and count % 2 == 1:
        return "featured_balanced_grid", [
            {"count": 1, "weights": [1.0], "height": 1.1, "featured": True},
            *[
                {
                    "count": row_count,
                    "weights": [1.0] * row_count,
                    "height": 1.0,
                }
                for row_count in _chunks(count - 1, column_count)
            ],
        ]
    return "balanced_grid", [
        {"count": row_count, "weights": [1.0] * row_count, "height": 1.0}
        for row_count in rows
    ]


def layout_panels(
    panel_count: int,
    *,
    aspect_ratio: float = 1.45,
    columns: int | None = None,
    primary_index: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, content-aware normalized panel layout."""
    if panel_count < 0:
        raise ValueError("panel_count cannot be negative")
    template, rows = _row_recipe(
        panel_count,
        aspect_ratio=aspect_ratio,
        columns=columns,
        primary_index=primary_index,
    )
    height_total = sum(float(row["height"]) for row in rows)
    panels = []
    index = 0
    y_cursor = 0.0
    for row_index, row in enumerate(rows):
        row_height = float(row["height"]) / height_total
        weights = row["weights"]
        total_weight = sum(weights)
        x_cursor = 0.0
        for column_index, weight in enumerate(weights):
            width = float(weight) / total_weight
            role = "primary" if row.get("featured") and column_index == 0 else "supporting"
            panels.append(
                {
                    "index": index,
                    "row": row_index,
                    "column": column_index,
                    "x": round(x_cursor, 8),
                    "y": round(y_cursor, 8),
                    "width": round(width, 8),
                    "height": round(row_height, 8),
                    "weight": float(weight),
                    "role": role,
                }
            )
            x_cursor += width
            index += 1
        y_cursor += row_height
    return {
        "template": template,
        "panel_count": panel_count,
        "row_count": len(rows),
        "column_count": max((row["count"] for row in rows), default=0),
        "variable_panel_sizes": any(row.get("featured") for row in rows),
        "empty_placeholder_panels": 0,
        "read_order": "row_major_left_to_right",
        "panels": panels,
    }


def write_figure_plan(
    chart_specs: list[dict[str, Any]],
    output: Path,
    *,
    width_mm: float = 180.0,
    columns: int | None = None,
    primary_index: int | None = None,
) -> dict[str, Any]:
    page_aspect = 1.45
    layout = layout_panels(
        len(chart_specs),
        aspect_ratio=page_aspect,
        columns=columns,
        primary_index=primary_index,
    )
    payload = {
        "status": "GENERATED" if chart_specs else "NOT_GENERATED",
        "width_mm": width_mm,
        "height_mm": round(width_mm / page_aspect, 3),
        "page_aspect_ratio": page_aspect,
        "columns": layout["column_count"],
        "rows": layout["row_count"],
        "layout": layout,
        "font_family": "Arial, Helvetica, sans-serif",
        "background": "#FFFFFF",
        "panel_letters": "bold lowercase in parentheses",
        "color_tokens": COLOR_TOKENS,
        "panels": [
            {
                "index": index + 1,
                "panel": _panel_label(index),
                "chart_id": spec["id"],
                "title": spec["title"],
                "basis": spec.get("basis"),
                "decision": spec.get("decision"),
                "rectangle": layout["panels"][index] if index < len(layout["panels"]) else None,
            }
            for index, spec in enumerate(chart_specs)
        ],
        "export_strategy": {
            "png": "Render composed SVG at the requested raster size.",
            "svg": "Native vector composition.",
            "pdf": (
                "Convert the composed SVG with a local vector converter; no implicit "
                "raster fallback and no runtime network dependency."
            ),
            "pdf_status": "NOT_SUPPORTED_WITHOUT_LOCAL_VECTOR_CONVERTER",
        },
        "export_requirements": [
            "Use real captured frames and supplied chart exports only.",
            "Do not insert blank panels to force an even count.",
            "Keep a common scale and color meaning across Cases.",
            "Retain variable names and units on axes and color bars.",
        ],
    }
    _json_dump(output, payload)
    return payload


def write_publication_plan(
    chart_specs: list[dict[str, Any]],
    output: Path,
    *,
    max_panels_per_figure: int = 6,
) -> dict[str, Any]:
    maximum = max(1, int(max_panels_per_figure))
    grouped: dict[int | None, list[dict[str, Any]]] = {}
    for spec in chart_specs:
        case_id = spec.get("case_id")
        normalized_id = int(case_id) if case_id is not None else None
        grouped.setdefault(normalized_id, []).append(spec)
    ordered_case_ids = sorted(
        (case_id for case_id in grouped if case_id is not None)
    )
    if None in grouped:
        ordered_case_ids.append(None)

    output.parent.mkdir(parents=True, exist_ok=True)
    figures = []
    omitted_chart_ids = []
    selected_chart_count = 0
    for case_id in ordered_case_ids:
        candidates = grouped[case_id]
        ranked = sorted(
            candidates,
            key=lambda spec: (
                -float((spec.get("decision") or {}).get("score", 0.0)),
                str(spec.get("id", "")),
            ),
        )
        selected = ranked[:maximum]
        omitted = ranked[maximum:]
        omitted_chart_ids.extend(str(spec.get("id")) for spec in omitted)
        selected_chart_count += len(selected)
        figure_id = (
            f"case_{case_id}"
            if case_id is not None
            else "experiment_comparisons"
        )
        figure_title = (
            f"Case {case_id} Scientific Summary"
            if case_id is not None
            else "Experiment Comparisons"
        )
        plan_path = output.parent / "figure_plans" / f"{figure_id}.json"
        specs_path = output.parent / "figure_plans" / f"{figure_id}.specs.json"
        figure_plan = write_figure_plan(selected, plan_path)
        _json_dump(specs_path, selected)
        figures.append(
            {
                "figure_id": figure_id,
                "case_id": case_id,
                "title": figure_title,
                "chart_count": len(selected),
                "source_chart_count": len(candidates),
                "omitted_chart_count": len(omitted),
                "omitted_chart_ids": [
                    str(spec.get("id")) for spec in omitted
                ],
                "layout": figure_plan["layout"],
                "panels": figure_plan["panels"],
                "plan_path": plan_path.relative_to(output.parent).as_posix(),
                "specs_path": specs_path.relative_to(output.parent).as_posix(),
            }
        )

    payload = {
        "status": "GENERATED" if figures else "NOT_GENERATED",
        "selection_policy": (
            "TOP_SCIENTIFIC_VALUE_PER_CASE; analysis artifacts remain complete"
        ),
        "max_panels_per_figure": maximum,
        "source_chart_count": len(chart_specs),
        "selected_chart_count": selected_chart_count,
        "omitted_chart_count": len(omitted_chart_ids),
        "omitted_chart_ids": omitted_chart_ids,
        "figure_count": len(figures),
        "figures": figures,
        "export_strategy": (
            "Compose each figure from its selected specs and identity-matched "
            "SVG exports."
        ),
    }
    _json_dump(output, payload)
    return payload


def _svg_body(path: Path) -> tuple[ET.Element, float, float]:
    root = ET.parse(path).getroot()
    view_box = root.get("viewBox")
    if view_box:
        values = [float(value) for value in re.split(r"[,\s]+", view_box.strip()) if value]
        if len(values) == 4:
            return root, values[2], values[3]
    width = float(re.sub(r"[^0-9.]", "", root.get("width", "800")) or 800)
    height = float(re.sub(r"[^0-9.]", "", root.get("height", "450")) or 450)
    return root, width, height


def _resolve_svg_spec(
    path: Path,
    root: ET.Element,
    chart_specs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_id = {
        str(spec.get("id")): spec
        for spec in chart_specs
        if spec.get("id")
    }
    chart_id = root.get("data-pfc-chart-id")
    if chart_id and chart_id in by_id:
        return by_id[chart_id], {
            "status": "RESOLVED",
            "method": "EMBEDDED_CHART_ID",
            "chart_id": chart_id,
        }

    filename_case = re.search(r"pfc_case_(\d+)_", path.name)
    embedded_case = root.get("data-pfc-case-id")
    case_id = (
        int(embedded_case)
        if embedded_case not in (None, "", "null")
        else int(filename_case.group(1)) if filename_case else None
    )
    candidates = [
        spec for spec in chart_specs
        if case_id is None
        or (
            spec.get("case_id") is not None
            and int(spec["case_id"]) == case_id
        )
    ]
    title = root.get("data-pfc-title")
    if not title:
        text_values = [
            str(node.text).strip()
            for node in root.iter()
            if node.tag.endswith("text") and node.text and str(node.text).strip()
        ]
        title_matches = [
            candidate for candidate in candidates
            if candidate.get("title") in text_values
        ]
        if len(title_matches) == 1:
            return title_matches[0], {
                "status": "RESOLVED",
                "method": "UNIQUE_EMBEDDED_TITLE",
                "chart_id": title_matches[0]["id"],
            }
    else:
        title_matches = [
            candidate for candidate in candidates
            if str(candidate.get("title")) == title
        ]
        if len(title_matches) == 1:
            return title_matches[0], {
                "status": "RESOLVED",
                "method": "UNIQUE_EMBEDDED_TITLE",
                "chart_id": title_matches[0]["id"],
            }
    raise ValueError(
        f"Cannot resolve SVG chart identity safely for {path.name}; "
        "provide data-pfc-chart-id metadata or a unique embedded title"
    )


def compose_publication_svg(
    chart_specs: list[dict[str, Any]],
    chart_svg_dir: Path,
    output: Path,
    *,
    columns: int | None = None,
    panel_width: int | None = None,
    panel_height: int | None = None,
    scene_png: Path | None = None,
    width_px: int = 3600,
    aspect_ratio: float = 1.45,
    primary_index: int | None = None,
) -> dict[str, Any]:
    """Compose supplied panels without fabricating missing images."""
    chart_svg_dir = chart_svg_dir.resolve()
    chart_panels = sorted(
        chart_svg_dir.glob("*.svg"),
        key=lambda path: _natural_sort_key(path.name),
    )
    entries: list[
        tuple[
            str,
            Path,
            dict[str, Any],
            dict[str, Any],
            ET.Element | None,
            float,
            float,
        ]
    ] = []
    if scene_png and scene_png.is_file():
        entries.append(
            (
                "png",
                scene_png,
                {
                    "id": "viewer_scene",
                    "title": "PFC 真实计算帧场景",
                    "basis": "Current captured frame rendered by the offline Viewer.",
                },
                {
                    "status": "RESOLVED",
                    "method": "DECLARED_SCENE",
                    "chart_id": "viewer_scene",
                },
                None,
                0.0,
                0.0,
            )
        )
    for path in chart_panels:
        root_element, source_width, source_height = _svg_body(path)
        spec, identity = _resolve_svg_spec(path, root_element, chart_specs)
        entries.append(
            (
                "svg",
                path,
                {
                    "id": spec["id"],
                    "title": spec.get("title", path.stem),
                    "basis": spec.get("basis"),
                },
                identity,
                root_element,
                source_width,
                source_height,
            )
        )
    if not entries:
        plan = write_figure_plan(
            chart_specs,
            output.with_suffix(".plan.json"),
            columns=columns,
            primary_index=primary_index,
        )
        return {
            "status": "NOT_GENERATED",
            "reason": "No ECharts SVG or scene PNG exports were supplied.",
            "plan": plan,
        }

    if panel_width is not None or panel_height is not None:
        legacy_columns = max(1, int(columns or 2))
        legacy_width = max(200, int(panel_width or 900))
        legacy_height = max(120, int(panel_height or 560))
        rows = math.ceil(len(entries) / legacy_columns)
        gap = 24
        margin = 28
        width = margin * 2 + legacy_columns * legacy_width + (legacy_columns - 1) * gap
        height = margin * 2 + rows * legacy_height + (rows - 1) * gap
        layout = layout_panels(len(entries), columns=legacy_columns)
    else:
        width = max(1200, int(width_px))
        height = max(800, round(width / max(aspect_ratio, 0.5)))
        gap = max(10, round(width * 0.012))
        margin = max(16, round(width * 0.018))
        layout = layout_panels(
            len(entries),
            aspect_ratio=aspect_ratio,
            columns=columns,
            primary_index=primary_index if primary_index is not None else (0 if scene_png else None),
        )

    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "version": "1.1",
            "width": f"{width}px",
            "height": f"{height}px",
            "viewBox": f"0 0 {width} {height}",
        },
    )
    ET.SubElement(
        root,
        f"{{{SVG_NS}}}rect",
        {
            "x": "0",
            "y": "0",
            "width": str(width),
            "height": str(height),
            "fill": "#FFFFFF",
        },
    )
    content_width = width - margin * 2
    content_height = height - margin * 2
    for index, (
        kind,
        path,
        spec,
        identity,
        source_element,
        source_width,
        source_height,
    ) in enumerate(entries):
        rectangle = layout["panels"][index]
        x = margin + rectangle["x"] * content_width + gap * 0.5
        y = margin + rectangle["y"] * content_height + gap * 0.5
        cell_width = rectangle["width"] * content_width - gap
        cell_height = rectangle["height"] * content_height - gap
        label_y = y + 22
        label = _panel_label(index)
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}text",
            {
                "x": str(x),
                "y": str(label_y),
                "font-family": "Arial, Helvetica, sans-serif",
                "font-size": "22",
                "font-weight": "700",
                "fill": "#1A1A1A",
            },
        ).text = f"({label})"
        title_lines = _wrap_text(
            str(spec.get("title", "")),
            max(12, int(cell_width / 9.2)),
        )
        for line_index, line in enumerate(title_lines):
            ET.SubElement(
                root,
                f"{{{SVG_NS}}}text",
                {
                    "x": str(x + 42),
                    "y": str(label_y + line_index * 19),
                    "font-family": "Arial, Helvetica, sans-serif",
                    "font-size": "17",
                    "font-weight": "600",
                    "fill": "#1A1A1A",
                },
            ).text = line
        header_height = 24 + len(title_lines) * 19
        graphic_y = y + header_height
        graphic_height = cell_height - header_height
        if kind == "png":
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            ET.SubElement(
                root,
                f"{{{SVG_NS}}}image",
                {
                    "x": str(x),
                    "y": str(graphic_y),
                    "width": str(cell_width),
                    "height": str(graphic_height),
                    "preserveAspectRatio": "xMidYMid meet",
                    "href": f"data:image/png;base64,{payload}",
                },
            )
        else:
            source = source_element
            if source is None:
                raise ValueError(f"SVG source could not be parsed: {path}")
            scale = min(
                cell_width / max(source_width, 1),
                graphic_height / max(source_height, 1),
            )
            graphic = ET.SubElement(
                root,
                f"{{{SVG_NS}}}g",
                {"transform": f"translate({x},{graphic_y}) scale({scale:.8f})"},
            )
            for child in list(source):
                if child.get("data-pfc-embedded-title") == "1":
                    continue
                graphic.append(child)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    plan_specs = [spec for _, _, spec, _, _, _, _ in entries]
    plan = write_figure_plan(
        plan_specs,
        output.with_suffix(".plan.json"),
        columns=columns,
        primary_index=primary_index if primary_index is not None else (0 if scene_png else None),
    )
    return {
        "status": "GENERATED",
        "output": str(output),
        "panels": [str(path) for _, path, _, _, _, _, _ in entries],
        "identities": [
            {"path": str(path), **identity}
            for _, path, _, identity, _, _, _ in entries
        ],
        "panel_count": len(entries),
        "vector": True,
        "layout_template": layout["template"],
        "different_panel_sizes": layout["variable_panel_sizes"],
        "plan": plan,
        "verification": "NOT_VERIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart-specs", required=True)
    parser.add_argument("--svg-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--columns", type=int)
    parser.add_argument("--scene-png")
    parser.add_argument("--width-px", type=int, default=3600)
    parser.add_argument("--aspect-ratio", type=float, default=1.45)
    parser.add_argument("--primary-index", type=int)
    args = parser.parse_args()
    specs = json.loads(Path(args.chart_specs).read_text(encoding="utf-8"))
    result = compose_publication_svg(
        specs,
        Path(args.svg_dir),
        Path(args.out),
        columns=args.columns,
        scene_png=Path(args.scene_png) if args.scene_png else None,
        width_px=args.width_px,
        aspect_ratio=args.aspect_ratio,
        primary_index=args.primary_index,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
