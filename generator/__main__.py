"""CLI: python -m generator generate|validate."""

import argparse
import sys

from . import __version__
from .output import build_artifacts, publish
from .schema import ValidationError, load_scenario
from .validate import validate_dataset


def parser():
    result = argparse.ArgumentParser(
        description="Deterministic synthetic alert-episode datasets"
    )
    result.add_argument("--version", action="version", version=__version__)
    commands = result.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="materialize a new synthetic-oracle dataset"
    )
    generate.add_argument("--scenario", required=True, help="authored scenario.yaml")
    generate.add_argument(
        "--seed",
        required=True,
        type=int,
        help="signed 64-bit root seed (zero is valid)",
    )
    generate.add_argument(
        "--output", required=True, help="new output directory; its parent must exist"
    )
    validate = commands.add_parser(
        "validate", help="check schema and semantic invariants"
    )
    target = validate.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--scenario", help="validate authored scenario without sampling"
    )
    target.add_argument(
        "--dataset", help="validate the four materialized dataset files"
    )
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            scenario, raw, _ = load_scenario(args.scenario)
            artifacts, warnings = build_artifacts(scenario, args.seed, raw)
            publish(artifacts, args.output)
            message = f"Generated {args.output} (seed {args.seed})"
        elif args.scenario:
            _, _, warnings = load_scenario(args.scenario)
            message = f"Valid scenario: {args.scenario}"
        else:
            warnings = validate_dataset(args.dataset)
            message = f"Valid dataset: {args.dataset}"
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(message)
        return 0
    except (ValidationError, OSError) as exc:
        message = str(exc)
        if args.command == "generate" and message.startswith("scenario.yaml:"):
            message = args.scenario + message[len("scenario.yaml") :]
        print(f"error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
