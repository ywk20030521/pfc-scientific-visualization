"""Create an installable ZIP of this Skill without executing runtime tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from packaging import package_skill_zip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = package_skill_zip(Path(args.skill_root), Path(args.out))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
