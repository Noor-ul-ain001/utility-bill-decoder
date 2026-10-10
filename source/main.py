"""Command-line entry point.

Examples:
    python main.py --bills ../test/bills --csv ../test/csv --out ../output
    python main.py --bills ../test/bills --csv ../test/csv --out ../output --only KESC_0002 --no-cache
    python main.py --bills ../train/bills --demo
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import config
import pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Utility Bill Decoder: fill level1.csv / level2.csv from bill images.")
    parser.add_argument("--bills", type=Path, default=config.DEFAULT_TEST_BILLS, help="folder of bill images")
    parser.add_argument("--csv", type=Path, default=config.DEFAULT_TEST_CSV, help="folder with level1.csv / level2.csv templates")
    parser.add_argument("--out", type=Path, default=config.DEFAULT_OUTPUT, help="output folder")
    parser.add_argument("--only", action="append", default=None, metavar="BILL_ID",
                        help="process only this bill id (repeatable, or comma-separated)")
    parser.add_argument("--no-cache", action="store_true", help="ignore cached extractions and answers")
    parser.add_argument("--level", choices=("1", "2", "all"), default="all", help="which CSV(s) to generate")
    parser.add_argument("--demo", action="store_true", help="print Level 1 JSON for every image in --bills (no CSV needed)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    return parser.parse_args(argv)


def run_demo(args: argparse.Namespace) -> int:
    images = pipeline.list_bill_images(args.bills)
    if args.only:
        images = [p for p in images if p.stem in _only(args)]
    if not images:
        print(f"No bill images found in {args.bills}", file=sys.stderr)
        return 1
    failures = 0
    for index, image in enumerate(images, start=1):
        print(f"\n[{index}/{len(images)}] {image.stem}", flush=True)
        result = pipeline.process_bill(image, image.stem, args.out / "cache", use_cache=not args.no_cache)
        if result.error:
            failures += 1
            print(f"  FAILED: {result.error}")
        print(json.dumps(result.level1, ensure_ascii=False, indent=2))
        if result.extraction:
            for check in result.extraction.checks:
                mark = "PASS" if check.passed else "WARN"
                print(f"  [{mark}] {check.check}: {check.detail}")
    print(f"\nDone: {len(images) - failures} OK, {failures} failed.")
    return 0 if failures == 0 else 2


def _only(args: argparse.Namespace) -> set[str]:
    return {item.strip() for value in args.only or [] for item in value.split(",") if item.strip()}


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; bill text can contain Urdu.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        config.check_provider()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    if not config.API_KEY:
        print("Warning: API_KEY is not set; only cached bills can be processed.", file=sys.stderr)

    print(f"Utility Bill Decoder · model {config.MODEL_PROVIDER}:{config.MODEL_NAME}")
    if args.demo:
        return run_demo(args)

    started = time.monotonic()
    try:
        summary = pipeline.run_batch(
            args.bills, args.csv, args.out,
            only=_only(args) or None, use_cache=not args.no_cache, level=args.level,
            progress=lambda msg: print(msg, flush=True),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    ok = summary.processed - summary.failures
    print(
        f"\nSummary: {ok}/{summary.processed} bills OK, {summary.warnings} validation warning(s), "
        f"{summary.failures} failure(s) in {time.monotonic() - started:.0f}s"
    )
    if summary.failed_bills:
        print(f"Failed bills: {', '.join(summary.failed_bills)}")
    return 0 if summary.failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
