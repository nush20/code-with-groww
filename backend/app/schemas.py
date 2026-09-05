from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthSignup(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name", "email")
    @classmethod
    def clean_auth_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.casefold()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address")
        return value


class AuthLogin(BaseModel):
    email: str
    password: str


class AuthUserOut(BaseModel):
    id: str
    name: str
    email: str
    is_demo: bool = False


class WatchlistCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    company_name: str = Field(min_length=1, max_length=200)
    instrument_key: str = Field(min_length=1, max_length=120)

    @field_validator("symbol", "company_name", "instrument_key")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()


class MarketDataOut(BaseModel):
    price: float
    previous_close: float
    change_percent: float
    day_high: float
    day_low: float
    market_timestamp: datetime
    is_stale: bool


class StockSearchResult(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    instrument_key: str


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    company_name: str
    instrument_key: Optional[str] = None
    created_at: datetime
    market: Optional[MarketDataOut] = None
    market_error: Optional[str] = None


class DeleteResponse(BaseModel):
    message: str


class CatchupStockOut(BaseModel):
    instrument_key: str
    symbol: str
    baseline_price: float
    baseline_time: datetime


class CatchupStatusOut(BaseModel):
    last_caught_up_at: Optional[datetime] = None
    stocks: list[CatchupStockOut]


class CatchupFailureOut(BaseModel):
    symbol: str
    reason: str


class CatchupMarkOut(BaseModel):
    message: str
    caught_up_at: Optional[datetime] = None
    updated: int
    failed: list[CatchupFailureOut] = Field(default_factory=list)


class JourneyPointOut(BaseModel):
    price: float
    time: datetime


class CurrentJourneyPointOut(JourneyPointOut):
    return_pct: float


class ExcursionOut(CurrentJourneyPointOut):
    direction: str


class DataFreshnessOut(BaseModel):
    market_timestamp: datetime
    is_stale: bool


class UnusualnessOut(BaseModel):
    observed_excursion_pct: float
    typical_daily_movement_pct: Optional[float] = None
    trading_session_equivalent: int
    expected_window_movement_pct: Optional[float] = None
    significance_multiple: Optional[float] = None
    state: str
    history_sessions_used: int


class WatchLevelEventOut(BaseModel):
    event_type: str
    level_id: int
    target_price: float
    direction: str
    event_candle_time: datetime
    event_candle_high: float
    event_candle_low: float
    latest_price: float
    currently_beyond_level: bool
    max_price_after_reach: Optional[float] = None
    min_price_after_reach: Optional[float] = None


class CompanyDevelopmentOut(BaseModel):
    id: str
    instrument_key: str
    symbol: str
    type: str
    headline: str
    summary: Optional[str] = None
    published_at: datetime
    source_name: str
    source_url: Optional[str] = None
    simulated: bool = False


class CatchupContextOut(BaseModel):
    status: Literal["AVAILABLE", "NONE", "UNAVAILABLE"]
    company_developments: list[CompanyDevelopmentOut] = Field(default_factory=list)


class WatchLevelCreate(BaseModel):
    instrument_key: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=30)
    target_price: float = Field(gt=0)
    direction: Literal["ABOVE", "BELOW"]

    @field_validator("instrument_key", "symbol")
    @classmethod
    def trim_level_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("symbol")
    @classmethod
    def uppercase_level_symbol(cls, value: str) -> str:
        return value.upper()


class WatchLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_key: str
    symbol: str
    target_price: float
    direction: str
    active: bool
    created_at: datetime
    updated_at: datetime


class HiddenJourneyEventOut(BaseModel):
    type: str
    instrument_key: str
    symbol: str
    company_name: str
    headline: str
    summary: str
    baseline: JourneyPointOut
    current: CurrentJourneyPointOut
    excursion: ExcursionOut
    reversal_pct: float
    is_hidden_journey: bool
    unusualness: UnusualnessOut
    watch_level_events: list[WatchLevelEventOut] = Field(default_factory=list)
    context: CatchupContextOut = Field(default_factory=lambda: CatchupContextOut(status="NONE"))
    data_freshness: DataFreshnessOut


class CatchupOut(BaseModel):
    mode: Literal["live", "demo"] = "live"
    since: Optional[datetime] = None
    meaningful_count: int
    quiet_count: int
    insufficient_count: int
    unavailable_count: int
    unusualness_insufficient_count: int = 0
    unusualness_unavailable_count: int = 0
    events: list[HiddenJourneyEventOut]
    demo: Optional[dict] = None


class MarketSessionOut(BaseModel):
    date: date
    status: str
    label: str
    updated_at: Optional[datetime] = None


class MarketRecapFreshnessOut(BaseModel):
    market_timestamp: datetime
    is_stale: bool


class MarketRecapStoryOut(BaseModel):
    instrument_key: str
    symbol: str
    company_name: str
    classification: str
    semantic_state: str
    reference_price: float
    open: float
    high: float
    high_time: datetime
    low: float
    low_time: datetime
    current_or_close: float
    latest_time: datetime
    session_return_pct: float
    max_excursion_pct: float
    reversal_pct: float
    direction: str
    display_label: str
    short_summary: str
    movement_label: str
    session_state: str
    summary: str
    explanation: str
    freshness: MarketRecapFreshnessOut
    context: CatchupContextOut = Field(default_factory=lambda: CatchupContextOut(status="NONE"))


class DailyWatchlistDevelopmentOut(BaseModel):
    id: str
    type: str
    headline: str
    summary: Optional[str] = None
    published_at: datetime
    source_name: str
    source_url: Optional[str] = None
    symbols: list[str]


class DailyWatchlistDevelopmentsOut(BaseModel):
    status: Literal["AVAILABLE", "NONE", "PARTIAL", "UNAVAILABLE"]
    date: date
    developments: list[DailyWatchlistDevelopmentOut] = Field(default_factory=list)
    unavailable_count: int = 0


class WatchlistMoverOut(BaseModel):
    symbol: str
    company_name: str
    return_pct: float


class DailyWatchlistImpactOut(BaseModel):
    average_return_pct: float
    up_count: int
    down_count: int
    flat_count: int
    analyzed_count: int
    largest_gainer: Optional[WatchlistMoverOut] = None
    largest_decliner: Optional[WatchlistMoverOut] = None


class WatchlistPeriodStockOut(BaseModel):
    instrument_key: str
    symbol: str
    company_name: str
    return_pct: float
    high: float
    low: float


class MarketRecapOut(BaseModel):
    range: str
    period: Optional["MarketPeriodOut"] = None
    session: Optional[MarketSessionOut] = None
    analyzed_count: int
    stories: list[MarketRecapStoryOut]
    quiet_count: int
    unavailable_count: int
    daily_developments: Optional[DailyWatchlistDevelopmentsOut] = None
    watchlist_impact: Optional[DailyWatchlistImpactOut] = None
    market_overview: list[WatchlistPeriodStockOut] = Field(default_factory=list)


class MarketPeriodOut(BaseModel):
    start_date: date
    end_date: date
    session_count: int
    is_partial: bool
    label: str


class PricePointOut(BaseModel):
    timestamp: datetime
    close: float


class StockDetailOut(BaseModel):
    symbol: str
    company_name: str
    instrument_key: str
    range: str
    period: MarketPeriodOut
    classification: str
    semantic_state: str
    display_label: str
    short_summary: str
    movement_label: str
    reference_price: float
    latest_price: float
    period_return_pct: float
    period_high: float
    period_high_time: datetime
    period_low: float
    period_low_time: datetime
    peak_return_pct: float
    trough_return_pct: float
    max_excursion_pct: float
    direction: str
    reversal_pct: float
    session_state: str
    summary: str
    explanation: str
    freshness: MarketRecapFreshnessOut
    candles: list[PricePointOut]
    context: CatchupContextOut = Field(default_factory=lambda: CatchupContextOut(status="NONE"))


MarketRecapOut.model_rebuild()
