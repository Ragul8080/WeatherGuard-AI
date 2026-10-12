# WeatherGuard AI

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-teal.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/dashboard-Streamlit-red.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Autonomous AI-powered weather monitoring and alerting system engineered with **LangGraph**, **LangChain**, **FastAPI**, **Streamlit**, **SQLAlchemy**, and **Open-Meteo**.

---

## 1. Project Overview

WeatherGuard AI operates continuously and autonomously to protect people and assets from adverse weather events. Every hour, the system fetches multi-day forecasts from Open-Meteo, parses and stores readings, executes a deterministic numerical rules engine over a 6-hour forward horizon, detects and deduplicates safety thresholds, invokes a local LLM (Ollama) or deterministic fallback for human-readable guidance, and dispatches HTML email notifications.

### Core Architectural Principle
- **Deterministic Python Engine:** Makes numerical alert calculations, threshold comparisons, duplicate detection, and database operations. **The LLM never decides whether an alert triggers.**
- **LangGraph:** Orchestrates the multi-step stateful workflow with conditional routing (no-alert vs alert vs duplicate-skipped).
- **LangChain:** Powers controlled tool abstractions and structured local LLM interactions.
- **Ollama:** Optional local AI model (e.g. `llama3.2`) generating user-friendly explanations. If Ollama is offline, the system continues running without interruption via template fallbacks.

---

## 2. System Architecture

```text
                                  ┌─────────────────────────────┐
                                  │      Open-Meteo API         │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
┌──────────────────┐               ┌─────────────────────────────┐               ┌──────────────────┐
│   APScheduler    │ ────────────> │     LangGraph Workflow      │ ────────────> │    SMTP Email    │
│ (Hourly Daemon)  │               │   (State & Routing Engine)  │               │  Notifications   │
└──────────────────┘               └──────────────┬──────────────┘               └──────────────────┘
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                      ┌──────────────────────┐        ┌──────────────────────┐
                      │  SQLAlchemy Database │        │  Ollama Local LLM    │
                      │  (SQLite/PostgreSQL) │        │  (Optional Guidance) │
                      └──────────┬───────────┘        └──────────────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
┌──────────────────────┐                   ┌──────────────────────┐
│   FastAPI Backend    │                   │ Streamlit Dashboard  │
│   (Port 8000)        │                   │ (Port 8501)          │
└──────────────────────┘                   └──────────────────────┘
```

---

## 3. Technology Stack

- **Runtime:** Python 3.12+
- **Workflow Orchestration:** LangGraph 0.2+ (StateGraph, conditional routing)
- **Tool & LLM Integration:** LangChain, langchain-ollama
- **Weather Provider:** Open-Meteo (Eligible Free/Non-Commercial API)
- **Database & ORM:** SQLAlchemy 2.x (SQLite for local dev, PostgreSQL for production)
- **Scheduler:** APScheduler (BlockingScheduler with non-overlapping execution)
- **Web API:** FastAPI & Uvicorn (Pydantic 2.x)
- **Interactive UI:** Streamlit & Plotly (6-section operational dashboard)
- **Testing:** Pytest, pytest-mock, pytest-asyncio
- **Containerization:** Docker & Docker Compose

---

## 4. LangGraph Workflow Structure

The workflow consists of 12 distinct, single-responsibility nodes:

```text
START
  │
  ▼
[initialize]
  │
  ▼
[fetch_weather]
  │
  ▼
[validate_forecast]
  │
  ▼
[save_forecast]
  │
  ▼
[analyse_forecast]
  │
  ▼
[check_alert_required] ───(No alert needed)───────────────┐
  │                                                        │
  ▼ (Alert condition detected)                             │
[check_duplicate_alerts] ──(All duplicates skipped)───────┤
  │                                                        │
  ▼ (New alerts qualified)                                 │
[create_alerts]                                            │
  │                                                        │
  ▼                                                        │
[generate_ai_explanation] (Ollama / Fallback)              │
  │                                                        │
  ▼                                                        │
[send_email]                                               │
  │                                                        │
  ▼                                                        │
[record_notification]                                      │
  │                                                        │
  ▼                                                        │
[finalize] <───────────────────────────────────────────────┘
  │
  ▼
 END
```

---

## 5. Quickstart & Installation

