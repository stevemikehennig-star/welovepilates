"""WeLovePilates Monitor — Einstiegspunkt / CLI.

Beispiele:
    python -m wlp_monitor.main                 # alles ausführen, Report + Dashboard + E-Mail
    python -m wlp_monitor.main --only uptime booking_flow --no-email
    python -m wlp_monitor.main --fail-on-error # Exit-Code != 0 bei Fehlerstatus (für CI-Alarm)
"""
from __future__ import annotations

import argparse
import sys
import traceback

from .config import Credentials, load_settings
from .section import STATUS_EMOJI, STATUS_LABEL, Section, errored
from . import storage
from .monitors import uptime, booking_flow
from .analysis import ads_insights, seo_insights, schedule_optimizer
from .reporting import dashboard, email_report
from .reporting.report import build_report

# Reihenfolge = Reihenfolge im Report. Buchungsprozess bewusst weit oben.
MODULES = {
    "uptime": ("website", lambda st, cr: uptime.run(st)),
    "booking_flow": ("website", lambda st, cr: booking_flow.run(st)),
    "google_ads": ("data", lambda st, cr: ads_insights.run(st, cr)),
    "seo": ("data", lambda st, cr: seo_insights.run(st, cr)),
    "bookings": ("data", lambda st, cr: schedule_optimizer.run(st, cr)),
}
ORDER = ["uptime", "booking_flow", "bookings", "google_ads", "seo"]


def run_module(key: str, settings, creds) -> Section:
    _, fn = MODULES[key]
    try:
        return fn(settings, creds)
    except Exception as exc:  # noqa: BLE001 - ein Modul darf den Rest nicht killen
        traceback.print_exc()
        return errored(key, key.title(), f"Unerwarteter Fehler: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WeLovePilates Monitor")
    parser.add_argument("--config", default=None, help="Pfad zu config.yaml")
    parser.add_argument("--only", nargs="+", choices=list(MODULES),
                        help="Nur diese Module ausführen")
    parser.add_argument("--no-email", action="store_true", help="Keine E-Mail senden")
    parser.add_argument("--email-on", choices=["always", "problems"], default="always",
                        help="'problems' = nur bei Status warning/error mailen (für häufige Checks)")
    parser.add_argument("--no-dashboard", action="store_true", help="Kein Dashboard erzeugen")
    parser.add_argument("--no-save", action="store_true", help="Keinen Snapshot speichern")
    parser.add_argument("--fail-on-error", action="store_true",
                        help="Exit-Code != 0 bei Gesamtstatus 'error' (für CI-Alarm)")
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    creds = Credentials()

    keys = args.only or ORDER
    keys = [k for k in ORDER if k in keys]  # stabile Reihenfolge

    print(f"WeLovePilates Monitor — {settings.today_str()}")
    print(f"Module: {', '.join(keys)}\n")

    sections: list[Section] = []
    for key in keys:
        print(f"→ {key} ...", flush=True)
        sec = run_module(key, settings, creds)
        print(f"   {STATUS_EMOJI[sec.status]} {STATUS_LABEL[sec.status]}: {sec.summary}")
        sections.append(sec)

    report = build_report(sections, settings)

    if not args.no_save:
        path = storage.save_snapshot(report, report["date"])
        print(f"\nSnapshot gespeichert: {path}")

    if not args.no_dashboard:
        try:
            out = dashboard.generate(report, settings)
            print(f"Dashboard erzeugt: {out}")
        except Exception as exc:  # noqa: BLE001
            print(f"Dashboard-Fehler: {exc}")

    overall = report["overall_status"]

    if not args.no_email:
        if args.email_on == "problems" and overall not in ("warning", "error"):
            print("E-Mail übersprungen (--email-on problems, keine Probleme).")
        else:
            result = email_report.send(report, settings, creds)
            if result.get("sent"):
                print(f"E-Mail gesendet an {result['to']}")
            else:
                print(f"E-Mail nicht gesendet: {result.get('reason')}")

    print(f"\nGesamtstatus: {STATUS_EMOJI[overall]} {STATUS_LABEL[overall]}")

    if args.fail_on_error and overall == "error":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
