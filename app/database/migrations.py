"""Database schema creation and migration helper."""

from app.database.connection import engine, init_db
from app.database.models import Base
from app.logging_config import logger


def run_migrations() -> None:
    """Run database table creation / schema updates."""
    logger.info("Verifying database schema...")
    init_db()
    logger.info("Database schema verification completed.")


if __name__ == "__main__":
    run_migrations()
