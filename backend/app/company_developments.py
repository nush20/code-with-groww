"""Shared, normalized company developments used to enrich meaningful Catch-Up events."""

from __future__ import annotations

import hashlib
import html
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from .market_data import MarketDataError, _upstox_get


UPSTOX_NEWS_URL = "https://api.upstox.com/v2/news"
DEVELOPMENT_TYPES = {
    "EARNINGS", "GUIDANCE", "MAJOR_ORDER_OR_DEAL", "MERGER_OR_ACQUISITION",
    "REGULATORY_OR_LEGAL", "MANAGEMENT_CHANGE", "DIVIDEND", "BUYBACK",
    "STOCK_SPLIT", "MAJOR_BUSINESS_ANNOUNCEMENT", "OTHER_MATERIAL",
}


def _brief_source_summary(value: Any, limit: int = 280) -> str | None:
    """Clean and shorten provider copy without generating or adding facts."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = " ".join(text.split())
    if not text:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text)
    brief = " ".join(sentences[:2])
    if len(brief) <= limit:
        return brief
    shortened = brief[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{shortened}…"


class CompanyDevelopmentError(RuntimeError):
    pass


class CompanyDevelopmentProvider(Protocol):
    def get_recent_developments(self, instrument_key: str, symbol: str) -> list[dict[str, Any]]: ...


def _development_type(text: str) -> str:
    lowered = text.casefold()
    rules = (
        ("EARNINGS", ("quarterly result", "financial result", "earnings", "profit", "revenue")),
        ("GUIDANCE", ("guidance", "outlook", "forecast")),
        ("DIVIDEND", ("dividend",)),
        ("BUYBACK", ("buyback", "buy-back")),
        ("STOCK_SPLIT", ("stock split", "share split", "bonus issue", "bonus share")),
        ("MERGER_OR_ACQUISITION", ("merger", "acquisition", "acquires", "takeover")),
        ("MANAGEMENT_CHANGE", ("ceo", "cfo", "managing director", "resignation", "appoints", "appointment")),
        ("REGULATORY_OR_LEGAL", ("sebi", "regulator", "tribunal", "court", "legal", "penalty", "investigation")),
        ("MAJOR_ORDER_OR_DEAL", ("order win", "wins order", "contract", "agreement", "deal", "partnership")),
        ("MAJOR_BUSINESS_ANNOUNCEMENT", ("launches", "expansion", "new plant", "commissioned", "fund raise")),
    )
    return next((category for category, words in rules if any(word in lowered for word in words)), "OTHER_MATERIAL")


def normalize_upstox_development(instrument_key: str, symbol: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        headline = " ".join(str(raw["heading"]).split())
        published_at = datetime.fromtimestamp(int(raw["published_time"]) / 1000, tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OSError):
        return None
    url = str(raw.get("article_link") or "").strip()
    summary = _brief_source_summary(raw.get("summary"))
    if not headline or not url:
        return None
    identity = hashlib.sha256(f"{instrument_key}|{url}|{published_at.isoformat()}".encode()).hexdigest()[:20]
    return {
        "id": identity,
        "instrument_key": instrument_key,
        "symbol": symbol,
        "type": _development_type(f"{headline} {summary}"),
        "headline": headline,
        "summary": summary,
        "published_at": published_at,
        "source_name": "Upstox News",
        "source_url": url,
        "simulated": False,
    }


class UpstoxCompanyDevelopmentProvider:
    def get_recent_developments(self, instrument_key: str, symbol: str) -> list[dict[str, Any]]:
        try:
            payload = _upstox_get(UPSTOX_NEWS_URL, params={
                "category": "instrument_keys",
                "instrument_keys": instrument_key,
                "page_number": 1,
                "page_size": 50,
            })
        except MarketDataError as exc:
            raise CompanyDevelopmentError("Company context temporarily unavailable") from exc
        raw_items = (payload.get("data") or {}).get(instrument_key) or []
        return [normalized for raw in raw_items if (normalized := normalize_upstox_development(instrument_key, symbol, raw))]


class CompanyDevelopmentService:
    """Caches shared facts per instrument; applies personal time windows afterwards."""

    def __init__(self, provider: CompanyDevelopmentProvider | None = None):
        self.provider = provider or UpstoxCompanyDevelopmentProvider()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def _recent(self, instrument_key: str, symbol: str) -> list[dict[str, Any]]:
        ttl = int(os.getenv("COMPANY_DEVELOPMENT_CACHE_SECONDS", "300"))
        cached = self._cache.get(instrument_key)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1]
        developments = self.provider.get_recent_developments(instrument_key, symbol)
        self._cache[instrument_key] = (time.monotonic(), developments)
        return developments

    def get_developments(self, instrument_key: str, symbol: str, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        start = start_time.replace(tzinfo=timezone.utc) if start_time.tzinfo is None else start_time.astimezone(timezone.utc)
        end = end_time.replace(tzinfo=timezone.utc) if end_time.tzinfo is None else end_time.astimezone(timezone.utc)
        low_value = re.compile(r"\b(stocks? to watch|top gainers?|top losers?|market live|nifty|sensex)\b", re.I)
        candidates = [item for item in self._recent(instrument_key, symbol)
                      if start <= item["published_at"] <= end and not low_value.search(item["headline"])]
        unique = {}
        for item in sorted(candidates, key=lambda value: value["published_at"], reverse=True):
            key = re.sub(r"[^a-z0-9]+", " ", item["headline"].casefold()).strip()
            unique.setdefault(key, item)
        limit = max(1, min(int(os.getenv("COMPANY_DEVELOPMENT_LIMIT", "3")), 3))
        return list(unique.values())[:limit]

    def get_developments_on_date(self, instrument_key: str, symbol: str, session_date, market_timezone) -> list[dict[str, Any]]:
        """Return every normalized provider item mapped to an instrument on one local date."""
        candidates = [item for item in self._recent(instrument_key, symbol)
                      if item["published_at"].astimezone(market_timezone).date() == session_date]
        unique = {}
        for item in sorted(candidates, key=lambda value: value["published_at"], reverse=True):
            key = item["source_url"] or re.sub(r"[^a-z0-9]+", " ", item["headline"].casefold()).strip()
            unique.setdefault(key, item)
        return list(unique.values())


company_development_service = CompanyDevelopmentService()
