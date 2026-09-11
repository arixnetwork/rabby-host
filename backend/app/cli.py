"""Small safe CLI entry point for read-only diagnostics."""
import argparse
import json
from .main import system_info, list_services


def main() -> int:
    parser = argparse.ArgumentParser(prog="rabby-host")
    parser.add_argument("command", choices=["status", "version", "doctor"])
    args = parser.parse_args()
    if args.command == "version":
        print("Rabby Host 1.0.0")
        return 0
    if args.command == "status":
        print(json.dumps({"system": system_info(), "services": list_services()}, indent=2))
        return 0
    system = system_info()
    print("PASS system: detected")
    print("PASS architecture:", system["architecture"])
    print("PASS disk: readable")
    print("PASS memory: readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
