"""Erzeugt ein Dashboard mit realistischen BEISPIEL-Daten (docs/index.html),
damit man sofort sieht, wie der Monitor aussieht — noch bevor echte Zugangsdaten
hinterlegt sind. Schreibt KEINE echten Snapshots.

Aufruf:  python scripts/generate_demo.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wlp_monitor.analysis.schedule_optimizer import _build_heatmap, WEEKDAYS  # noqa: E402
from wlp_monitor.config import load_settings  # noqa: E402
from wlp_monitor.reporting import dashboard  # noqa: E402
from wlp_monitor.reporting.report import build_report  # noqa: E402
from wlp_monitor.section import Section  # noqa: E402

CAPACITY = 8
COURSES = ["Reformer Flow", "Reformer Basics", "Power Pilates", "Stretch & Relax"]


def _demo_bookings_section() -> Section:
    # Nachfrageprofil: Morgens (07–09) und abends (17–19) stark, mittags schwach.
    profile = {7: 7, 8: 8, 9: 6, 12: 3, 17: 8, 18: 7, 19: 5}
    slot_participants: dict[tuple[int, int], list[int]] = {}
    slot_service: dict[tuple[int, int], dict[str, int]] = {}
    service_totals: dict[str, int] = {c: 0 for c in COURSES}

    for wd in range(6):  # Mo–Sa
        for hour, base in profile.items():
            # Wochenende morgens etwas voller, abends leerer
            val = base + (1 if (wd == 5 and hour <= 9) else 0) - (2 if (wd == 5 and hour >= 17) else 0)
            val = max(1, min(CAPACITY, val))
            # 4 Wochen -> 4 Termine je Slot
            plist = [val, max(1, val - 1), val, max(1, val - 2)]
            slot_participants[(wd, hour)] = plist
            course = COURSES[hour % len(COURSES)]
            slot_service[(wd, hour)] = {course: sum(plist)}
            service_totals[course] += sum(plist)

    total = sum(sum(v) for v in slot_participants.values())

    sec = Section(key="bookings", title="Kursbuchungen & Kursplan", status="info")
    sec.summary = "142 Buchungen in 30 Tagen, 3 stark / 2 schwach ausgelastete Slots."
    sec.metrics = {
        "buchungen_zeitraum": total,
        "zeitraum_tage": 30,
        "aktive_kurse": len(COURSES),
        "beliebtester_kurs": max(service_totals, key=service_totals.get),
        "heatmap": _build_heatmap(slot_participants, CAPACITY),
    }
    sec.items = [
        {"zeit": "Mo 28.07. 07:00", "kurs": "Reformer Basics", "teilnehmer": 8, "status": "CONFIRMED"},
        {"zeit": "Mo 28.07. 18:00", "kurs": "Reformer Flow", "teilnehmer": 7, "status": "CONFIRMED"},
        {"zeit": "Di 29.07. 08:00", "kurs": "Power Pilates", "teilnehmer": 8, "status": "CONFIRMED"},
        {"zeit": "Di 29.07. 12:00", "kurs": "Stretch & Relax", "teilnehmer": 3, "status": "CONFIRMED"},
        {"zeit": "Mi 30.07. 17:00", "kurs": "Reformer Flow", "teilnehmer": 8, "status": "CONFIRMED"},
    ]
    sec.suggestions = [
        "Mo 07:00 & Di 08:00 sind ausgebucht (100 %). Zusätzlichen Frühkurs oder "
        "zweiten Reformer-Slot anbieten.",
        "Di 12:00 ist schwach ausgelastet (~38 %). Mittags-Slot testweise streichen "
        "oder als Business-Lunch-Kurs (30 Min.) neu positionieren.",
        "Abendfenster 17–19 Uhr trägt das Geschäft — Kernangebot dort absichern und "
        "Wartelisten aktiv nachbesetzen.",
    ]
    return sec


def _demo_sections() -> list[Section]:
    uptime = Section(key="uptime", title="Website & Fehler", status="ok")
    uptime.summary = "Alle 4 Seiten erreichbar und schnell."
    uptime.metrics = {"geprüfte_seiten": 4, "tote_links": 0, "seo_probleme": 1}
    uptime.items = [
        {"page": "Startseite", "url": "/", "http": 200, "load_seconds": 0.9, "status": "ok"},
        {"page": "Kurse", "url": "/kurse", "http": 200, "load_seconds": 1.4, "status": "ok"},
        {"page": "Preise", "url": "/preise", "http": 200, "load_seconds": 1.1, "status": "ok"},
        {"page": "Kontakt", "url": "/kontakt", "http": 200, "load_seconds": 0.8, "status": "ok"},
    ]
    uptime.suggestions = ["On-Page: Startseite: Meta-Description zu lang (182 Zeichen) — Ziel ≤ 160."]

    booking = Section(key="booking_flow", title="Buchungsprozess", status="ok")
    booking.summary = "Buchungsprozess vollständig durchlaufbar."
    booking.metrics = {"schritte_gesamt": 4, "schritte_ok": 4, "js_fehler": 0, "server_fehler_requests": 0}
    booking.items = [
        {"step": 1, "description": "Buchungsseite öffnen", "action": "goto", "status": "ok"},
        {"step": 2, "description": "Kursliste wird angezeigt", "action": "expect_visible", "status": "ok"},
        {"step": 3, "description": "Ersten Kurs anklicken", "action": "click_first", "status": "ok"},
        {"step": 4, "description": "Terminauswahl erscheint", "action": "expect_visible", "status": "ok"},
    ]

    ads = Section(key="google_ads", title="Google Ads", status="warning")
    ads.summary = "82,40 € Ausgaben, 3.0 Conversions, CPA 27,47 €."
    ads.metrics = {
        "kosten": "82,40 €", "conversions": 3.0, "klicks": 41, "impressionen": 2380,
        "ctr": "1,72%", "cpa": "27,47 €", "verschwendetes_budget": "18,90 €",
    }
    ads.items = [
        {"kampagne": "Search – Pilates Berlin", "kosten": "51,20 €", "klicks": 24, "ctr": "2,10%", "conv": 2.0, "cpa": "25,60 €", "roas": "3,1"},
        {"kampagne": "Search – Reformer Schöneberg", "kosten": "18,30 €", "klicks": 11, "ctr": "1,80%", "conv": 1.0, "cpa": "18,30 €", "roas": "4,2"},
        {"kampagne": "Display – Retargeting", "kosten": "12,90 €", "klicks": 6, "ctr": "0,60%", "conv": 0.0, "cpa": "—", "roas": "—"},
    ]
    ads.suggestions = [
        "Kampagne „Display – Retargeting“ hat niedrige CTR (0,60 %) und 0 Conversions. "
        "Creatives erneuern oder Budget in die Search-Kampagne verschieben.",
        "3 Keywords ohne Conversion verbrennen ~18,90 € (z. B. „pilates günstig“). "
        "Als negativ ausschließen.",
        "„Search – Reformer Schöneberg“ läuft mit ROAS 4,2 sehr gut — Budget erhöhen.",
    ]

    seo = Section(key="seo", title="SEO-Fortschritt", status="info")
    seo.summary = "312 Klicks (▲ 14%), Ø-Position 8.6, 5 Keyword-Chancen."
    seo.metrics = {
        "klicks": 312, "klicks_trend": "▲ 14%", "impressionen": 9840,
        "impressionen_trend": "▲ 9%", "ctr": "3,17%", "ø_position": "8.6",
        "position_trend": "▲ 6%", "chancen_keywords": 5,
    }
    seo.items = [
        {"typ": "Chance", "keyword": "reformer pilates berlin", "position": "6.2", "impressionen": 620, "klicks": 28},
        {"typ": "Chance", "keyword": "pilates schöneberg", "position": "7.8", "impressionen": 410, "klicks": 15},
        {"typ": "Chance", "keyword": "pilates studio frauen berlin", "position": "11.4", "impressionen": 180, "klicks": 4},
    ]
    seo.suggestions = [
        "„reformer pilates berlin“ steht auf Position 6.2 bei 620 Impressionen — mit "
        "eigener Landingpage + internen Links auf Seite 1 bringen.",
        "„pilates schöneberg“ (Pos. 7.8): lokalen Content + Google-Business-Profil "
        "stärken (Standort, Öffnungszeiten, Bewertungen).",
        "Durchschnittsposition verbessert sich (9.1 → 8.6). Kurs beibehalten. 👍",
    ]

    return [uptime, booking, _demo_bookings_section(), ads, seo]


def _demo_history(report: dict) -> list[dict]:
    """14 Tage synthetische Historie für die Trend-Sparklines."""
    history = []
    for i in range(14):
        seo_clicks = round(250 + 60 * math.sin(i / 3) + i * 3)
        bookings = round(120 + 12 * math.sin(i / 2) + i)
        ads_clicks = round(35 + 8 * math.sin(i / 2.5))
        history.append({
            "date": f"2026-07-{i + 13:02d}",
            "sections": [
                {"key": "seo", "metrics": {"klicks": seo_clicks}},
                {"key": "bookings", "metrics": {"buchungen_zeitraum": bookings}},
                {"key": "google_ads", "metrics": {"klicks": ads_clicks}},
            ],
        })
    return history


def main() -> None:
    settings = load_settings()
    sections = _demo_sections()
    report = build_report(sections, settings)
    report["demo"] = True
    out = dashboard.generate(report, settings, history=_demo_history(report))
    print(f"Demo-Dashboard erzeugt: {out}")


if __name__ == "__main__":
    main()
