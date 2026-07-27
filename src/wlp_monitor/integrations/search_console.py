"""Google-Search-Console-Datenabruf (SEO).

Authentifizierung über einen Service-Account (JSON als Umgebungsvariable).
Der Service-Account muss in der Search Console als Nutzer der Property
hinzugefügt sein. Bewertung/Empfehlungen: analysis/seo_insights.py.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..config import Credentials

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _service(creds: Credentials):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(creds.search_console_json())
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)


def _query(service, site: str, start: date, end: date,
           dimensions: list[str], row_limit: int = 1000) -> list[dict[str, Any]]:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
    rows = resp.get("rows", [])
    out = []
    for r in rows:
        keys = r.get("keys", [])
        entry = {dim: keys[i] for i, dim in enumerate(dimensions)}
        entry.update({
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": r.get("ctr", 0) * 100,
            "position": r.get("position", 0),
        })
        out.append(entry)
    return out


def fetch(creds: Credentials, site: str, lookback_days: int) -> dict[str, Any]:
    """Holt Totals, Top-Queries und Top-Pages für aktuellen & vorherigen Zeitraum."""
    service = _service(creds)

    # Search Console hat ~2-3 Tage Datenverzug
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=lookback_days)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=lookback_days)

    def totals(s: date, e: date) -> dict[str, float]:
        rows = _query(service, site, s, e, dimensions=["date"])
        clicks = sum(r["clicks"] for r in rows)
        impressions = sum(r["impressions"] for r in rows)
        # gewichtete Ø-Position
        pos = (sum(r["position"] * r["impressions"] for r in rows) / impressions) if impressions else 0
        return {
            "clicks": clicks,
            "impressions": impressions,
            "ctr": (clicks / impressions * 100) if impressions else 0,
            "avg_position": pos,
        }

    return {
        "totals_current": totals(start, end),
        "totals_previous": totals(prev_start, prev_end),
        "queries": _query(service, site, start, end, dimensions=["query"], row_limit=1000),
        "pages": _query(service, site, start, end, dimensions=["page"], row_limit=500),
        "date_range": {
            "current": [start.isoformat(), end.isoformat()],
            "previous": [prev_start.isoformat(), prev_end.isoformat()],
        },
    }
