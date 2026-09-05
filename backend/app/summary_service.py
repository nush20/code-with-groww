from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Protocol

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


class SummaryProvider(Protocol):
    """Future providers receive verified facts only, never raw candles."""

    def generate(self, facts: dict[str, Any]) -> dict[str, str]: ...


def classify_analysis(analysis: dict[str, Any], meaningful_threshold: float) -> str:
    if abs(analysis["max_excursion_pct"]) < meaningful_threshold:
        return "QUIET"

    reversal = analysis["reversal_pct"]
    if reversal < 30:
        bucket = "MOSTLY_HELD"
    elif reversal <= 70:
        bucket = "PARTIALLY_REVERSED" if analysis["direction"] == "up" else "PARTIALLY_RECOVERED"
    else:
        bucket = "MOSTLY_REVERSED" if analysis["direction"] == "up" else "MOSTLY_RECOVERED"

    if analysis["direction"] == "up":
        return f"UP_MOVE_{bucket}"
    return f"DECLINE_{bucket}"


def _period_language(range_name: str, session_state: str) -> str:
    if range_name == "1D":
        return "today" if session_state == "IN_PROGRESS" else "during the latest session"
    return {
        "1W": "during the week",
        "2W": "over the two-week period",
        "1M": "during the one-month period",
    }[range_name]


def _headline(state: str, range_name: str) -> str:
    period = {"1D": "Session", "1W": "Weekly", "2W": "Two-week", "1M": "Monthly"}[range_name]
    labels = {
        "UP_MOVE_MOSTLY_HELD": f"{period} rise mostly held",
        "UP_MOVE_PARTIALLY_REVERSED": f"{period} rise partially reversed",
        "UP_MOVE_MOSTLY_REVERSED": f"{period} rally mostly reversed",
        "DECLINE_MOSTLY_HELD": f"{period} decline mostly held",
        "DECLINE_PARTIALLY_RECOVERED": f"{period} decline partially recovered",
        "DECLINE_MOSTLY_RECOVERED": f"{period} decline mostly recovered",
        "QUIET": f"Quiet {period.lower()}",
    }
    return labels[state]


class TemplateSummaryProvider:
    def generate(self, facts: dict[str, Any]) -> dict[str, str]:
        if facts.get("summary_kind") == "catchup":
            return self._catchup(facts)
        state = facts["semantic_state"]
        period = _period_language(facts["range"], facts["session_state"])
        excursion = abs(facts["max_excursion_pct"])
        reversal = facts["reversal_pct"]
        ending = facts["period_return_pct"]
        position = "above" if ending >= 0 else "below"
        final_verb = "is currently" if facts["session_state"] == "IN_PROGRESS" else "ended"

        if state == "QUIET":
            summary = (
                f"{facts['symbol']} stayed within the meaningful-movement threshold {period}. "
                f"It {final_verb} {abs(ending):.2f}% {position} the period’s starting level."
            )
        elif facts["direction"] == "up":
            summary = (
                f"{facts['symbol']} rose as much as {excursion:.2f}% {period} before about "
                f"{reversal:.0f}% of that move reversed. It {final_verb} {abs(ending):.2f}% "
                f"{position} the period’s starting level."
            )
        else:
            summary = (
                f"{facts['symbol']} fell as much as {excursion:.2f}% {period} before recovering about "
                f"{reversal:.0f}% of the decline. It {final_verb} {abs(ending):.2f}% "
                f"{position} the period’s starting level."
            )
        movement = "Rose" if facts["direction"] == "up" else "Fell"
        return {
            "headline": _headline(state, facts["range"]),
            "short_summary": f"{movement} as much as {excursion:.2f}%",
            "summary": summary,
        }

    def _catchup(self, facts: dict[str, Any]) -> dict[str, str]:
        direction = facts["market_facts"]["direction"]
        excursion = abs(facts["market_facts"]["max_excursion_pct"])
        reversal = facts["market_facts"]["reversal_pct"]
        unusual = facts["market_facts"].get("significance_multiple")
        hidden = facts["market_facts"]["is_hidden_journey"]
        levels = facts["personal_facts"]["watch_levels_reached"]

        if levels:
            formatted = ", ".join(f"₹{level:,.2f}" for level in levels)
            headline = f"Your {formatted} price alert was reached"
        elif unusual is not None:
            headline = "A larger-than-usual price move happened"
        elif hidden:
            headline = "A temporary price move was easy to miss"
        else:
            headline = "A meaningful price move happened"

        market = facts["market_facts"]
        if all(market.get(key) is not None for key in ("baseline_price", "excursion_price", "latest_price")):
            first_verb = "climbed" if direction == "up" else "fell"
            second_verb = "fell back" if direction == "up" else "recovered"
            effect = "temporary rise disappeared" if direction == "up" else "decline was recovered"
            summary = (
                f"{facts['symbol']} {first_verb} from ₹{market['baseline_price']:,.2f} to "
                f"₹{market['excursion_price']:,.2f}, then {second_verb} to ₹{market['latest_price']:,.2f}. "
                f"That means {reversal:.0f}% of the {effect}."
            )
        else:
            summary = (
                f"{facts['symbol']} moved {'up' if direction == 'up' else 'down'} {excursion:.2f}% before "
                f"{reversal:.0f}% of that move {'faded' if direction == 'up' else 'recovered'}."
            )
        return {"headline": headline, "short_summary": summary, "summary": summary}


