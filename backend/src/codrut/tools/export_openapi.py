import argparse
import json
from pathlib import Path

from codrut.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "api" / "openapi.json"


def render_openapi_schema() -> str:
    schema = create_app().openapi()
    return json.dumps(schema, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def write_openapi_schema(output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi_schema())
    return output


def check_openapi_schema(output: Path = DEFAULT_OUTPUT) -> bool:
    if not output.exists():
        return False
    return output.read_text() == render_openapi_schema()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Codrut OpenAPI schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Snapshot output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the existing snapshot differs from the generated schema.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        if check_openapi_schema(args.output):
            print(f"OpenAPI snapshot is current: {args.output}")
            return 0
        print(f"OpenAPI snapshot is not current: {args.output}")
        return 1

    output = write_openapi_schema(args.output)
    print(f"Wrote OpenAPI snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
