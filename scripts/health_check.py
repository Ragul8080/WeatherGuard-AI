"""Comprehensive system health check script."""

import sys
from pathlib import Path
from sqlalchemy import text

# Force UTF-8 on Windows console if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from app.ai.llm import is_ollama_available
from app.config import settings
from app.database.connection import engine
from app.logging_config import logger


def run_health_check() -> bool:
    """Evaluate core components and print diagnostic summary."""
    print("==================================================")
    print("       WEATHERGUARD AI - SYSTEM HEALTH CHECK       ")
    print("==================================================")
    all_ok = True

    # 1. Module Imports
    print("\n[1/5] Verifying Application Imports...")
    try:
        import fastapi
        import langchain
        import langgraph
        import sqlalchemy
        import streamlit
        print("  [OK] Core modules imported successfully.")
    except Exception as e:
        print(f"  [FAIL] Import Error: {e}")
        all_ok = False

    # 2. Database Connectivity
    print("\n[2/5] Testing Database Connection...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = "SQLite" if settings.DATABASE_URL.startswith("sqlite") else "PostgreSQL"
        print(f"  [OK] Database ({db_type}) connected successfully.")
    except Exception as e:
        print(f"  [FAIL] Database Connection Failed: {e}")
        all_ok = False

    # 3. Weather API (Open-Meteo)
    print("\n[3/5] Testing Open-Meteo Weather API Connectivity...")
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                settings.OPEN_METEO_BASE_URL,
                params={"latitude": 13.0827, "longitude": 80.2707, "forecast_days": 1},
            )
            if resp.status_code in (200, 400):
                print(f"  [OK] Open-Meteo endpoint reachable (HTTP {resp.status_code}).")
            else:
                print(f"  [FAIL] Unexpected response from Open-Meteo: HTTP {resp.status_code}")
                all_ok = False
    except Exception as e:
        print(f"  [FAIL] Open-Meteo API Unreachable: {e}")
        all_ok = False

    # 4. Ollama Availability
    print("\n[4/5] Checking Local AI (Ollama)...")
    ollama_up = is_ollama_available()
    if ollama_up:
        print(f"  [OK] Ollama server reachable at {settings.OLLAMA_BASE_URL} (Model: {settings.OLLAMA_MODEL}).")
    else:
        if settings.OLLAMA_ENABLED:
            print(f"  [WARN] Ollama is enabled in .env but server is not currently reachable at {settings.OLLAMA_BASE_URL}.")
            print("         (Fallback: System will use deterministic template explanations).")
        else:
            print("  [INFO] Ollama is disabled in configuration. Using deterministic template fallback.")

    # 5. SMTP Configuration
    print("\n[5/5] Checking SMTP Email Settings...")
    if settings.is_smtp_configured:
        print(f"  [OK] SMTP configured (Host: {settings.SMTP_HOST}, Recipient: {settings.ALERT_RECIPIENT}).")
    else:
        print("  [INFO] SMTP not fully configured (Alerts will run in safe mock/logged delivery mode).")

    print("\n==================================================")
    if all_ok:
        print(" HEALTH CHECK: ALL PRIMARY SYSTEMS HEALTHY")
    else:
        print(" HEALTH CHECK: ONE OR MORE REQUIRED CHECKS FAILED")
    print("==================================================")
    return all_ok


if __name__ == "__main__":
    success = run_health_check()
    sys.exit(0 if success else 1)
