import argparse
from pathlib import Path
import sys

from .data import DataError, decimal_units, load_dataset
from .measure import run
from .reporting import publish, render


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure law firm visibility in recorded model answers."
    )
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help="Directory with catalog.json and answers.jsonl",
    )
    parser.add_argument(
        "--budget-usd", required=True, help="Maximum modeled spend in USD"
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="New report directory, or an identical previous result",
    )
    args = parser.parse_args(argv)
    try:
        limit = decimal_units(args.budget_usd, 9)
        report = run(load_dataset(args.data), limit)
        publish(args.out, render(report))
    except (DataError, OSError) as error:
        print(f"amlaw-index: {error}", file=sys.stderr)
        return 2
    coverage = report["coverage"]
    print(
        f"{coverage['analyzed']}/{coverage['expected']} answers analyzed, "
        f"USD {report['budget']['modeled_spend_usd']} modeled spend. Report: {args.out / 'index.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
