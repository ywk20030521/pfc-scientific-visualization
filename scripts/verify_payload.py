"""Verify chunked Viewer payload values against standardized NPZ data."""
from __future__ import annotations

import argparse
import base64
import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np


class VerificationError(RuntimeError):
    pass


def _extract_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise VerificationError(f"No JSON payload in {path}")
    return json.loads(text[start : end + 1])


def _decode(base64_text: str, dtype: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    values = np.frombuffer(base64.b64decode(base64_text), dtype=dtype)
    return values.reshape(shape) if shape else values


def _frame_payload(meta: dict[str, Any], case_dir: Path, frame_index: int) -> dict[str, Any]:
    frame_meta = meta["frames"][frame_index]
    chunk_path = case_dir / "chunks" / f"chunk_{frame_meta['chunk']:03d}.js"
    chunk = _extract_json(chunk_path)
    return chunk["frames"][frame_meta["chunkOffset"]]


def verify_payload(experiment_root: Path, data_root: Path, samples_per_case: int = 3) -> dict[str, Any]:
    experiment_root = experiment_root.resolve()
    data_root = data_root.resolve()
    experiment = json.loads((experiment_root / "experiment.json").read_text(encoding="utf-8"))
    catalog = _extract_json(data_root / "catalog.js")
    failures: list[str] = []
    case_reports = []
    rng = random.Random(20261108)

    for case in experiment["cases"]:
        case_id = int(case["case_id"])
        summary = next((item for item in catalog["cases"] if int(item["id"]) == case_id), None)
        if summary is None:
            failures.append(f"Case {case_id}: catalog record missing")
            continue
        case_dir = data_root / "cases" / f"case_{case_id}"
        meta = _extract_json(case_dir / "meta.js")
        arrays_path = Path(case["arrays_path"])
        arrays_path = arrays_path if arrays_path.is_absolute() else experiment_root / arrays_path
        with np.load(arrays_path, allow_pickle=False) as arrays:
            source_count = len(arrays["cycle"])
            if int(meta["sourceFrameCount"]) != source_count:
                failures.append(f"Case {case_id}: source frame count mismatch")
            if int(meta["viewerFrameCount"]) != int(summary["viewerFrameCount"]):
                failures.append(f"Case {case_id}: summary/meta frame count mismatch")
            cycles = [int(row["cycle"]) for row in meta["frames"]]
            if any(right <= left for left, right in zip(cycles, cycles[1:])):
                failures.append(f"Case {case_id}: viewer Cycles are not strictly increasing")
            chosen = sorted(
                {0, len(meta["frames"]) - 1, *[
                    rng.randrange(len(meta["frames"])) for _ in range(max(0, samples_per_case - 2))
                ]}
            )
            frame_checks = []
            for viewer_index in chosen:
                frame_meta = meta["frames"][viewer_index]
                source_index = int(frame_meta["sourceIndex"])
                frame = _frame_payload(meta, case_dir, viewer_index)
                start = int(arrays["frame_offsets"][source_index])
                end = int(arrays["frame_offsets"][source_index + 1])
                ids = _decode(frame["ids"], "<u4")
                xyz = _decode(frame["xyz"], "<f4", (-1, 3))
                displacement = _decode(frame["displacement"], "<f4")
                speed = _decode(frame["speed"], "<f4")
                radius = _decode(frame["radius"], "<f4")
                expected_ids = np.asarray(arrays["ball_id"][start:end], dtype=np.uint32)
                if not np.array_equal(ids, expected_ids):
                    failures.append(f"Case {case_id} frame {viewer_index}: Ball IDs differ")
                if not np.allclose(
                    xyz,
                    np.asarray(arrays["ball_xyz"][start:end], dtype=np.float32),
                    rtol=2e-6,
                    atol=1e-9,
                    equal_nan=True,
                ):
                    failures.append(f"Case {case_id} frame {viewer_index}: XYZ differs")
                if not np.allclose(
                    radius,
                    np.asarray(arrays["ball_radius"][start:end], dtype=np.float32),
                    rtol=2e-6,
                    atol=1e-9,
                    equal_nan=True,
                ):
                    failures.append(f"Case {case_id} frame {viewer_index}: radius differs")
                if int(frame["cycle"]) != int(arrays["cycle"][source_index]):
                    failures.append(f"Case {case_id} frame {viewer_index}: Cycle differs")
                if not math.isclose(
                    float(frame["time"]),
                    float(arrays["mechanical_time_total"][source_index]),
                    rel_tol=1e-12,
                    abs_tol=1e-15,
                ):
                    failures.append(f"Case {case_id} frame {viewer_index}: mechanical time differs")
                frame_checks.append(
                    {
                        "viewer_index": viewer_index,
                        "source_index": source_index,
                        "cycle": int(frame["cycle"]),
                        "ball_count": int(len(ids)),
                        "displacement_finite": int(np.isfinite(displacement).sum()),
                        "speed_finite": int(np.isfinite(speed).sum()),
                    }
                )

            history_checks = []
            if meta["frames"]:
                sample_frame = meta["frames"][rng.randrange(len(meta["frames"]))]
                start = int(arrays["frame_offsets"][sample_frame["sourceIndex"]])
                end = int(arrays["frame_offsets"][sample_frame["sourceIndex"] + 1])
                if end > start:
                    ball_row = rng.randrange(start, end)
                    ball_id = int(arrays["ball_id"][ball_row])
                    bucket = ball_id % int(meta["historyBucketCount"])
                    histories = _extract_json(case_dir / "histories" / f"bucket_{bucket:03d}.js")
                    entry = next((item for item in histories["entries"] if int(item["id"]) == ball_id), None)
                    if entry is None:
                        failures.append(f"Case {case_id}: history for Ball {ball_id} missing")
                    else:
                        stride = 5 + len(meta.get("historyMetrics", ["displacement", "speed"]))
                        rows = _decode(entry["data"], "<f4").reshape(-1, stride)
                        matching = rows[np.rint(rows[:, 0]).astype(np.int64) == int(sample_frame["index"])]
                        if not len(matching):
                            failures.append(f"Case {case_id}: Ball {ball_id} history lacks selected frame")
                        else:
                            if not np.allclose(
                                matching[0, 2:5],
                                np.asarray(arrays["ball_xyz"][ball_row], dtype=np.float32),
                                rtol=2e-6,
                                atol=1e-9,
                                equal_nan=True,
                            ):
                                failures.append(f"Case {case_id}: Ball {ball_id} history XYZ differs")
                        history_checks.append({"ball_id": ball_id, "bucket": bucket, "row_count": int(len(rows))})
            case_reports.append(
                {
                    "case_id": case_id,
                    "source_frames": source_count,
                    "viewer_frames": int(meta["viewerFrameCount"]),
                    "frame_policy": summary["frameStatus"],
                    "frame_checks": frame_checks,
                    "history_checks": history_checks,
                }
            )

    return {
        "status": "PASS" if not failures else "FAIL",
        "experiment": experiment.get("experiment_id"),
        "payload": str(data_root),
        "case_count": len(case_reports),
        "checks_per_case": samples_per_case,
        "cases": case_reports,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--report")
    parser.add_argument("--samples-per-case", type=int, default=3)
    args = parser.parse_args()
    result = verify_payload(
        Path(args.experiment_root),
        Path(args.data_root),
        samples_per_case=args.samples_per_case,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
