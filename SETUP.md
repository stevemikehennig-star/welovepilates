# Einrichtung — WeLovePilates Monitor

Diese Anleitung führt Schritt für Schritt durch die Einrichtung. Reihenfolge egal — jedes Modul funktioniert unabhängig. Was noch nicht eingerichtet ist, erscheint im Report als „⚙️ nicht eingerichtet“.

> **Wichtig:** Zugangsdaten niemals in Dateien committen. Lokal in `.env`, in GitHub unter **Settings → Secrets and variables → Actions**.

---

## 0. Überblick der benötigten Secrets

| Secret | Wofür | Pflicht für |
|---|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | E-Mail-Versand | E-Mail-Report |
| `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID` | Google Ads API | Ads-Auswertung |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Search Console API | SEO-Modul |
| `WIX_API_KEY`, `WIX_SITE_ID` | Wix Bookings API | Kursauswertung |

---

## 1. E-Mail-Versand (SMTP) — für den Report per Mail

Am einfachsten mit Gmail:

1. Google-Konto → **Sicherheit** → 2-Faktor-Authentifizierung aktivieren.
2. https://myaccount.google.com/apppasswords öffnen → **App-Passwort** erstellen (16 Zeichen).
3. Secrets setzen:
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `587`
   - `SMTP_USER` = deine Gmail-Adresse
   - `SMTP_PASSWORD` = das **App-Passwort** (nicht das normale Passwort!)

Die Empfänger-Adresse steht in `config.yaml` → `reporting.email.to` (aktuell `stevemikehennig@gmail.com`).

---

## 2. Wix Bookings — Kursbuchungs-Auswertung

1. Im **Wix-Konto** anmelden → https://manage.wix.com
2. Rechts oben aufs Profil → **Einstellungen** → **API-Schlüssel** (API Keys Manager),
   oder direkt: https://manage.wix.com/account/api-keys
3. **Neuen API-Schlüssel generieren**. Berechtigungen mindestens: *Wix Bookings — Lesen* (Bookings/Read).
4. Den Schlüssel kopieren (wird nur einmal angezeigt!) → Secret `WIX_API_KEY`.
5. **Site-ID** ermitteln: Im Wix-Dashboard der Website → URL enthält die Site-ID, oder unter
   **Einstellungen → Website-Info**. → Secret `WIX_SITE_ID`.
6. Falls der Schlüssel auf **Konto-Ebene** liegt, zusätzlich `WIX_ACCOUNT_ID` setzen.

> Die Felder der Wix-Bookings-Antwort können je nach Setup leicht abweichen. Falls Kurse/Zeiten
> nicht sauber erkannt werden, in `src/wlp_monitor/integrations/wix_bookings.py` die Funktion
> `_normalize()` anpassen. Dokumentation: https://dev.wix.com/docs/rest/business-solutions/bookings

---

## 3. Google Search Console — SEO-Modul

Am robustesten per **Service-Account**:

