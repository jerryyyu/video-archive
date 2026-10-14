"""Ingest from camera SD card -> local archive (default) or external drive.

Usage:
    python scripts/ingest.py                          # dry-run, target=local
    python scripts/ingest.py --apply                  # camera -> local
    python scripts/ingest.py --apply --target external  # camera -> external (skip computer)
    python scripts/ingest.py --apply --year 2026 --month 4
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import manifest
from common import (
    Config,
    iter_files,
    load_config,
    parse_dji_name,
    year_month_bucket,
)


def plan(cfg: Config, year: int | None, month: int | None, target: str) -> list[tuple[Path, Path]]:
    camera_root = cfg.camera_mount / "DCIM"
    if not camera_root.exists():
        sys.exit(f"camera DCIM not found at {camera_root} — is the SD card mounted?")

    if target == "local":
        dest_root = cfg.local_archive
        skip_roots = list(cfg.local_scan_roots)
    elif target == "external":
        if cfg.external_archive is None:
            sys.exit("external_archive is not set in config")
        if not cfg.external_archive.exists():
            sys.exit(f"external archive not mounted: {cfg.external_archive}")
        dest_root = cfg.external_archive
        skip_roots = [cfg.external_archive]
    else:
        sys.exit(f"unknown --target {target}")

    # A file counts as "already have it" if it's physically under a skip root,
    # OR the manifest records it as present anywhere (local or external). The
    # manifest is the source of truth, so this skips footage already archived to
    # the external SSD even when that drive isn't mounted. Only net-new files
    # (absent from every tier) are ingested.
    existing = set()
    for root in skip_roots:
        if root.exists():
            existing.update(p.name for p in iter_files(root, cfg))
    for name, rec in manifest.load().items():
        if rec.local or rec.external:
            existing.add(name)

    actions: list[tuple[Path, Path]] = []
    for src in iter_files(camera_root, cfg):
        if src.name in existing:
            continue
        bucket = year_month_bucket(src.name)
        if not bucket:
            # Non-DJI naming: drop in an "unsorted" bucket so nothing is lost.
            bucket = "unsorted"
        else:
            parsed = parse_dji_name(src.name)
            assert parsed is not None
            y, mo, _ = parsed
            if year is not None and y != year:
                continue
            if month is not None and mo != month:
                continue
        dest = dest_root / bucket / src.name
        actions.append((src, dest))
    return actions


def run(actions: list[tuple[Path, Path]], apply: bool) -> None:
    by_bucket: dict[str, int] = {}
    total_bytes = 0
    for src, dest in actions:
        by_bucket[dest.parent.name] = by_bucket.get(dest.parent.name, 0) + 1
        total_bytes += src.stat().st_size

    print(f"{len(actions)} file(s) to ingest, {total_bytes / 1_073_741_824:.2f} GB total")
    for bucket, n in sorted(by_bucket.items()):
        print(f"  {bucket}: {n}")

    if not apply:
        print("\n(dry run — pass --apply to copy)")
        return

    for src, dest in actions:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            continue
        shutil.copy2(src, dest)
        print(f"copied {src.name} -> {dest.parent.name}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually copy files")
    ap.add_argument("--year", type=int, help="only files from this year")
    ap.add_argument("--month", type=int, help="only files from this month")
    ap.add_argument("--target", choices=("local", "external"), default="local",
                    help="destination tier (default: local)")
    args = ap.parse_args()

    cfg = load_config()
    actions = plan(cfg, args.year, args.month, args.target)
    run(actions, args.apply)


if __name__ == "__main__":
    main()
