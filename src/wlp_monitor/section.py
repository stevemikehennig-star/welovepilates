"""Gemeinsames Datenmodell für Report-Abschnitte.

Jeder Monitor / jede Integration liefert eine `Section` zurück. Das Reporting
(E-Mail & Dashboard) rendert einheitlich aus diesen Abschnitten.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Status-Rangfolge für die Gesamtbewertung (höher = kritischer)
STATUS_ORDER = {"ok": 0, "info": 1, "not_configured": 1, "warning": 2, "error": 3}
STATUS_LABEL = {
    "ok": "OK",
    "info": "Info",
    "not_configured": "Nicht eingerichtet",
    "warning": "Achtung",
    "error": "Fehler",
}
STATUS_EMOJI = {
    "ok": "✅",
    "info": "ℹ️",
    "not_configured": "⚙️",
    "warning": "⚠️",
    "error": "🚨",
}


@dataclass
class Section:
    key: str
    title: str
    status: str = "ok"                       # ok | info | warning | error | not_configured
    summary: str = ""                        # eine Zeile Zusammenfassung
    metrics: dict[str, Any] = field(default_factory=dict)   # Kennzahlen (Name -> Wert)
    items: list[dict[str, Any]] = field(default_factory=list)  # Detailzeilen
    suggestions: list[str] = field(default_factory=list)    # konkrete Vorschläge
    setup_hint: str = ""                     # nur bei status == not_configured
    error_detail: str = ""                   # technische Details bei Fehlern

    def worse_than(self, other_status: str) -> bool:
        return STATUS_ORDER.get(self.status, 0) > STATUS_ORDER.get(other_status, 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def not_configured(key: str, title: str, hint: str) -> Section:
    return Section(
        key=key,
        title=title,
        status="not_configured",
        summary="Noch nicht eingerichtet — siehe SETUP.md.",
        setup_hint=hint,
    )


def errored(key: str, title: str, message: str) -> Section:
    return Section(
        key=key,
        title=title,
        status="error",
        summary="Modul konnte nicht ausgeführt werden.",
        error_detail=message,
    )


def overall_status(sections: list[Section]) -> str:
    """Schlimmster Status über alle Abschnitte (not_configured zählt nicht als kritisch)."""
    worst = "ok"
    for s in sections:
        if s.status in ("not_configured", "info"):
            continue
        if STATUS_ORDER.get(s.status, 0) > STATUS_ORDER.get(worst, 0):
            worst = s.status
    return worst
