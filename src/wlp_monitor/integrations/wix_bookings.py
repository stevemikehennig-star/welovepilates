"""Wix-Bookings-Datenabruf über die Wix REST API.

Holt die Buchungen für einen Zeitraum und normalisiert sie in eine einfache
Struktur (Kurs, Startzeit, Teilnehmerzahl, Status). Auswertung & Kursplan-
Optimierung: analysis/schedule_optimizer.py.

Docs: https://dev.wix.com/docs/rest/business-solutions/bookings
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..config import Credentials

BASE = "https://www.wixapis.com"
BOOKINGS_QUERY = f"{BASE}/bookings/v2/bookings/query"


def _headers(wix: dict[str, str]) -> dict[str, str]:
    h = {
        "Authorization": wix["api_key"],
        "wix-site-id": wix["site_id"],
        "Content-Type": "application/json",
    }
    if wix.get("account_id"):
        h["wix-account-id"] = wix["account_id"]
    return h


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Wix liefert ISO-8601, teils mit 'Z'
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize(booking: dict[str, Any]) -> dict[str, Any]:
    """Extrahiert die relevanten Felder robust aus einem Wix-Booking-Objekt."""
    entity = booking.get("bookedEntity", {}) or {}
    slot = entity.get("slot", {}) or {}
    schedule = entity.get("schedule", {}) or {}

    title = (
        entity.get("title")
        or slot.get("serviceId")
        or schedule.get("scheduleId")
        or "Unbekannter Kurs"
    )
    start = _parse_dt(slot.get("startDate") or schedule.get("firstSessionStart")
                      or booking.get("startDate"))
    participants = (
        booking.get("numberOfParticipants")
        or booking.get("totalParticipants")
        or 1
    )
    return {
        "id": booking.get("id"),
        "service": title,
        "service_id": slot.get("serviceId"),
        "start": start.isoformat() if start else None,
        "participants": int(participants) if participants else 1,
        "status": booking.get("status", "UNKNOWN"),
        "created": booking.get("createdDate"),
    }


def fetch(creds: Credentials, lookback_days: int) -> list[dict[str, Any]]:
    """Holt Buchungen der letzten `lookback_days` Tage (paginierend)."""
    wix = creds.wix()
    headers = _headers(wix)

    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    bookings: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(20):  # Sicherheitslimit gegen Endlos-Pagination
        query: dict[str, Any] = {
            "query": {
                "filter": {"createdDate": {"$gte": since}},
                "sort": [{"fieldName": "createdDate", "order": "DESC"}],
                "cursorPaging": {"limit": 100},
            }
        }
        if cursor:
            query["query"]["cursorPaging"]["cursor"] = cursor
        resp = requests.post(BOOKINGS_QUERY, json=query, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        page = data.get("bookings", [])
        bookings.extend(_normalize(b) for b in page)

        paging = (data.get("pagingMetadata") or {})
        cursor = (paging.get("cursors") or {}).get("next")
        if not cursor or not page:
            break

    return bookings
