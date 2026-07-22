from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.protected_content import (
    ProtectedContentService,
    load_protected_content_package,
    reversion_protected_content_package,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, import, or activate a protected Cody content package."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "import", "activate"):
        command = subparsers.add_parser(name)
        command.add_argument(
            "source",
            help="JSON package path, or - to read it from stdin.",
        )
    reversion = subparsers.add_parser("reversion")
    reversion.add_argument("source", help="Existing JSON package path.")
    reversion.add_argument("destination", help="New JSON package path.")
    reversion.add_argument("--package-id", required=True, help="New immutable package ID.")
    return parser


def _read_source(source: str) -> bytes:
    if source == "-":
        return sys.stdin.buffer.read()
    return Path(source).read_bytes()


async def _run(command: str, source: str) -> dict:
    package = load_protected_content_package(_read_source(source))
    if command == "validate":
        return {
            "status": "valid",
            "package_id": package.package_id,
            "checksum": package.checksum,
            "questionnaires": len(package.questionnaires),
            "email_templates": len(package.email_templates),
        }

    async with SessionLocal() as session:
        service = ProtectedContentService(session)
        try:
            result = (
                await service.import_package(package)
                if command == "import"
                else await service.activate_package(package)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return asdict(result)


def _reversion(source: str, destination: str, package_id: str) -> dict:
    destination_path = Path(destination)
    if destination_path.exists():
        raise OSError(f"Destination already exists: {destination_path}")
    package = reversion_protected_content_package(
        _read_source(source),
        package_id=package_id,
    )
    destination_path.write_text(
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "reversioned",
        "package_id": package.package_id,
        "checksum": package.checksum,
        "questionnaires": len(package.questionnaires),
        "email_templates": len(package.email_templates),
        "destination": str(destination_path),
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        output = (
            _reversion(args.source, args.destination, args.package_id)
            if args.command == "reversion"
            else asyncio.run(_run(args.command, args.source))
        )
    except (DomainError, OSError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
