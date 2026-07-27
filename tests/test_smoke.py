"""Smoke-Tests: Pipeline läuft ohne Zugangsdaten sauber durch."""
from __future__ import annotations

from wlp_monitor.analysis import ads_insights, schedule_optimizer, seo_insights
from wlp_monitor.config import Credentials, load_settings
from wlp_monitor.reporting import dashboard, email_report
from wlp_monitor.reporting.report import build_report
from wlp_monitor.section import Section, overall_status


def test_config_loads():
    s = load_settings()
    assert s.base_url.startswith("http")
    assert s.timezone_name == "Europe/Berlin"


def test_modules_degrade_without_credentials():
    """Ohne Secrets müssen die Datenmodule 'not_configured' liefern, nicht crashen."""
    s = load_settings()
    creds = Credentials()  # leeres Environment im Test
    for mod in (ads_insights, seo_insights, schedule_optimizer):
        sec = mod.run(s, creds)
        assert isinstance(sec, Section)
        assert sec.status in ("not_configured", "info", "ok", "warning", "error")


def test_overall_status_ranking():
    secs = [
        Section(key="a", title="A", status="ok"),
        Section(key="b", title="B", status="warning"),
        Section(key="c", title="C", status="not_configured"),
    ]
    assert overall_status(secs) == "warning"
    secs.append(Section(key="d", title="D", status="error"))
    assert overall_status(secs) == "error"


def test_build_report_and_dashboard(tmp_path):
    s = load_settings()
    secs = [
        Section(key="uptime", title="Website & Fehler", status="ok",
                summary="alles ok",
                items=[{"page": "Start", "http": 200, "status": "ok"}],
                metrics={"geprüfte_seiten": 1}),
    ]
    report = build_report(secs, s)
    assert report["overall_status"] == "ok"
    assert report["sections"][0]["title"] == "Website & Fehler"

    out = dashboard.generate(report, s, history=[], output_name="test.html")
    html = out.read_text(encoding="utf-8")
    assert "WeLovePilates Monitor" in html
    assert "Website &amp; Fehler" in html or "Website & Fehler" in html
    out.unlink()


def test_email_bodies_render():
    s = load_settings()
    report = build_report(
        [Section(key="x", title="Test", status="ok", summary="ok",
                 suggestions=["Mach dies"], metrics={"a": 1})],
        s,
    )
    html = email_report._build_html(report)
    text = email_report._build_text(report)
    assert "Mach dies" in html
    assert "Test" in text


def test_heatmap_builder():
    slots = {(0, 8): [8, 7, 8], (2, 18): [4, 5]}
    hm = schedule_optimizer._build_heatmap(slots, capacity=8)
    assert hm["weekdays"][0] == "Mo"
    assert len(hm["grid"]) == 7
