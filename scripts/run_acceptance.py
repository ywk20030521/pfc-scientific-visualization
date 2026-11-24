"""Optional browser acceptance + real publication export for a generated Viewer.

This script closes the loop that ``run_pipeline.py`` deliberately leaves as
NOT_VERIFIED.  It does NOT modify the standardized input or the analysis
result's 03/04 trees; it only writes into 06_publication_figures/ and
07_metadata/ acceptance files.

Usage::

    python run_acceptance.py --analysis-root <AnalysisResult> [--browser <path>]

It invokes ``verify_lazy_viewer.mjs --export-dir`` (raw CDP, no npm
dependency, produces real PNG/SVG), then ``publication.py`` to compose the
publication SVG from the exported per-chart SVGs, and finally writes an
acceptance report with genuine PASS/FAIL/NOT_VERIFIED gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_acceptance(
    analysis_root: Path,
    *,
    browser: str | None = None,
    node: str = "node",
) -> dict[str, Any]:
    analysis_root = analysis_root.resolve()
    viewer = analysis_root / "04_viewer" / "scientific_viewer.html"
    if not viewer.is_file():
        raise FileNotFoundError(f"No Viewer found: {viewer}")

    pub_root = analysis_root / "06_publication_figures"
    meta_root = analysis_root / "07_metadata"
    export_dir = pub_root / "exports"
    report_path = meta_root / "browser_acceptance.json"
    cmd = [node, str(SCRIPT_DIR / "verify_lazy_viewer.mjs"),
           "--file", str(viewer), "--export-dir", str(export_dir),
           "--report", str(report_path)]
    if browser:
        cmd += ["--browser", browser]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    browser_pass = False
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        browser_pass = bool(report.get("pass"))

    # Only SVGs whose embedded chart id matches a real chart spec can be
    # resolved by publication.py.  Viewer-internal panels
    # (``viewer:current_frame:*``) and ball_history.svg are excluded.
    spec_path = analysis_root / "03_analysis" / "chart_specs.json"
    known_ids = set()
    if spec_path.is_file():
        for spec in json.loads(spec_path.read_text(encoding="utf-8")):
            if spec.get("id"):
                known_ids.add(str(spec["id"]))
    exported_svgs = []
    if export_dir.is_dir():
        for path in export_dir.glob("*.svg"):
            head = path.read_text(encoding="utf-8", errors="replace")[:2000]
            import re as _re
            m = _re.search(r'data-pfc-chart-id="([^"]+)"', head)
            if m and m.group(1) in known_ids:
                exported_svgs.append(path)
    exported_svgs.sort()
    composed = pub_root / "composed_figure.svg"
    composition_status = "NOT_GENERATED"
    composition_error = None
    if exported_svgs:
        # publication.py globs *.svg in --svg-dir; isolate chart panels there.
        import shutil
        panel_dir = pub_root / "chart_panels"
        if panel_dir.exists():
            shutil.rmtree(panel_dir)
        panel_dir.mkdir(parents=True)
        for svg in exported_svgs:
            shutil.copy2(svg, panel_dir / svg.name)
        spec = spec_path
        compose_cmd = [
            sys.executable, str(SCRIPT_DIR / "charts" / "publication.py"),
            "--chart-specs", str(spec),
            "--svg-dir", str(panel_dir),
            "--out", str(composed),
        ]
        cp = subprocess.run(compose_cmd, capture_output=True, text=True)
        if cp.returncode == 0 and composed.is_file() and composed.stat().st_size > 0:
            composition_status = "GENERATED"
        else:
            composition_error = (cp.stderr or cp.stdout)[-800:]

    result = {
        "status": "ACCEPTED" if browser_pass and composition_status == "GENERATED"
                  else "PARTIAL",
        "generated_utc": _utc(),
        "browser_acceptance": {
            "status": "PASS" if browser_pass else "FAIL",
            "report": str(report_path) if report_path.is_file() else None,
            "stderr": proc.stderr[-800:],
        },
        "publication_export": {
            "status": composition_status,
            "svg_count": len(exported_svgs),
            "composed_figure": str(composed) if composed.is_file() else None,
            "error": composition_error,
        },
    }
    _dump(meta_root / "acceptance_result.json", result)

    # Update output_contract.json truthfully, in place.
    contract_path = meta_root / "output_contract.json"
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        for item in contract.get("items", []):
            if item.get("id") == "offline_viewer":
                item["verification"] = "PASS" if browser_pass else "FAIL"
            if item.get("id") == "publication_composed_svg" and composition_status == "GENERATED":
                item["status"] = "GENERATED"
                item["path"] = "06_publication_figures/composed_figure.svg"
                item.pop("reason", None)
        contract["verification"] = "PASS" if result["status"] == "ACCEPTED" else "PARTIAL"
        _dump(contract_path, contract)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--browser")
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    result = run_acceptance(Path(args.analysis_root), browser=args.browser, node=args.node)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
