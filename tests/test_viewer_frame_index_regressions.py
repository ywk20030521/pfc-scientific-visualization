"""Regression tests for missing values and the unified frame-index contract."""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis import analyze_experiment
from viewer import build_viewer
from viewer.payload_builder import _selected_indices, _slice_chart


def _registered_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    start = text.find("(") + 1
    decoder = json.JSONDecoder()
    for offset in range(start, len(text)):
        if text[offset] not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No registered JSON payload in {path}")


def _write_synthetic_case(root: Path, case_id: int, frames: int = 351) -> dict:
    case_root = root / "cases" / f"case_{case_id}"
    case_root.mkdir(parents=True, exist_ok=True)
    frame_index = np.arange(frames, dtype=np.int64)
    ball_id = np.full(frames, case_id + 1, dtype=np.int64)
    xyz = np.column_stack(
        [
            1.0e-12 * frame_index.astype(np.float64) ** 3,
            1.0e-13 * frame_index.astype(np.float64) ** 2,
            np.full(frames, 2.5, dtype=np.float64),
        ]
    )
    force = np.asarray(
        [
            np.nan if index == 0
            else 0.0 if index == 50
            else float(index * 10)
            for index in frame_index
        ],
        dtype=np.float64,
    )
    empty_wall = np.zeros(0, dtype=np.float64)
    empty_int = np.zeros(0, dtype=np.int64)
    arrays = {
        "cycle": frame_index + 1,
        "mechanical_time_total": frame_index.astype(np.float64) * 0.01,
        "frame_offsets": np.arange(frames + 1, dtype=np.int64),
        "ball_id": ball_id,
        "ball_xyz": xyz,
        "ball_radius": np.full(frames, 0.1, dtype=np.float64),
        "ball_frame_index": frame_index,
        "wall_offsets": np.zeros(frames + 1, dtype=np.int64),
        "wall_id": empty_int,
        "wall_vertex_id": empty_int,
        "wall_vertex_xyz": np.zeros((0, 3), dtype=np.float64),
        "fracture_event_id": empty_int,
        "fracture_cycle": empty_int,
        "fracture_mechanical_time_total": empty_wall,
        "fracture_mode": np.zeros(0, dtype=np.int8),
        "fracture_position": np.zeros((0, 3), dtype=np.float64),
        "fracture_normal": np.zeros((0, 3), dtype=np.float64),
        "fracture_diameter": empty_wall,
        "top_force_n": force,
        "bottom_force_n": force.copy(),
        "platen_distance_m": 2.5 - 0.001 * frame_index.astype(np.float64),
    }
    np.savez_compressed(case_root / "arrays.npz", **arrays)
    (case_root / "static.json").write_text(
        json.dumps(
            {
                "balls": [
                    {
                        "id": case_id + 1,
                        "x": 0.0,
                        "y": 0.0,
                        "z": 2.5,
                        "radius": 0.1,
                    }
                ],
                "walls": [],
            }
        ),
        encoding="utf-8",
    )
    return {
        "schema_version": "1.0.0",
        "case_id": case_id,
        "label": f"Case {case_id}",
        "run_id": f"synthetic_case_{case_id}",
        "dimension": 3,
        "source_format": "MOCK",
        "frame_count": frames,
        "arrays_path": f"cases/case_{case_id}/arrays.npz",
        "channels": [],
        "entity_groups": [{"entity_type": "ball", "source": "REAL_PFC"}],
        "metadata": {
            "geometry": {
                "dimension": 3,
                "axis": "z",
                "axis_index": 2,
                "height0": 2.5,
                "area0": 4.0,
            },
            "ball_count_min": 1,
            "ball_count_max": 1,
            "event_count": 0,
        },
    }


