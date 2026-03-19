"""
migrate_db.py
Run this ONCE to update your existing davs.db to the new schema.
Place this file in the same folder as your app.py and davs.db, then run:
    python migrate_db.py
"""

import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), 'davs.db')

def migrate():
    print(f"[MIGRATE] Opening database: {DB_FILE}")

    if not os.path.exists(DB_FILE):
        print("[MIGRATE] davs.db not found! Make sure this script is in the same folder as app.py")
        return

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        # ── Check existing columns in sessions table ──
        existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        print(f"[MIGRATE] Existing sessions columns: {existing_cols}")

        # ── Add absent_json column if missing ──
        if 'absent_json' not in existing_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN absent_json TEXT NOT NULL DEFAULT '[]'")
            print("[MIGRATE] ✅ Added column: absent_json")
        else:
            print("[MIGRATE] ✔  Column absent_json already exists — skipping")

        # ── Add nfc_registration table if missing ──
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"[MIGRATE] Existing tables: {tables}")

        if 'nfc_registration' not in tables:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS nfc_registration ("
                "  id INTEGER PRIMARY KEY CHECK (id = 1),"
                "  waiting INTEGER NOT NULL DEFAULT 0,"
                "  scanned_uid TEXT NOT NULL DEFAULT '',"
                "  requested_by TEXT NOT NULL DEFAULT '',"
                "  requested_at TEXT NOT NULL DEFAULT ''"
                ");"
            )
            conn.execute(
                "INSERT OR IGNORE INTO nfc_registration (id, waiting, scanned_uid) VALUES (1, 0, '')"
            )
            print("[MIGRATE] ✅ Created table: nfc_registration")
        else:
            print("[MIGRATE] ✔  Table nfc_registration already exists — skipping")

        # ── Verify final schema ──
        final_cols = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        print(f"\n[MIGRATE] Final sessions columns: {final_cols}")
        print("\n[MIGRATE] ✅ Migration complete! You can now run app.py normally.")

if __name__ == "__main__":
    migrate()