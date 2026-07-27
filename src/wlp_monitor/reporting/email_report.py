"""Tagesreport als E-Mail versenden (SMTP)."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from ..config import Credentials, Settings
from ..section import STATUS_EMOJI, STATUS_LABEL


def _build_html(report: dict[str, Any]) -> str:
    overall = report["overall_status"]
    parts = [
        f"<h2>🩷 WeLovePilates Monitor — {report['date']}</h2>",
        f"<p><strong>Gesamtstatus:</strong> {STATUS_EMOJI[overall]} {STATUS_LABEL[overall]}</p>",
    ]

    if report.get("suggestions"):
        parts.append("<h3>🎯 Wichtigste Empfehlungen</h3><ul>")
        for s in report["suggestions"][:8]:
            parts.append(f"<li><strong>{s['bereich']}:</strong> {s['vorschlag']}</li>")
        parts.append("</ul>")

    for sec in report["sections"]:
        parts.append(
            f"<h3>{STATUS_EMOJI[sec['status']]} {sec['title']} "
            f"<small>({STATUS_LABEL[sec['status']]})</small></h3>"
        )
        parts.append(f"<p>{sec['summary']}</p>")
        simple = {k: v for k, v in (sec.get("metrics") or {}).items()
                  if not isinstance(v, (list, dict))}
        if simple:
            parts.append("<p>" + " · ".join(
                f"<strong>{k.replace('_', ' ')}:</strong> {v}" for k, v in simple.items()
            ) + "</p>")
        if sec.get("suggestions"):
            parts.append("<ul>")
            for s in sec["suggestions"]:
                parts.append(f"<li>{s}</li>")
            parts.append("</ul>")

    parts.append(
        "<hr><p style='color:#888;font-size:12px'>Automatisch erzeugt · "
        "Volles Dashboard auf GitHub Pages.</p>"
    )
    body = "".join(parts)
    return f"<div style='font-family:sans-serif;max-width:680px;margin:auto'>{body}</div>"


def _build_text(report: dict[str, Any]) -> str:
    lines = [f"WeLovePilates Monitor — {report['date']}",
             f"Gesamtstatus: {STATUS_LABEL[report['overall_status']]}", ""]
    if report.get("suggestions"):
        lines.append("Wichtigste Empfehlungen:")
        for s in report["suggestions"][:8]:
            lines.append(f" - {s['bereich']}: {s['vorschlag']}")
        lines.append("")
    for sec in report["sections"]:
        lines.append(f"[{STATUS_LABEL[sec['status']]}] {sec['title']}: {sec['summary']}")
    return "\n".join(lines)


def send(report: dict[str, Any], settings: Settings, creds: Credentials) -> dict[str, Any]:
    """Versendet die E-Mail. Liefert ein Status-Dict (kein Abbruch bei Fehlern)."""
    cfg = settings.section("reporting").get("email", {})
    if not cfg.get("enabled", True):
        return {"sent": False, "reason": "E-Mail deaktiviert."}
    if not creds.smtp_ready():
        return {"sent": False, "reason": "SMTP nicht konfiguriert (siehe SETUP.md)."}

    smtp = creds.smtp()
    to_addr = cfg.get("to", smtp["user"])
    overall = report["overall_status"]
    prefix = cfg.get("subject_prefix", "[WeLovePilates Monitor]")
    subject = f"{prefix} {report['date']} — {STATUS_EMOJI[overall]} {STATUS_LABEL[overall]}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp["from"]
    msg["To"] = to_addr
    msg.attach(MIMEText(_build_text(report), "plain", "utf-8"))
    msg.attach(MIMEText(_build_html(report), "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=30) as server:
            server.starttls()
            server.login(smtp["user"], smtp["password"])
            server.sendmail(smtp["from"], [to_addr], msg.as_string())
        return {"sent": True, "to": to_addr}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "reason": f"SMTP-Fehler: {exc}"}
