"""SQLAlchemy models for WeatherGuard AI."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all models."""
    pass


class WeatherReading(Base):
    """Hourly weather reading and forecast data point."""

    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rain_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weather_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wind_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_weather_readings_loc_forecast", "location", "forecast_time"),
        Index("ix_weather_readings_fetched_at", "fetched_at"),
    )

    def __repr__(self) -> str:
        return f"<WeatherReading(id={self.id}, loc={self.location}, time={self.forecast_time}, temp={self.temperature_c})>"


class WeatherAlert(Base):
    """Triggered weather alert record."""

    __tablename__ = "weather_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="WARNING")
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ai_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    alert_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    notifications: Mapped[List["NotificationHistory"]] = relationship(
        "NotificationHistory", back_populates="alert", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WeatherAlert(id={self.id}, key={self.alert_key}, type={self.alert_type}, severity={self.severity})>"


class NotificationHistory(Base):
    """Email and dispatch notification audit log."""

    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("weather_alerts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    alert: Mapped[Optional["WeatherAlert"]] = relationship("WeatherAlert", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<NotificationHistory(id={self.id}, alert_id={self.alert_id}, status={self.status}, recipient={self.recipient})>"


class UserPreference(Base):
    """User and system thresholds configuration."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[str] = mapped_column(String(100), default="Chennai")
    latitude: Mapped[float] = mapped_column(Float, default=13.0827)
    longitude: Mapped[float] = mapped_column(Float, default=80.2707)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")
    rain_probability_threshold: Mapped[float] = mapped_column(Float, default=70.0)
    minimum_rainfall_mm: Mapped[float] = mapped_column(Float, default=1.0)
    high_rainfall_mm: Mapped[float] = mapped_column(Float, default=10.0)
    low_temperature_threshold: Mapped[float] = mapped_column(Float, default=15.0)
    high_wind_threshold: Mapped[float] = mapped_column(Float, default=40.0)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<UserPreference(id={self.id}, location={self.location}, email={self.email})>"


class WorkflowExecution(Base):
    """Execution history for autonomous weather monitoring workflows."""

    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, wf={self.workflow_id}, status={self.status})>"
