"""Shared helpers: config loading, filename parsing, file discovery."""
from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DJI_NAME_RE = re.compile(r"DJI_(\d{4})(\d{2})(\d{2})(\d{6})_(\d+)_[A-Z](\.[A-Za-z0-9]+)$")


@dataclass(frozen=True)
class Config:
    camera_mounts: Tuple[Path, ...]
    local_archive: Path
    local_scan_extras: Tuple[Path, ...]
    external_archive: Optional[Path]
    capcut_exports: Optional[Path]
    exclude_extensions: Tuple[str, ...]
    exclude_glob: Tuple[str, ...]
    exclude_dirs: Tuple[str, ...]

    @property
    def camera_mount(self) -> Path:
        """First configured camera mount that's plugged in (else the first configured)."""
        for m in self.camera_mounts:
            if (m / "DCIM").exists():
                return m
        return self.camera_mounts[0]

    @property
    def local_scan_roots(self) -> Tuple[Path, ...]:
        """All local paths that scan.py should walk."""
        return (self.local_archive, *self.local_scan_extras)


def load_config() -> Config:
    base = _read_json(REPO_ROOT / "config.json")
    override = REPO_ROOT / "config.local.json"
    if override.exists():
        _merge(base, _read_json(override))
    paths = base["paths"]
    rules = base["rules"]
    ext = paths["external_archive"].strip()
    capcut = paths.get("capcut_exports", "").strip()
    return Config(
        camera_mounts=tuple(Path(p).expanduser() for p in paths.get("camera_mounts") or [paths["camera_mount"]]),
        local_archive=Path(paths["local_archive"]).expanduser(),
        local_scan_extras=tuple(Path(p).expanduser() for p in paths.get("local_scan_extras", [])),
        external_archive=Path(ext).expanduser() if ext else None,
        capcut_exports=Path(capcut).expanduser() if capcut else None,
        exclude_extensions=tuple(e.lower() for e in rules["exclude_extensions"]),
        exclude_glob=tuple(rules["exclude_glob"]),
        exclude_dirs=tuple(rules.get("exclude_dirs", [])),
    )


def _read_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _merge(into: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(into.get(k), dict):
            _merge(into[k], v)
        else:
            into[k] = v


def parse_dji_name(name: str) -> Optional[Tuple[int, int, int]]:
    """Return (year, month, day) parsed from a DJI filename, or None."""
    m = DJI_NAME_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def year_month_bucket(name: str) -> Optional[str]:
    parsed = parse_dji_name(name)
    if not parsed:
        return None
    y, mo, _ = parsed
    return f"{y:04d}-{mo:02d}"


def is_excluded(name: str, cfg: Config) -> bool:
    lower = name.lower()
    if any(lower.endswith(ext) for ext in cfg.exclude_extensions):
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in cfg.exclude_glob)


def iter_files(root: Path, cfg: Config):
    """Yield (path, relative_name) for every video file under root, excluding rule matches."""
    if not root.exists():
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if is_excluded(p.name, cfg):
            continue
        if cfg.exclude_dirs and any(part in cfg.exclude_dirs for part in p.relative_to(root).parts[:-1]):
            continue
        yield p


def index_by_basename(root: Path, cfg: Config):
    """Map basename -> path for files already present under root."""
    return {p.name: p for p in iter_files(root, cfg)}