### Step 1: Clone and Create Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 3: Configure Environment Variables

Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Review or edit `.env`:
```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./weather.db

LATITUDE=13.0827
LONGITUDE=80.2707
LOCATION_NAME=Chennai
TIMEZONE=Asia/Kolkata

WEATHER_CHECK_INTERVAL_MINUTES=60
ALERT_HORIZON_HOURS=6

RAIN_PROBABILITY_THRESHOLD=70
MIN_RAINFALL_MM=1.0
HIGH_RAINFALL_MM=10.0
LOW_TEMPERATURE_C=15.0
HIGH_WIND_KMH=40.0

OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# SMTP Configuration (Leave blank for safe logged MOCK mode)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
ALERT_RECIPIENT=
```

### Step 4: Initialize and Seed Database

```powershell
python scripts/init_db.py
python scripts/seed_data.py
```

### Step 5: Verify System Health

```powershell
python scripts/health_check.py
```

---

## 6. Running the Application

### 1. Run the FastAPI Backend (Port 8000)
```powershell
uvicorn app.main:app --reload --port 8000
```
Interactive documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 2. Run the Streamlit Dashboard (Port 8501)
```powershell
streamlit run dashboard/app.py
```
Open your browser to: `http://localhost:8501`

### 3. Run the Autonomous Scheduler Daemon
```powershell
python -m app.scheduler.hourly
```

**Options for development/testing:**
- Run single check immediately and exit:
  ```powershell
  python -m app.scheduler.hourly --run-once
  ```
- Override check interval to every 30 seconds for quick testing:
  ```powershell
  python -m app.scheduler.hourly --interval-seconds 30
  ```

---

## 7. Running Tests

Execute the automated test suite:

```powershell
pytest -v
```

The test suite covers:
- Weather client response parsing, error handling, retries, and `MockWeatherProvider`
- Deterministic alert rules engine for all thresholds
- Duplicate prevention using composite idempotency keys
- Database repositories and schema integrity
- LangGraph compilation, routing branches, failure recovery, and fallback
- SMTP email mocking, template rendering, and error recording
- All FastAPI endpoints

---

## 8. Docker Deployment

Deploy the entire production stack (PostgreSQL, FastAPI, Scheduler, Streamlit) with Docker Compose:

```powershell
docker compose up --build -d
```

Check service status:
```powershell
docker compose ps
docker compose logs -f app
```

Shutdown:
```powershell
docker compose down
```

---

## 9. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health status of DB, Weather API, Ollama, SMTP |
| `GET` | `/api/weather/latest` | Most recent recorded weather observation |
| `GET` | `/api/weather/history` | Historical readings with limit/date filters |
| `GET` | `/api/weather/forecast` | Direct multi-day forecast from Open-Meteo |
| `GET` | `/api/alerts` | List of triggered weather alerts |
| `GET` | `/api/alerts/latest` | Most recently triggered alert |
| `GET` | `/api/settings` | Current thresholds and preferences |
| `PUT` | `/api/settings` | Update thresholds and coordinates |
| `POST` | `/api/weather/check` | Manually triggers one LangGraph workflow check |
| `POST` | `/api/alerts/test-email` | Dispatches diagnostic test notification |
| `POST` | `/api/chat` | Optional AI conversational weather assistant |

---

## 10. Database Schema

1. **`weather_readings`:** Stores hourly forecasts and observations (location, coordinates, forecast time, fetched at, temperature, humidity, rain probability, precipitation, rain mm, weather code, wind speed).
2. **`weather_alerts`:** Stores triggered alerts with unique `alert_key` (e.g. `Chennai:RAIN_WARNING:2026-10-13T14:00`), severity, message, and AI explanation.
3. **`notification_history`:** Audit log of all email dispatch attempts (alert ID, recipient, attempted at, sent at, status, error message, retry count).
4. **`user_preferences`:** Configurable safety thresholds and contact details.
5. **`workflow_executions`:** Observability log tracking workflow runs, statuses, runtimes, and alert counts.

---

## 11. Security Notes

- Credentials (database passwords, SMTP credentials) are managed exclusively through environment variables.
- Passwords and secrets are never logged in application or workflow logs.
- When SMTP is not configured, the application runs in a safe simulated mock mode, ensuring zero risk of accidental email spam or startup crashes.
