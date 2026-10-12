"""Script to inspect and display SQLite database contents."""

import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def inspect_database():
    db_file = "weather.db"
    print("=" * 70)
    print(f" WEATHERGUARD AI -- DATABASE INSPECTOR ({db_file})")
    print("=" * 70)

    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        tables = [
            r[0]
            for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]

        if not tables:
            print("No tables found in database. Run 'python scripts/init_db.py' first.")
            return

        print(f"Found {len(tables)} tables: {', '.join(tables)}\n")

        for table in tables:
            count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"[TABLE: {table.upper()}] (Total rows: {count})")

            cur.execute(f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT 5")
            rows = cur.fetchall()

            if not rows:
                print("   (Table is currently empty)\n")
                continue

            cols = [d[0] for d in cur.description]
            print("   Columns:", " | ".join(cols))
            print("   " + "-" * 65)

            for idx, row in enumerate(rows, start=1):
                vals = [str(row[c]) if row[c] is not None else "NULL" for c in cols]
                print(f"   [{idx}] " + " | ".join(vals))
            print("\n")

        conn.close()

    except Exception as e:
        print(f"Error reading database: {e}")


if __name__ == "__main__":
    inspect_database()
