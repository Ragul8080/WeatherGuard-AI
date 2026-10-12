"""Email notification delivery and history recording."""

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import NotificationHistory, WeatherAlert
from app.database.repositories import NotificationRepository
from app.logging_config import logger
from app.notifications.templates import render_alert_email
from app.utils.time import now_utc


class EmailSender:
    """Robust SMTP email sender with retry logic and error isolation."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: Optional[bool] = None,
        sender: Optional[str] = None,
        max_retries: Optional[int] = None,
    ):
        self.host = host if host is not None else settings.SMTP_HOST
        self.port = port if port is not None else settings.SMTP_PORT
        self.username = username if username is not None else settings.SMTP_USERNAME
        self.password = password if password is not None else settings.SMTP_PASSWORD
        self.use_tls = use_tls if use_tls is not None else settings.SMTP_USE_TLS
        self.sender = sender if sender is not None else settings.SMTP_SENDER_EMAIL
        self.max_retries = max_retries if max_retries is not None else settings.EMAIL_MAX_RETRIES

    def send_email(
        self,
        recipient: str,
        subject: str,
        plain_text: str,
        html_content: str,
    ) -> bool:
        """Send multipart email with retry logic. Returns True if sent, raises on failure."""
        if not self.host or not recipient:
            logger.warning(
                "SMTP host or recipient is not configured. Email delivery skipped in safe mock mode."
            )
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = recipient

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        attempt = 0
        backoff = 1.0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                logger.info(
                    f"Sending email alert to {recipient} via {self.host}:{self.port} "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                with smtplib.SMTP(self.host, self.port, timeout=10.0) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)

                logger.info(f"Email successfully delivered to {recipient}.")
                return True

            except (
                smtplib.SMTPException,
                smtplib.socket.error,
                TimeoutError,
            ) as exc:
                last_error = exc
                logger.error(
                    f"SMTP delivery error on attempt {attempt}/{self.max_retries}: {exc}"
                )
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2.0

        raise RuntimeError(f"Email delivery failed after {self.max_retries} attempts: {last_error}")


class NotificationService:
    """Service to coordinate alert notifications and persistent auditing."""

    def __init__(self, db: Session, email_sender: Optional[EmailSender] = None):
        self.db = db
        self.repo = NotificationRepository(db)
        self.sender = email_sender or EmailSender()

    def dispatch_alert(
        self,
        alert: WeatherAlert,
        recipient_override: Optional[str] = None,
        ai_explanation: Optional[str] = None,
        user_timezone: str = "Asia/Kolkata",
    ) -> NotificationHistory:
        """Dispatch email for an alert and log the attempt in database."""
        recipient = recipient_override or settings.ALERT_RECIPIENT
        if not recipient:
            logger.warning(
                f"No alert recipient defined for alert ID {alert.id}. Recording SKIPPED notification."
            )
            history = NotificationHistory(
                alert_id=alert.id,
                recipient="unconfigured@local",
                attempted_at=now_utc(),
                sent_at=None,
                status="SKIPPED",
                error_message="No recipient configured in user preferences or environment.",
                retry_count=0,
            )
            return self.repo.record_attempt(history)

        subject, text, html = render_alert_email(
            alert=alert,
            ai_explanation=ai_explanation,
            user_timezone=user_timezone,
        )

        history = NotificationHistory(
            alert_id=alert.id,
            recipient=recipient,
            attempted_at=now_utc(),
            retry_count=0,
        )

        try:
            sent = self.sender.send_email(
                recipient=recipient,
                subject=subject,
                plain_text=text,
                html_content=html,
            )
            if sent:
                history.sent_at = now_utc()
                history.status = "SENT"
                history.error_message = None
            else:
                # Host wasn't configured, so recorded as MOCK_SENT or SKIPPED
                history.sent_at = now_utc()
                history.status = "MOCK_SENT"
                history.error_message = "SMTP host unconfigured. Simulated mock delivery."
        except Exception as err:
            logger.error(f"Failed to deliver notification for alert {alert.id}: {err}")
            history.status = "FAILED"
            history.error_message = str(err)
            history.retry_count = self.sender.max_retries

        return self.repo.record_attempt(history)

    def dispatch_all(
        self,
        alerts: List[WeatherAlert],
        recipient: Optional[str] = None,
        ai_explanation: Optional[str] = None,
        user_timezone: str = "Asia/Kolkata",
    ) -> List[NotificationHistory]:
        """Dispatch notifications for all active alerts."""
        results = []
        for alert in alerts:
            history = self.dispatch_alert(
                alert=alert,
                recipient_override=recipient,
                ai_explanation=ai_explanation,
                user_timezone=user_timezone,
            )
            results.append(history)
        return results
