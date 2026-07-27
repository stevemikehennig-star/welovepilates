"""Tagesreport aus den einzelnen Abschnitten zusammenstellen."""
from __future__ import annotations

from typing import Any

from ..config import Settings, utc_now
from ..section import Section, overall_status


def build_report(sections: list[Section], settings: Settings) -> dict[str, Any]:
    """Baut die serialisierbare Report-Struktur für Speicher/E-Mail/Dashboard."""
    overall = overall_status(sections)

    # Alle Vorschläge über alle Abschnitte hinweg einsammeln (für die Kurzübersicht)
    all_suggestions: list[dict[str, str]] = []
    for s in sections:
        for sug in s.suggestions:
            all_suggestions.append({"bereich": s.title, "vorschlag": sug})

    return {
        "date": settings.today_str(),
        "generated_at": utc_now().isoformat(),
        "site": settings.base_url,
        "overall_status": overall,
        "sections": [s.to_dict() for s in sections],
        "suggestions": all_suggestions,
    }
