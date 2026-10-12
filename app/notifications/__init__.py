"""Notification and email dispatch system."""

from app.notifications.email import EmailSender, NotificationService
from app.notifications.templates import render_alert_email

__all__ = ["EmailSender", "NotificationService", "render_alert_email"]
