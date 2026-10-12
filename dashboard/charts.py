"""Interactive Plotly charts for the Streamlit dashboard."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List
from app.database.models import WeatherReading


def create_forecast_charts(readings: List[WeatherReading]):
    """Generate modern Plotly figures for forecast visualization."""
    if not readings:
        return None, None, None

    data = [
        {
            "Time": r.forecast_time,
            "Temperature (°C)": r.temperature_c,
            "Rain Probability (%)": r.precipitation_probability or 0.0,
            "Rainfall (mm)": r.rain_mm or 0.0,
            "Wind Speed (km/h)": r.wind_speed_kmh or 0.0,
            "Humidity (%)": r.humidity or 0.0,
        }
        for r in readings
    ]
    df = pd.DataFrame(data).sort_values("Time")

    # 1. Temperature Chart
    fig_temp = go.Figure()
    fig_temp.add_trace(
        go.Scatter(
            x=df["Time"],
            y=df["Temperature (°C)"],
            mode="lines+markers",
            name="Temperature (°C)",
            line=dict(color="#f97316", width=3, shape="spline"),
            marker=dict(size=6, color="#ea580c"),
            fill="tozeroy",
            fillcolor="rgba(249, 115, 22, 0.1)",
        )
    )
    fig_temp.update_layout(
        title="24-Hour Temperature Trajectory",
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        template="plotly_white",
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="Temperature (°C)"),
    )

    # 2. Rain Probability & Expected Accumulation Chart
    fig_rain = go.Figure()
    fig_rain.add_trace(
        go.Bar(
            x=df["Time"],
            y=df["Rainfall (mm)"],
            name="Rainfall (mm)",
            marker_color="#0284c7",
            opacity=0.7,
            yaxis="y2",
        )
    )
    fig_rain.add_trace(
        go.Scatter(
            x=df["Time"],
            y=df["Rain Probability (%)"],
            mode="lines+markers",
            name="Rain Probability (%)",
            line=dict(color="#2563eb", width=2.5, shape="spline"),
            marker=dict(size=5, color="#1d4ed8"),
            yaxis="y",
        )
    )
    fig_rain.update_layout(
        title="Precipitation Probability & Expected Rainfall",
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        template="plotly_white",
        yaxis=dict(
            title="Probability (%)",
            range=[0, 105],
            showgrid=True,
            gridcolor="#f1f5f9",
        ),
        yaxis2=dict(
            title="Rainfall (mm)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # 3. Wind Speed Chart
    fig_wind = go.Figure()
    fig_wind.add_trace(
        go.Scatter(
            x=df["Time"],
            y=df["Wind Speed (km/h)"],
            mode="lines+markers",
            name="Wind Speed (km/h)",
            line=dict(color="#059669", width=2.5, shape="spline"),
            marker=dict(size=5, color="#047857"),
            fill="tozeroy",
            fillcolor="rgba(5, 150, 105, 0.08)",
        )
    )
    fig_wind.update_layout(
        title="Wind Velocity (10m)",
        margin=dict(l=20, r=20, t=40, b=20),
        height=280,
        template="plotly_white",
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="Wind (km/h)"),
    )

    return fig_temp, fig_rain, fig_wind
