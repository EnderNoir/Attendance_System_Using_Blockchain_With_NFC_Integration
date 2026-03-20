"""
DAVS Database Reset Script
===========================
Clears all accounts, students, sessions, subjects, and attendance data.
Creates a single fresh super admin account.

Usage:
    python reset_db.py

WARNING: This deletes all data. Run only when you want a clean slate.
"""

import sqlite3, hashlib, os, json
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), 'davs.db')

# ── Super admin credentials (change if needed) ─────────────────────────────
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
ADMIN_FULLNAME = 'System Administrator'

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def reset():
    if not os.path.exists(DB_FILE):
        print(f"[ERROR] Database not found: {DB_FILE}")
        print("Run the Flask app first to create the database.")
        return

    confirm = input(
        "\n⚠  WARNING: This will DELETE all accounts, students, sessions,\n"
        "   subjects, and attendance records.\n"
        "   Only the super admin account will remain.\n\n"
        "   Type YES to confirm: "
    ).strip()

    if confirm != 'YES':
        print("Cancelled.")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pw  = hash_password(ADMIN_PASSWORD)

    tables_to_clear = [
        'attendance_logs',
        'sessions',
        'students',
        'student_overrides',
        'subjects',
        'photos',
        'nfc_scanner',
        'nfc_registration',
    ]

    print("\n[RESET] Clearing tables...")
    for table in tables_to_clear:
        try:
            conn.execute(f"DELETE FROM {table}")
            print(f"  ✓ Cleared {table}")
        except Exception as e:
            print(f"  - Skipped {table}: {e}")

    # Clear all accounts
    conn.execute("DELETE FROM accounts")
    conn.execute("DELETE FROM users")
    print("  ✓ Cleared accounts / users")

    # Reset nfc_scanner state
    try:
        conn.execute("INSERT OR REPLACE INTO nfc_scanner (id,waiting,scanned_uid,requested_by,requested_at) VALUES (1,0,'','',?)", (now,))
        conn.execute("INSERT OR REPLACE INTO nfc_registration (id,waiting,scanned_uid,requested_by,requested_at) VALUES (1,0,'','',?)", (now,))
        print("  ✓ Reset nfc_scanner")
    except Exception as e:
        print(f"  - nfc_scanner reset failed: {e}")

    # Create super admin in both accounts and users tables
    conn.execute(
        "INSERT INTO accounts (username,password_hash,role,full_name,email,status,"
        "sections_json,my_subjects_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ADMIN_USERNAME, pw, 'admin', ADMIN_FULLNAME, '',
         'approved', '[]', '[]', now, now)
    )
    conn.execute(
        "INSERT INTO users (username,password,role,full_name,email,status,"
        "sections_json,my_subjects_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (ADMIN_USERNAME, pw, 'admin', ADMIN_FULLNAME, '',
         'approved', '[]', '[]', now)
    )

    conn.commit()
    conn.close()

    print(f"\n[DONE] Database reset complete.")
    print(f"\n  Super Admin Account:")
    print(f"  Username : {ADMIN_USERNAME}")
    print(f"  Password : {ADMIN_PASSWORD}")
    print(f"\n  Start Hardhat and Flask, then log in with these credentials.\n")

if __name__ == '__main__':
    reset()