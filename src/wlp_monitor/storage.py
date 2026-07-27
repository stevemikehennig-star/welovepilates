"""Historische Snapshots speichern, damit Trends (SEO, Ads, Auslastung)
über die Zeit dargestellt werden können.

Jeder Tageslauf schreibt eine JSON-Datei nach data/history/YYYY-MM-DD.json.
Diese Dateien werden ins Repo committet und vom Dashboard ausgewertet.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT

HISTORY_DIR = ROOT / "data" / "history"
LATEST_FILE = ROOT / "data" / "latest.json"


def _ensure_dirs() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_snapshot(report: dict[str, Any], date_str: str) -> Path:
    """Speichert den Tagesreport und aktualisiert latest.json."""
    _ensure_dirs()
    path = HISTORY_DIR / f"{date_str}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=_json_default)
    with open(LATEST_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=_json_default)
    return path


def load_history(limit_days: int = 30) -> list[dict[str, Any]]:
    """Lädt die letzten N Tages-Snapshots (chronologisch aufsteigend)."""
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("*.json"))
    out: list[dict[str, Any]] = []
    for f in files[-limit_days:]:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def load_latest() -> dict[str, Any] | None:
    if LATEST_FILE.exists():
        try:
            with open(LATEST_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    return str(o)
