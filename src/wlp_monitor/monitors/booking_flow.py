"""Synthetischer Buchungs-Flow-Test mit Playwright.

Simuliert die Schritte eines Kunden bis KURZ VOR die echte Buchung/Bezahlung
(es wird NICHT real gebucht) und meldet, sobald einer der Schritte fehlschlägt.
Erfasst außerdem JavaScript-Fehler und fehlgeschlagene Netzwerk-Requests.

Die konkreten Schritte kommen aus config.yaml -> booking_flow.steps und müssen
an das echte Wix-Bookings-Widget angepasst werden (die Selektoren dort sind
generisch als Startpunkt gewählt).
"""
from __future__ import annotations

from pathlib import Path

from ..config import ROOT, Settings
from ..section import Section, errored

SCREENSHOT_DIR = ROOT / "docs" / "assets" / "booking"


def _resolve_target(target: str, start_url: str) -> str:
    return start_url if target == "start_url" else target


def run(settings: Settings) -> Section:
    cfg = settings.section("booking_flow")
    section = Section(key="booking_flow", title="Buchungsprozess")

    if not cfg.get("enabled", True):
        section.status = "info"
        section.summary = "Buchungs-Test ist in der Konfiguration deaktiviert."
        return section

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return errored(
            "booking_flow", "Buchungsprozess",
            "Playwright ist nicht installiert. In CI übernimmt das der Workflow "
            "(pip install + 'playwright install chromium').",
        )

    start_url = cfg.get("start_url") or settings.url("/buchen")
    steps = cfg.get("steps", [])
    js_errors: list[str] = []
    failed_requests: list[str] = []
    step_results: list[dict[str, object]] = []
    screenshot_path = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="de-DE",
            )
            page = context.new_page()

            page.on("pageerror", lambda exc: js_errors.append(str(exc)))
            page.on("console", lambda msg: js_errors.append(msg.text)
                    if msg.type == "error" else None)

            def _on_response(resp):
                try:
                    if resp.status >= 500:
                        failed_requests.append(f"HTTP {resp.status} {resp.url}")
                except Exception:
                    pass
            page.on("response", _on_response)

            failed_step = None
            for idx, step in enumerate(steps, start=1):
                action = step.get("action")
                desc = step.get("description", action)
                result = {"step": idx, "description": desc, "action": action}
                try:
                    if action == "goto":
                        url = _resolve_target(step.get("target", "start_url"), start_url)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2500)  # Wix lädt Widgets asynchron nach
                    elif action == "expect_visible":
                        page.locator(step["selector"]).first.wait_for(
                            state="visible", timeout=15000)
                    elif action == "click_first":
                        page.locator(step["selector"]).first.click(timeout=15000)
                        page.wait_for_timeout(2000)
                    elif action == "wait":
                        page.wait_for_timeout(int(step.get("ms", 1000)))
                    else:
                        result["status"] = "warning"
                        result["detail"] = f"Unbekannte Aktion '{action}' übersprungen."
                        step_results.append(result)
                        continue
                    result["status"] = "ok"
                except PWTimeout:
                    result["status"] = "error"
                    result["detail"] = "Element/Schritt nicht innerhalb des Timeouts erreichbar."
                    failed_step = result
                except Exception as exc:  # noqa: BLE001 - Schritt-Robustheit
                    result["status"] = "error"
                    result["detail"] = str(exc)
                    failed_step = result
                step_results.append(result)
                if failed_step:
                    break

            if failed_step and cfg.get("screenshot_on_failure", True):
                SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                screenshot_path = str(
                    (SCREENSHOT_DIR / f"failure-{settings.today_str()}.png").relative_to(ROOT))
                try:
                    page.screenshot(path=str(ROOT / screenshot_path), full_page=True)
                except Exception:
                    screenshot_path = ""

            context.close()
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return errored("booking_flow", "Buchungsprozess",
                       f"Browser-Test fehlgeschlagen: {exc}")

    # --- Auswertung ---
    section.items = step_results
    failed = [s for s in step_results if s.get("status") == "error"]
    section.metrics = {
        "schritte_gesamt": len(steps),
        "schritte_ok": len([s for s in step_results if s.get("status") == "ok"]),
        "js_fehler": len(js_errors),
        "server_fehler_requests": len(failed_requests),
    }
    if js_errors:
        section.metrics["js_errors_list"] = js_errors[:10]
    if failed_requests:
        section.metrics["failed_requests_list"] = failed_requests[:10]
    if screenshot_path:
        section.metrics["screenshot"] = screenshot_path

    if failed:
        section.status = "error"
        first = failed[0]
        section.summary = (
            f"BUCHUNG GESTÖRT bei Schritt {first['step']}: {first['description']}."
        )
        section.suggestions.append(
            "Buchungswidget dringend manuell prüfen — Kunden können evtl. nicht buchen!"
        )
        if screenshot_path:
            section.suggestions.append(f"Screenshot des Fehlers: {screenshot_path}")
    else:
        if js_errors or failed_requests:
            section.status = "warning"
            section.summary = (
                "Buchung durchlaufbar, aber JavaScript-/Serverfehler im Hintergrund."
            )
        else:
            section.status = "ok"
            section.summary = "Buchungsprozess vollständig durchlaufbar."

    if js_errors:
        section.suggestions.append(
            f"{len(js_errors)} JavaScript-Fehler im Buchungs-Widget prüfen (siehe Details)."
        )

    return section
