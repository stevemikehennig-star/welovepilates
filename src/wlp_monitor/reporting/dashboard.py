"""Statisches HTML-Dashboard für GitHub Pages erzeugen."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import ROOT, Settings
from ..section import STATUS_EMOJI, STATUS_LABEL
from .. import storage

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Kennzahlen mit diesen Schlüsseln sind komplexe Strukturen (Tabellen/Heatmaps)
# und werden NICHT als einfache Kachel angezeigt.
_COMPLEX_KEYS = {
    "top_slots", "heatmap", "broken_links_list", "js_errors_list",
    "failed_requests_list",
}


def _simple_metrics(metrics: dict[str, Any]) -> list[tuple[str, Any]]:
    out = []
    for k, v in (metrics or {}).items():
        if k in _COMPLEX_KEYS or isinstance(v, (list, dict)):
            continue
        label = k.replace("_", " ")
        out.append((label, v))
    return out


def _heat_color(val: Any) -> str:
    try:
        alpha = max(0.08, min(1.0, float(val) / 100))
    except (TypeError, ValueError):
        alpha = 0.08
    return f"rgba(194,24,91,{alpha:.2f})"


def _heat_text(val: Any) -> str:
    try:
        return "#ffffff" if float(val) >= 55 else "inherit"
    except (TypeError, ValueError):
        return "inherit"


def _sparkline(values: list[float], width: int = 170, height: int = 32) -> str:
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    n = len(pts)
    coords = []
    for i, v in enumerate(pts):
        x = i / (n - 1) * (width - 4) + 2
        y = height - 2 - (v - lo) / span * (height - 6)
        coords.append(f"{x:.1f},{y:.1f}")
    path = " ".join(coords)
    last_x, last_y = coords[-1].split(",")
    return (
        f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline fill="none" stroke="var(--accent)" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{path}"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2.6" fill="var(--accent)"/></svg>'
    )


def _build_trends(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Zeitreihen aus der Historie für Sparklines aufbereiten."""
    if len(history) < 2:
        return {}

    def series_for(section_key: str, metric_key: str) -> list[float | None]:
        vals: list[float | None] = []
        for snap in history:
            found = None
            for sec in snap.get("sections", []):
                if sec.get("key") == section_key:
                    raw = (sec.get("metrics") or {}).get(metric_key)
                    found = _to_number(raw)
                    break
            vals.append(found)
        return vals

    definitions = [
        ("SEO-Klicks", "seo", "klicks"),
        ("Buchungen (Zeitraum)", "bookings", "buchungen_zeitraum"),
        ("Ads-Klicks", "google_ads", "klicks"),
    ]
    series = []
    for label, sk, mk in definitions:
        vals = series_for(sk, mk)
        clean = [v for v in vals if v is not None]
        if len(clean) < 2:
            continue
        series.append({
            "label": label,
            "last": _fmt_number(clean[-1]),
            "svg": _sparkline(vals),
        })
    return {"days": len(history), "series": series}


def _to_number(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = raw.replace("€", "").replace("%", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _fmt_number(v: float) -> str:
    return f"{int(v):,}".replace(",", ".") if v == int(v) else f"{v:.1f}"


def generate(report: dict[str, Any], settings: Settings,
             history: list[dict[str, Any]] | None = None,
             output_name: str = "index.html") -> Path:
    cfg = settings.section("reporting").get("dashboard", {})
    output_dir = ROOT / cfg.get("output_dir", "docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    if history is None:
        history = storage.load_history(int(cfg.get("history_days", 30)))
    trends = _build_trends(history)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["simple_metrics"] = _simple_metrics
    env.filters["heat_color"] = _heat_color
    env.filters["heat_text"] = _heat_text

    template = env.get_template("dashboard.html.j2")
    html = template.render(
        report=report,
        trends=trends,
        status_emoji=STATUS_EMOJI,
        status_label=STATUS_LABEL,
    )
    out = output_dir / output_name
    out.write_text(html, encoding="utf-8")
    return out
