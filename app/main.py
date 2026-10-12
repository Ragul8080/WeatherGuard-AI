"""WeatherGuard AI FastAPI main application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.config import settings
from app.database.connection import init_db
from app.logging_config import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    # Startup
    setup_logging()
    logger.info("==================================================")
    logger.info("   Starting WeatherGuard AI Server                ")
    logger.info(f"   Environment: {settings.APP_ENV}                ")
    logger.info(f"   Database:    {settings.DATABASE_URL.split('@')[-1]}")
    logger.info(f"   Location:    {settings.LOCATION_NAME}          ")
    logger.info("==================================================")

    try:
        init_db()
        logger.info("Database verified on startup.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")

    yield

    # Shutdown
    logger.info("Shutting down WeatherGuard AI Server gracefully...")


app = FastAPI(
    title="WeatherGuard AI",
    description=(
        "Autonomous AI-powered weather monitoring and alerting service using "
        "LangGraph, LangChain, Open-Meteo, SQLAlchemy, and Ollama."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(router)


@app.get("/", summary="Root Welcome Index", tags=["General"])
def root_index():
    """Welcome route providing service metadata and direct navigation links."""
    return {
        "service": "WeatherGuard AI",
        "version": __version__,
        "status": "online",
        "interactive_docs": "/docs",
        "health_check": "/health",
        "streamlit_dashboard": "http://localhost:8501 (Start with: streamlit run dashboard/app.py)",
        "endpoints": {
            "latest_weather": "/api/weather/latest",
            "forecast": "/api/weather/forecast",
            "history": "/api/weather/history",
            "alerts": "/api/alerts",
            "settings": "/api/settings",
            "trigger_check": "POST /api/weather/check",
            "test_email": "POST /api/alerts/test-email",
            "chat": "POST /api/chat",
        },
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Silent response for browser favicon requests."""
    from fastapi.responses import Response
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.APP_ENV == "development",
    )
