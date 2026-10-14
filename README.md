# video-archive

Manage DJI (and other camera) video files across three locations:

- **Camera SD card** (e.g. `/Volumes/DJI`) — ephemeral, gets wiped
- **Local archive** on this computer (e.g. `~/Documents/DJI`) — grouped by `YYYY-MM`
- **External drive** archive — long-term cold storage

Also tracked: **CapCut exports** (`capcut_exports` in config, e.g. `~/Movies/CapCut`) —
finished edits, either loose `.mov` files or `<project>/` folders holding the video plus
an `.AAC` sidecar. They get bucket `capcut` in the manifest, push to
`<external>/capcut/` preserving the project layout, and pull back to the CapCut root.
CapCut's `User Data/` (drafts + cache) is excluded via the `exclude_dirs` rule and is
never archived — drafts only reference source footage by path, so archiving them
wouldn't make projects portable anyway.

Filenames are the identity key. The manifest at `manifest.jsonl` is the source
of truth for which file lives where. It's gitignored since it lists every clip
you own — keep it local (or back it up somewhere private).

Zero dependencies; Python 3.9+.

## Layout

```
config.json           # default paths + exclude rules
config.local.json     # optional, gitignored, per-machine overrides (deep-merged)
manifest.jsonl        # gitignored; one record per filename, tracks presence on each device
scripts/
  ingest.py           # camera     -> local computer    (year-month buckets)
  push.py             # local      -> external drive
  pull.py             # external   -> local             (cherry-pick a bucket/file)
  scan.py             # update manifest by scanning all available devices
  status.py           # query the manifest
  common.py           # config + filename parsing helpers
  manifest.py         # manifest read/write
```

## Quick start

```sh
# 1) Put this machine's paths in config.local.json — it overrides config.json.
#    camera_mounts lists every camera you use; the first one plugged in wins.
#    external_archive can stay blank until you have a drive. Example:
#      {"paths": {"camera_mounts": ["/Volumes/DJI", "/Volumes/Pocket4P"],
#                 "external_archive": "/Volumes/MyDrive/video-archive"}}

# 2) Pull in new clips from the camera, grouped by year-month.
python scripts/ingest.py            # dry run — shows what would copy
python scripts/ingest.py --apply

# 3) Mirror local -> external when the drive is connected.
python scripts/push.py --apply

# 4) Pull something back from the external drive.
python scripts/pull.py --bucket 2025-12 --apply

# 5) Refresh the manifest after any of the above (or any manual change).
python scripts/scan.py

# 6) See what's where.
python scripts/status.py                          # summary table
python scripts/status.py --bucket 2026-04         # files in one bucket
python scripts/status.py --missing-from external  # not yet archived off-machine
python scripts/status.py --only-on camera         # not yet ingested
```

## Conventions

- Year-month buckets are derived from the DJI filename timestamp
  (`DJI_YYYYMMDD...`). Non-DJI names land in `unsorted/`.
- `.LRF` proxies, `.THM`/`.SCR` thumbnails, and macOS `._*` / `.DS_Store`
  cruft are excluded by default (see `rules` in `config.json`).
- All scripts default to dry-run; pass `--apply` to actually move bytes.
- Sync direction is normally `camera -> local -> external`. `pull.py` exists
  for the occasional reverse trip when you need a clip back from cold storage.

## Multiple machines

The manifest isn't committed, so each clone keeps its own. Running `scan.py`
with the camera and external drive plugged in rebuilds it from what's actually
on disk.
