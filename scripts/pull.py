"""Pull specific files/buckets from external drive -> local archive.

Usage:
    python scripts/pull.py --bucket 2025-12              # dry run
    python scripts/pull.py --bucket 2025-12 --apply
    python scripts/pull.py --name DJI_20251215123456_0042_D.MP4 --apply
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import Config, iter_files, load_config


def plan(cfg: Config, bucket: str | None, name: str | None) -> list[tuple[Path, Path]]:
    if cfg.external_archive is None:
        sys.exit("external_archive is not set in config")
    if not cfg.external_archive.exists():
        sys.exit(f"external archive not mounted: {cfg.external_archive}")
    if not bucket and not name:
        sys.exit("provide --bucket and/or --name")

    existing = {p.name for p in iter_files(cfg.local_archive, cfg)}
    if cfg.capcut_exports:
        existing |= {p.name for p in iter_files(cfg.capcut_exports, cfg)}
    actions: list[tuple[Path, Path]] = []
    for src in iter_files(cfg.external_archive, cfg):
        rel = src.relative_to(cfg.external_archive)
        if bucket and not str(rel).startswith(f"{bucket}/"):
            continue
        if name and src.name != name:
            continue
        if src.name in existing:
            continue
        # CapCut exports restore to their own root, not the DJI archive.
        if rel.parts[0] == "capcut" and cfg.capcut_exports:
            dest = cfg.capcut_exports / Path(*rel.parts[1:])
        else:
            dest = cfg.local_archive / rel
        actions.append((src, dest))
    return actions


def run(actions: list[tuple[Path, Path]], apply: bool) -> None:
    total_bytes = sum(src.stat().st_size for src, _ in actions)
    print(f"{len(actions)} file(s) to pull, {total_bytes / 1_073_741_824:.2f} GB total")
    if not apply:
        print("(dry run — pass --apply to copy)")
        return

    for src, dest in actions:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"pulled {src.name} -> {dest.parent.name}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually copy files")
    ap.add_argument("--bucket", help="pull all files in this YYYY-MM bucket")
    ap.add_argument("--name", help="pull a specific filename")
    args = ap.parse_args()

    cfg = load_config()
    actions = plan(cfg, args.bucket, args.name)
    run(actions, args.apply)


if __name__ == "__main__":
    main()
