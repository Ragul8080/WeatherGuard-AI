"""Streamlit Dashboard for WeatherGuard AI."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
from app.ai.llm import is_ollama_available
from app.config import settings
from app.database.connection import SessionLocal, init_db
from app.database.models import (
    NotificationHistory,
    UserPreference,
    WeatherAlert,
    WeatherReading,
    WorkflowExecution,
)
from app.database.repositories import (
    NotificationRepository,
    UserPreferenceRepository,
    WeatherAlertRepository,
    WeatherReadingRepository,
    WorkflowExecutionRepository,
)
from app.graph.workflow import run_workflow
from app.logging_config import logger
from app.utils.time import format_display_time, now_utc
from dashboard.charts import create_forecast_charts
from dashboard.components import decode_weather_code, render_metric_card, severity_badge

# Page Configuration
st.set_page_config(
    page_title="WeatherGuard AI — Autonomous Weather Monitoring",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main { background-color: #f8fafc; }
    .stMetric { background: white; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; }
    h1, h2, h3 { color: #0f172a; font-family: -apple-system, sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_db_session():
    """Create session and ensure DB initialized."""
    init_db()
    return SessionLocal()


def main():
    db = get_db_session()
    pref_repo = UserPreferenceRepository(db)
    reading_repo = WeatherReadingRepository(db)
    alert_repo = WeatherAlertRepository(db)
    wf_repo = WorkflowExecutionRepository(db)

    pref = pref_repo.get_preferences(settings.LOCATION_NAME)
    location_name = pref.location

    # Sidebar Navigation
    st.sidebar.image(
        "https://images.unsplash.com/photo-1534088568595-a066f410bcda?w=400&auto=format&fit=crop&q=60",
        use_container_width=True,
    )
    st.sidebar.title("WeatherGuard AI")
    st.sidebar.caption("Autonomous Monitoring & Alert Engine")

    # Manual Trigger Button
    if st.sidebar.button("⚡ Trigger Weather Check Now", use_container_width=True):
        with st.spinner("Executing LangGraph autonomous workflow..."):
            res = run_workflow(location=pref.location)
            st.sidebar.success(f"Check Complete! Status: {res.get('workflow_status')}")
            st.rerun()

    menu = st.sidebar.radio(
        "Navigation",
        [
            "📊 Overview Dashboard",
            "📈 24h Forecast",
            "🚨 Alerts Log",
            "🕒 Historical Readings",
            "⚙️ Settings & Thresholds",
            "🖥️ System Status",
        ],
    )

    st.sidebar.divider()
    st.sidebar.markdown(f"**Location:** `{pref.location}`")
    st.sidebar.markdown(f"**Coordinates:** `{pref.latitude:.4f}, {pref.longitude:.4f}`")
    st.sidebar.markdown(f"**Timezone:** `{pref.timezone}`")

    # ----------------------------------------------------
    # SECTION 1: OVERVIEW DASHBOARD
    # ----------------------------------------------------
    if menu == "📊 Overview Dashboard":
        st.title(f"Weather Monitoring — {pref.location}")
        latest = reading_repo.get_latest_reading(pref.location)
        latest_exec = wf_repo.get_latest_execution()
        active_alerts = alert_repo.get_latest_alerts(pref.location, limit=3)

        # Alert banner if active alerts exist
        if active_alerts:
            st.warning(
                f"🚨 **Active Advisory:** {active_alerts[0].alert_type} "
                f"({active_alerts[0].severity}) — {active_alerts[0].message}"
            )

        # Top Metric Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            temp_val = f"{latest.temperature_c:.1f} °C" if latest and latest.temperature_c is not None else "--"
            sub = f"Humidity: {latest.humidity:.0f}%" if latest and latest.humidity is not None else ""
            render_metric_card("Current Temperature", temp_val, sub, "🌡️")
        with c2:
            prob_val = f"{latest.precipitation_probability:.0f} %" if latest and latest.precipitation_probability is not None else "--"
            rain_val = f"Expected: {latest.rain_mm or 0.0:.1f} mm" if latest else ""
            render_metric_card("Rain Probability", prob_val, rain_val, "🌧️")
        with c3:
            wind_val = f"{latest.wind_speed_kmh:.1f} km/h" if latest and latest.wind_speed_kmh is not None else "--"
            render_metric_card("Wind Velocity", wind_val, "10m surface winds", "💨")
        with c4:
            cond_str = decode_weather_code(latest.weather_code) if latest and latest.weather_code is not None else "No data"
            render_metric_card("Condition", cond_str, f"Checked: {format_display_time(latest.fetched_at, pref.timezone) if latest else '--'}", "🌤️")

        # Next check & status row
        st.subheader("Autonomous Workflow Status")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.metric("Alert Engine", "ACTIVE" if pref.alert_enabled else "MUTED")
        with sc2:
            st.metric("Last Run Status", latest_exec.status if latest_exec else "PENDING")
        with sc3:
            st.metric("Last Executed", format_display_time(latest_exec.started_at, pref.timezone) if latest_exec else "--")

        st.divider()
        st.subheader("Quick 24h Trend")
        readings = reading_repo.get_recent_readings(pref.location, limit=24)
        if readings:
            fig_temp, fig_rain, _ = create_forecast_charts(readings)
            st.plotly_chart(fig_temp, use_container_width=True)
            st.plotly_chart(fig_rain, use_container_width=True)
        else:
            st.info("No forecast data stored yet. Click 'Trigger Weather Check Now' in the sidebar!")

    # ----------------------------------------------------
    # SECTION 2: FORECAST
    # ----------------------------------------------------
    elif menu == "📈 24h Forecast":
        st.title("Hourly Weather Forecast")
        readings = reading_repo.get_recent_readings(pref.location, limit=36)
        if not readings:
            st.info("No forecast data currently available. Trigger a check from the sidebar.")
        else:
            fig_temp, fig_rain, fig_wind = create_forecast_charts(readings)
            st.plotly_chart(fig_temp, use_container_width=True)
            st.plotly_chart(fig_rain, use_container_width=True)
            st.plotly_chart(fig_wind, use_container_width=True)

            # Table view
            with st.expander("Detailed Hourly Breakdown Table"):
                df_table = pd.DataFrame(
                    [
                        {
                            "Forecast Time": format_display_time(r.forecast_time, pref.timezone),
                            "Temp (°C)": r.temperature_c,
                            "Precip Prob (%)": r.precipitation_probability,
                            "Rain (mm)": r.rain_mm,
                            "Wind (km/h)": r.wind_speed_kmh,
                            "Condition": decode_weather_code(r.weather_code) if r.weather_code is not None else "--",
                        }
                        for r in readings
                    ]
                )
                st.dataframe(df_table, use_container_width=True)

    # ----------------------------------------------------
    # SECTION 3: ALERTS LOG
    # ----------------------------------------------------
    elif menu == "🚨 Alerts Log":
        st.title("Weather Alerts & Notifications Audit")
        alerts = alert_repo.get_latest_alerts(pref.location, limit=50)

        if not alerts:
            st.success("No alerts triggered. Weather conditions are within normal safety thresholds.")
        else:
            for alt in alerts:
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background: white; border-radius: 8px; border: 1px solid #e2e8f0; padding: 18px; margin-bottom: 14px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 17px; font-weight: 700; color: #0f172a;">
                                    {alt.alert_type} &bull; {alt.location}
                                </span>
                                <div>{severity_badge(alt.severity)}</div>
                            </div>
                            <p style="margin: 8px 0; color: #334155; font-size: 14px;">
                                <strong>Forecast Event Time:</strong> {format_display_time(alt.forecast_time, pref.timezone)} &bull;
                                <strong>Triggered At:</strong> {format_display_time(alt.triggered_at, pref.timezone)}
                            </p>
                            <p style="margin: 4px 0; color: #475569; font-size: 14px;">
                                {alt.message}
                            </p>
                            <div style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 10px 12px; margin-top: 10px; font-size: 13px; color: #1e293b;">
                                <strong>AI Explanation / Advisory:</strong><br/>
                                {alt.ai_explanation or 'Standard threshold trigger.'}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # ----------------------------------------------------
    # SECTION 4: HISTORICAL READINGS
    # ----------------------------------------------------
    elif menu == "🕒 Historical Readings":
        st.title("Historical Weather Observations")
        limit = st.slider("Readings to Display", min_value=12, max_value=120, value=48, step=12)
        readings = reading_repo.get_recent_readings(pref.location, limit=limit)

        if readings:
            data = [
                {
                    "Forecast Time": format_display_time(r.forecast_time, pref.timezone),
                    "Fetched At": format_display_time(r.fetched_at, pref.timezone),
                    "Temp (°C)": r.temperature_c,
                    "Humidity (%)": r.humidity,
                    "Rain Prob (%)": r.precipitation_probability,
                    "Rain (mm)": r.rain_mm,
                    "Wind (km/h)": r.wind_speed_kmh,
                }
                for r in readings
            ]
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "📥 Export CSV",
                df.to_csv(index=False),
                "weather_history.csv",
                "text/csv",
            )
        else:
            st.info("No recorded observations yet.")

    # ----------------------------------------------------
    # SECTION 5: SETTINGS & THRESHOLDS
    # ----------------------------------------------------
    elif menu == "⚙️ Settings & Thresholds":
        st.title("Configuration & Alert Thresholds")
        st.write("Modify weather monitoring thresholds and target coordinates.")

        with st.form("settings_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_loc = st.text_input("Location Name", value=pref.location)
                new_lat = st.number_input("Latitude", value=float(pref.latitude), format="%.4f")
                new_lon = st.number_input("Longitude", value=float(pref.longitude), format="%.4f")
                new_tz = st.text_input("Timezone (IANA)", value=pref.timezone)
                new_email = st.text_input("Alert Recipient Email", value=pref.email or "")
            with c2:
                new_rain_prob = st.slider("Rain Probability Threshold (%)", 0, 100, int(pref.rain_probability_threshold))
                new_min_rain = st.number_input("Minimum Rain for Alert (mm)", value=float(pref.minimum_rainfall_mm), step=0.5)
                new_high_rain = st.number_input("High Rainfall Threshold (mm)", value=float(pref.high_rainfall_mm), step=1.0)
                new_low_temp = st.number_input("Low Temperature Advisory (°C)", value=float(pref.low_temperature_threshold), step=1.0)
                new_high_wind = st.number_input("High Wind Alert (km/h)", value=float(pref.high_wind_threshold), step=5.0)
                new_enabled = st.checkbox("Autonomous Alerts Enabled", value=pref.alert_enabled)

            submitted = st.form_submit_button("Save Preferences")
            if submitted:
                pref.location = new_loc
                pref.latitude = new_lat
                pref.longitude = new_lon
                pref.timezone = new_tz
                pref.email = new_email
                pref.rain_probability_threshold = float(new_rain_prob)
                pref.minimum_rainfall_mm = float(new_min_rain)
                pref.high_rainfall_mm = float(new_high_rain)
                pref.low_temperature_threshold = float(new_low_temp)
                pref.high_wind_threshold = float(new_high_wind)
                pref.alert_enabled = new_enabled
                pref_repo.update_preferences(pref)
                st.success("Preferences updated successfully!")
                st.rerun()

    # ----------------------------------------------------
    # SECTION 6: SYSTEM STATUS
    # ----------------------------------------------------
    elif menu == "🖥️ System Status":
        st.title("System Health & Observability")
        ollama_ok = is_ollama_available()
        latest_exec = wf_repo.get_latest_execution()
        executions = wf_repo.get_executions(limit=10)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Database", "CONNECTED" if db else "ERROR")
            st.metric("Database Engine", "SQLite" if settings.DATABASE_URL.startswith("sqlite") else "PostgreSQL")
        with c2:
            st.metric("Ollama Local LLM", "ONLINE" if ollama_ok else "OFFLINE / FALLBACK")
            st.metric("Ollama Model", settings.OLLAMA_MODEL)
        with c3:
            st.metric("SMTP Email", "CONFIGURED" if settings.is_smtp_configured else "MOCK / SAFE MODE")
            st.metric("Check Interval", f"{settings.WEATHER_CHECK_INTERVAL_MINUTES} mins")

        st.subheader("Recent Workflow Execution Audit")
        if executions:
            audit_data = [
                {
                    "Workflow ID": e.workflow_id,
                    "Status": e.status,
                    "Started At": format_display_time(e.started_at, pref.timezone),
                    "Completed At": format_display_time(e.completed_at, pref.timezone) if e.completed_at else "--",
                    "Alerts Count": e.alerts_count,
                    "Details": e.details or "--",
                }
                for e in executions
            ]
            st.dataframe(pd.DataFrame(audit_data), use_container_width=True)
        else:
            st.info("No workflow executions logged yet.")

    db.close()


if __name__ == "__main__":
    main()
