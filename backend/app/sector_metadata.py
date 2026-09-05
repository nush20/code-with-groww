"""Normalize sector metadata at the backend boundary.

Upstox instrument search may expose a sector/category for some instruments.
The curated fallback keeps prototype results useful when that optional field is
absent. Consumers should use this function rather than maintaining UI maps.
"""

from __future__ import annotations

SECTOR_BY_SYMBOL = {
    **dict.fromkeys(("INFY", "TCS", "HCLTECH", "WIPRO", "TECHM", "TATAELXSI", "TATATECH", "INFOBEAN", "PINELABS"), "Technology"),
    **dict.fromkeys(("RELIANCE", "ONGC", "BPCL", "IOC", "POWERGRID", "NTPC"), "Energy"),
    **dict.fromkeys(("HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"), "Banking"),
    **dict.fromkeys(("TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA"), "Metals"),
    **dict.fromkeys(("TATAMOTORS", "MARUTI", "EICHERMOT", "M&M", "BAJAJ-AUTO"), "Automobile"),
    **dict.fromkeys(("ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA"), "Consumer"),
    **dict.fromkeys(("SUNPHARMA", "DRREDDY", "CIPLA", "APOLLOHOSP"), "Healthcare"),
}


def sector_for(symbol: str, provider_sector: str | None = None) -> str:
    supplied = " ".join(str(provider_sector or "").split())
    if supplied and supplied.casefold() not in {"other", "unknown", "n/a", "na"}:
        return supplied.title()
    return SECTOR_BY_SYMBOL.get(symbol.strip().upper(), "Other")
