"""
DAVS — Full System Reset
=========================
Fixes the root cause of students reappearing after reset:

  ROOT CAUSE: get_all_students() in app.py reads StudentRegistered events
  directly from the Hardhat blockchain on every Flask startup. Clearing
    PostgreSQL cleanup alone does nothing — the blockchain still has all the registrations
  and app.py repopulates the students table automatically on next run.

  THE FIX: This script deletes the attendance-contract.json file after
    clearing PostgreSQL data. Without it, app.py keeps reading historical
    blockchain registrations. On next deploy you restore it.
  Alternatively use --keep-contract to skip that step if you want to redeploy
  the contract yourself via Hardhat.

Usage:
    python reset_db.py              — interactive, prompts for confirmation
    python reset_db.py --yes        — skip confirmation (for automation)
    python reset_db.py --keep-contract  — clear DB but don't touch contract

WARNING: Permanently deletes ALL data. Cannot be undone.
"""

import hashlib, os, sys, shutil
from datetime import datetime
from dotenv import load_dotenv
from services.ops.db_compat import connect_db

# ── Load environment ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/davs').strip()

# Handle Railway/Heroku postgres:// prefix
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

DB_BACKEND = 'postgres'
CONTRACT_FILE  = os.path.join(BASE_DIR, 'attendance-contract.json')
UPLOAD_FOLDER  = os.path.join(BASE_DIR, 'static', 'uploads')

ADMIN_USERNAME = 'superadmin'
ADMIN_PASSWORD = 'admin123'
ADMIN_FULLNAME = 'Super Administrator'
ADMIN_ROLE    = 'super_admin'

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}")
def sep():     print("  " + "─" * 50)


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=?",
        (table_name,),
    ).fetchone()
    return bool(row and row[0])

# ── STEP 1: Verify DB exists ──────────────────────────────────────────────────
def check_db():
    try:
        with connect_db(DATABASE_URL) as conn:
            conn.execute("SELECT 1")
        ok(f"Connected to {DB_BACKEND}")
    except Exception as e:
        err(f"Could not connect to {DB_BACKEND}: {e}")
        print("  Set DATABASE_URL in .env, then re-run this script.")
        sys.exit(1)

# ── STEP 2: Clear all PostgreSQL tables ──────────────────────────────────────
def reset_postgres():
    print("\n  Clearing database tables...")
    sep()

    conn = connect_db(DATABASE_URL)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pw  = hash_password(ADMIN_PASSWORD)

    # ── Wipe all data tables ──────────────────────────────────────────────────
    data_tables = [
        'attendance_logs',
        'sessions',
        'students',
        'student_overrides',
        'subjects',
        'photos',
        'accounts',
        'users',
        'schedules',
        'event_schedules',
        'no_class_days',
        'excuse_requests',
    ]
    for table in data_tables:
        try:
            # Check if table exists first
            exists = _table_exists(conn, table)
            if not exists:
                warn(f"Table not found, skipping: {table}")
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.execute(f"DELETE FROM {table}")
            ok(f"Cleared {table:<22} ({count} rows deleted)")
        except Exception as e:
            warn(f"Could not clear {table}: {e}")

    # ── Reset NFC scanner rows (must keep id=1) ───────────────────────────────
    for table in ['nfc_scanner', 'nfc_registration']:
        try:
            exists = _table_exists(conn, table)
            if not exists:
                warn(f"Table not found, skipping: {table}")
                continue
            conn.execute(f"DELETE FROM {table}")
            conn.execute(
                f"INSERT INTO {table} "
                f"(id, waiting, scanned_uid, requested_by, requested_at) "
                f"VALUES (1, 0, '', '', ?)",
                (now,)
            )
            ok(f"Reset    {table:<22} (id=1 row restored)")
        except Exception as e:
            warn(f"Could not reset {table}: {e}")

    # ── Recreate super admin in accounts ─────────────────────────────────────
    try:
        conn.execute(
            "INSERT INTO accounts "
            "(username, password_hash, role, full_name, email, status, "
            " sections_json, my_subjects_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ADMIN_USERNAME, pw, ADMIN_ROLE, ADMIN_FULLNAME,
             '', 'approved', '[]', '[]', now, now)
        )
        ok(f"Created  accounts.superadmin  ({ADMIN_USERNAME} / {ADMIN_PASSWORD})")
    except Exception as e:
        err(f"Failed to create super admin in accounts: {e}")

    # ── Mirror into legacy users table ───────────────────────────────────────
    try:
        conn.execute(
            "INSERT INTO users "
            "(username, password, role, full_name, email, status, "
            " sections_json, my_subjects_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ADMIN_USERNAME, pw, ADMIN_ROLE, ADMIN_FULLNAME,
             '', 'approved', '[]', '[]', now)
        )
        ok(f"Mirrored users.superadmin (legacy table)")
    except Exception as e:
        warn(f"Legacy users table skipped: {e}")

    conn.commit()
    conn.close()

# ── STEP 3: Clear uploaded photos ────────────────────────────────────────────
def reset_uploads():
    print("\n  Clearing uploaded photos...")
    sep()
    if not os.path.exists(UPLOAD_FOLDER):
        warn(f"Uploads folder not found: {UPLOAD_FOLDER}")
        return
    removed = 0
    failed  = 0
    for fname in os.listdir(UPLOAD_FOLDER):
        fpath = os.path.join(UPLOAD_FOLDER, fname)
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                removed += 1
            except Exception as e:
                warn(f"Could not delete {fname}: {e}")
                failed += 1
    ok(f"Deleted {removed} photo file(s)  ({failed} failed)")

