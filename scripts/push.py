"""Push local archive -> external drive.

Covers the DJI local roots (into YYYY-MM buckets) and CapCut exports
(into <external>/capcut/, preserving the per-project folder layout).

Usage:
    python scripts/push.py                   # dry-run preview
    python scripts/push.py --apply           # actually copy
    python scripts/push.py --apply --bucket 2026-04   # only one year-month
    python scripts/push.py --apply --bucket capcut    # only CapCut exports
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import Config, iter_files, load_config


def plan(cfg: Config, bucket_filter: str | None) -> list[tuple[Path, Path]]:
    if cfg.external_archive is None:
        sys.exit("external_archive is not set in config — set it once the drive is plugged in")
    if not cfg.external_archive.parent.exists():
        sys.exit(f"external archive parent does not exist: {cfg.external_archive.parent}")

    existing = {p.name for p in iter_files(cfg.external_archive, cfg)}
    actions: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for root in cfg.local_scan_roots:
        if not root.exists():
            continue
        for src in iter_files(root, cfg):
            if src.name in existing or src.name in seen:
                continue
            rel = src.relative_to(root)
            if bucket_filter and not str(rel).startswith(f"{bucket_filter}/"):
                continue
            actions.append((src, cfg.external_archive / rel))
            seen.add(src.name)

    # CapCut exports land under <external>/capcut/, preserving project layout.
    if cfg.capcut_exports and cfg.capcut_exports.exists():
        for src in iter_files(cfg.capcut_exports, cfg):
            if src.name in existing or src.name in seen:
                continue
            rel = Path("capcut") / src.relative_to(cfg.capcut_exports)
            if bucket_filter and not str(rel).startswith(f"{bucket_filter}/"):
                continue
            actions.append((src, cfg.external_archive / rel))
            seen.add(src.name)
    return actions


def run(actions: list[tuple[Path, Path]], apply: bool) -> None:
    total_bytes = sum(src.stat().st_size for src, _ in actions)
    print(f"{len(actions)} file(s) to push, {total_bytes / 1_073_741_824:.2f} GB total")
    if not apply:
        print("(dry run — pass --apply to copy)")
        return

    for src, dest in actions:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"pushed {src.name} -> {dest.parent.name}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually copy files")
    ap.add_argument("--bucket", help="only this YYYY-MM bucket (or any top-level dir)")
    args = ap.parse_args()

    cfg = load_config()
    actions = plan(cfg, args.bucket)
    run(actions, args.apply)


if __name__ == "__main__":
    main()
