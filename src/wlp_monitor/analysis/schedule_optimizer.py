"""Kursbuchungs-Auswertung & Kursplan-Optimierung aus Wix-Bookings-Daten.

Liefert:
  * tägliche Auswertung: welche Kurse wurden gebucht, zu welcher Uhrzeit
  * Nachfrage-Heatmap (Wochentag × Uhrzeit) über einen längeren Zeitraum
  * konkrete Vorschläge für einen optimierten Kursplan
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import Credentials, Settings
from ..integrations import wix_bookings
from ..section import Section, errored, not_configured

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

SETUP_HINT = (
    "Wix Bookings anbinden: im Wix-Konto einen API-Key erstellen (API Keys "
    "Manager) und API-Key + Site-ID als Secrets WIX_API_KEY / WIX_SITE_ID "
    "hinterlegen. Details in SETUP.md."
)

# Nur bestätigte/gültige Buchungen zählen
VALID_STATUS = {"CONFIRMED", "PENDING", "WAITING_LIST", "UNKNOWN"}


def _local(dt_iso: str | None, tz: ZoneInfo) -> datetime | None:
    if not dt_iso:
        return None
    try:
        dt = datetime.fromisoformat(dt_iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def run(settings: Settings, creds: Credentials) -> Section:
    cfg = settings.section("bookings")
    if not cfg.get("enabled", True):
        s = Section(key="bookings", title="Kursbuchungen & Kursplan", status="info")
        s.summary = "Kursauswertung ist deaktiviert."
        return s

    if not creds.wix_ready():
        return not_configured("bookings", "Kursbuchungen & Kursplan", SETUP_HINT)

    tz = settings.tz
    optimizer_days = int(cfg.get("optimizer_lookback_days", 30))
    capacity = int(cfg.get("default_capacity", 8))
    high_pct = float(cfg.get("high_demand_pct", 85))
    low_pct = float(cfg.get("low_demand_pct", 40))

    try:
        bookings = wix_bookings.fetch(creds, lookback_days=optimizer_days)
    except Exception as exc:  # noqa: BLE001
        return errored("bookings", "Kursbuchungen & Kursplan",
                       f"Datenabruf fehlgeschlagen: {exc}")

    section = Section(key="bookings", title="Kursbuchungen & Kursplan")

    valid = [b for b in bookings if b.get("status", "UNKNOWN") in VALID_STATUS]

    # --- Tagesauswertung (gestern gebuchte / für heute stattfindende Kurse) ---
    yesterday = settings.now().date()
    todays_lookback = int(cfg.get("lookback_days", 1))
    recent = []
    for b in valid:
        start = _local(b.get("start"), tz)
        if start is None:
            continue
        delta_days = (start.date() - yesterday).days
        # Kurse, die in den letzten `lookback_days` gebucht wurden bzw. anstehen
        if -todays_lookback <= delta_days <= 7:
            recent.append((start, b))
    recent.sort(key=lambda x: x[0])

    # --- Nachfrage-Aggregation über den Optimierungszeitraum ---
    # slot_key = (weekday_index, hour) -> Liste Teilnehmerzahlen
    slot_participants: dict[tuple[int, int], list[int]] = defaultdict(list)
    slot_service: dict[tuple[int, int], defaultdict] = defaultdict(lambda: defaultdict(int))
    service_totals: dict[str, int] = defaultdict(int)

    for b in valid:
        start = _local(b.get("start"), tz)
        if start is None:
            continue
        key = (start.weekday(), start.hour)
        p = int(b.get("participants", 1))
        slot_participants[key].append(p)
        slot_service[key][b.get("service", "?")] += p
        service_totals[b.get("service", "?")] += p

    # Auslastung je Slot berechnen
    slot_rows = []
    high_demand, low_demand = [], []
    for (wd, hour), plist in slot_participants.items():
        sessions = len(plist)
        avg_participants = sum(plist) / sessions if sessions else 0
        utilization = avg_participants / capacity * 100 if capacity else 0
        top_service = max(slot_service[(wd, hour)].items(), key=lambda x: x[1])[0] \
            if slot_service[(wd, hour)] else "?"
        row = {
            "slot": f"{WEEKDAYS[wd]} {hour:02d}:00",
            "weekday": wd, "hour": hour,
            "buchungen": sum(plist),
            "termine": sessions,
            "ø_teilnehmer": round(avg_participants, 1),
            "auslastung": round(utilization),
            "top_kurs": top_service,
        }
        slot_rows.append(row)
        if utilization >= high_pct and sessions >= 2:
            high_demand.append(row)
        elif utilization <= low_pct and sessions >= 2:
            low_demand.append(row)

    slot_rows.sort(key=lambda r: r["buchungen"], reverse=True)
    high_demand.sort(key=lambda r: r["auslastung"], reverse=True)
    low_demand.sort(key=lambda r: r["auslastung"])

    # --- Detail: Tagesbuchungen ---
    section.items = [
        {
            "zeit": start.strftime("%a %d.%m. %H:%M"),
            "kurs": b.get("service"),
            "teilnehmer": b.get("participants"),
            "status": b.get("status"),
        }
        for start, b in recent[:40]
    ]

    total_bookings = sum(int(b.get("participants", 1)) for b in valid)
    section.metrics = {
        "buchungen_zeitraum": total_bookings,
        "zeitraum_tage": optimizer_days,
        "aktive_kurse": len(service_totals),
        "beliebtester_kurs": max(service_totals.items(), key=lambda x: x[1])[0]
        if service_totals else "—",
        "top_slots": slot_rows[:8],
        "heatmap": _build_heatmap(slot_participants, capacity),
    }

    # --- Vorschläge für optimierten Kursplan ---
    suggestions: list[str] = []
    for r in high_demand[:5]:
        suggestions.append(
            f"{r['slot']} ist stark nachgefragt ({r['auslastung']}% Auslastung, "
            f"Kurs „{r['top_kurs']}“). Zusätzlichen Kurs in diesem Zeitfenster anbieten "
            f"oder benachbarte Slots öffnen."
        )
    for r in low_demand[:4]:
        suggestions.append(
            f"{r['slot']} ist schwach ausgelastet ({r['auslastung']}%). Zeitfenster "
            f"überdenken, mit einem stärkeren Slot zusammenlegen oder Kursart wechseln."
        )
    # Bestes Zeitfenster hervorheben
    if slot_rows:
        best = slot_rows[0]
        suggestions.append(
            f"Top-Zeitfenster insgesamt: {best['slot']} ({best['buchungen']} Buchungen). "
            f"Kernangebot dort sichern."
        )
    if not suggestions:
        suggestions.append(
            "Noch zu wenig Buchungsdaten für belastbare Vorschläge — Auswertung wächst täglich."
        )

    section.suggestions = suggestions
    section.summary = (
        f"{total_bookings} Buchungen in {optimizer_days} Tagen, "
        f"{len(high_demand)} stark / {len(low_demand)} schwach ausgelastete Slots."
    )
    if high_demand or low_demand:
        section.status = "info"
    return section


def _build_heatmap(slot_participants: dict[tuple[int, int], list[int]],
                   capacity: int) -> dict[str, object]:
    """Heatmap-Daten (Wochentag × Stunde) fürs Dashboard aufbereiten."""
    hours = sorted({h for (_wd, h) in slot_participants})
    if not hours:
        hours = list(range(7, 21))
    grid = []
    for wd in range(7):
        row = []
        for h in hours:
            plist = slot_participants.get((wd, h), [])
            if plist:
                util = round(sum(plist) / len(plist) / capacity * 100) if capacity else 0
            else:
                util = None
            row.append(util)
        grid.append(row)
    return {"weekdays": WEEKDAYS, "hours": hours, "grid": grid}
