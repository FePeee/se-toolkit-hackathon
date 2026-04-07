"""
Migration script to add report_day and report_time columns to users table.
Run this once to update the database schema.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "habittracker.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if "report_day" not in columns:
        print("Adding report_day column...")
        cursor.execute("ALTER TABLE users ADD COLUMN report_day TEXT")
        conn.commit()
        print("✅ report_day column added")

    if "report_time" not in columns:
        print("Adding report_time column...")
        cursor.execute("ALTER TABLE users ADD COLUMN report_time TEXT")
        conn.commit()
        print("✅ report_time column added")

    conn.close()
    print("✅ Migration completed")


if __name__ == "__main__":
    migrate()
