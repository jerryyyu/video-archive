"""Reorganize an archive root so all files live in YYYY-MM/ buckets.

Walks the target root, parses each filename's DJI timestamp, and moves the file
into <root>/YYYY-MM/. Files in already-correct buckets are left alone.
Non-DJI filenames go to <root>/unsorted/. Empty source directories are removed
at the end.

Usage:
    python scripts/reorganize.py --target external         # dry-run
    python scripts/reorganize.py --target external --apply
    python scripts/reorganize.py --target local --apply
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from common import Config, iter_files, load_config, year_month_bucket

BUCKET_RE = re.compile(r"^\d{4}-\d{2}$")


def plan(cfg: Config, target: str) -> list[tuple[Path, Path]]:
    if target == "local":
        root = cfg.local_archive
    elif target == "external":
        if cfg.external_archive is None:
            sys.exit("external_archive is not set in config")
        root = cfg.external_archive
    else:
        sys.exit(f"unknown --target {target}")

    if not root.exists():
        sys.exit(f"root does not exist: {root}")

    actions: list[tuple[Path, Path]] = []
    for src in iter_files(root, cfg):
        rel = src.relative_to(root)
        if not rel.parts:
            continue
        top = rel.parts[0]
        if top == "capcut":  # CapCut exports keep their project layout
            continue
        bucket = year_month_bucket(src.name) or "unsorted"
        if top == bucket:
            continue
        dest = root / bucket / src.name
        actions.append((src, dest))
    return actions


def run(actions: list[tuple[Path, Path]], root: Path, apply: bool) -> None:
    by_bucket: dict[str, int] = {}
    for _, dest in actions:
        by_bucket[dest.parent.name] = by_bucket.get(dest.parent.name, 0) + 1

    print(f"{len(actions)} file(s) to move under {root}")
    for bucket, n in sorted(by_bucket.items()):
        print(f"  -> {bucket}: {n}")

    if not apply:
        print("\n(dry run — pass --apply to move)")
        return

    collisions = 0
    for src, dest in actions:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            collisions += 1
            print(f"skip (already at dest): {src.name}")
            continue
        shutil.move(str(src), str(dest))

    # Clean up empty non-bucket directories.
    removed = 0
    for d in sorted(root.iterdir(), key=lambda p: p.name):
        if not d.is_dir() or BUCKET_RE.match(d.name) or d.name in ("unsorted", "capcut"):
            continue
        try:
            d.rmdir()
            removed += 1
            print(f"removed empty dir: {d.name}")
        except OSError:
            remaining = list(d.iterdir())
            print(f"kept {d.name} ({len(remaining)} file(s) left): {[p.name for p in remaining[:5]]}")

    print(f"\nmoved {len(actions) - collisions} file(s), removed {removed} empty dir(s)")
    if collisions:
        print(f"{collisions} file(s) already at destination (skipped)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", choices=("local", "external"), required=True)
    ap.add_argument("--apply", action="store_true", help="actually move files")
    args = ap.parse_args()

    cfg = load_config()
    root = cfg.local_archive if args.target == "local" else cfg.external_archive
    actions = plan(cfg, args.target)
    run(actions, root, args.apply)


if __name__ == "__main__":
    main()
