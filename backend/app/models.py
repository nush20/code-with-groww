from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(120), nullable=False)
    sector: Mapped[str] = mapped_column(String(80), nullable=False, default="Other")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserBaseline(Base):
    __tablename__ = "user_baselines"
    __table_args__ = (
        UniqueConstraint("user_id", "instrument_key", name="uq_baseline_user_instrument"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline_price: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WatchLevel(Base):
    __tablename__ = "watch_levels"
    __table_args__ = (
        UniqueConstraint("user_id", "instrument_key", "direction", name="uq_watch_level_user_instrument_direction"),
        CheckConstraint("target_price > 0", name="ck_watch_level_positive_target"),
        CheckConstraint("direction IN ('ABOVE', 'BELOW')", name="ck_watch_level_direction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(12), nullable=False, default="PRICE")
    target_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
