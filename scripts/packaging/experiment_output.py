"""Create the analysis-result index and package the Skill."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUTPUT_DIRS = (
    "03_analysis",
    "04_viewer",
    "05_charts",
    "06_publication_figures",
    "07_metadata",
    "report",
)

REQUIRED_DIRS = frozenset({"03_analysis", "04_viewer", "07_metadata"})
DISPLAY_DIRS = frozenset({"04_viewer", "05_charts"})


def _file_role(relative: str) -> str:
    top = relative.split("/", 1)[0]
    if top.startswith("0") or top == "report":
        return "scientific_delivery"
    return "auxiliary"


def _required_for(relative: str, package: str) -> bool:
    top = relative.split("/", 1)[0]
    if package == "display":
        return top in DISPLAY_DIRS
    return top in REQUIRED_DIRS or top in {"05_charts", "06_publication_figures", "report"}


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


def materialize_output_contract(
    output_root: Path,
    *,
    title: str = "PFC Scientific Analysis",
    data_boundary: str = "UNKNOWN",
) -> dict[str, Any]:
    output_root = output_root.resolve()
    for name in OUTPUT_DIRS:
        (output_root / name).mkdir(parents=True, exist_ok=True)
    generated = []
    not_generated = []
    files = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        if "07_metadata" in path.parts and path.name == "output_index.json":
            continue
        rel = path.relative_to(output_root).as_posix()
        record = {
            "path": rel,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "file_role": _file_role(rel),
            "required_for_scientific_package": _required_for(rel, "scientific"),
            "required_for_display_package": _required_for(rel, "display"),
            "run_id": None,
        }
        files.append(record)
        generated.append(rel)
    for name in OUTPUT_DIRS:
        if not any(rel.startswith(name + "/") for rel in generated):
            not_generated.append(name + "/")
    index = {
        "title": title,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_boundary": data_boundary,
        "status_model": {
            "GENERATED": "file was actually produced",
            "NOT_GENERATED": "not produced",
            "NOT_CAPTURED": "source experiment did not capture it",
            "NOT_SUPPORTED": "system cannot generate it",
            "INVALID": "data/result failed an integrity check",
            "NOT_VERIFIED": "implemented or generated without acceptance testing",
        },
        "actual_generation": {
            "generated": generated,
            "not_generated": not_generated,
        },
        "verification": {
            "status": "NOT_VERIFIED",
            "reason": "This delivery package was assembled without running PFC, browser, integration, or test programs.",
        },
        "files": files,
    }
    _json_dump(output_root / "07_metadata" / "output_index.json", index)
    return index


def package_experiment(
    output_root: Path,
    destination: Path,
    *,
    package: str = "scientific",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a verified package in a temp file, then publish atomically.

    package='scientific' includes the full analysis output tree;
    package='display' includes only 04_viewer + 05_charts (no raw/standardized
    scientific data is copied into the archive).
    """
    if package not in {"scientific", "display"}:
        raise ValueError(f"Unsupported package type: {package}")
    output_root = output_root.resolve()
    destination = destination.resolve()
    index_path = output_root / "07_metadata" / "output_index.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"output_index.json missing: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    included = [
        item for item in index.get("files", [])
        if _required_for(str(item.get("path", "")), package)
    ]
    if not included:
        raise ValueError(f"No files selected for {package} package")

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in included:
                relative = str(item["path"])
                source = output_root / relative
                if not source.is_file():
                    raise FileNotFoundError(f"Indexed file missing: {source}")
                digest = _sha256(source)
                if digest != item.get("sha256"):
                    raise ValueError(f"Indexed hash mismatch: {relative}")
                archive.write(source, relative)
            archive.writestr(
                "package_manifest.json",
                json.dumps(
                    {
                        "status": "GENERATED",
                        "package": package,
                        "run_id": run_id,
                        "source_index_sha256": _sha256(index_path),
                        "files": included,
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
            )
        with zipfile.ZipFile(temp_path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f"Corrupt archive member: {bad}")
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {
        "status": "GENERATED",
        "package": package,
        "run_id": run_id,
        "path": str(destination),
        "file_count": len(included),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "integrity": "PASS",
    }


def package_skill_zip(skill_root: Path, output_zip: Path) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    output_zip = output_zip.resolve()
    if not (skill_root / "SKILL.md").is_file():
        raise ValueError("Skill root does not contain SKILL.md")
    if output_zip == skill_root or skill_root in output_zip.parents and output_zip.name == skill_root.name:
        raise ValueError("Choose a ZIP path outside the Skill directory")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(skill_root.rglob("*")):
            relative = path.relative_to(skill_root)
            if (
                not path.is_file()
                or path.resolve() == output_zip
                or any(part in {".git", "__pycache__", ".pytest_cache", "validation_output", "build"} for part in relative.parts)
                or path.name.endswith(".zip")
            ):
                continue
            archive.write(path, (Path(skill_root.name) / relative).as_posix())
    return {
        "status": "GENERATED",
        "path": str(output_zip),
        "bytes": output_zip.stat().st_size,
        "sha256": _sha256(output_zip),
    }
