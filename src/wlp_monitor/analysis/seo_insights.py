"""SEO-Auswertung aus Search-Console-Daten: Fortschritt + tägliche Vorschläge,
wie die Seite weiter nach oben kommt.
"""
from __future__ import annotations

from ..config import Credentials, Settings
from ..integrations import search_console
from ..section import Section, errored, not_configured

SETUP_HINT = (
    "Search Console anbinden: Service-Account anlegen, dessen JSON als Secret "
    "GOOGLE_SERVICE_ACCOUNT_JSON hinterlegen und den Service-Account in der "
    "Search Console als Nutzer der Property hinzufügen. Details in SETUP.md."
)


def _trend(cur: float, prev: float) -> str:
    if prev == 0:
        return "—"
    change = (cur - prev) / prev * 100
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "▬")
    return f"{arrow} {abs(change):.0f}%"


def run(settings: Settings, creds: Credentials) -> Section:
    cfg = settings.section("seo")
    if not cfg.get("enabled", True):
        s = Section(key="seo", title="SEO-Fortschritt", status="info")
        s.summary = "SEO-Auswertung ist deaktiviert."
        return s

    if not creds.search_console_ready():
        return not_configured("seo", "SEO-Fortschritt", SETUP_HINT)

    site = cfg.get("search_console_property", "")
    try:
        data = search_console.fetch(creds, site, int(cfg.get("lookback_days", 28)))
    except Exception as exc:  # noqa: BLE001
        return errored("seo", "SEO-Fortschritt", f"Datenabruf fehlgeschlagen: {exc}")

    section = Section(key="seo", title="SEO-Fortschritt")
    cur = data["totals_current"]
    prev = data["totals_previous"]

    section.metrics = {
        "klicks": int(cur["clicks"]),
        "klicks_trend": _trend(cur["clicks"], prev["clicks"]),
        "impressionen": int(cur["impressions"]),
        "impressionen_trend": _trend(cur["impressions"], prev["impressions"]),
        "ctr": f"{cur['ctr']:.2f}%",
        "ø_position": f"{cur['avg_position']:.1f}",
        "position_trend": _trend(prev["avg_position"], cur["avg_position"]),  # kleiner = besser
        "zeitraum": " bis ".join(data["date_range"]["current"]),
    }

    # --- Chancen finden ---
    sd = cfg.get("striking_distance", {})
    sd_min = float(sd.get("min_position", 4.0))
    sd_max = float(sd.get("max_position", 15.0))
    sd_impr = float(sd.get("min_impressions", 30))

    striking = [
        q for q in data["queries"]
        if sd_min <= q["position"] <= sd_max and q["impressions"] >= sd_impr
    ]
    striking.sort(key=lambda q: q["impressions"], reverse=True)

    lc = cfg.get("low_ctr", {})
    lc_impr = float(lc.get("min_impressions", 100))
    lc_ctr = float(lc.get("max_ctr_pct", 1.5))
    low_ctr_pages = [
        p for p in data["pages"]
        if p["impressions"] >= lc_impr and p["ctr"] < lc_ctr
    ]
    low_ctr_pages.sort(key=lambda p: p["impressions"], reverse=True)

    section.items = [
        {"typ": "Chance (Seite 1 in Reichweite)", "keyword": q["query"],
         "position": f"{q['position']:.1f}", "impressionen": int(q["impressions"]),
         "klicks": int(q["clicks"])}
        for q in striking[:10]
    ]

    # --- Vorschläge ---
    suggestions: list[str] = []
    for q in striking[:5]:
        suggestions.append(
            f"„{q['query']}“ steht auf Position {q['position']:.1f} bei "
            f"{int(q['impressions'])} Impressionen — mit gezieltem Inhalt/internen Links "
            f"auf Seite 1 bringen."
        )
    for p in low_ctr_pages[:3]:
        suggestions.append(
            f"Seite {p['page']} hat viele Impressionen aber nur {p['ctr']:.1f}% CTR — "
            f"Title & Meta-Description attraktiver formulieren (Standort, USP, Angebot)."
        )

    # Trend-basierte Hinweise
    if cur["avg_position"] < prev["avg_position"]:
        suggestions.append(
            f"Durchschnittsposition verbessert sich ({prev['avg_position']:.1f} → "
            f"{cur['avg_position']:.1f}). Kurs beibehalten. 👍"
        )
    elif cur["avg_position"] > prev["avg_position"] + 0.5:
        suggestions.append(
            f"Durchschnittsposition verschlechtert sich ({prev['avg_position']:.1f} → "
            f"{cur['avg_position']:.1f}). Prüfen, ob Wettbewerber überholt haben."
        )
    if not suggestions:
        suggestions.append("Keine akuten SEO-Chancen erkannt — Content-Ausbau weiterführen.")

    section.suggestions = suggestions
    section.metrics["chancen_keywords"] = len(striking)
    section.summary = (
        f"{int(cur['clicks'])} Klicks ({_trend(cur['clicks'], prev['clicks'])}), "
        f"Ø-Position {cur['avg_position']:.1f}, {len(striking)} Keyword-Chancen."
    )
    if striking or low_ctr_pages:
        section.status = "info"
    return section