class GeminiSummaryProvider:
    """Rewrites verified facts only; deterministic templates remain the fallback."""

    def __init__(self, fallback: SummaryProvider | None = None):
        self.fallback = fallback or TemplateSummaryProvider()
        self._cache: dict[str, dict[str, str]] = {}

    @staticmethod
    def _api_key() -> str | None:
        load_dotenv()
        shared_env = os.getenv("GEMINI_ENV_FILE")
        if not os.getenv("GEMINI_API_KEY") and shared_env:
            load_dotenv(shared_env)
        return os.getenv("GEMINI_API_KEY")

    @staticmethod
    def _valid(result: Any, serialized_facts: str) -> bool:
        if not isinstance(result, dict):
            return False
        limits = {"headline": 90, "short_summary": 160, "summary": 420}
        if any(not isinstance(result.get(key), str) or not result[key].strip() or len(result[key]) > limit
               for key, limit in limits.items()):
            return False
        combined = " ".join(result.values()).casefold()
        if any(term in combined for term in (
            "buy this", "sell this", "investment advice", "caused the price", "drove the price", "because of the news",
            "market sentiment", "investor sentiment", "investor confidence", "investor interest", "positive momentum",
        )):
            return False
        number_pattern = r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?(?![A-Za-z])"
        supplied = {float(value.replace(",", "")) for value in re.findall(number_pattern, serialized_facts)}
        allowed = {round(value, places) for value in supplied for places in (0, 1, 2, 4)}
        output = {float(value.replace(",", "")) for value in re.findall(number_pattern, combined)}
        return all(any(abs(value - candidate) < 1e-6 for candidate in allowed) for value in output)

    def generate(self, facts: dict[str, Any]) -> dict[str, str]:
        fallback = self.fallback.generate(facts)
        api_key = self._api_key()
        if not api_key:
            return fallback
        serialized = json.dumps(facts, default=str, sort_keys=True, separators=(",", ":"))
        cache_key = hashlib.sha256(serialized.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        task_rules = (
            "For Catch-Up, make the headline prioritize a personal watch level, then unusualness, then a hidden round trip. "
            "Keep summary to one sentence describing the price journey; do not repeat news or the reasons list."
            if facts.get("summary_kind") == "catchup" else
            "For Market Recap, describe the full selected period in no more than two sentences and emphasize its distinctive price path."
        )
        prompt = (
            "Write a concise factual market-watchlist summary using ONLY the verified JSON facts below. "
            "Do not calculate, predict, recommend, add outside knowledge, or claim news caused a price move. "
            "Do not mention sentiment, investors, confidence, momentum, reasons, or causes. Every clause must directly restate a JSON field. "
            f"Use plain English. {task_rules} Return JSON with exactly headline, short_summary, summary. "
            "Preserve supplied numbers; omit a detail rather than infer it.\nVERIFIED_FACTS:\n" + serialized
        )
        try:
            from google import genai
            from google.genai import types
            timeout_ms = int(os.getenv("GEMINI_TIMEOUT_MS", "4000"))
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL_NAME", "gemini-3.1-flash-lite"), contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=1000, response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text or "")
            if not self._valid(result, serialized):
                raise ValueError("Gemini returned an invalid summary")
            normalized = {key: result[key].strip() for key in ("headline", "short_summary", "summary")}
            self._cache[cache_key] = normalized
            return normalized
        except Exception:
            logger.warning("Gemini summary unavailable; using deterministic template", exc_info=True)
            return fallback


class SummaryService:
    """Turns structured, calculated market facts into language."""

    def __init__(self, provider: SummaryProvider | None = None):
        self.provider = provider or TemplateSummaryProvider()

    def generate(self, facts: dict[str, Any]) -> dict[str, str]:
        return self.provider.generate(facts)


summary_service = SummaryService(
    GeminiSummaryProvider() if os.getenv("SUMMARY_PROVIDER", "template").casefold() == "gemini" else None
)