# ── STEP 4: Remove contract file (THE KEY FIX) ───────────────────────────────
def reset_contract():
    """
    This is the fix that actually stops students from reappearing.

    app.py does this on startup:
        contract = web3.eth.contract(address=..., abi=...)

    And get_all_students() does this on every call:
        ef = contract.events.StudentRegistered.create_filter(from_block=0, ...)
        entries = ef.get_all_entries()   # ← reads ALL past blockchain events
        ...
        db_save_student(s)               # ← repopulates PostgreSQL automatically

    By removing attendance-contract.json, app.py sets contract=None and
    get_all_students() no longer reloads historical student identity events.
    """
    print("\n  Resetting blockchain contract reference...")
    sep()

    if not os.path.exists(CONTRACT_FILE):
        warn("attendance-contract.json not found — already in offline mode")
        return

    # Back up the file before removing it
    backup_path = CONTRACT_FILE + '.reset_backup'
    try:
        shutil.copy2(CONTRACT_FILE, backup_path)
        ok(f"Backed up → attendance-contract.json.reset_backup")
    except Exception as e:
        warn(f"Could not create backup: {e}")

    try:
        os.remove(CONTRACT_FILE)
        ok("Removed  attendance-contract.json")
        print()
        print("  ┌─────────────────────────────────────────────────────┐")
        print("  │  BLOCKCHAIN IS NOW IN OFFLINE / RESET MODE          │")
        print("  │                                                     │")
        print("  │  Students will no longer reappear on Flask restart. │")
        print("  │                                                     │")
        print("  │  To restore blockchain mode:                        │")
        print("  │    1. Stop Flask                                    │")
        print("  │    2. npx hardhat run scripts/deploy.js             │")
        print("  │           --network sepolia                         │")
        print("  │    3. python app.py                                 │")
        print("  │                                                     │")
        print("  │  Or to restore your backup without redeploying:    │")
        print("  │    rename attendance-contract.json.reset_backup     │")
        print("  │    back to   attendance-contract.json               │")
        print("  └─────────────────────────────────────────────────────┘")
    except Exception as e:
        err(f"Could not remove attendance-contract.json: {e}")

# ── STEP 5: Verify the reset worked ──────────────────────────────────────────
def verify_reset():
    print("\n  Verifying reset...")
    sep()
    conn = connect_db(DATABASE_URL)

    checks = [
        ('students',         'SELECT COUNT(*) FROM students'),
        ('sessions',         'SELECT COUNT(*) FROM sessions'),
        ('attendance_logs',  'SELECT COUNT(*) FROM attendance_logs'),
        ('subjects',         'SELECT COUNT(*) FROM subjects'),
        ('schedules',        'SELECT COUNT(*) FROM schedules'),
        ('event_schedules',  'SELECT COUNT(*) FROM event_schedules'),
        ('no_class_days',    'SELECT COUNT(*) FROM no_class_days'),
        ('photos',           'SELECT COUNT(*) FROM photos'),
        ('accounts',         'SELECT COUNT(*) FROM accounts'),
    ]
    all_ok = True
    for label, sql in checks:
        try:
            count = conn.execute(sql).fetchone()[0]
            expected = 1 if label == 'accounts' else 0
            status = "✓" if count == expected else "✗"
            if count != expected:
                all_ok = False
            print(f"    {status}  {label:<20} {count} row(s)")
        except Exception as e:
            warn(f"Could not verify {label}: {e}")
            all_ok = False

    conn.close()
    print()
    if all_ok:
        ok("Verification passed — database is clean")
    else:
        warn("Some tables may not be fully cleared — check output above")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    auto_yes      = '--yes'            in sys.argv
    keep_contract = '--keep-contract'  in sys.argv

    print()
    print("  ══════════════════════════════════════════════════════")
    print("   DAVS — Full System Reset")
    print("  ══════════════════════════════════════════════════════")
    print()

    check_db()

    if not auto_yes:
        print("""
  ⚠  This will permanently delete:
    • All students (PostgreSQL + blockchain contract reference)
       • All classroom sessions and attendance logs
       • All teacher/admin accounts
       • All subjects and uploaded photos

  Only the super admin (superadmin / admin123) will remain.
  Students will NOT reappear after Flask restart.
""")
        answer = input("  Type  YES  to confirm: ").strip()
        if answer != 'YES':
            print("\n  Cancelled. Nothing was changed.\n")
            sys.exit(0)

    # Run all reset steps
    reset_postgres()
    reset_uploads()

    if not keep_contract:
        reset_contract()
    else:
        print("\n  Skipping contract reset (--keep-contract flag set)")
        warn("Students may reappear if Hardhat is running with old registrations")

    verify_reset()

    print()
    print("  ══════════════════════════════════════════════════════")
    print("   RESET COMPLETE")
    print("  ══════════════════════════════════════════════════════")
    print()
    print(f"   Login:    {ADMIN_USERNAME}  /  {ADMIN_PASSWORD}  (role: super_admin)")
    print()
    print("   Next steps:")
    print("   1.  python app.py               ← restart Flask")
    print("   2.  Log in as admin")
    print("   3.  Enroll students fresh via /register")
    print()
    if not keep_contract:
        print("   To re-enable blockchain after fresh deploy:")
        print("   1.  npx hardhat run scripts/deploy.js --network sepolia")
        print("   2.  python app.py")
        print()

if __name__ == '__main__':
    main()