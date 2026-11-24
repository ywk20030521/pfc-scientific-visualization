"""Plan or execute a conservative cleanup of generated intermediate data.

The command is dry-run by default. ``--apply`` additionally requires the exact
confirmation token. Standardized contracts managed by pfc-headless are rejected,
and analysis products are protected by name and by file-extension checks.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIRMATION = "CLEAN_INTERMEDIATE"
PROTECTED_NAMES = {
    "01_raw_data",
    "02_standardized_data",
    "03_analysis",
    "04_viewer",
    "05_charts",
    "06_publication_figures",
    "07_metadata",
    "report",
}
PROTECTED_SUFFIXES = {
    ".sav",
    ".prj",
    ".dat",
    ".fis",
    ".his",
    ".p2dat",
    ".p3dat",
}
INTERMEDIATE_PATTERNS = (
    "work",
    "work_*",
    "intermediate",
    "intermediate_*",
    "intermediates",
    "tmp",
    "tmp_*",
    "temp",
    "temp_*",
    ".cache",
    "__pycache__",
    ".pytest_cache",
    "failed_pipeline_attempt_*",
)


class CleanupError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contains_protected(path: Path) -> bool:
    for item in path.rglob("*"):
        if any(part in PROTECTED_NAMES for part in item.parts):
            return True
        if item.is_file() and item.suffix.lower() in PROTECTED_SUFFIXES:
            return True
    return False


def _candidate_directories(root: Path) -> list[Path]:
    candidates = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.is_symlink():
            continue
        if any(fnmatch.fnmatchcase(child.name, pattern) for pattern in INTERMEDIATE_PATTERNS):
            candidates.append(child)
    return candidates


def _files(path: Path) -> list[dict[str, Any]]:
    result = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        result.append(
            {
                "relative_path": item.relative_to(path).as_posix(),
                "size_bytes": item.stat().st_size,
                "sha256": _sha256(item),
            }
        )
    return result


def _indexed_files(root: Path) -> set[str]:
    """Files claimed by an existing output index are in use, never disposable."""
    index_path = root / "07_metadata" / "output_index.json"
    if not index_path.is_file():
        return set()
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {
        str(item.get("path"))
        for item in index.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }


def _candidate_in_use(candidate: Path, root: Path, indexed: set[str]) -> bool:
    if not indexed:
        return False
    for item in candidate.rglob("*"):
        if item.is_file() and item.relative_to(root).as_posix() in indexed:
            return True
    return False


def plan_cleanup(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise CleanupError(f"Cleanup root does not exist: {root}")
    if (root / "delivery_manifest.json").is_file():
        raise CleanupError(
            "Refusing a pfc-headless standardized contract; cleanup only "
            "pfc-scientific-visualization analysis-output roots"
        )
    if not (root / "03_analysis").is_dir() and not (root / "04_viewer").is_dir():
        raise CleanupError("Root does not look like a scientific analysis output")
    accepted = []
    skipped = []
    indexed = _indexed_files(root)
    for candidate in _candidate_directories(root):
        if _contains_protected(candidate):
            skipped.append(
                {
                    "path": candidate.relative_to(root).as_posix(),
                    "reason": "contains raw/standardized/delivery evidence or a protected file suffix",
                }
            )
            continue
        if _candidate_in_use(candidate, root, indexed):
            skipped.append(
                {
                    "path": candidate.relative_to(root).as_posix(),
                    "reason": "contains a file claimed by output_index.json (in use)",
                }
            )
            continue
        file_records = _files(candidate)
        accepted.append(
            {
                "path": candidate.relative_to(root).as_posix(),
                "file_count": len(file_records),
                "size_bytes": sum(item["size_bytes"] for item in file_records),
                "files": file_records,
            }
        )
    return {
        "generated_utc": _utc_now(),
        "root": str(root),
        "dry_run": True,
        "applied": False,
        "confirmation_token": CONFIRMATION,
        "protected_names": sorted(PROTECTED_NAMES),
        "protected_suffixes": sorted(PROTECTED_SUFFIXES),
        "candidate_patterns": list(INTERMEDIATE_PATTERNS),
        "accepted": accepted,
        "skipped": skipped,
        "accepted_bytes": sum(item["size_bytes"] for item in accepted),
    }


def apply_cleanup(root: Path, plan: dict[str, Any], confirmation: str) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise CleanupError(f"Confirmation must be exactly {CONFIRMATION!r}")
    root = root.resolve()
    for item in plan["accepted"]:
        target = (root / item["path"]).resolve()
        if root not in target.parents:
            raise CleanupError(f"Candidate escaped cleanup root: {target}")
        if target.name in PROTECTED_NAMES or target.is_symlink():
            raise CleanupError(f"Refusing protected or symlink target: {target}")
        if _contains_protected(target):
            raise CleanupError(f"Protected evidence appeared during cleanup: {target}")
        if _candidate_in_use(target, root, _indexed_files(root)):
            raise CleanupError(f"Indexed evidence appeared during cleanup: {target}")
        shutil.rmtree(target)
    result = {
        **plan,
        "dry_run": False,
        "applied": True,
        "applied_utc": _utc_now(),
        "removed": [item["path"] for item in plan["accepted"]],
    }
    log_dir = root / "07_metadata"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "cleanup_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", help="Write the dry-run plan to this JSON file")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    root = Path(args.root)
    plan = plan_cleanup(root)
    result = apply_cleanup(root, plan, args.confirm) if args.apply else plan
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
