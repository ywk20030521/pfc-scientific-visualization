"""Package a generated offline viewer directory into a single shareable ZIP.

Usage:
    python scripts/viewer/package_viewer.py <viewer_root> <output.zip>

The HTML must stay next to its `viewer/` and `data/` directories. Sending only
the HTML will not work because vendor scripts and frame data are loaded as
relative files. A ZIP preserves the relative paths and keeps the viewer fully
offline after extraction.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def package(viewer_root: Path, output: Path) -> dict[str, object]:
    viewer_root = viewer_root.resolve()
    output = output.resolve()
    html = viewer_root / "scientific_viewer.html"
    if not html.is_file():
        raise SystemExit(f"Missing scientific_viewer.html in {viewer_root}")
    for required in ("viewer", "data"):
        if not (viewer_root / required).is_dir():
            raise SystemExit(f"Missing {required}/ in {viewer_root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in viewer_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(viewer_root).as_posix())
    return {
        "viewer_root": str(viewer_root),
        "zip": str(output),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
        "zip_bytes": output.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer_root", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(package(args.viewer_root, args.output_zip), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
