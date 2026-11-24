"""Build the chunked scientific Viewer from already standardized data.

This command never starts PFC or recomputes experiment data.
"""

from viewer.external_builder import main


if __name__ == "__main__":
    raise SystemExit(main())
