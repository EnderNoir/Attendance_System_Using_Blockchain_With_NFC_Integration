"""
migrate_db.py
=============
Run this whenever you update app.py and get a missing column error.
It is safe to run multiple times — existing columns and data are never touched.

Usage:
    python migrate_db.py
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from services.ops.db_compat import connect_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/davs')

# All columns that should exist across all tables.
# Format: (table, column_name, definition)
COLUMNS_TO_ADD = [
    # students table
    ("students", "full_name",       "TEXT NOT NULL DEFAULT ''"),
    ("students", "program",         "TEXT NOT NULL DEFAULT ''"),
    ("students", "student_id",      "TEXT NOT NULL DEFAULT ''"),
    ("students", "year_level",      "TEXT NOT NULL DEFAULT ''"),
    ("students", "section",         "TEXT NOT NULL DEFAULT ''"),
    ("students", "adviser",         "TEXT NOT NULL DEFAULT ''"),
    ("students", "email",           "TEXT NOT NULL DEFAULT ''"),
    ("students", "contact",         "TEXT NOT NULL DEFAULT ''"),
    ("students", "major",           "TEXT NOT NULL DEFAULT ''"),
    ("students", "semester",        "TEXT NOT NULL DEFAULT ''"),
    ("students", "school_year",     "TEXT NOT NULL DEFAULT ''"),
    ("students", "date_registered", "TEXT NOT NULL DEFAULT ''"),
    ("students", "raw_name",        "TEXT NOT NULL DEFAULT ''"),
    ("students", "eth_address",     "TEXT NOT NULL DEFAULT ''"),
    ("students", "reg_tx_hash",     "TEXT NOT NULL DEFAULT ''"),
    ("students", "reg_block",       "INTEGER NOT NULL DEFAULT 0"),
    ("students", "photo_file",      "TEXT NOT NULL DEFAULT ''"),
    ("students", "created_at",      "TEXT NOT NULL DEFAULT ''"),
    ("students", "updated_at",      "TEXT NOT NULL DEFAULT ''"),

    # sessions table
    ("sessions", "teacher_username",  "TEXT NOT NULL DEFAULT ''"),
    ("sessions", "total_enrolled",    "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "total_present",     "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "total_late",        "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "total_absent",      "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "total_excused",     "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "warn_log_json",     "TEXT NOT NULL DEFAULT '[]'"),
    ("sessions", "invalid_log_json",  "TEXT NOT NULL DEFAULT '[]'"),

    # accounts table
    ("accounts", "updated_at",        "TEXT NOT NULL DEFAULT ''"),

    # photos table
    ("photos",   "uploaded_at",       "TEXT NOT NULL DEFAULT ''"),

    # attendance_logs table
    ("attendance_logs", "excuse_note",       "TEXT NOT NULL DEFAULT ''"),
    ("attendance_logs", "excuse_request_id",  "INTEGER DEFAULT NULL"),

    # sessions table – extra columns added later
    ("sessions", "grace_period",    "INTEGER NOT NULL DEFAULT 15"),
    ("sessions", "auto_end_at",     "TEXT"),
    ("sessions", "schedule_id",     "TEXT DEFAULT NULL"),
    ('schedules', 'semester', "TEXT NOT NULL DEFAULT '1st Semester'"),
    ('sessions', 'semester', "TEXT NOT NULL DEFAULT '1st Semester'"),
    ('sessions', 'session_tx_hash', "TEXT NOT NULL DEFAULT ''"),
    ('sessions', 'session_block_number', "INTEGER NOT NULL DEFAULT 0"),
]

# Tables that must exist (created if missing)
TABLES_TO_CREATE = [
    (
        "nfc_registration",
        """CREATE TABLE IF NOT EXISTS nfc_registration (
            id           INTEGER PRIMARY KEY CHECK (id = 1),
            waiting      INTEGER NOT NULL DEFAULT 0,
            scanned_uid  TEXT NOT NULL DEFAULT '',
            requested_by TEXT NOT NULL DEFAULT '',
            requested_at TEXT NOT NULL DEFAULT ''
        )"""
    ),
    (
        "nfc_scanner",
        """CREATE TABLE IF NOT EXISTS nfc_scanner (
            id           INTEGER PRIMARY KEY CHECK (id = 1),
            waiting      INTEGER NOT NULL DEFAULT 0,
            scanned_uid  TEXT NOT NULL DEFAULT '',
            requested_by TEXT NOT NULL DEFAULT '',
            requested_at TEXT NOT NULL DEFAULT ''
        )"""
    ),
    (
        "student_overrides",
        """CREATE TABLE IF NOT EXISTS student_overrides (
            nfc_id          TEXT PRIMARY KEY,
            full_name       TEXT DEFAULT '',
            student_id      TEXT DEFAULT '',
            email           TEXT DEFAULT '',
            contact         TEXT DEFAULT '',
            adviser         TEXT DEFAULT '',
            major           TEXT DEFAULT '',
            semester        TEXT DEFAULT '',
            school_year     TEXT DEFAULT '',
            date_registered TEXT DEFAULT '',
            course          TEXT DEFAULT '',
            year_level      TEXT DEFAULT '',
            section         TEXT DEFAULT ''
        )"""
    ),
    (
        "schedules",
        """CREATE TABLE IF NOT EXISTS schedules (
            schedule_id      TEXT PRIMARY KEY,
            section_key      TEXT NOT NULL DEFAULT '',
            subject_id       TEXT NOT NULL DEFAULT '',
            subject_name     TEXT NOT NULL DEFAULT '',
            course_code      TEXT NOT NULL DEFAULT '',
            teacher_username TEXT NOT NULL DEFAULT '',
            teacher_name     TEXT NOT NULL DEFAULT '',
            day_of_week      INTEGER NOT NULL DEFAULT 1,
            start_time       TEXT NOT NULL DEFAULT '',
            end_time         TEXT NOT NULL DEFAULT '',
            semester         TEXT NOT NULL DEFAULT '',
            grace_minutes    INTEGER NOT NULL DEFAULT 15,
            is_active        INTEGER NOT NULL DEFAULT 1,
            created_by       TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT ''
        )"""
    ),
    (
        "excuse_requests",
        """CREATE TABLE IF NOT EXISTS excuse_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sess_id         TEXT NOT NULL DEFAULT '',
            nfc_id          TEXT NOT NULL DEFAULT '',
            student_name    TEXT NOT NULL DEFAULT '',
            student_id      TEXT NOT NULL DEFAULT '',
            student_email   TEXT NOT NULL DEFAULT '',
            reason_type     TEXT NOT NULL DEFAULT '',
            reason_detail   TEXT NOT NULL DEFAULT '',
            attachment_file TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'pending',
            reviewed_by     TEXT NOT NULL DEFAULT '',
            reviewed_at     TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT ''
        )"""
    ),
]

# Data backfills: copy old column → new column where new is empty
BACKFILLS = [
    # (table, source_col, dest_col)
    ("students", "name",     "full_name"),
    ("students", "course",   "program"),
    ("students", "tx_hash",  "reg_tx_hash"),
    ("sessions", "teacher",  "teacher_username"),
]

# Indexes to create
INDEXES = [
    ("idx_stu_program",   "CREATE INDEX IF NOT EXISTS idx_stu_program ON students(program)"),
    ("idx_stu_section",   "CREATE INDEX IF NOT EXISTS idx_stu_section ON students(year_level, section)"),
    ("idx_sess_teacher",  "CREATE INDEX IF NOT EXISTS idx_sess_teacher ON sessions(teacher_username)"),
    ("idx_sess_ended",    "CREATE INDEX IF NOT EXISTS idx_sess_ended ON sessions(ended_at)"),
    ("idx_sess_section",  "CREATE INDEX IF NOT EXISTS idx_sess_section ON sessions(section_key)"),
    ("idx_att_sess",      "CREATE INDEX IF NOT EXISTS idx_att_sess ON attendance_logs(sess_id)"),
    ("idx_att_nfc",       "CREATE INDEX IF NOT EXISTS idx_att_nfc ON attendance_logs(nfc_id)"),
    ("idx_att_status",    "CREATE INDEX IF NOT EXISTS idx_att_status ON attendance_logs(status)"),
    ("idx_subj_code",     "CREATE INDEX IF NOT EXISTS idx_subj_code ON subjects(course_code)"),
    ("idx_sched_teacher", "CREATE INDEX IF NOT EXISTS idx_sched_teacher ON schedules(teacher_username)"),
    ("idx_sched_day",     "CREATE INDEX IF NOT EXISTS idx_sched_day ON schedules(day_of_week)"),
    ("idx_excuse_sess",   "CREATE INDEX IF NOT EXISTS idx_excuse_sess ON excuse_requests(sess_id)"),
    ("idx_excuse_nfc",    "CREATE INDEX IF NOT EXISTS idx_excuse_nfc ON excuse_requests(nfc_id)"),
    ("idx_excuse_status", "CREATE INDEX IF NOT EXISTS idx_excuse_status ON excuse_requests(status)"),
]


def get_existing_columns(conn, table):
    try:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=? "
            "ORDER BY ordinal_position",
            (table,)
        ).fetchall()
        return [row[0] for row in rows]
    except Exception:
        return []


def get_existing_tables(conn):
    return [row[0] for row in conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()]


def migrate():
    print("[MIGRATE] Opening PostgreSQL connection")
    conn = connect_db(DATABASE_URL)

    existing_tables = get_existing_tables(conn)
    print(f"[MIGRATE] Tables found: {existing_tables}")

    # ── 1. Create missing tables ───────────────────────────────────────────
    print("\n-- Creating missing tables --")
    for table_name, create_sql in TABLES_TO_CREATE:
        if table_name not in existing_tables:
            conn.execute(create_sql)
            # Seed single-row tables
            if table_name in ('nfc_registration', 'nfc_scanner'):
                conn.execute(
                    f"INSERT OR IGNORE INTO {table_name} "
                    "(id, waiting, scanned_uid, requested_by, requested_at) "
                    "VALUES (1, 0, '', '', ?)",
                    (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),)
                )
            print(f"  [OK] Created table: {table_name}")
        else:
            print(f"  [SKIP] Table already exists: {table_name}")

    # -- 2. Add missing columns --
    print("\n-- Adding missing columns --")
    added, skipped = [], []
    for table, col, defn in COLUMNS_TO_ADD:
        if table not in get_existing_tables(conn):
            print(f"  [WARN] Table {table} not found, skipping {col}")
            continue
        existing_cols = get_existing_columns(conn, table)
        if col in existing_cols:
            skipped.append(f"{table}.{col}")
            continue
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            added.append(f"{table}.{col}")
            print(f"  [NEW] Added: {table}.{col}")
        except Exception as e:
            print(f"  [ERR] Could not add {table}.{col}: {e}")

    # -- 3. Backfill data from old column names --
    print("\n-- Backfilling data from renamed columns --")
    for table, src, dst in BACKFILLS:
        existing_cols = get_existing_columns(conn, table)
        if src in existing_cols and dst in existing_cols:
            try:
                conn.execute(
                    f"UPDATE {table} SET {dst} = {src} "
                    f"WHERE ({dst} IS NULL OR {dst} = '') AND ({src} IS NOT NULL AND {src} != '')"
                )
                print(f"  [OK] Backfilled {table}.{src} -> {table}.{dst}")
            except Exception as e:
                print(f"  [ERR] Backfill {table}.{src}->{dst}: {e}")
        else:
            print(f"  [SKIP] Skipped backfill {table}.{src}->{dst} (one or both columns missing)")

    # -- 4. Create indexes --
    print("\n-- Creating indexes --")
    for idx_name, idx_sql in INDEXES:
        try:
            conn.execute(idx_sql)
            print(f"  [OK] Index: {idx_name}")
        except Exception as e:
            print(f"  [ERR] Index {idx_name}: {e}")

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"[DONE] Migration complete.")
    print(f"  Added {len(added)} column(s)")
    if added:
        for c in added: print(f"    + {c}")
    if skipped:
        print(f"  Skipped {len(skipped)} already-existing column(s)")
    print(f"\n[INFO] Restart Flask now: python app.py")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    migrate()