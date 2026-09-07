from __future__ import annotations

import argparse
import json
import sys

import database_safety


def main() -> int:
    parser = argparse.ArgumentParser(description="TV Manager database/config protection utility")
    parser.add_argument("--startup", action="store_true", help="Create a safe startup backup if possible")
    parser.add_argument("--scan", action="store_true", help="Scan available database backups")
    parser.add_argument("--backup", action="store_true", help="Create a safe database and config backup")
    parser.add_argument("--reason", default="manual", help="Backup reason label")
    parser.add_argument("--include-secrets", action="store_true", help="Include full .env values in config backup")
    args = parser.parse_args()

    try:
        if args.scan:
            print(json.dumps(database_safety.scan_backups(), indent=2, default=str))
            return 0
        if args.startup or args.backup:
            reason = "startup" if args.startup and args.reason == "manual" else args.reason
            result = database_safety.protect_now(reason=reason, include_config=True, include_secrets=args.include_secrets)
            print(json.dumps(result, indent=2, default=str))
            return 0 if result.get("ok") else 2
        parser.print_help()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Database protection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
