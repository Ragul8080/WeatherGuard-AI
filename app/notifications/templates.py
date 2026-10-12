"""Email templates for weather alerts."""

from datetime import datetime
from typing import Optional, Tuple
from app.database.models import WeatherAlert
from app.utils.time import format_display_time, now_utc


DISCLAIMER_TEXT = (
    "This notification is generated from forecast data and configured "
    "application thresholds. It is not an official meteorological warning."
)


def render_alert_email(
    alert: WeatherAlert,
    ai_explanation: Optional[str] = None,
    user_timezone: str = "Asia/Kolkata",
) -> Tuple[str, str, str]:
    """Generate (subject, plain_text, html_content) for weather alert email."""
    subject = f"[{alert.severity}] WeatherGuard AI Alert: {alert.alert_type} for {alert.location}"

    formatted_fc_time = format_display_time(alert.forecast_time, user_timezone)
    generated_time = format_display_time(now_utc(), user_timezone)
    explanation = ai_explanation or alert.ai_explanation or "No supplementary AI explanation available."

    prob_str = f"{alert.probability:.0f}%" if alert.probability is not None else "N/A"
    rain_str = f"{alert.rainfall_mm:.1f} mm" if alert.rainfall_mm is not None else "N/A"

    # Plain text version
    plain_text = f"""==================================================
WEATHERGUARD AI WEATHER ALERT
==================================================
Location:        {alert.location}
Alert Type:      {alert.alert_type}
Severity:        {alert.severity}
Forecast Time:   {formatted_fc_time}
Probability:     {prob_str}
Rainfall:        {rain_str}
Generated At:    {generated_time}

MESSAGE:
{alert.message}

AI EXPLANATION & GUIDANCE:
{explanation}

--------------------------------------------------
DISCLAIMER:
{DISCLAIMER_TEXT}
==================================================
"""

    # Severity color mapping
    severity_colors = {
        "NORMAL": "#2563eb",
        "INFORMATIONAL": "#0284c7",
        "WARNING": "#d97706",
        "HIGH": "#dc2626",
    }
    badge_color = severity_colors.get(alert.severity.upper(), "#dc2626")

    # HTML version
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .header {{ background: #0f172a; color: #ffffff; padding: 24px; }}
    .badge {{ display: inline-block; padding: 4px 12px; font-size: 12px; font-weight: 700; border-radius: 9999px; text-transform: uppercase; background-color: {badge_color}; color: #ffffff; }}
    .title {{ margin: 12px 0 4px 0; font-size: 20px; font-weight: 700; color: #ffffff; }}
    .content {{ padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
    .stat-card {{ background: #f1f5f9; padding: 12px; border-radius: 8px; }}
    .stat-label {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; }}
    .stat-value {{ font-size: 15px; font-weight: 600; color: #0f172a; margin-top: 4px; }}
    .section {{ margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
    .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; color: #475569; margin-bottom: 8px; }}
    .ai-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px; color: #166534; font-size: 14px; line-height: 1.5; }}
    .footer {{ background: #f8fafc; padding: 16px 24px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; line-height: 1.4; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">{alert.severity}</span>
      <h1 class="title">WeatherGuard AI Alert</h1>
      <p style="margin: 0; color: #94a3b8; font-size: 13px;">Location: {alert.location} &bull; Generated: {generated_time}</p>
    </div>
    <div class="content">
      <div class="grid">
        <div class="stat-card">
          <div class="stat-label">Alert Type</div>
          <div class="stat-value">{alert.alert_type}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Forecast Time</div>
          <div class="stat-value">{formatted_fc_time}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Precipitation Chance</div>
          <div class="stat-value">{prob_str}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Expected Rainfall</div>
          <div class="stat-value">{rain_str}</div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Message Details</div>
        <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.5;">{alert.message}</p>
      </div>

      <div class="section">
        <div class="section-title">AI Forecast Summary & Recommendation</div>
        <div class="ai-box">
          {explanation}
        </div>
      </div>
    </div>
    <div class="footer">
      <strong>Disclaimer:</strong> {DISCLAIMER_TEXT}
    </div>
  </div>
</body>
</html>
"""

    return subject, plain_text, html_content
