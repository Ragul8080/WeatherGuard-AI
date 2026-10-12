"""Reusable UI components for the Streamlit dashboard."""

import streamlit as st


def render_metric_card(title: str, value: str, subvalue: str = "", icon: str = "🌡️"):
    """Render a clean styled metric card."""
    st.markdown(
        f"""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748b; font-size: 13px; font-weight: 600; text-transform: uppercase;">
                {icon} {title}
            </div>
            <div style="font-size: 26px; font-weight: 700; color: #0f172a; margin-top: 6px;">
                {value}
            </div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                {subvalue}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def severity_badge(severity: str) -> str:
    """Return colored HTML badge for alert severity."""
    sev = severity.upper()
    colors = {
        "NORMAL": ("#dbeafe", "#1e40af"),
        "INFORMATIONAL": ("#e0f2fe", "#0369a1"),
        "WARNING": ("#fef3c7", "#b45309"),
        "HIGH": ("#fee2e2", "#b91c1c"),
    }
    bg, fg = colors.get(sev, ("#f1f5f9", "#475569"))
    return f'<span style="background-color: {bg}; color: {fg}; padding: 3px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase;">{sev}</span>'


def decode_weather_code(code: int) -> str:
    """Translate WMO weather interpretation code to human-readable string."""
    codes = {
        0: "Clear Sky ☀️",
        1: "Mainly Clear 🌤️",
        2: "Partly Cloudy ⛅",
        3: "Overcast ☁️",
        45: "Fog 🌫️",
        48: "Depositing Rime Fog 🌫️",
        51: "Light Drizzle 🌦️",
        53: "Moderate Drizzle 🌦️",
        55: "Dense Drizzle 🌧️",
        61: "Slight Rain 🌧️",
        63: "Moderate Rain 🌧️",
        65: "Heavy Rain ⛈️",
        71: "Slight Snow 🌨️",
        73: "Moderate Snow 🌨️",
        75: "Heavy Snow ❄️",
        80: "Slight Rain Showers 🌦️",
        81: "Moderate Rain Showers 🌧️",
        82: "Violent Rain Showers ⛈️",
        95: "Thunderstorm ⚡",
        96: "Thunderstorm with Hail ⛈️",
        99: "Heavy Thunderstorm with Hail ⛈️",
    }
    return codes.get(code, f"Code {code} ⛅")
