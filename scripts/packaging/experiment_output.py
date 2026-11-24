"""Create the analysis-result index and package the Skill."""
from __future__ import annotations

import hashlib
import json
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
