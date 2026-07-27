"""Konfiguration laden: nicht-geheime Einstellungen aus config.yaml,
geheime Zugangsdaten aus Umgebungsvariablen (.env lokal / GitHub Secrets in CI).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

# Projektwurzel = zwei Ebenen über dieser Datei (src/wlp_monitor/config.py)
ROOT = Path(__file__).resolve().parents[2]

# .env laden, falls vorhanden (lokal). In CI kommen die Werte aus dem Environment.
load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    """Umgebungsvariable lesen (getrimmt)."""
    return (os.environ.get(name) or default).strip()


@dataclass
class Settings:
    """Gebündelte Konfiguration inkl. der (nicht-geheimen) YAML-Werte."""

    raw: dict[str, Any]

    # --- häufig gebrauchte Kurzzugriffe ---
    @property
    def base_url(self) -> str:
        return self.raw["site"]["base_url"].rstrip("/")

    @property
    def timezone_name(self) -> str:
        return self.raw["site"].get("timezone", "Europe/Berlin")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def section(self, name: str) -> dict[str, Any]:
        return self.raw.get(name, {}) or {}

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today_str(self) -> str:
        return self.now().strftime("%Y-%m-%d")

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"


def load_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path) if config_path else ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Settings(raw=raw)


# --- Zugangsdaten-Container (nur Vorhandensein prüfen, nie loggen!) ---


@dataclass
class Credentials:
    """Liest Secrets aus dem Environment und meldet, was konfiguriert ist."""

    def smtp(self) -> dict[str, str]:
        return {
            "host": env("SMTP_HOST"),
            "port": env("SMTP_PORT", "587"),
            "user": env("SMTP_USER"),
            "password": env("SMTP_PASSWORD"),
            "from": env("SMTP_FROM") or env("SMTP_USER"),
        }

    def smtp_ready(self) -> bool:
        s = self.smtp()
        return bool(s["host"] and s["user"] and s["password"])

    def google_ads(self) -> dict[str, str]:
        return {
            "developer_token": env("GOOGLE_ADS_DEVELOPER_TOKEN"),
            "client_id": env("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": env("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": env("GOOGLE_ADS_REFRESH_TOKEN"),
            "customer_id": env("GOOGLE_ADS_CUSTOMER_ID"),
            "login_customer_id": env("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        }

    def google_ads_ready(self) -> bool:
        a = self.google_ads()
        return all(a[k] for k in ("developer_token", "client_id", "client_secret", "refresh_token", "customer_id"))

    def search_console_json(self) -> str:
        return env("GOOGLE_SERVICE_ACCOUNT_JSON")

    def search_console_ready(self) -> bool:
        return bool(self.search_console_json())

    def wix(self) -> dict[str, str]:
        return {
            "api_key": env("WIX_API_KEY"),
            "site_id": env("WIX_SITE_ID"),
            "account_id": env("WIX_ACCOUNT_ID"),
        }

    def wix_ready(self) -> bool:
        w = self.wix()
        return bool(w["api_key"] and w["site_id"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
