# 🩷 WeLovePilates Monitor

Automatische **Überwachung und Optimierung** der [welovepilates.de](https://www.welovepilates.de)-Website. Läuft täglich per GitHub Actions und liefert Report per **E-Mail** und als **Web-Dashboard** (GitHub Pages).

## Was der Monitor macht

| Bereich | Was geprüft/ausgewertet wird | Ergebnis |
|---|---|---|
| **Website & Fehler** | Erreichbarkeit aller wichtigen Seiten, HTTP-Fehler, Ladezeiten, tote Links, On-Page-SEO-Basics (Title, Meta, H1, Alt-Texte) | Alarm bei Fehlern |
| **Buchungsprozess** ⭐ | Simuliert den kompletten Buchungs-Flow im Browser (Playwright) bis kurz vor die echte Buchung — erkennt, wenn Kunden nicht buchen können. Erfasst JavaScript-/Serverfehler. | Alarm, wenn Buchung gestört |
| **Kursbuchungen & Kursplan** | Welche Kurse zu welcher Uhrzeit gebucht wurden (Wix Bookings), Nachfrage-Heatmap (Wochentag × Uhrzeit), Auslastung je Slot | Vorschläge für optimierten Kursplan |
| **Google Ads** | Tägliche Kampagnen-Auswertung: Kosten, CPA, CTR, ROAS, Budget-Limits, Keyword-Verschwendung | Konkrete Optimierungsvorschläge |
| **SEO-Fortschritt** | Search-Console-Daten: Klicks/Impressionen/Position im Trend, "fast auf Seite 1"-Keywords, schwache CTR | Vorschläge, wie die Seite weiter nach oben kommt |

## So läuft es

```
GitHub Actions (Cron)
  ├─ Täglicher Report  (06–07 Uhr)  → alle Module → E-Mail + Dashboard
  └─ Buchungs-Check    (alle 3 Std) → Website + Buchung → Alarm nur bei Problem
```

- **Historie** wird als JSON in `data/history/` gespeichert (versioniert) → Trends im Dashboard.
- **Dashboard** wird nach `docs/` gebaut und über **GitHub Pages** veröffentlicht.
- Fehlende Zugangsdaten führen **nicht** zum Absturz — das jeweilige Modul meldet „nicht eingerichtet".

## Schnellstart (lokal)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
python -m playwright install chromium        # für den Buchungs-Test

cp .env.example .env                          # Zugangsdaten eintragen (siehe SETUP.md)

# Demo-Dashboard mit Beispieldaten ansehen (ohne Zugangsdaten):
python scripts/generate_demo.py
open docs/index.html

# Echter Lauf (nutzt die Werte aus .env):
python -m wlp_monitor.main
python -m wlp_monitor.main --only uptime booking_flow   # nur Website + Buchung
python -m wlp_monitor.main --no-email --no-save          # Test ohne Nebenwirkungen
```

## Einrichtung

Die vollständige Anleitung (Google-Ads-Token, Search-Console-Service-Account, Wix-API-Key, GitHub Secrets & Pages) steht in **[SETUP.md](SETUP.md)**.

## Projektstruktur

```
src/wlp_monitor/
├── config.py            Konfiguration (config.yaml) + Secrets (Environment)
├── section.py           gemeinsames Report-Datenmodell
├── storage.py           Historie speichern/laden (data/history/*.json)
├── main.py              CLI / Orchestrator
├── monitors/
│   ├── uptime.py        Website-Erreichbarkeit, Fehler, On-Page-SEO, tote Links
│   └── booking_flow.py  Buchungs-Flow-Test (Playwright)
├── integrations/
│   ├── google_ads.py    Google Ads API
│   ├── search_console.py Search Console API
│   └── wix_bookings.py  Wix Bookings API
├── analysis/
│   ├── ads_insights.py       Ads-Auswertung + Vorschläge
│   ├── seo_insights.py       SEO-Auswertung + Vorschläge
│   └── schedule_optimizer.py Kursbuchungen + Kursplan-Optimierung
└── reporting/
    ├── report.py        Report zusammenstellen
    ├── email_report.py  E-Mail-Versand (SMTP)
    └── dashboard.py     HTML-Dashboard (GitHub Pages)

config.yaml              nicht-geheime Einstellungen (URLs, Schwellwerte, Buchungs-Schritte)
.env.example             Vorlage für Zugangsdaten
.github/workflows/       tägliche & 3-stündliche Läufe
scripts/generate_demo.py Demo-Dashboard mit Beispieldaten
tests/                   Smoke-Tests
```

## Anpassen

- **Buchungs-Flow-Schritte / Selektoren:** `config.yaml` → `booking_flow.steps` an das echte Wix-Widget anpassen.
- **Überwachte Seiten & Schwellwerte:** `config.yaml` → `uptime`, `google_ads`, `seo`, `bookings`.
- **Kapazität pro Kurs / Nachfrage-Grenzen:** `config.yaml` → `bookings`.
