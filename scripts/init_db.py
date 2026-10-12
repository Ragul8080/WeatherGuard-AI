"""Database initialization script."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import init_db
from app.logging_config import logger


def main():
    logger.info("Running database initialization...")
    try:
        init_db()
        print("SUCCESS: Database initialized successfully.")
    except Exception as e:
        print(f"ERROR: Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
