"""Google-Ads-Datenabruf über die offizielle Google Ads API.

Liefert Kampagnen- und Keyword-Kennzahlen für zwei Zeiträume (aktueller Tag
und Vergleichszeitraum). Die eigentliche Bewertung/Empfehlungen erfolgen in
analysis/ads_insights.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..config import Credentials


def _client(creds: dict[str, str]):
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": creds["developer_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "use_proto_plus": True,
    }
    if creds.get("login_customer_id"):
        config["login_customer_id"] = creds["login_customer_id"]
    return GoogleAdsClient.load_from_dict(config)


def _date_clause(start: date, end: date) -> str:
    return f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"


def _sum_campaign_rows(client, customer_id: str, start: date, end: date) -> dict[str, dict[str, Any]]:
    """Aggregiert Kampagnen-Kennzahlen für einen Zeitraum -> {campaign_name: metrics}."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.cost_micros,
            metrics.clicks,
            metrics.impressions,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.search_budget_lost_impression_share
        FROM campaign
        WHERE {_date_clause(start, end)}
          AND campaign.status != 'REMOVED'
    """
    out: dict[str, dict[str, Any]] = {}
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            name = row.campaign.name
            agg = out.setdefault(name, {
                "name": name, "cost": 0.0, "clicks": 0, "impressions": 0,
                "conversions": 0.0, "conv_value": 0.0,
                "budget_lost_is": 0.0, "_rows": 0,
            })
            agg["cost"] += row.metrics.cost_micros / 1_000_000
            agg["clicks"] += row.metrics.clicks
            agg["impressions"] += row.metrics.impressions
            agg["conversions"] += row.metrics.conversions
            agg["conv_value"] += row.metrics.conversions_value
            agg["budget_lost_is"] += row.metrics.search_budget_lost_impression_share
            agg["_rows"] += 1
    # Abgeleitete Kennzahlen
    for agg in out.values():
        agg["ctr"] = (agg["clicks"] / agg["impressions"] * 100) if agg["impressions"] else 0.0
        agg["cpa"] = (agg["cost"] / agg["conversions"]) if agg["conversions"] else None
        agg["roas"] = (agg["conv_value"] / agg["cost"]) if agg["cost"] else None
        rows = agg.pop("_rows") or 1
        agg["budget_lost_is"] = agg["budget_lost_is"] / rows * 100  # Ø in %
    return out


def _wasted_keywords(client, customer_id: str, start: date, end: date,
                     min_cost: float) -> list[dict[str, Any]]:
    """Keywords mit Kosten aber ohne Conversion (Budget-Verschwendung)."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            ad_group_criterion.keyword.text,
            metrics.cost_micros,
            metrics.clicks,
            metrics.conversions
        FROM keyword_view
        WHERE {_date_clause(start, end)}
          AND metrics.conversions = 0
          AND metrics.cost_micros > {int(min_cost * 1_000_000)}
        ORDER BY metrics.cost_micros DESC
        LIMIT 15
    """
    out: list[dict[str, Any]] = []
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            out.append({
                "campaign": row.campaign.name,
                "keyword": row.ad_group_criterion.keyword.text,
                "cost": row.metrics.cost_micros / 1_000_000,
                "clicks": row.metrics.clicks,
            })
    return out


def fetch(creds: Credentials, lookback_days: int, comparison_days: int,
          wasted_min_cost: float) -> dict[str, Any]:
    """Holt alle nötigen Ads-Daten. Kann Exceptions werfen (vom Aufrufer gefangen)."""
    ads = creds.google_ads()
    client = _client(ads)
    customer_id = ads["customer_id"]

    today = date.today()
    cur_start = today - timedelta(days=lookback_days)
    cur_end = today - timedelta(days=1)
    cmp_start = today - timedelta(days=comparison_days)
    cmp_end = today - timedelta(days=1)

    current = _sum_campaign_rows(client, customer_id, cur_start, cur_end)
    comparison = _sum_campaign_rows(client, customer_id, cmp_start, cmp_end)
    wasted = _wasted_keywords(client, customer_id, cur_start, cur_end, wasted_min_cost)

    return {
        "current": current,
        "comparison": comparison,
        "wasted_keywords": wasted,
        "date_range": {
            "current": [cur_start.isoformat(), cur_end.isoformat()],
            "comparison": [cmp_start.isoformat(), cmp_end.isoformat()],
        },
    }
