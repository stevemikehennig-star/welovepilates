"""Website-Monitoring: Erreichbarkeit, HTTP-Fehler, Ladezeit, On-Page-SEO-Basics
und tote interne Links.

Läuft ohne externe Zugangsdaten — braucht nur Netzzugriff auf die Seite.
"""
from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..config import Settings
from ..section import Section

USER_AGENT = (
    "Mozilla/5.0 (compatible; WeLovePilatesMonitor/0.1; "
    "+https://github.com/) monitoring bot"
)


def _get(url: str, timeout: int) -> tuple[requests.Response | None, float, str]:
    """Lädt eine URL, liefert (Response|None, Ladezeit, Fehlermeldung)."""
    start = time.monotonic()
    try:
        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True
        )
        return resp, time.monotonic() - start, ""
    except requests.RequestException as exc:
        return None, time.monotonic() - start, str(exc)


def _check_seo(html: str) -> tuple[list[str], dict[str, object]]:
    """On-Page-SEO-Basics prüfen. Liefert (Probleme, Kennzahlen)."""
    soup = BeautifulSoup(html, "html.parser")
    issues: list[str] = []
    metrics: dict[str, object] = {}

    title = (soup.title.string or "").strip() if soup.title else ""
    metrics["title_len"] = len(title)
    if not title:
        issues.append("Kein <title> vorhanden.")
    elif len(title) < 15:
        issues.append(f"Title zu kurz ({len(title)} Zeichen) — Ziel 30–60.")
    elif len(title) > 65:
        issues.append(f"Title zu lang ({len(title)} Zeichen) — wird abgeschnitten.")

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = (desc_tag.get("content", "").strip() if desc_tag else "")
    metrics["meta_description_len"] = len(desc)
    if not desc:
        issues.append("Keine Meta-Description — schwächt die Klickrate in Google.")
    elif len(desc) > 160:
        issues.append(f"Meta-Description zu lang ({len(desc)} Zeichen) — Ziel ≤ 160.")

    h1s = soup.find_all("h1")
    metrics["h1_count"] = len(h1s)
    if len(h1s) == 0:
        issues.append("Keine H1-Überschrift gefunden.")
    elif len(h1s) > 1:
        issues.append(f"Mehrere H1-Überschriften ({len(h1s)}) — idealerweise genau eine.")

    imgs = soup.find_all("img")
    missing_alt = [i for i in imgs if not i.get("alt")]
    metrics["images"] = len(imgs)
    metrics["images_without_alt"] = len(missing_alt)
    if imgs and len(missing_alt) > len(imgs) * 0.3:
        issues.append(
            f"{len(missing_alt)} von {len(imgs)} Bildern ohne alt-Text (SEO/Barrierefreiheit)."
        )

    if not soup.find("link", attrs={"rel": "canonical"}):
        issues.append("Kein Canonical-Tag gesetzt.")

    return issues, metrics


def _collect_internal_links(html: str, base_url: str, page_url: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        full = urljoin(page_url, href)
        if urlparse(full).netloc != host:
            continue
        full = full.split("#")[0]
        if full not in seen:
            seen.add(full)
            out.append(full)
        if len(out) >= limit:
            break
    return out


def run(settings: Settings) -> Section:
    cfg = settings.section("uptime")
    timeout = int(cfg.get("timeout_seconds", 20))
    slow_threshold = float(cfg.get("slow_threshold_seconds", 4.0))

    section = Section(key="uptime", title="Website & Fehler")
    items: list[dict[str, object]] = []
    all_seo_issues: list[str] = []
    worst = "ok"
    checked_pages = 0
    links_for_check: list[str] = []

    for page in cfg.get("pages", []):
        url = settings.url(page["path"])
        name = page.get("name", page["path"])
        resp, elapsed, err = _get(url, timeout)
        checked_pages += 1

        if resp is None:
            items.append({"page": name, "url": url, "status": "error",
                          "detail": f"Nicht erreichbar: {err}"})
            worst = "error"
            continue

        status_code = resp.status_code
        row: dict[str, object] = {
            "page": name, "url": url, "http": status_code,
            "load_seconds": round(elapsed, 2),
        }
        if status_code >= 500:
            row["status"] = "error"
            row["detail"] = f"Serverfehler (HTTP {status_code})"
            worst = "error"
        elif status_code >= 400:
            row["status"] = "error"
            row["detail"] = f"Seite liefert HTTP {status_code}"
            worst = "error"
        elif elapsed > slow_threshold:
            row["status"] = "warning"
            row["detail"] = f"Langsam: {elapsed:.1f}s (Schwelle {slow_threshold}s)"
            if worst == "ok":
                worst = "warning"
        else:
            row["status"] = "ok"

        # On-Page-SEO
        if page.get("check_seo") and status_code < 400 and resp.text:
            seo_issues, seo_metrics = _check_seo(resp.text)
            row["seo_issues"] = seo_issues
            row["seo_metrics"] = seo_metrics
            if seo_issues:
                all_seo_issues.extend(f"{name}: {i}" for i in seo_issues)

        # Links für die Broken-Link-Prüfung sammeln (nur von der Startseite)
        if cfg.get("check_broken_links") and page["path"] in ("/", "") and resp.text:
            links_for_check = _collect_internal_links(
                resp.text, settings.base_url, url, int(cfg.get("max_links_to_check", 40))
            )

        items.append(row)

    # Tote interne Links prüfen (HEAD, mit GET-Fallback)
    broken: list[dict[str, object]] = []
    for link in links_for_check:
        try:
            r = requests.head(link, timeout=timeout, allow_redirects=True,
                              headers={"User-Agent": USER_AGENT})
            if r.status_code >= 400 or r.status_code == 405:
                r = requests.get(link, timeout=timeout, allow_redirects=True,
                                 headers={"User-Agent": USER_AGENT})
            if r.status_code >= 400:
                broken.append({"url": link, "http": r.status_code})
        except requests.RequestException as exc:
            broken.append({"url": link, "http": "error", "detail": str(exc)})

    if broken:
        if worst == "ok":
            worst = "warning"

    # --- Zusammenfassung & Vorschläge ---
    section.status = worst
    section.items = items
    section.metrics = {
        "geprüfte_seiten": checked_pages,
        "tote_links": len(broken),
        "seo_probleme": len(all_seo_issues),
    }
    if broken:
        section.metrics["broken_links_list"] = broken

    errors = [i for i in items if i.get("status") == "error"]
    warnings = [i for i in items if i.get("status") == "warning"]
    if errors:
        section.summary = f"{len(errors)} Seite(n) mit Fehler, {len(broken)} tote Links."
    elif warnings or broken:
        section.summary = f"Alle Seiten erreichbar, aber {len(warnings)} langsam / {len(broken)} tote Links."
    else:
        section.summary = f"Alle {checked_pages} Seiten erreichbar und schnell."

    # SEO-Probleme als Vorschläge (die "SEO-Fortschritt"-Sektion ergänzt das um GSC-Daten)
    for issue in all_seo_issues[:10]:
        section.suggestions.append(f"On-Page: {issue}")
    for b in broken[:10]:
        section.suggestions.append(f"Toten Link reparieren/entfernen: {b['url']} (HTTP {b.get('http')})")

    return section
