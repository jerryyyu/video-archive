"""Manifest helpers: read/write the source-of-truth filename index.

The manifest lives at <repo>/manifest.jsonl. One JSON record per line, keyed by
filename. Each record tracks which devices (camera/local/external) currently
hold the file, the year-month bucket, byte size, and the last scan timestamp.

Format:
    {"name": "DJI_...MP4", "bucket": "2026-04", "size": 12345678,
     "camera": "DJI_013", "local": "2026-04", "external": null,
     "last_scanned": "2026-06-14T21:50:00"}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common import REPO_ROOT

MANIFEST_PATH = REPO_ROOT / "manifest.jsonl"


@dataclass
class Record:
    name: str
    bucket: str | None = None
    size: int | None = None
    camera: str | None = None     # subfolder on camera (e.g. "DJI_013") or None
    local: str | None = None      # bucket on local (e.g. "2026-04") or None
    external: str | None = None   # bucket on external or None
    last_scanned: str = ""

    def locations(self) -> list[str]:
        return [k for k in ("camera", "local", "external") if getattr(self, k)]


def load() -> dict[str, Record]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[str, Record] = {}
    with MANIFEST_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            r = Record(**d)
            out[r.name] = r
    return out


def save(records: dict[str, Record]) -> None:
    tmp = MANIFEST_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        for name in sorted(records):
            f.write(json.dumps(asdict(records[name])) + "\n")
    tmp.replace(MANIFEST_PATH)
