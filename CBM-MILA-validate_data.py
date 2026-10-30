#!/usr/bin/env python3
"""Validate the published CBM Mila dataset before an automated Git push."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scraper  # noqa: E402  (the repository root is intentionally added above)


def read_json(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read valid JSON from {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CBM Mila's data/data.json")
    parser.add_argument(
        "--previous",
        type=Path,
        help="Optional previous dataset used to detect a decrease in played matches.",
    )
    parser.add_argument(
        "--accept-regression",
        action="store_true",
        help="Allow an intentional official correction that decreases played matches.",
    )
    args = parser.parse_args()

    if scraper.jsonschema is None:
        print("Validation cannot continue: the 'jsonschema' dependency is not installed.", file=sys.stderr)
        return 2

    data_path = ROOT / "data" / "data.json"
    schema_path = ROOT / "data" / "schema.json"
    status_path = ROOT / "data" / "status.json"
    if not schema_path.is_file():
        print(f"Validation failed: required schema file is missing: {schema_path}", file=sys.stderr)
        return 1

    data = read_json(data_path)
    if data is None:
        print(f"Validation failed: {data_path} is missing or is not a JSON object.", file=sys.stderr)
        return 1

    status = read_json(status_path)
    if status is None:
        print(f"Validation failed: {status_path} is missing or is not a JSON object.", file=sys.stderr)
        return 1
    queue = status.get("queuedNotifications", {})
    if not isinstance(queue, dict):
        print("Validation failed: queuedNotifications must be a JSON object.", file=sys.stderr)
        return 1
    if not isinstance(queue.get("events", []), list) or not isinstance(queue.get("telegram", []), list):
        print("Validation failed: queued notification collections must be JSON arrays.", file=sys.stderr)
        return 1
    if not isinstance(status.get("notificationEvents", {}), dict):
        print("Validation failed: notificationEvents must be a JSON object.", file=sys.stderr)
        return 1

    previous_data = None
    if args.previous:
        previous_data = read_json(args.previous)
        if previous_data is None:
            print(f"Validation failed: previous dataset is missing or invalid: {args.previous}", file=sys.stderr)
            return 1

    errors = scraper.validate_dataset(
        data,
        previous_data=previous_data,
        schema_path=str(schema_path),
        accept_regression=args.accept_regression,
    )
    if errors:
        print("Dataset validation failed; the workflow must not publish these data:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("Dataset validation passed: JSON Schema and club/standings sanity checks are OK.")
    if previous_data is not None:
        print("Previous-data comparison passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
