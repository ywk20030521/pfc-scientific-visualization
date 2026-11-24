"""Command-line entry point for conservative intermediate-data cleanup."""

from maintenance.cleanup_delivery import main


if __name__ == "__main__":
    raise SystemExit(main())
