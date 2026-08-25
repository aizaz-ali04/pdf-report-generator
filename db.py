"""
db.py — SQLite connection + schema for the PDF report generator.

Two tables:
  orders  : the "little shop" dataset (seeded with random data)
  reports : bookkeeping for every PDF we generate (id, path, created_at)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "report.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # better concurrent read/write behavior
    return conn


def init_db():
    """Create tables if they don't exist yet. Safe to call every startup."""
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            product TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