class FrameIndexRegressionTests(unittest.TestCase):
    def test_351_frames_sample_to_8_with_aligned_missing_first_derivatives(self):
        source_count = 351
        selected = _selected_indices(source_count, 8)
        source_indices = list(range(source_count))
        times = [index * 0.01 for index in source_indices]
        speed = [None] + [2.0 + index * 0.01 for index in range(1, source_count)]
        acceleration = [None] + [3.0 + index * 0.02 for index in range(1, source_count)]

        for values in (speed, acceleration):
            chart = _slice_chart(
                {
                    "case_id": 0,
                    "type": "line",
                    "source_indices": source_indices,
                    "x": {"name": "机械时间", "unit": "s", "data": times},
                    "y": {"name": "派生量", "unit": "m/s", "data": values},
                    "display": {
                        "x": {
                            "values": [str(value) for value in times],
                            "tooltip_values": list(times),
                        },
                        "y": {
                            "values": ["—" if value is None else str(value) for value in values],
                            "tooltip_values": list(values),
                        },
                    },
                },
                selected,
                source_count,
            )
            self.assertEqual(chart["source_indices"], selected)
            self.assertEqual(len(chart["x"]["data"]), 8)
            self.assertEqual(len(chart["y"]["data"]), 8)
            self.assertIsNone(chart["y"]["data"][0])
            self.assertEqual(chart["x"]["data"], [times[index] for index in selected])
            self.assertEqual(chart["y"]["data"][1:], [values[index] for index in selected[1:]])
            self.assertEqual(len(chart["display"]["x"]["values"]), 8)
            self.assertEqual(len(chart["display"]["y"]["tooltip_values"]), 8)

    def test_payload_history_preserves_source_and_viewer_frame_indices(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            standardized = root / "Standardized"
            standardized.mkdir()
            cases = [
                _write_synthetic_case(standardized, 0),
                _write_synthetic_case(standardized, 1),
            ]
            (standardized / "experiment.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "title": "351 Frame Regression",
                        "cases": cases,
                        "data_boundary": {"mode": "READ_ONLY"},
                    }
                ),
                encoding="utf-8",
            )
            analysis_root = root / "03_analysis"
            analyze_experiment(standardized, analysis_root)
            output = root / "04_viewer" / "scientific_viewer.html"
            build_viewer(
                standardized,
                output,
                analysis_root=analysis_root,
                max_frames=8,
                title="351 Frame Regression",
            )

            expected_sources = _selected_indices(351, 8)
            meta = _registered_json(
                output.parent / "data" / "cases" / "case_0" / "meta.js"
            )
            self.assertEqual(meta["sourceFrameCount"], 351)
            self.assertEqual(meta["viewerFrameCount"], 8)
            self.assertEqual(
                [item["sourceIndex"] for item in meta["frames"]],
                expected_sources,
            )
            self.assertEqual(meta["historyFrameStride"], 8)

            charts = _registered_json(
                output.parent / "data" / "cases" / "case_0" / "charts.js"
            )
            temporal = [
                chart for chart in charts
                if chart.get("source_indices")
                and chart.get("x", {}).get("unit") in {"s", "cycle"}
            ]
            self.assertTrue(temporal)
            for chart in temporal:
                self.assertEqual(chart["source_indices"], expected_sources)
                self.assertEqual(len(chart["x"]["data"]), 8)
                if chart.get("y"):
                    self.assertEqual(len(chart["y"]["data"]), 8)
                for series in chart.get("series", []):
                    self.assertEqual(len(series["data"]), 8)
                expected_x = (
                    [item["time"] for item in meta["frames"]]
                    if chart["x"]["unit"] == "s"
                    else [item["cycle"] for item in meta["frames"]]
                )
                self.assertEqual(chart["x"]["data"], expected_x)

            speed = next(
                chart for chart in charts
                if chart["id"] == "case_0:speed_time"
            )
            acceleration = next(
                chart for chart in charts
                if chart["id"] == "case_0:acceleration_time"
            )
            self.assertIsNone(speed["y"]["data"][0])
            self.assertIsNone(acceleration["y"]["data"][0])

            history = _registered_json(
                output.parent
                / "data"
                / "cases"
                / "case_0"
                / "histories"
                / "bucket_001.js"
            )
            entry = next(item for item in history["entries"] if item["id"] == 1)
            rows = np.frombuffer(
                base64.b64decode(entry["data"]),
                dtype="<f4",
            ).reshape(-1, 8)
            self.assertEqual(len(rows), 8)
            self.assertEqual(
                [int(round(value)) for value in rows[:, 0]],
                expected_sources,
            )
            self.assertEqual(
                [int(round(value)) for value in rows[:, 1]],
                list(range(8)),
            )
            self.assertEqual(
                [int(round(value)) for value in rows[:, 0]],
                [meta["frames"][index]["sourceIndex"] for index in range(8)],
            )


if __name__ == "__main__":
    unittest.main()