1. https://console.cloud.google.com → Projekt anlegen (oder vorhandenes wählen).
2. **APIs & Dienste → Bibliothek** → „Google Search Console API“ **aktivieren**.
3. **APIs & Dienste → Anmeldedaten → Anmeldedaten erstellen → Dienstkonto**.
4. Beim Dienstkonto → **Schlüssel → Neuer Schlüssel → JSON** herunterladen.
5. Den **kompletten JSON-Inhalt** als **einzeiligen** Wert in Secret `GOOGLE_SERVICE_ACCOUNT_JSON` einfügen.
6. Wichtig: In der **Search Console** (https://search.google.com/search-console) →
   Property auswählen → **Einstellungen → Nutzer und Berechtigungen → Nutzer hinzufügen** →
   die **E-Mail des Dienstkontos** (`...@...iam.gserviceaccount.com`) als **Vollständig** (oder eingeschränkt) hinzufügen.
7. In `config.yaml` → `seo.search_console_property` die Property eintragen:
   - Domain-Property: `sc-domain:welovepilates.de`
   - oder URL-Property: `https://www.welovepilates.de/`

---

## 4. Google Ads — Kampagnen-Auswertung

Etwas aufwändiger (Google-Vorgabe). Schritte:

1. **Developer-Token:** In einem **Google-Ads-Verwaltungskonto (MCC)** → Tools → **API-Center** →
   Developer-Token beantragen. → Secret `GOOGLE_ADS_DEVELOPER_TOKEN`.
   (Für Basiszugriff genügt oft „Basic Access“; die Beantragung kann 1–2 Tage dauern.)
2. **OAuth-Client:** In der Google Cloud Console → **Anmeldedaten → OAuth-Client-ID erstellen**
   (Typ „Desktop“). → `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`.
3. **Refresh-Token generieren:** Mit dem offiziellen Google-Ads-Python-Beispiel
   `generate_user_credentials.py`
   (https://github.com/googleads/google-ads-python/blob/main/examples/authentication/generate_user_credentials.py)
   einmalig den Login durchführen → `GOOGLE_ADS_REFRESH_TOKEN`.
4. **Kundennummer:** Die 10-stellige Ads-Kundennummer **ohne Bindestriche** → `GOOGLE_ADS_CUSTOMER_ID`.
5. **Nur bei MCC:** die MCC-Kundennummer → `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (sonst leer lassen).

Schwellwerte (hoher CPA, niedrige CTR, Budget-Limit, verschwendetes Budget) lassen sich in
`config.yaml` → `google_ads.thresholds` anpassen.

---

## 5. Buchungs-Flow-Test an das echte Wix-Widget anpassen

Der Buchungs-Test (`config.yaml` → `booking_flow`) nutzt zunächst **generische Selektoren**.
Bitte einmalig anpassen:

1. `booking_flow.start_url` auf die echte Buchungsseite setzen (z. B. `.../buchen` oder die
   Seite mit dem Wix-Bookings-Kalender).
2. Die `steps` an den tatsächlichen Ablauf anpassen. Verfügbare Aktionen:
   - `goto` — Seite öffnen (`target: start_url` oder eine URL)
   - `expect_visible` — auf ein Element warten (`selector`)
   - `click_first` — erstes passendes Element klicken (`selector`)
   - `wait` — feste Pause (`ms`)
3. Selektoren findest du im Browser mit Rechtsklick → *Untersuchen*. Wix nutzt oft
   `data-hook`-Attribute (z. B. `[data-hook="book-button"]`).

> Der Test bucht **nichts** real — er stoppt vor dem verbindlichen Schritt. Bei einem Fehler
> wird (optional) ein Screenshot unter `docs/assets/booking/` abgelegt.

---

## 6. GitHub Secrets setzen

1. Repository → **Settings → Secrets and variables → Actions → New repository secret**.
2. Alle benötigten Secrets aus der Tabelle in Abschnitt 0 anlegen.

---

## 7. GitHub Pages aktivieren (Dashboard)

1. Repository → **Settings → Pages**.
2. **Source:** „Deploy from a branch“.
3. **Branch:** den Branch mit dem Dashboard wählen (nach dem Merge in `main`: `main`), **Folder: `/docs`**.
4. Speichern. Nach dem nächsten Lauf ist das Dashboard unter
   `https://<dein-github-name>.github.io/welovepilates/` erreichbar.

> Der tägliche Workflow committet `docs/` automatisch zurück ins Repo (dafür ist
> `permissions: contents: write` gesetzt). Damit aktualisiert sich das Dashboard von selbst.

---

## 8. Workflows starten / testen

- Manuell testen: Repository → **Actions** → Workflow wählen → **Run workflow**.
- Zeitpläne: `daily-report.yml` (täglich ~06 Uhr) und `booking-monitor.yml` (alle 3 Std).
  Cron-Zeiten sind **UTC** — bei Bedarf in den `.yml`-Dateien anpassen.
- Schlägt der Buchungs-Check fehl, wird der Lauf **rot** (GitHub benachrichtigt automatisch)
  und es geht eine E-Mail raus.

---

## Fragen / Anpassungen

Fast alles Verhalten steckt in `config.yaml`. Für tiefergehende Änderungen (neue Kennzahlen,
andere Vorschlagslogik) sind die Module in `src/wlp_monitor/` bewusst klein und kommentiert gehalten.
