"""Google-Ads-Auswertung: Kennzahlen + tägliche Optimierungsvorschläge."""
from __future__ import annotations

from ..config import Credentials, Settings
from ..integrations import google_ads
from ..section import Section, errored, not_configured

SETUP_HINT = (
    "Google Ads API einrichten: Developer-Token beantragen, OAuth-Client anlegen, "
    "Refresh-Token generieren und als GitHub Secrets hinterlegen "
    "(GOOGLE_ADS_*). Details in SETUP.md."
)


def _fmt_eur(v: float | None) -> str:
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".") if v is not None else "—"


def run(settings: Settings, creds: Credentials) -> Section:
    cfg = settings.section("google_ads")
    if not cfg.get("enabled", True):
        s = Section(key="google_ads", title="Google Ads", status="info")
        s.summary = "Google-Ads-Auswertung ist deaktiviert."
        return s

    if not creds.google_ads_ready():
        return not_configured("google_ads", "Google Ads", SETUP_HINT)

    th = cfg.get("thresholds", {})
    try:
        data = google_ads.fetch(
            creds,
            lookback_days=int(cfg.get("lookback_days", 1)),
            comparison_days=int(cfg.get("comparison_days", 7)),
            wasted_min_cost=float(th.get("wasted_spend_eur", 15)),
        )
    except Exception as exc:  # noqa: BLE001
        return errored("google_ads", "Google Ads", f"Datenabruf fehlgeschlagen: {exc}")

    section = Section(key="google_ads", title="Google Ads")
    current = data["current"]
    wasted = data["wasted_keywords"]

    total_cost = sum(c["cost"] for c in current.values())
    total_conv = sum(c["conversions"] for c in current.values())
    total_clicks = sum(c["clicks"] for c in current.values())
    total_impr = sum(c["impressions"] for c in current.values())
    avg_cpa = (total_cost / total_conv) if total_conv else None

    section.metrics = {
        "kosten": _fmt_eur(total_cost),
        "conversions": round(total_conv, 1),
        "klicks": total_clicks,
        "impressionen": total_impr,
        "ctr": f"{(total_clicks / total_impr * 100):.2f}%" if total_impr else "—",
        "cpa": _fmt_eur(avg_cpa),
        "zeitraum": " bis ".join(data["date_range"]["current"]),
    }

    # Kampagnen-Detailzeilen
    rows = []
    for c in sorted(current.values(), key=lambda x: x["cost"], reverse=True):
        rows.append({
            "kampagne": c["name"],
            "kosten": _fmt_eur(c["cost"]),
            "klicks": c["clicks"],
            "ctr": f"{c['ctr']:.2f}%",
            "conv": round(c["conversions"], 1),
            "cpa": _fmt_eur(c["cpa"]),
            "roas": f"{c['roas']:.2f}" if c["roas"] else "—",
        })
    section.items = rows

    # --- Vorschläge ---
    suggestions: list[str] = []
    high_cpa = float(th.get("high_cpa_eur", 50))
    low_ctr = float(th.get("low_ctr_pct", 1.5))
    budget_lost = float(th.get("budget_lost_is_pct", 10))

    for c in current.values():
        if c["cpa"] is not None and c["cpa"] > high_cpa:
            suggestions.append(
                f"Kampagne „{c['name']}“ hat hohen CPA ({_fmt_eur(c['cpa'])}). "
                f"Gebote/Keywords prüfen oder Zielgruppe eingrenzen."
            )
        if c["impressions"] >= 100 and c["ctr"] < low_ctr:
            suggestions.append(
                f"Kampagne „{c['name']}“ hat niedrige CTR ({c['ctr']:.2f}%). "
                f"Anzeigentexte/Assets überarbeiten (mehr USP: Ladies-only, Red-Light, Boutique)."
            )
        if c["budget_lost_is"] > budget_lost:
            suggestions.append(
                f"Kampagne „{c['name']}“ verliert {c['budget_lost_is']:.0f}% Impressionen "
                f"wegen Budget-Limit. Bei gutem CPA Budget erhöhen."
            )

    if wasted:
        top = wasted[0]
        total_wasted = sum(w["cost"] for w in wasted)
        suggestions.append(
            f"{len(wasted)} Keywords ohne Conversion verbrennen ~{_fmt_eur(total_wasted)} "
            f"(z. B. „{top['keyword']}“: {_fmt_eur(top['cost'])}). Als negativ ausschließen "
            f"oder pausieren."
        )
        section.metrics["verschwendetes_budget"] = _fmt_eur(total_wasted)

    if not suggestions:
        suggestions.append("Keine Auffälligkeiten — Kampagnen laufen im Zielbereich. 👍")

    section.suggestions = suggestions

    # Status
    if any("Budget-Limit" in s or "hohen CPA" in s for s in suggestions) or wasted:
        section.status = "warning"
    section.summary = (
        f"{_fmt_eur(total_cost)} Ausgaben, {round(total_conv,1)} Conversions, "
        f"CPA {_fmt_eur(avg_cpa)}."
    )
    return section
