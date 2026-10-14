"""Query the manifest: show where files live across camera/computer/external.

Usage:
    python scripts/status.py                       # high-level summary
    python scripts/status.py --bucket 2026-04      # files in this YYYY-MM bucket
    python scripts/status.py --missing-from local  # not present on local
    python scripts/status.py --only-on camera      # only on camera (not yet ingested)
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import manifest

DEVICES = ("camera", "local", "external")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bucket", help="filter to a YYYY-MM bucket")
    ap.add_argument("--missing-from", choices=DEVICES, help="show files not on this device")
    ap.add_argument("--only-on", choices=DEVICES, help="show files only on this device")
    ap.add_argument("--limit", type=int, default=20, help="max files to list (default 20)")
    args = ap.parse_args()

    records = manifest.load()
    if not records:
        print("manifest is empty — run scripts/scan.py first")
        return

    filtered = list(records.values())
    if args.bucket:
        filtered = [r for r in filtered if r.bucket == args.bucket]
    if args.missing_from:
        filtered = [r for r in filtered if getattr(r, args.missing_from) is None]
    if args.only_on:
        filtered = [r for r in filtered if r.locations() == [args.only_on]]

    if not (args.bucket or args.missing_from or args.only_on):
        _print_summary(records)
        return

    total_bytes = sum(r.size or 0 for r in filtered)
    print(f"{len(filtered)} file(s), {total_bytes / 1_073_741_824:.2f} GB")
    for r in sorted(filtered, key=lambda r: r.name)[: args.limit]:
        locs = ",".join(r.locations()) or "-"
        print(f"  {r.name}  [{locs}]")
    if len(filtered) > args.limit:
        print(f"  ... ({len(filtered) - args.limit} more)")


def _print_summary(records: dict[str, manifest.Record]) -> None:
    by_bucket: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    everywhere = 0
    for r in records.values():
        b = r.bucket or "unsorted"
        for d in DEVICES:
            if getattr(r, d):
                by_bucket[b][d] += 1
        by_bucket[b]["total"] += 1
        if all(getattr(r, d) for d in DEVICES):
            everywhere += 1

    print(f"{len(records)} tracked files")
    print(f"  fully synced (camera+local+external): {everywhere}")
    print()
    print(f"{'bucket':<12} {'total':>6} {'camera':>7} {'local':>6} {'external':>9}")
    for b in sorted(by_bucket):
        row = by_bucket[b]
        print(f"{b:<12} {row['total']:>6} {row['camera']:>7} {row['local']:>6} {row['external']:>9}")


if __name__ == "__main__":
    main()
