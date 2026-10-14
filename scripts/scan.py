"""Scan camera/local/external and update the manifest source of truth.

Each device's presence is set to its containing folder (e.g. "DJI_013" on the
camera, "2026-04" on local/external) or None if missing. Records for files no
longer present anywhere are dropped.

Usage:
    python scripts/scan.py                # scan all available devices
    python scripts/scan.py --camera-only  # only update camera column
    python scripts/scan.py --local-only
    python scripts/scan.py --external-only
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import manifest
from common import Config, iter_files, load_config, year_month_bucket


def _bucket_for(path: Path, root: Path) -> str:
    """Top-level subfolder of `path` under `root`, used as a presence marker."""
    rel = path.relative_to(root)
    return rel.parts[0] if rel.parts else ""


def scan_device(root: Path, cfg: Config, marker: str | None = None) -> dict[str, tuple[str, int]]:
    """Return {filename: (bucket_or_subfolder, size_bytes)}.

    `marker` overrides the per-file presence marker (used for the CapCut
    exports root, where subfolders are project names rather than buckets).
    """
    if not root.exists():
        return {}
    out: dict[str, tuple[str, int]] = {}
    for p in iter_files(root, cfg):
        out[p.name] = (marker or _bucket_for(p, root), p.stat().st_size)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--camera-only", action="store_true")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--external-only", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    records = manifest.load()
    now = datetime.now().isoformat(timespec="seconds")

    do_all = not (args.camera_only or args.local_only or args.external_only)
    camera_dcim = cfg.camera_mount / "DCIM"

    if do_all or args.camera_only:
        if camera_dcim.exists():
            found = scan_device(camera_dcim, cfg)
            _apply(records, found, "camera", now)
            print(f"camera: {len(found)} files")
        else:
            print(f"camera: not mounted at {cfg.camera_mount} (skipped — existing entries preserved)")

    if do_all or args.local_only:
        roots = [r for r in cfg.local_scan_roots if r.exists()]
        capcut_found = {}
        if cfg.capcut_exports and cfg.capcut_exports.exists():
            capcut_found = scan_device(cfg.capcut_exports, cfg, marker="capcut")
        if roots or capcut_found:
            found = dict(capcut_found)
            for root in roots:
                for name, val in scan_device(root, cfg).items():
                    found.setdefault(name, val)
            _apply(records, found, "local", now)
            print(f"local: {len(found)} files across {len(roots)} root(s)"
                  + (f" + {len(capcut_found)} capcut exports" if capcut_found else ""))
        else:
            print("local: no roots exist (skipped)")

    if do_all or args.external_only:
        if cfg.external_archive and cfg.external_archive.exists():
            found = scan_device(cfg.external_archive, cfg)
            _apply(records, found, "external", now)
            print(f"external: {len(found)} files")
        else:
            print("external: not mounted (skipped — existing entries preserved)")

    # Drop records that have no presence anywhere.
    dropped = [n for n, r in records.items() if not r.locations()]
    for n in dropped:
        del records[n]
    if dropped:
        print(f"dropped {len(dropped)} stale entries")

    manifest.save(records)
    print(f"manifest now tracks {len(records)} files at {manifest.MANIFEST_PATH}")


def _apply(records: dict[str, manifest.Record], found: dict[str, tuple[str, int]], device: str, now: str) -> None:
    # Clear this device on every record first so removals are reflected.
    for r in records.values():
        setattr(r, device, None)
    for name, (bucket_or_subfolder, size) in found.items():
        # Non-DJI files under a "capcut" marker bucket as "capcut".
        fallback = "capcut" if bucket_or_subfolder == "capcut" else None
        r = records.get(name)
        if r is None:
            r = manifest.Record(name=name, bucket=year_month_bucket(name) or fallback, size=size)
            records[name] = r
        else:
            r.size = size
            if r.bucket is None:
                r.bucket = year_month_bucket(name) or fallback
        setattr(r, device, bucket_or_subfolder)
        r.last_scanned = now


if __name__ == "__main__":
    main()
