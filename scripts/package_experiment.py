"""Create a scientific or lightweight display package from an analysis output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from packaging import package_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--package", choices=["scientific", "display"], default="scientific"
    )
    parser.add_argument("--run-id")
    parser.add_argument("--report")
    args = parser.parse_args()
    result = package_experiment(
        Path(args.output_root),
        Path(args.destination),
        package=args.package,
        run_id=args.run_id,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
