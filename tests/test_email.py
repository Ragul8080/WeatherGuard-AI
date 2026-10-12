"""Tests for email notification service and template rendering."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, WeatherAlert
from app.notifications.email import EmailSender, NotificationService
from app.notifications.templates import DISCLAIMER_TEXT, render_alert_email
from app.utils.time import now_utc


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_alert():
    return WeatherAlert(
        id=1,
        location="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        alert_type="RAIN_WARNING",
        severity="WARNING",
        forecast_time=now_utc(),
        probability=85.0,
        rainfall_mm=4.5,
        message="85% chance of rain with 4.5 mm expected.",
        alert_key="Chennai:RAIN_WARNING:test",
        status="ACTIVE",
    )


def test_render_alert_email(sample_alert):
    """Verify that email templates generate valid subject, text, HTML, and include disclaimer."""
    subj, text, html = render_alert_email(
        sample_alert,
        ai_explanation="Carry an umbrella.",
        user_timezone="Asia/Kolkata",
    )
    assert "[WARNING]" in subj
    assert "Chennai" in subj
    assert "Carry an umbrella." in text
    assert DISCLAIMER_TEXT in text
    assert "<!DOCTYPE html>" in html
    assert "Carry an umbrella." in html
    assert DISCLAIMER_TEXT in html


def test_email_sender_mock_mode_when_unconfigured():
    """Verify EmailSender returns False in safe mock mode without raising when host is empty."""
    sender = EmailSender(host="", sender="alerts@test.com")
    result = sender.send_email(
        recipient="user@test.com",
        subject="Test",
        plain_text="Text",
        html_content="<p>HTML</p>",
    )
    assert result is False


def test_email_sender_with_mocked_smtp():
    """Verify EmailSender successfully sends via SMTP when mocked."""
    sender = EmailSender(
        host="smtp.example.com",
        port=587,
        username="user",
        password="secretpassword",
        use_tls=True,
    )
    mock_smtp_inst = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        mock_smtp_inst.__enter__.return_value = mock_smtp_inst
        sent = sender.send_email(
            recipient="test@example.com",
            subject="Subj",
            plain_text="Text",
            html_content="<p>HTML</p>",
        )
        assert sent is True
        mock_smtp_inst.starttls.assert_called_once()
        mock_smtp_inst.login.assert_called_once_with("user", "secretpassword")
        mock_smtp_inst.send_message.assert_called_once()


def test_notification_service_dispatches_and_audits(test_db, sample_alert):
    """Verify NotificationService logs records in notification_history."""
    test_db.add(sample_alert)
    test_db.commit()

    service = NotificationService(test_db, email_sender=EmailSender(host=""))
    history = service.dispatch_alert(
        alert=sample_alert,
        recipient_override="dev@example.com",
    )
    test_db.commit()

    assert history.id is not None
    assert history.recipient == "dev@example.com"
    assert history.status == "MOCK_SENT"
