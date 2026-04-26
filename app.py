from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session, send_from_directory
from web3 import Web3
from datetime import datetime
from functools import wraps
from threading import Thread, Lock
import json, os, secrets, time, hashlib, uuid, re
from collections import deque
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename
import secrets as _sec
import psycopg2, socket

from dotenv import load_dotenv
# pdfminer is imported inside parse_registration_pdf() so a startup
# import glitch can never permanently disable PDF parsing for the session.

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'davs-super-secret-2024')
APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'Asia/Manila')


def _now_local():
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE)).replace(tzinfo=None)
    except Exception:
        return _now_local()


# ── Jinja2 custom filters ─────────────────────────────────────────────────────
import json as _json_mod
from services.cvsu_parsing import (
    _extract_cvsu_fields,
    _generate_cvsu_email,
    _parse_cvsu_pdf_text,
    _surname_sort_key,
    normalize_course_name,
)
from services.attendance_email_templates import (
    send_student_attendance_receipt as _send_student_attendance_receipt_template,
    send_teacher_session_summary as _send_teacher_session_summary_template,
)
from services.attendance_view_routes_service import (
    attendance_report_impl as _attendance_report_impl,
    view_attendance_impl as _view_attendance_impl,
)
from services.admin_user_update_service import (
    update_faculty_impl as _update_faculty_impl,
    update_student_impl as _update_student_impl,
)
from services.admin_schedule_routes_service import (
    admin_schedule_create_impl as _admin_schedule_create_impl,
    admin_schedule_delete_impl as _admin_schedule_delete_impl,
    admin_schedule_edit_impl as _admin_schedule_edit_impl,
    admin_schedules_page_impl as _admin_schedules_page_impl,
    api_active_sessions_info_impl as _api_active_sessions_info_impl,
    api_schedules_search_impl as _api_schedules_search_impl,
    api_schedules_today_impl as _api_schedules_today_impl,
)
from services.attendance_stats_service import attendance_stats_impl as _attendance_stats_impl
from services.email_service import (
    get_email_config as _get_email_config_service,
    save_email_config as _save_email_config_service,
    send_email_async as _send_email_async_service,
)
from services.excuse_email_templates import (
    send_excuse_received_email as _send_excuse_received_email_template,
    send_excuse_resolved_email as _send_excuse_resolved_email_template,
)
from services.welcome_email_templates import (
    send_password_changed_success_email as _send_password_changed_success_email_template,
    send_staff_welcome_email as _send_staff_welcome_email_template,
    send_student_welcome_email as _send_student_welcome_email_template,
)
from services.excel_helpers import xl_helpers as _xl_helpers
from services.export_attendance_routes import (
    export_session_attendance_impl as _export_session_attendance_impl,
    export_student_sessions_impl as _export_student_sessions_impl,
)
from services.export_basic_csv_routes import (
    export_csv_all_impl as _export_csv_all_impl,
    export_csv_single_impl as _export_csv_single_impl,
    teacher_export_section_csv_impl as _teacher_export_section_csv_impl,
)
from services.export_stats_csv_service import export_stats_csv_impl as _export_stats_csv_impl
from services.export_stats_data import build_stats_export_dataset as _build_stats_export_dataset
from services.export_stats_xlsx_service import export_stats_xlsx_impl as _export_stats_xlsx_impl
from services.dashboard_page_service import dashboard_page_impl as _dashboard_page_impl
from services.profile_api_service import api_my_profile_impl as _api_my_profile_impl
from services.profile_routes_service import (
    delete_photo_impl as _delete_photo_impl,
    get_my_photo_impl as _get_my_photo_impl,
    update_profile_impl as _update_profile_impl,
    upload_photo_impl as _upload_photo_impl,
)
from services.student_sessions_api_service import student_sessions_api_impl as _student_sessions_api_impl
from services.teacher_schedule_api_service import api_schedules_upcoming_impl as _api_schedules_upcoming_impl
from services.teacher_schedule_page_service import teacher_schedule_page_impl as _teacher_schedule_page_impl
from services.teacher_portal_routes_service import (
    admin_sessions_page_impl as _admin_sessions_page_impl,
    teacher_create_session_page_impl as _teacher_create_session_page_impl,
    teacher_dashboard_page_impl as _teacher_dashboard_page_impl,
    teacher_records_page_impl as _teacher_records_page_impl,
    teacher_sessions_students_page_impl as _teacher_sessions_students_page_impl,
)
from services.ops.migrate_db import migrate as _auto_migrate

AUTO_THREAD = None
AUTO_THREAD_LOCK = Lock()

PASSWORD_OTP_TTL_SECONDS = 600
PASSWORD_OTP_COOLDOWN_SECONDS = 60
PASSWORD_OTP_MAX_ATTEMPTS = 5

# ── Email config helpers ──────────────────────────────────────────────────
def get_email_config():
    """Load SMTP config from DB. Returns dict with all keys."""
    return _get_email_config_service(get_db)
 
def save_email_config(cfg: dict):
    """Upsert email config into DB."""
    _save_email_config_service(cfg, get_db)
 
def _send_email(to_addrs: list, subject: str, html_body: str):
    """
    Send an HTML email via Gmail SMTP in a background thread.
    Silently logs errors — never crashes the main request.
    """
    cfg = get_email_config()
    _send_email_async_service(to_addrs, subject, html_body, cfg)
 
def send_student_attendance_receipt(
        student_name, student_email, student_id,
        subject_name, section_key, teacher_name,
        tap_time, status, tx_hash, block_num,
        sess_id=None, nfc_id=None, semester=None, time_slot=None):
        """Send attendance receipt email to student."""
        _send_student_attendance_receipt_template(
                student_name=student_name,
                student_email=student_email,
                student_id=student_id,
                subject_name=subject_name,
                section_key=section_key,
                teacher_name=teacher_name,
                tap_time=tap_time,
                status=status,
                tx_hash=tx_hash,
                block_num=block_num,
                sess_id=sess_id,
                nfc_id=nfc_id,
                send_email_fn=_send_email,
                url_for_fn=url_for,
                semester=semester,
                time_slot=time_slot,
        )
 
def send_teacher_session_summary(
        teacher_email, teacher_name,
        subject_name, section_key, time_slot,
        started_at, ended_at,
        present_count, late_count, absent_count, excused_count,
        student_rows, session_tx_hash=None, session_block_number=None,
        course_code=None, semester=None):
        """Send session summary email to teacher when session ends."""
        _send_teacher_session_summary_template(
                teacher_email=teacher_email,
                teacher_name=teacher_name,
                subject_name=subject_name,
                section_key=section_key,
                time_slot=time_slot,
                started_at=started_at,
                ended_at=ended_at,
                present_count=present_count,
                late_count=late_count,
                absent_count=absent_count,
                excused_count=excused_count,
                student_rows=student_rows,
                session_tx_hash=session_tx_hash,
                session_block_number=session_block_number,
                send_email_fn=_send_email,
                course_code=course_code,
                semester=semester,
        )


def send_student_welcome_email(
    *,
    student_name,
    student_email,
    nfc_id,
    student_id='',
    course='',
    year_level='',
    section=''):
    """Send account-created welcome email to student."""
    _send_student_welcome_email_template(
        student_name=student_name,
        student_email=student_email,
        nfc_id=nfc_id,
        student_id=student_id,
        course=course,
        year_level=year_level,
        section=section,
        send_email_fn=_send_email,
    )


def send_staff_welcome_email(
    *,
    full_name,
    email,
    username,
    role,
    initial_password=''):
    """Send account-created welcome email to teacher/admin/staff."""
    _send_staff_welcome_email_template(
        full_name=full_name,
        email=email,
        username=username,
        role=role,
        initial_password=initial_password,
        login_url=request.url_root.rstrip('/') + url_for('login'),
        send_email_fn=_send_email,
    )


def send_password_changed_success_email(
    *,
    full_name,
    email,
    username,
    role):
    """Send confirmation email after successful password update."""
    _send_password_changed_success_email_template(
        full_name=full_name,
        email=email,
        username=username,
        role=role,
        send_email_fn=_send_email,
    )


def _mask_email(email: str) -> str:
    email = (email or '').strip()
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        local_masked = local[0] + '*' if local else '*'
    else:
        local_masked = local[0] + ('*' * (len(local) - 2)) + local[-1]
    return f"{local_masked}@{domain}"


def _password_otp_hash(code: str) -> str:
    return hashlib.sha256(f"{code}|{app.secret_key}".encode('utf-8')).hexdigest()


def _send_password_change_otp_email(*, full_name: str, email: str, otp_code: str):
    if not email or '@' not in email:
        return False, 'No valid email is registered on your profile.'

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:22px;border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;">
      <h2 style="margin:0 0 10px;color:#1e4a1a;">Password Change OTP</h2>
      <p style="margin:0 0 12px;color:#334155;">Hello {full_name or 'User'},</p>
      <p style="margin:0 0 14px;color:#334155;">Use this one-time code to continue your DAVS password change request:</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;text-align:center;">
        <p style="margin:0;font-size:28px;letter-spacing:6px;font-weight:700;color:#0f172a;">{otp_code}</p>
      </div>
      <p style="margin:12px 0 0;color:#b45309;font-size:13px;font-weight:700;">This code expires in 10 minutes and can only be used once.</p>
      <p style="margin:8px 0 0;color:#b91c1c;font-size:13px;font-weight:700;">If you did not request this, secure your account immediately and report it to your DAVS administrator.</p>
      <div style="margin-top:14px;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
        <p style="margin:0;color:#475569;font-size:12px;line-height:1.5;">
          Privacy and lawful use notice: DAVS account and attendance data are collected and processed only for legitimate academic attendance monitoring,
          verification, and school administrative purposes. Any unauthorized or illegal use of this information is strictly prohibited.
        </p>
      </div>
      <p style="margin:14px 0 0;color:#94a3b8;font-size:11px;">Cavite State University - DAVS System (Automated Message)</p>
    </div>
    """

    _send_email([email], '[DAVS] Password Change OTP Code', html)
    return True, ''


def request_password_change_otp_for_current_user():
    username = session.get('username', '')
    user = db_get_user(username)
    if not user:
        return False, 'Not logged in', 401

    email = (user.get('email') or '').strip()
    if '@' not in email:
        return False, 'Add a valid email in your profile before requesting OTP.', 400

    now = int(time.time())
    state = session.get('password_change_otp') or {}
    cooldown_until = int(state.get('cooldown_until') or 0)
    if cooldown_until > now:
        wait_seconds = cooldown_until - now
        return False, f'Please wait {wait_seconds}s before requesting a new OTP.', 429

    otp_code = f"{_sec.randbelow(1000000):06d}"
    session['password_change_otp'] = {
        'username': username,
        'code_hash': _password_otp_hash(otp_code),
        'expires_at': now + PASSWORD_OTP_TTL_SECONDS,
        'tries_left': PASSWORD_OTP_MAX_ATTEMPTS,
        'cooldown_until': now + PASSWORD_OTP_COOLDOWN_SECONDS,
    }
    session.modified = True

    sent, err = _send_password_change_otp_email(
        full_name=user.get('full_name', username),
        email=email,
        otp_code=otp_code,
    )
    if not sent:
        return False, err or 'Unable to send OTP email.', 500

    return True, _mask_email(email), 200


def validate_password_change_otp_for_current_user(otp_code: str):
    username = session.get('username', '')
    state = session.get('password_change_otp') or {}
    if not state or state.get('username') != username:
        return False, 'Request an OTP first.'

    now = int(time.time())
    expires_at = int(state.get('expires_at') or 0)
    if now > expires_at:
        session.pop('password_change_otp', None)
        session.modified = True
        return False, 'OTP expired. Please request a new code.'

    otp_code = (otp_code or '').strip()
    if not otp_code:
        return False, 'OTP is required to change password.'

    expected_hash = state.get('code_hash') or ''
    if not expected_hash or not _sec.compare_digest(_password_otp_hash(otp_code), expected_hash):
        tries_left = int(state.get('tries_left') or 0) - 1
        if tries_left <= 0:
            session.pop('password_change_otp', None)
            session.modified = True
            return False, 'OTP attempts exceeded. Request a new code.'
        state['tries_left'] = tries_left
        session['password_change_otp'] = state
        session.modified = True
        return False, f'Invalid OTP. {tries_left} attempt(s) left.'

    session.pop('password_change_otp', None)
    session.modified = True
    return True, ''

@app.context_processor
def inject_globals():
    return dict(
        photos_db     = db_get_all_photos(),
        pending_count = db_pending_count(),
        fmt_time      = fmt_time,
        fmt_time_short= fmt_time_short,
    )

BLOCKCHAIN_RPC_URL = (
    os.getenv('SEPOLIA_RPC_URL', '').strip()
    or os.getenv('BLOCKCHAIN_RPC_URL', '').strip()
    or os.getenv('WEB3_PROVIDER_URI', '').strip()
    or "http://127.0.0.1:8545"
)
web3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))

BLOCKCHAIN_ONLINE = web3.is_connected()
if BLOCKCHAIN_ONLINE:
    try:
        _cid = int(web3.eth.chain_id)
        if _cid == 11155111:
            print('[OK] Connected to Sepolia')
        elif _cid in (31337, 1337):
            print('[OK] Connected to local EVM node')
        else:
            print(f'[OK] Connected to chain {_cid}')
    except Exception:
        print('[OK] Connected to blockchain RPC')
else:
    print('[WARNING] Blockchain RPC unreachable — students will load from database cache.')

contract_data_path = os.path.join(os.path.dirname(__file__), 'attendance-contract.json')
ADMIN_PRIVATE_KEY = (os.getenv('ADMIN_PRIVATE_KEY') or os.getenv('PRIVATE_KEY') or '').strip().replace('"', '').replace("'", "")
if ADMIN_PRIVATE_KEY and not ADMIN_PRIVATE_KEY.startswith('0x'):
    if len(ADMIN_PRIVATE_KEY) == 64:
        ADMIN_PRIVATE_KEY = '0x' + ADMIN_PRIVATE_KEY

if not ADMIN_PRIVATE_KEY:
    print("[BLOCKCHAIN WARNING] No ADMIN_PRIVATE_KEY found. Transactions will fail.")

try:
    # Read address from .env
    contract_address = os.getenv('ATTENDANCE_CONTRACT_ADDRESS')
    if not contract_address:
        print("[BLOCKCHAIN ERROR] ATTENDANCE_CONTRACT_ADDRESS not found in .env")
        raise ValueError("ATTENDANCE_CONTRACT_ADDRESS not found in .env")
    
    # Read ABI from JSON file
    if not os.path.exists(contract_data_path):
        print(f"[BLOCKCHAIN ERROR] Contract ABI file not found at {contract_data_path}")
        raise FileNotFoundError(f"Contract ABI file not found at {contract_data_path}")
        
    with open(contract_data_path) as f:
        contract_data = json.load(f)
    
    if not contract_data.get('abi'):
        print("[BLOCKCHAIN ERROR] Invalid contract JSON: 'abi' field missing")
        raise KeyError("'abi' field missing in contract JSON")
        
    contract      = web3.eth.contract(address=contract_address, abi=contract_data['abi'])
    admin_account = None
    if BLOCKCHAIN_ONLINE:
        if ADMIN_PRIVATE_KEY:
            try:
                admin_account = web3.eth.account.from_key(ADMIN_PRIVATE_KEY).address
                print(f"[BLOCKCHAIN] Admin account loaded: {admin_account}")
            except Exception as e:
                print(f"[BLOCKCHAIN ERROR] Invalid ADMIN_PRIVATE_KEY: {e}")
                admin_account = None
        else:
            try:
                accounts = web3.eth.accounts
                admin_account = accounts[0] if accounts else None
                print(f"[BLOCKCHAIN] Using default node account: {admin_account}")
            except Exception as e:
                print(f"[BLOCKCHAIN ERROR] Could not get accounts from node: {e}")
                admin_account = None

except Exception as _ce:
    print(f"[WARNING] Blockchain system initialization failed: {_ce}")
    contract      = None
    admin_account = None
    BLOCKCHAIN_ONLINE = False
    print("[INFO] Offline mode active: contract/RPC unavailable.")

BLOCKCHAIN_LOCK = Lock()
BASE_DIR      = os.path.dirname(__file__)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

# Detect environment
IS_RAILWAY = os.getenv('RAILWAY_ENVIRONMENT_ID') is not None or os.getenv('RAILWAY_STATIC_URL') is not None
IS_PROD = IS_RAILWAY or os.getenv('NODE_ENV') == 'production'

# Handle Railway/Heroku postgres:// prefix
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Default to localhost ONLY if not in production/Railway
if not DATABASE_URL:
    if IS_RAILWAY:
        print("\n" + "!"*80)
        print("CRITICAL ERROR: DATABASE_URL is NOT set in Railway environment variables!")
        print("Please add a PostgreSQL service and link it to this project.")
        print("!"*80 + "\n")
    else:
        # Fallback for local development
        DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/davs'

DB_BACKEND = 'postgres'

# --- AUTO MIGRATION ---
# Moved to the end of the script (after init_db) to ensure base tables exist.
# ----------------------

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
UPLOAD_FOLDER_EXCUSES = os.path.join(BASE_DIR, 'static', 'uploads', 'excuses')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_EXCUSES, exist_ok=True)

ALLOWED_EXTENSIONS_EXCUSES = {'png', 'jpg', 'jpeg', 'pdf'}

EXCUSE_REASONS = [
    ('sickness', 'Sickness / Illness'),
    ('lbm', 'LBM'),
    ('emergency', 'Family Emergency'),
    ('bereavement', 'Bereavement'),
    ('medical', 'Medical Appointment'),
    ('accident', 'Accident / Injury'),
    ('official', 'Official School Business'),
    ('weather', 'Extreme Weather / Calamity'),
    ('transport', 'Transportation Problem'),
    ('others', 'Others')
]

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def normalize_semester(sem):
    if not sem: return ""
    s = str(sem).strip().upper()
    if 'FIRST' in s or '1ST' in s: return 'First'
    if 'SECOND' in s or '2ND' in s: return 'Second'
    if 'SUMMER' in s: return 'Summer'
    return s.title()


def _canonical_role(role_value):
    role_norm = (role_value or '').strip().lower().replace(' ', '_')
    if role_norm in ('superadmin', 'super_admin'):
        return 'super_admin'
    if role_norm in ('admin', 'administrator'):
        return 'admin'
    if role_norm in ('teacher', 'instructor', 'faculty'):
        return 'teacher'
    return role_norm or 'teacher'

def normalize_section_key(key):
    """
    Returns a canonical section key: 'Course|Year|Section'
    Example: 'BSIT|1|A' -> 'BS Information Technology|1st Year|A'
    Handles both '|' and '-' as separators.
    """
    if not key:
        return ""
        
    # Standardize separator
    key = str(key).replace('-', '|')
    parts = [p.strip() for p in key.split('|')]
    
    if len(parts) >= 3:
        course = parts[0]
        year = parts[1]
        section = parts[2].upper()
        
        # Normalize course
        course_canonical = normalize_course_name(course)
        
        # Normalize year level
        year_map = {
            '1': '1st Year', '2': '2nd Year', '3': '3rd Year', '4': '4th Year', '5': '5th Year',
            '1st': '1st Year', '2nd': '2nd Year', '3rd': '3rd Year', '4th': '4th Year',
            '1st year': '1st Year', '2nd year': '2nd Year', '3rd year': '3rd Year',
            '4th year': '4th Year', '5th year': '5th Year',
        }
        year_normalized = year_map.get(year.lower(), year)
        
        return f"{course_canonical}|{year_normalized}|{section}"
        
    return key.strip()

def build_student_section_key(student):
    # Use 'course' (from _student_row) or original 'program' column
    course = (student.get('course') or student.get('program') or '').strip()
    year_level = (student.get('year_level') or '').strip()
    section = (student.get('section') or '').strip().upper()
    if not course or not year_level or not section:
        return None
    return normalize_section_key(f"{course}|{year_level}|{section}")


def generate_cvsu_email(name, provided_email=''):
    """
    Generate CVSU email pattern: sc.firstname.lastname@cvsu.edu.ph
    If provided_email is given and not empty, return it.
    Otherwise, generate from name.
    """
    provided_email = provided_email.strip()
    if provided_email:
        return provided_email

    clean = re.sub(r'\b[A-Za-z]\.\s*', '', name).strip()
    clean = re.sub(r'\b(JR|SR|II|III|IV)\.?\b', '', clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\s+', ' ', clean)
    words = clean.split()
    if len(words) >= 2:
        first_slug = ''.join(re.sub(r'[^a-z]', '', w.lower()) for w in words[:-1])
        last_slug = re.sub(r'[^a-z]', '', words[-1].lower())
        if first_slug and last_slug:
            return f'sc.{first_slug}.{last_slug}@cvsu.edu.ph'
    return ''


class _PgRowCompat(dict):
    """
    psycopg RealDictRow compatibility shim that supports both:
    - mapping access: row['name']
    - positional access: row[0], row[1]
    """
    def __getitem__(self, key):
        if isinstance(key, int):
            values = list(self.values())
            return values[key]
        return super().__getitem__(key)


class _PgCursorCompat:
    def __init__(self, cursor):
        self._cursor = cursor

    @staticmethod
    def _wrap_row(row):
        if row is None:
            return None
        if isinstance(row, dict):
            return _PgRowCompat(row)
        return row

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        return [self._wrap_row(r) for r in self._cursor.fetchall()]

    @property
    def lastrowid(self):
        try:
            return self._cursor.lastrowid
        except Exception:
            return None

    def __iter__(self):
        for row in self._cursor:
            yield self._wrap_row(row)


class _PgConnCompat:
    def __init__(self, conn):
        self._conn = conn

    def _convert_sql(self, sql: str):
        s = sql
        s = re.sub(
            r"\bid\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
            "id BIGSERIAL PRIMARY KEY",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(r"\bPRAGMA\s+journal_mode\s*=\s*WAL\b", "SELECT 1", s, flags=re.IGNORECASE)
        s = re.sub(r"\bPRAGMA\s+foreign_keys\s*=\s*ON\b", "SELECT 1", s, flags=re.IGNORECASE)
        s = re.sub(
            r"PRAGMA\s+table_info\((\w+)\)",
            r"SELECT column_name AS name FROM information_schema.columns WHERE table_schema='public' AND table_name='\1' ORDER BY ordinal_position",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r"SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type='table'",
            "SELECT table_name AS name FROM information_schema.tables WHERE table_schema='public'",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(r"\browid\b", "id", s, flags=re.IGNORECASE)
        s = s.replace("AUTOINCREMENT", "")
        if re.search(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", s, flags=re.IGNORECASE):
            s = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", "INSERT INTO ", s, flags=re.IGNORECASE)
            s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        if re.search(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+nfc_scanner\s+", s, flags=re.IGNORECASE):
            s = re.sub(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+", "INSERT INTO ", s, flags=re.IGNORECASE)
            s = s.rstrip().rstrip(";") + (
                " ON CONFLICT (id) DO UPDATE SET "
                "waiting=EXCLUDED.waiting, scanned_uid=EXCLUDED.scanned_uid, "
                "requested_by=EXCLUDED.requested_by, requested_at=EXCLUDED.requested_at"
            )
        return s.replace("?", "%s")

    def execute(self, sql, params=()):
        converted = self._convert_sql(sql)
        from psycopg2.extras import RealDictCursor  # pyright: ignore[reportMissingModuleSource]
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(converted, params or ())
        return _PgCursorCompat(cur)

    def executescript(self, script):
        statements = [s.strip() for s in script.split(";") if s.strip()]
        for statement in statements:
            self.execute(statement)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()


def get_db():
    class _CompatRow(dict):
        def __init__(self, keys, values):
            super().__init__(zip(keys, values))
            self._keys = list(keys)
            self._values = list(values)

        def __getitem__(self, key):
            if isinstance(key, int):
                return self._values[key]
            return super().__getitem__(key)

    class _CompatCursor:
        def __init__(self, cursor):
            self._cursor = cursor
            self._keys = []

        def _rewrite_insert_or_replace(self, stmt):
            match = re.match(
                r'^INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*;?$',
                stmt,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not match:
                return None

            table_name = match.group(1)
            columns = [column.strip().strip('"') for column in match.group(2).split(',')]
            values_clause = match.group(3).strip()
            conflict_column = 'id' if 'id' in columns else columns[0]
            update_columns = [column for column in columns if column != conflict_column]

            if update_columns:
                updates = ', '.join(f'{column}=EXCLUDED.{column}' for column in update_columns)
                return (
                    f'INSERT INTO {table_name} ({", ".join(columns)}) '
                    f'VALUES ({values_clause}) '
                    f'ON CONFLICT ({conflict_column}) DO UPDATE SET {updates}'
                )

            return (
                f'INSERT INTO {table_name} ({", ".join(columns)}) '
                f'VALUES ({values_clause}) '
                f'ON CONFLICT ({conflict_column}) DO NOTHING'
            )

        def _rewrite_sql(self, sql):
            stmt = (sql or '').strip()
            if not stmt:
                return stmt, None

            up = stmt.upper()
            if up.startswith('PRAGMA JOURNAL_MODE') or up.startswith('PRAGMA FOREIGN_KEYS'):
                return None, []

            m = re.match(r'^PRAGMA\s+TABLE_INFO\(([^\)]+)\)\s*$', stmt, flags=re.IGNORECASE)
            if m:
                table_name = m.group(1).strip().strip('"\'')
                qry = (
                    "SELECT (ordinal_position - 1) AS cid, "
                    "column_name AS name, data_type AS type, "
                    "0 AS notnull, column_default AS dflt_value, 0 AS pk "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s "
                    "ORDER BY ordinal_position"
                )
                return qry, (table_name,)

            if "FROM SQLITE_MASTER" in up:
                return (
                    "SELECT table_name AS name "
                    "FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE'"
                ), None

            stmt = re.sub(
                r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                'BIGSERIAL PRIMARY KEY',
                stmt,
                flags=re.IGNORECASE,
            )
            if re.search(r'INSERT\s+OR\s+REPLACE\s+INTO', stmt, flags=re.IGNORECASE):
                rewritten = self._rewrite_insert_or_replace(stmt)
                if rewritten:
                    stmt = rewritten
                else:
                    stmt = re.sub(r'INSERT\s+OR\s+REPLACE\s+INTO', 'INSERT INTO', stmt, flags=re.IGNORECASE)
            if re.search(r'INSERT\s+OR\s+IGNORE\s+INTO', stmt, flags=re.IGNORECASE):
                stmt = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', stmt, flags=re.IGNORECASE)
                if 'ON CONFLICT' not in stmt.upper():
                    stmt = stmt.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'

            # Handle GLOB (SQLite specific) -> replace with ~ (PostgreSQL regex)
            # Example: GLOB '[0-9]*' -> ~ '^[0-9].*'
            if ' GLOB ' in up:
                stmt = re.sub(r"GLOB\s+'\[([^\]]+)\]\*'", r"~ '^[\1].*'", stmt, flags=re.IGNORECASE)
                stmt = stmt.replace(' GLOB ', ' ~ ')

            # For PostgreSQL, append RETURNING id to INSERT statements to emulate lastrowid
            # Only for tables that actually use 'id' as their primary key
            id_tables = ['no_class_days', 'attendance_logs', 'excuse_requests', 'nfc_scanner', 'nfc_registration']
            if up.startswith('INSERT INTO') and 'RETURNING' not in up:
                target_table = None
                for t in id_tables:
                    if t.upper() in up:
                        target_table = t
                        break
                
                if target_table:
                    stmt = stmt.rstrip().rstrip(';') + ' RETURNING id'

            stmt = stmt.replace('?', '%s')
            return stmt, None

        def execute(self, sql, params=None):
            rewritten, forced_params = self._rewrite_sql(sql)
            if rewritten is None:
                self._keys = []
                self._empty = forced_params or []
                return self

            run_params = forced_params if forced_params is not None else params
            if run_params is None:
                self._cursor.execute(rewritten)
            else:
                self._cursor.execute(rewritten, run_params)
            self._keys = [d[0] for d in self._cursor.description] if self._cursor.description else []
            self._empty = None
            return self

        def executemany(self, sql, seq_of_params):
            rewritten, forced_params = self._rewrite_sql(sql)
            if rewritten is None:
                self._keys = []
                self._empty = []
                return self
            if forced_params is not None:
                raise RuntimeError('Forced SQL params are not supported with executemany')
            self._cursor.executemany(rewritten, seq_of_params)
            self._keys = [d[0] for d in self._cursor.description] if self._cursor.description else []
            self._empty = None
            return self

        def fetchone(self):
            if self._empty is not None:
                return None
            row = self._cursor.fetchone()
            if row is None:
                return None
            return _CompatRow(self._keys, row)

        def fetchall(self):
            if self._empty is not None:
                return []
            rows = self._cursor.fetchall()
            return [_CompatRow(self._keys, r) for r in rows]

        @property
        def rowcount(self):
            return self._cursor.rowcount

        @property
        def lastrowid(self):
            """Emulate SQLite's lastrowid for PostgreSQL via the underlying cursor."""
            try:
                # If we appended RETURNING id, it's available via fetchone
                # Note: This row was already fetched if execute() called it, 
                # but psycopg2 cursors don't cache fetch results like that.
                # Actually, our execute() doesn't fetch it yet.
                row = self._cursor.fetchone()
                return row[0] if row else None
            except Exception:
                return None

        @property
        def description(self):
            return self._cursor.description

        def close(self):
            self._cursor.close()

    class _CompatConnection:
        def __init__(self, dsn):
            self._conn = psycopg2.connect(dsn)
            self.row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                if exc_type is None:
                    self._conn.commit()
                else:
                    self._conn.rollback()
            finally:
                self._conn.close()

        def cursor(self):
            return _CompatCursor(self._conn.cursor())

        def execute(self, sql, params=None):
            cur = self.cursor()
            return cur.execute(sql, params)

        def executemany(self, sql, seq_of_params):
            cur = self.cursor()
            return cur.executemany(sql, seq_of_params)

        def executescript(self, sql_script):
            for part in [p.strip() for p in (sql_script or '').split(';') if p.strip()]:
                self.execute(part)

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close(self):
            self._conn.close()

    return _CompatConnection(DATABASE_URL)



def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS accounts (
        username        TEXT PRIMARY KEY,
        password_hash   TEXT NOT NULL,
        role            TEXT NOT NULL DEFAULT 'teacher',
        full_name       TEXT NOT NULL DEFAULT '',
        email           TEXT NOT NULL DEFAULT '',
        status          TEXT NOT NULL DEFAULT 'pending',
        sections_json   TEXT NOT NULL DEFAULT '[]',
        my_subjects_json TEXT NOT NULL DEFAULT '[]',
        created_at      TEXT NOT NULL DEFAULT '',
        updated_at      TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS subjects (
        subject_id  TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        course_code TEXT NOT NULL DEFAULT '',
        units       TEXT NOT NULL DEFAULT '3',
        created_by  TEXT NOT NULL DEFAULT '',
        created_at  TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_subj_code ON subjects(course_code);
    CREATE TABLE IF NOT EXISTS students (
        nfc_id          TEXT PRIMARY KEY,
        full_name       TEXT NOT NULL DEFAULT '',
        student_id      TEXT NOT NULL DEFAULT '',
        program         TEXT NOT NULL DEFAULT '',
        year_level      TEXT NOT NULL DEFAULT '',
        section         TEXT NOT NULL DEFAULT '',
        adviser         TEXT NOT NULL DEFAULT '',
        email           TEXT NOT NULL DEFAULT '',
        contact         TEXT NOT NULL DEFAULT '',
        major           TEXT NOT NULL DEFAULT '',
        semester        TEXT NOT NULL DEFAULT '',
        school_year     TEXT NOT NULL DEFAULT '',
        date_registered TEXT NOT NULL DEFAULT '',
        raw_name        TEXT NOT NULL DEFAULT '',
        eth_address     TEXT NOT NULL DEFAULT '',
        reg_tx_hash     TEXT NOT NULL DEFAULT '',
        reg_block       INTEGER NOT NULL DEFAULT 0,
        photo_file      TEXT NOT NULL DEFAULT '',
        created_at      TEXT NOT NULL DEFAULT '',
        updated_at      TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS sessions (
            sess_id         TEXT PRIMARY KEY,
            subject_id      TEXT NOT NULL DEFAULT '',
            subject_name    TEXT NOT NULL DEFAULT '',
            course_code     TEXT NOT NULL DEFAULT '',
            class_type      TEXT NOT NULL DEFAULT 'lecture',
            units           INTEGER NOT NULL DEFAULT 3,
            time_slot       TEXT NOT NULL DEFAULT '',
            section_key     TEXT NOT NULL DEFAULT '',
            teacher_username TEXT NOT NULL DEFAULT '',
            teacher_name    TEXT NOT NULL DEFAULT '',
            started_at      TEXT NOT NULL DEFAULT '',
            late_cutoff     TEXT NOT NULL DEFAULT '',
            auto_end_at     TEXT,
            ended_at        TEXT,
            grace_period    INTEGER NOT NULL DEFAULT 15,
            schedule_id     TEXT DEFAULT NULL,
            total_enrolled  INTEGER NOT NULL DEFAULT 0,
            total_present   INTEGER NOT NULL DEFAULT 0,
            total_late      INTEGER NOT NULL DEFAULT 0,
            total_absent    INTEGER NOT NULL DEFAULT 0,
            total_excused   INTEGER NOT NULL DEFAULT 0,
            warn_log_json   TEXT NOT NULL DEFAULT '[]',
            invalid_log_json TEXT NOT NULL DEFAULT '[]',
            semester        TEXT NOT NULL DEFAULT '1st Semester',
            session_tx_hash TEXT NOT NULL DEFAULT '',
            session_block_number INTEGER NOT NULL DEFAULT 0
        );
    CREATE INDEX IF NOT EXISTS idx_sess_ended   ON sessions(ended_at);
    CREATE INDEX IF NOT EXISTS idx_sess_section ON sessions(section_key);
    CREATE TABLE IF NOT EXISTS attendance_logs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        sess_id      TEXT NOT NULL,
        nfc_id       TEXT NOT NULL,
        student_name TEXT NOT NULL DEFAULT '',
        student_id   TEXT NOT NULL DEFAULT '',
        status       TEXT NOT NULL DEFAULT 'absent',
        class_type   TEXT NOT NULL DEFAULT 'lecture',
        tap_time     TEXT NOT NULL DEFAULT '',
        tx_hash      TEXT NOT NULL DEFAULT '',
        block_number INTEGER NOT NULL DEFAULT 0,
        excuse_note  TEXT NOT NULL DEFAULT '',
        created_at   TEXT NOT NULL DEFAULT '',
        UNIQUE(sess_id, nfc_id)
    );
    CREATE INDEX IF NOT EXISTS idx_att_sess  ON attendance_logs(sess_id);
    CREATE INDEX IF NOT EXISTS idx_att_nfc   ON attendance_logs(nfc_id);
    CREATE INDEX IF NOT EXISTS idx_att_status ON attendance_logs(status);
    CREATE TABLE IF NOT EXISTS photos (
        person_id   TEXT PRIMARY KEY,
        filename    TEXT NOT NULL,
        uploaded_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS nfc_scanner (
        id           INTEGER PRIMARY KEY CHECK (id = 1),
        waiting      INTEGER NOT NULL DEFAULT 0,
        scanned_uid  TEXT NOT NULL DEFAULT '',
        requested_by TEXT NOT NULL DEFAULT '',
        requested_at TEXT NOT NULL DEFAULT ''
    );
    INSERT OR IGNORE INTO nfc_scanner (id, waiting, scanned_uid) VALUES (1, 0, '');
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'teacher', full_name TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
        sections_json TEXT NOT NULL DEFAULT '[]',
        my_subjects_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS nfc_registration (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        waiting INTEGER NOT NULL DEFAULT 0,
        scanned_uid TEXT NOT NULL DEFAULT '',
        requested_by TEXT NOT NULL DEFAULT '',
        requested_at TEXT NOT NULL DEFAULT ''
    );
    INSERT OR IGNORE INTO nfc_registration (id, waiting, scanned_uid) VALUES (1, 0, '');
    CREATE TABLE IF NOT EXISTS student_overrides (
        nfc_id TEXT PRIMARY KEY, full_name TEXT DEFAULT '',
        student_id TEXT DEFAULT '', email TEXT DEFAULT '',
        contact TEXT DEFAULT '', adviser TEXT DEFAULT '',
        major TEXT DEFAULT '', semester TEXT DEFAULT '',
        school_year TEXT DEFAULT '', date_registered TEXT DEFAULT '',
        course TEXT DEFAULT '', year_level TEXT DEFAULT '',
        section TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS email_config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS schedules (
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
        class_type       TEXT NOT NULL DEFAULT 'lecture',
        grace_minutes    INTEGER NOT NULL DEFAULT 15,
        is_active        INTEGER NOT NULL DEFAULT 1,
        created_by       TEXT NOT NULL DEFAULT '',
        created_at       TEXT NOT NULL DEFAULT '',
        updated_at       TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_sched_teacher ON schedules(teacher_username);
    CREATE INDEX IF NOT EXISTS idx_sched_day     ON schedules(day_of_week);
    CREATE TABLE IF NOT EXISTS event_schedules (
        event_id             TEXT PRIMARY KEY,
        title                TEXT NOT NULL DEFAULT '',
        description          TEXT NOT NULL DEFAULT '',
        teacher_usernames_json TEXT NOT NULL DEFAULT '[]',
        section_keys_json    TEXT NOT NULL DEFAULT '[]',
        start_at             TEXT NOT NULL DEFAULT '',
        end_at               TEXT NOT NULL DEFAULT '',
        is_active            INTEGER NOT NULL DEFAULT 1,
        created_by           TEXT NOT NULL DEFAULT '',
        created_at           TEXT NOT NULL DEFAULT '',
        updated_at           TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_event_sched_start ON event_schedules(start_at);
    CREATE INDEX IF NOT EXISTS idx_event_sched_active ON event_schedules(is_active);
    CREATE TABLE IF NOT EXISTS no_class_days (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT NOT NULL DEFAULT '',
        description         TEXT NOT NULL DEFAULT '',
        from_date           TEXT NOT NULL DEFAULT '',
        to_date             TEXT NOT NULL DEFAULT '',
        teacher_usernames_json TEXT NOT NULL DEFAULT '[]',
        apply_all_teachers  INTEGER NOT NULL DEFAULT 0,
        is_active           INTEGER NOT NULL DEFAULT 1,
        created_by          TEXT NOT NULL DEFAULT '',
        created_at          TEXT NOT NULL DEFAULT '',
        updated_at          TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_no_class_days_range ON no_class_days(from_date, to_date);
    CREATE INDEX IF NOT EXISTS idx_no_class_days_active ON no_class_days(is_active);
    CREATE TABLE IF NOT EXISTS excuse_requests (
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
    );
    CREATE INDEX IF NOT EXISTS idx_excuse_sess   ON excuse_requests(sess_id);
    CREATE INDEX IF NOT EXISTS idx_excuse_status ON excuse_requests(status);
    """
    with get_db() as conn:
        conn.executescript(sql)
    _migrate_add_missing_columns()
    _migrate_users_to_accounts()
    _migrate_nfc_registration()
    print('[DB] Schema ready -> PostgreSQL')


def _migrate_add_missing_columns():
    migrations = [
        ('students', 'program', "TEXT NOT NULL DEFAULT ''"),
        ('students', 'full_name', "TEXT NOT NULL DEFAULT ''"),
        ('students', 'reg_tx_hash', "TEXT NOT NULL DEFAULT ''"),
        ('students', 'reg_block', 'INTEGER NOT NULL DEFAULT 0'),
        ('students', 'photo_file', "TEXT NOT NULL DEFAULT ''"),
        ('students', 'updated_at', "TEXT NOT NULL DEFAULT ''"),
        ('students', 'student_status', "TEXT NOT NULL DEFAULT 'active'"),  # active, graduated, alumni
        ('sessions', 'teacher_username', "TEXT NOT NULL DEFAULT ''"),
        ('sessions', 'class_type', "TEXT NOT NULL DEFAULT 'lecture'"),
        ('sessions', 'total_enrolled', 'INTEGER NOT NULL DEFAULT 0'),
        ('sessions', 'total_present', 'INTEGER NOT NULL DEFAULT 0'),
        ('sessions', 'total_late', 'INTEGER NOT NULL DEFAULT 0'),
        ('sessions', 'total_absent', 'INTEGER NOT NULL DEFAULT 0'),
        ('sessions', 'total_excused', 'INTEGER NOT NULL DEFAULT 0'),
        ('sessions', 'warn_log_json', "TEXT NOT NULL DEFAULT '[]'"),
        ('sessions', 'invalid_log_json', "TEXT NOT NULL DEFAULT '[]'"),
        ('sessions', 'grace_period', 'INTEGER NOT NULL DEFAULT 15'),
        ('sessions', 'auto_end_at', 'TEXT'),
        ('sessions', 'schedule_id', 'TEXT DEFAULT NULL'),
        ('sessions', 'session_tx_hash', "TEXT NOT NULL DEFAULT ''"),
        ('sessions', 'session_block_number', 'INTEGER NOT NULL DEFAULT 0'),
        ('accounts', 'updated_at', "TEXT NOT NULL DEFAULT ''"),
        ('photos', 'uploaded_at', "TEXT NOT NULL DEFAULT ''"),
        ('attendance_logs', 'excuse_request_id', 'INTEGER DEFAULT NULL'),
        ('attendance_logs', 'class_type', "TEXT NOT NULL DEFAULT 'lecture'"),
        ('schedules', 'section_key', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'subject_id', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'subject_name', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'course_code', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'teacher_username', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'teacher_name', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'day_of_week', 'INTEGER NOT NULL DEFAULT 1'),
        ('schedules', 'start_time', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'end_time', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'class_type', "TEXT NOT NULL DEFAULT 'lecture'"),
        ('schedules', 'grace_minutes', 'INTEGER NOT NULL DEFAULT 15'),
        ('schedules', 'is_active', 'INTEGER NOT NULL DEFAULT 1'),
        ('schedules', 'created_by', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'created_at', "TEXT NOT NULL DEFAULT ''"),
        ('schedules', 'updated_at', "TEXT NOT NULL DEFAULT ''"),
    ]
    with get_db() as conn:
        if DB_BACKEND == 'postgres':
            existing_tables = [
                r[0] for r in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE'"
                ).fetchall()
            ]
        else:
            existing_tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]

        if 'schedules' not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
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
                    class_type       TEXT NOT NULL DEFAULT 'lecture',
                    grace_minutes    INTEGER NOT NULL DEFAULT 15,
                    is_active        INTEGER NOT NULL DEFAULT 1,
                    created_by       TEXT NOT NULL DEFAULT '',
                    created_at       TEXT NOT NULL DEFAULT '',
                    updated_at       TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sched_teacher ON schedules(teacher_username)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sched_day     ON schedules(day_of_week)')
            print('[MIGRATION] Created missing table: schedules')

        if 'event_schedules' not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_schedules (
                    event_id             TEXT PRIMARY KEY,
                    title                TEXT NOT NULL DEFAULT '',
                    description          TEXT NOT NULL DEFAULT '',
                    teacher_usernames_json TEXT NOT NULL DEFAULT '[]',
                    section_keys_json    TEXT NOT NULL DEFAULT '[]',
                    start_at             TEXT NOT NULL DEFAULT '',
                    end_at               TEXT NOT NULL DEFAULT '',
                    is_active            INTEGER NOT NULL DEFAULT 1,
                    created_by           TEXT NOT NULL DEFAULT '',
                    created_at           TEXT NOT NULL DEFAULT '',
                    updated_at           TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_event_sched_start ON event_schedules(start_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_event_sched_active ON event_schedules(is_active)')
            print('[MIGRATION] Created missing table: event_schedules')

        if 'no_class_days' not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS no_class_days (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    title               TEXT NOT NULL DEFAULT '',
                    description         TEXT NOT NULL DEFAULT '',
                    from_date           TEXT NOT NULL DEFAULT '',
                    to_date             TEXT NOT NULL DEFAULT '',
                    teacher_usernames_json TEXT NOT NULL DEFAULT '[]',
                    apply_all_teachers  INTEGER NOT NULL DEFAULT 0,
                    is_active           INTEGER NOT NULL DEFAULT 1,
                    created_by          TEXT NOT NULL DEFAULT '',
                    created_at          TEXT NOT NULL DEFAULT '',
                    updated_at          TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_no_class_days_range ON no_class_days(from_date, to_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_no_class_days_active ON no_class_days(is_active)')
            print('[MIGRATION] Created missing table: no_class_days')

        if 'excuse_requests' not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS excuse_requests (
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
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_excuse_sess   ON excuse_requests(sess_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_excuse_status ON excuse_requests(status)')
            print('[MIGRATION] Created missing table: excuse_requests')

        def _run_migration_step(sql, params=None):
            conn.execute('SAVEPOINT mig_step')
            try:
                if params is None:
                    conn.execute(sql)
                else:
                    conn.execute(sql, params)
                conn.execute('RELEASE SAVEPOINT mig_step')
                return True, None
            except Exception as err:
                conn.execute('ROLLBACK TO SAVEPOINT mig_step')
                conn.execute('RELEASE SAVEPOINT mig_step')
                return False, err

        for table, col, col_def in migrations:
            ok, _ = _run_migration_step(f'ALTER TABLE {table} ADD COLUMN {col} {col_def}')
            if ok:
                print(f'[MIGRATION] Added {table}.{col}')

        ok, _ = _run_migration_step("ALTER TABLE no_class_days ADD COLUMN teacher_usernames_json TEXT NOT NULL DEFAULT '[]'")
        if ok:
            print('[MIGRATION] Added no_class_days.teacher_usernames_json')

        ok, _ = _run_migration_step('ALTER TABLE no_class_days ADD COLUMN apply_all_teachers INTEGER NOT NULL DEFAULT 0')
        if ok:
            print('[MIGRATION] Added no_class_days.apply_all_teachers')
        try:
            existing = [r[1] for r in conn.execute('PRAGMA table_info(students)').fetchall()]
            if 'course' in existing and 'program' in existing:
                ok, e = _run_migration_step("UPDATE students SET program = course WHERE program = '' AND course != ''")
                if not ok:
                    print(f'[MIGRATION] course->program copy: {e}')
        except Exception as e:
            print(f'[MIGRATION] course->program copy: {e}')
        try:
            existing = [r[1] for r in conn.execute('PRAGMA table_info(students)').fetchall()]
            if 'name' in existing and 'full_name' in existing:
                ok, e = _run_migration_step("UPDATE students SET full_name = name WHERE full_name = '' AND name != ''")
                if not ok:
                    print(f'[MIGRATION] name->full_name copy: {e}')
        except Exception as e:
            print(f'[MIGRATION] name->full_name copy: {e}')
        try:
            existing = [r[1] for r in conn.execute('PRAGMA table_info(students)').fetchall()]
            if 'tx_hash' in existing and 'reg_tx_hash' in existing:
                # DISABLED: Do not copy tx_hash to reg_tx_hash — student identity should never be on blockchain
                # ok, e = _run_migration_step("UPDATE students SET reg_tx_hash = tx_hash WHERE reg_tx_hash = '' AND tx_hash != ''")
                # if not ok:
                #     print(f'[MIGRATION] tx_hash->reg_tx_hash copy: {e}')
                pass
        except Exception as e:
            pass
        
        # CLEANUP: Clear any erroneous student registration blockchain references
        # Students should never have reg_tx_hash or eth_address values (those are for attendance only)
        ok, e = _run_migration_step("UPDATE students SET reg_tx_hash='', reg_block=0, eth_address='' WHERE reg_tx_hash != '' OR reg_block != 0 OR eth_address != ''")
        if ok:
            print('[MIGRATION] Cleared erroneous student blockchain references')
        else:
            print(f'[MIGRATION] Cleanup student references: {e}')
        try:
            existing = [r[1] for r in conn.execute('PRAGMA table_info(sessions)').fetchall()]
            if 'teacher' in existing and 'teacher_username' in existing:
                ok, e = _run_migration_step("UPDATE sessions SET teacher_username = teacher WHERE teacher_username = '' AND teacher != ''")
                if not ok:
                    print(f'[MIGRATION] teacher->teacher_username copy: {e}')
        except Exception as e:
            print(f'[MIGRATION] teacher->teacher_username copy: {e}')
        ok, e = _run_migration_step('CREATE INDEX IF NOT EXISTS idx_stu_program ON students(program)')
        if not ok:
            print(f'[MIGRATION] Index creation: {e}')
        ok, e = _run_migration_step('CREATE INDEX IF NOT EXISTS idx_stu_section ON students(year_level, section)')
        if not ok:
            print(f'[MIGRATION] Index creation: {e}')
        ok, e = _run_migration_step('CREATE INDEX IF NOT EXISTS idx_sess_teacher ON sessions(teacher_username)')
        if not ok:
            print(f'[MIGRATION] Index creation: {e}')


def _migrate_users_to_accounts():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM users').fetchall()
        for r in rows:
            d = dict(r)
            conn.execute(
                'INSERT OR IGNORE INTO accounts '
                '(username,password_hash,role,full_name,email,status,'
                ' sections_json,my_subjects_json,created_at,updated_at) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (
                    d['username'],
                    d['password'],
                    d.get('role', 'teacher'),
                    d.get('full_name', ''),
                    d.get('email', ''),
                    d.get('status', 'pending'),
                    d.get('sections_json', '[]'),
                    d.get('my_subjects_json', '[]'),
                    d.get('created_at', ''),
                    d.get('created_at', ''),
                ),
            )


def _migrate_nfc_registration():
    with get_db() as conn:
        row = conn.execute('SELECT * FROM nfc_registration WHERE id=1').fetchone()
        if row:
            conn.execute(
                'INSERT OR REPLACE INTO nfc_scanner '
                '(id,waiting,scanned_uid,requested_by,requested_at) VALUES (?,?,?,?,?)',
                (1, row['waiting'], row['scanned_uid'], row['requested_by'], row['requested_at']),
            )


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for col in (
        'present_json',
        'late_json',
        'excused_json',
        'warned_json',
        'absent_json',
        'tap_log_json',
        'warn_log_json',
        'invalid_log_json',
    ):
        key = col.replace('_json', '')
        if col in d:
            d[key] = json.loads(d.pop(col) or '[]')
        elif key not in d:
            d[key] = []
    d['excuse_notes'] = json.loads(d.pop('excuse_notes_json', '{}') or '{}') if 'excuse_notes_json' in d else {}
    d['tx_hashes'] = json.loads(d.pop('tx_hashes_json', '{}') or '{}') if 'tx_hashes_json' in d else {}
    if 'teacher_username' in d and 'teacher' not in d:
        d['teacher'] = d.pop('teacher_username')
    elif 'teacher_username' in d:
        d.pop('teacher_username')
    if d.get('section_key'):
        d['section_key'] = normalize_section_key(d['section_key'])
    return d


def load_sessions():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM sessions').fetchall()
        return {r['sess_id']: _session_row_with_logs(conn, r) for r in rows}


def load_session(sess_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE sess_id=?", (sess_id,)).fetchone()
        if not row:
            return None
        return _session_row_with_logs(conn, row)


def _session_row_with_logs(conn, row):
    d = dict(row)
    if d.get('section_key'):
        d['section_key'] = normalize_section_key(d['section_key'])
    logs = conn.execute(
        "SELECT * FROM attendance_logs WHERE sess_id=?", (d['sess_id'],)
    ).fetchall()
    present, late, excused, absent = [], [], [], []
    tap_log, excuse_notes, tx_hashes = [], {}, {}
    for lg in logs:
        nid = lg['nfc_id']
        st = lg['status']
        if st == 'excused':
            excused.append(nid)
            excuse_notes[nid] = lg['excuse_note']
        elif st == 'late':
            late.append(nid)
            present.append(nid)
        elif st == 'present':
            present.append(nid)
        elif st == 'absent':
            absent.append(nid)
        if lg['tap_time'] and st in ('present', 'late'):
            tap_log.append({
                'nfc_id': nid,
                'name': lg['student_name'],
                'student_id': lg['student_id'],
                'time': lg['tap_time'],
                'tx_hash': lg['tx_hash'],
                'block': lg['block_number'],
                'is_late': st == 'late',
                'timestamp': 0,
            })
        if lg['tx_hash']:
            tx_hashes[nid] = {
                'tx_hash': lg['tx_hash'],
                'block': lg['block_number'],
                'time': lg['tap_time'],
            }
    d['present'] = present
    d['late'] = late
    d['excused'] = excused
    d['absent'] = absent
    d['grace_period'] = int(d.get('grace_period', 15))
    d['semester'] = d.get('semester', '1st Semester')
    d['warned'] = []
    d['tap_log'] = tap_log
    d['warn_log'] = json.loads(d.pop('warn_log_json', '[]') or '[]')
    d['invalid_log'] = json.loads(d.pop('invalid_log_json', '[]') or '[]')
    d['excuse_notes'] = excuse_notes
    d['tx_hashes'] = tx_hashes
    # Ensure core fields are strings to prevent template crashes
    for k in ['teacher_name', 'subject_name', 'section_key', 'time_slot']:
        if k in d and d[k] is None:
            d[k] = ''
    return d

def save_session(sess_id, s):
    sk = normalize_section_key(s.get('section_key', ''))
    teacher_uname = s.get('teacher_username') or s.get('teacher') or ''
    teacher_name  = s.get('teacher_name', '')
    schedule_id   = s.get('schedule_id')
    class_type = str(s.get('class_type', 'lecture')).strip().lower()
    if class_type not in ('lecture', 'laboratory', 'school_event'):
        class_type = 'lecture'
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(sess_id,subject_id,subject_name,course_code,class_type,units,time_slot,"
            " section_key,teacher_username,teacher_name,started_at,late_cutoff,"
            " auto_end_at,ended_at,grace_period,schedule_id,"
            " warn_log_json,invalid_log_json,semester,session_tx_hash,session_block_number) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(sess_id) DO UPDATE SET "
            "subject_id=excluded.subject_id, subject_name=excluded.subject_name, "
            "course_code=excluded.course_code, class_type=excluded.class_type, "
            "units=excluded.units, "
            "time_slot=excluded.time_slot, section_key=excluded.section_key, "
            "teacher_username=excluded.teacher_username, "
            "teacher_name=excluded.teacher_name, "
            "started_at=excluded.started_at, late_cutoff=excluded.late_cutoff, "
            "auto_end_at=excluded.auto_end_at, "
            "ended_at=excluded.ended_at, "
            "grace_period=excluded.grace_period, "
            "schedule_id=excluded.schedule_id, "
            "warn_log_json=excluded.warn_log_json, "
            "invalid_log_json=excluded.invalid_log_json, "
            "semester=excluded.semester, "
            "session_tx_hash=excluded.session_tx_hash, "
            "session_block_number=excluded.session_block_number",
            (sess_id, s.get('subject_id', ''), s.get('subject_name', ''),
             s.get('course_code', ''), class_type, s.get('units', 3), s.get('time_slot', ''),
             sk, teacher_uname, teacher_name,
             s.get('started_at', ''), s.get('late_cutoff', ''),
             s.get('auto_end_at'), s.get('ended_at'),
             s.get('grace_period', 15), schedule_id,
             json.dumps(s.get('warn_log', [])), json.dumps(s.get('invalid_log', [])),
             s.get('semester', '1st Semester'),
             s.get('session_tx_hash', ''), s.get('session_block_number', 0))
        )
        counts = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM attendance_logs "
            "WHERE sess_id=? GROUP BY status", (sess_id,)
        ).fetchall()
        totals = {r['status']: r['cnt'] for r in counts}
        conn.execute(
            "UPDATE sessions SET total_present=?,total_late=?,total_absent=?,total_excused=? "
            "WHERE sess_id=?",
            (totals.get('present', 0) + totals.get('late', 0),
             totals.get('late', 0), totals.get('absent', 0),
             totals.get('excused', 0), sess_id)
        )

def save_sessions(sessions_dict):
    for sid, s in sessions_dict.items():
        save_session(sid, s)

def migrate_json_to_postgres():
    for fname, table, saver in [
        ('users.json',             'users',             lambda d: [db_save_user(u,v) for u,v in d.items()]),
        ('subjects.json',          'subjects',          lambda d: [db_save_subject(k,v) for k,v in d.items()]),
        ('student_photos.json',    'photos',            lambda d: [db_save_photo(k,v) for k,v in d.items()]),
        ('student_overrides.json', 'student_overrides', lambda d: [db_save_override(k,v) for k,v in d.items()]),
        ('sessions.json',          'sessions',          lambda d: save_sessions(d)),
    ]:
        fpath = os.path.join(BASE_DIR, fname)
        if os.path.exists(fpath):
            try:
                old = json.load(open(fpath))
                with get_db() as conn:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if count == 0 and old:
                    print(f"[DB] Migrating {fname} -> {table}...")
                    saver(old)
                    os.rename(fpath, fpath + '.migrated')
            except Exception as e:
                print(f"[DB] Migration warning for {fname}: {e}")
    if db_get_user('admin') is None:
        db_save_user('admin', {
            'username':'admin','password':hash_password('admin123'),'role':'admin',
            'full_name':'System Administrator','email':'admin@davs.edu',
            'status':'approved','sections':[],'my_subjects':[],
            'created_at':_now_local().strftime('%Y-%m-%d %H:%M:%S')
        })
    if db_get_user('superadmin') is None:
        db_save_user('superadmin', {
            'username':'superadmin','password':hash_password('Admin@DAVS2024'),
            'role':'super_admin','full_name':'Super Administrator',
            'email':'superadmin@davs.edu',
            'status':'approved','sections':[],'my_subjects':[],
            'created_at':_now_local().strftime('%Y-%m-%d %H:%M:%S')
        })
        print('[DB] Default superadmin account created (change password immediately!)')
    else:
        # Keep the bootstrap superadmin account privileged to avoid lockout.
        su = db_get_user('superadmin')
        if su and (su.get('role') != 'super_admin' or su.get('status') != 'approved'):
            su['role'] = 'super_admin'
            su['status'] = 'approved'
            db_save_user('superadmin', su)
            print('[DB] Corrected superadmin role/status to super_admin/approved')

def _account_row(row):
    if row is None: return None
    d = dict(row)
    if 'password_hash' in d:
        d['password'] = d.pop('password_hash')
    d['role'] = _canonical_role(d.get('role', 'teacher'))
    raw_sections     = json.loads(d.pop('sections_json',   '[]') or '[]')
    d['my_subjects'] = json.loads(d.pop('my_subjects_json','[]') or '[]')
    d['sections']    = [normalize_section_key(s) for s in raw_sections]
    return d

def _user_row(row):
    return _account_row(row)

def db_get_all_users():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM accounts").fetchall()
    return {r['username']: _account_row(r) for r in rows}

def db_get_user(username):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
    return _account_row(row)

def db_save_user(username, u):
    sections = [normalize_section_key(s) for s in u.get('sections', [])]
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    pw  = u.get('password', u.get('password_hash', ''))
    role = _canonical_role(u.get('role', 'teacher'))
    with get_db() as conn:
        conn.execute(
            "INSERT INTO accounts "
            "(username,password_hash,role,full_name,email,status,"
            " sections_json,my_subjects_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET "
            "password_hash=excluded.password_hash, role=excluded.role, "
            "full_name=excluded.full_name, email=excluded.email, "
            "status=excluded.status, sections_json=excluded.sections_json, "
            "my_subjects_json=excluded.my_subjects_json, updated_at=excluded.updated_at",
              (username, pw, role,
             u.get('full_name',''), u.get('email',''), u.get('status','pending'),
             json.dumps(sections), json.dumps(u.get('my_subjects',[])),
             u.get('created_at', now), now)
        )
        conn.execute(
            "INSERT INTO users "
            "(username,password,role,full_name,email,status,"
            " sections_json,my_subjects_json,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET "
            "password=excluded.password, role=excluded.role, "
            "full_name=excluded.full_name, email=excluded.email, "
            "status=excluded.status, sections_json=excluded.sections_json, "
            "my_subjects_json=excluded.my_subjects_json",
              (username, pw, role,
             u.get('full_name',''), u.get('email',''), u.get('status','pending'),
             json.dumps(sections), json.dumps(u.get('my_subjects',[])),
             u.get('created_at', now))
        )

def db_delete_user(username):
    with get_db() as conn:
        conn.execute("DELETE FROM accounts WHERE username=?", (username,))
        conn.execute("DELETE FROM users    WHERE username=?", (username,))

def db_pending_count():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM accounts WHERE status='pending'").fetchone()[0]

def _student_row(row):
    if row is None: return None
    d = dict(row)
    d['nfcId']    = d.get('nfc_id', '')
    d['name']     = d.get('full_name', '')
    d['course']   = d.get('program', '')
    d['address']  = d.get('eth_address', '')
    d['tx_hash']  = d.get('reg_tx_hash', '')
    d['section']  = (d.get('section') or '').strip().upper()
    return d

def db_save_student(s):
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as conn:
        conn.execute(
            "INSERT INTO students "
            "(nfc_id,full_name,student_id,program,year_level,section,"
            " adviser,email,contact,major,semester,school_year,"
            " date_registered,raw_name,eth_address,reg_tx_hash,reg_block,"
            " photo_file,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(nfc_id) DO UPDATE SET "
            "full_name=excluded.full_name, student_id=excluded.student_id, "
            "program=excluded.program, year_level=excluded.year_level, "
            "section=excluded.section, adviser=excluded.adviser, "
            "email=excluded.email, contact=excluded.contact, major=excluded.major, "
            "semester=excluded.semester, school_year=excluded.school_year, "
            "date_registered=excluded.date_registered, raw_name=excluded.raw_name, "
            "eth_address=excluded.eth_address, reg_tx_hash=excluded.reg_tx_hash, "
            "reg_block=excluded.reg_block, photo_file=excluded.photo_file, "
            "updated_at=excluded.updated_at",
            (
                s.get('nfcId', s.get('nfc_id','')),
                s.get('name',  s.get('full_name','')),
                s.get('student_id',''),
                s.get('course', s.get('program','')),
                s.get('year_level',''),
                (s.get('section') or '').strip().upper(),
                s.get('adviser',''), s.get('email',''), s.get('contact',''),
                s.get('major',''), s.get('semester',''), s.get('school_year',''),
                s.get('date_registered',''),
                s.get('raw_name',''),
                s.get('address', s.get('eth_address','')),
                '',  # ← ALWAYS EMPTY: reg_tx_hash must never be populated for student identity
                0,   # ← ALWAYS 0: reg_block must never be populated
                s.get('photo_file',''),
                s.get('created_at', now), now
            )
        )

def db_get_all_students():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY full_name").fetchall()
    return [_student_row(r) for r in rows]

def db_get_student(nfc_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM students WHERE nfc_id=?", (nfc_id,)).fetchone()
    return _student_row(row)

def db_delete_student(nfc_id):
    with get_db() as conn:
        conn.execute("DELETE FROM students WHERE nfc_id=?", (nfc_id,))

def db_save_attendance_log(sess_id, nfc_id, student_name, student_id,
                            status, tap_time, tx_hash='', block_number=0,
                            excuse_note='', class_type=''):
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    class_type_norm = str(class_type or '').strip().lower()
    if class_type_norm not in ('lecture', 'laboratory', 'school_event'):
        class_type_norm = ''
    if not class_type_norm:
        try:
            with get_db() as _conn:
                _row = _conn.execute(
                    "SELECT class_type FROM sessions WHERE sess_id=?",
                    (sess_id,),
                ).fetchone()
            class_type_norm = str((_row['class_type'] if _row else 'lecture') or 'lecture').strip().lower()
        except Exception:
            class_type_norm = 'lecture'
    if class_type_norm not in ('lecture', 'laboratory', 'school_event'):
        class_type_norm = 'lecture'
    with get_db() as conn:
        conn.execute(
            "INSERT INTO attendance_logs "
            "(sess_id,nfc_id,student_name,student_id,status,class_type,tap_time,"
            " tx_hash,block_number,excuse_note,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(sess_id,nfc_id) DO UPDATE SET "
            "status=excluded.status, class_type=excluded.class_type, tap_time=excluded.tap_time, "
            "tx_hash=excluded.tx_hash, block_number=excluded.block_number, "
            "excuse_note=excluded.excuse_note",
            (sess_id, nfc_id, student_name, student_id,
             status, class_type_norm, tap_time, tx_hash, block_number, excuse_note, now)
        )

def db_get_session_attendance(sess_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_logs WHERE sess_id=? ORDER BY tap_time",
            (sess_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def db_update_session_totals(sess_id):
    with get_db() as conn:
        counts = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM attendance_logs "
            "WHERE sess_id=? GROUP BY status", (sess_id,)
        ).fetchall()
        totals = {r['status']: r['cnt'] for r in counts}
        conn.execute(
            "UPDATE sessions SET "
            "total_present=?, total_late=?, total_absent=?, total_excused=? "
            "WHERE sess_id=?",
            (totals.get('present',0), totals.get('late',0),
             totals.get('absent',0),  totals.get('excused',0), sess_id)
        )

def nfc_is_waiting():
    with get_db() as conn:
        row = conn.execute("SELECT waiting FROM nfc_scanner WHERE id=1").fetchone()
    return bool(row and row['waiting'])

def nfc_set_waiting(flag, requested_by=''):
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as conn:
        conn.execute(
            "UPDATE nfc_scanner SET waiting=?, scanned_uid='', "
            "requested_by=?, requested_at=? WHERE id=1",
            (1 if flag else 0, requested_by, now)
        )
        conn.execute(
            "UPDATE nfc_registration SET waiting=?, scanned_uid='', "
            "requested_by=?, requested_at=? WHERE id=1",
            (1 if flag else 0, requested_by, now)
        )

def nfc_set_uid(uid):
    with get_db() as conn:
        conn.execute(
            "UPDATE nfc_scanner SET waiting=0, scanned_uid=? WHERE id=1", (uid,))
        conn.execute(
            "UPDATE nfc_registration SET waiting=0, scanned_uid=? WHERE id=1", (uid,))

def nfc_get_uid():
    with get_db() as conn:
        row = conn.execute(
            "SELECT scanned_uid FROM nfc_scanner WHERE id=1").fetchone()
    return row['scanned_uid'] if row else ''

def nfc_clear():
    with get_db() as conn:
        conn.execute(
            "UPDATE nfc_scanner SET waiting=0, scanned_uid='' WHERE id=1")
        conn.execute(
            "UPDATE nfc_registration SET waiting=0, scanned_uid='' WHERE id=1")

def db_get_all_subjects():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return {r['subject_id']: dict(r) for r in rows}

def db_get_subject(subject_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM subjects WHERE subject_id=?", (subject_id,)).fetchone()
    return dict(row) if row else None

def db_save_subject(subject_id, s):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO subjects (subject_id,name,course_code,units,created_by,created_at)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(subject_id) DO UPDATE SET"
            " name=excluded.name, course_code=excluded.course_code,"
            " units=excluded.units, created_by=excluded.created_by,"
            " created_at=excluded.created_at",
            (subject_id, s.get('name',''), s.get('course_code',''),
             str(s.get('units','3')), s.get('created_by',''), s.get('created_at',''))
        )

def db_delete_subject(subject_id):
    with get_db() as conn:
        conn.execute("DELETE FROM subjects WHERE subject_id=?", (subject_id,))

def db_get_all_photos():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM photos").fetchall()
    return {r['person_id']: r['filename'] for r in rows}

def db_get_photo(person_id):
    with get_db() as conn:
        row = conn.execute("SELECT filename FROM photos WHERE person_id=?", (person_id,)).fetchone()
    return row['filename'] if row else None

def db_save_photo(person_id, filename):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO photos (person_id,filename) VALUES (?,?)"
            " ON CONFLICT(person_id) DO UPDATE SET filename=excluded.filename",
            (person_id, filename)
        )

def db_delete_photo(person_id):
    with get_db() as conn:
        conn.execute("DELETE FROM photos WHERE person_id=?", (person_id,))

def db_rename_photo_key(old_key, new_key):
    with get_db() as conn:
        conn.execute("UPDATE photos SET person_id=? WHERE person_id=?", (new_key, old_key))

def db_get_override(nfc_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM student_overrides WHERE nfc_id=?", (nfc_id,)).fetchone()
    return dict(row) if row else {}

def db_save_override(nfc_id, fields):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO student_overrides (nfc_id,full_name,student_id,email,contact,"
            "adviser,major,semester,school_year,date_registered,course,year_level,section)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(nfc_id) DO UPDATE SET"
            " full_name=excluded.full_name, student_id=excluded.student_id,"
            " email=excluded.email, contact=excluded.contact,"
            " adviser=excluded.adviser, major=excluded.major,"
            " semester=excluded.semester, school_year=excluded.school_year,"
            " date_registered=excluded.date_registered,"
            " course=excluded.course, year_level=excluded.year_level,"
            " section=excluded.section",
            (nfc_id, fields.get('full_name',''), fields.get('student_id',''),
             fields.get('email',''), fields.get('contact',''),
             fields.get('adviser',''), fields.get('major',''),
             fields.get('semester',''), fields.get('school_year',''),
             fields.get('date_registered',''), fields.get('course',''),
             fields.get('year_level',''), fields.get('section','').upper())
        )

# ── Schedule DB helpers ────────────────────────────────────────────────────

def _event_schedule_to_rows(event_row):
    """Expand one event_schedules row into calendar-like schedule rows (teacher x section)."""
    title = str(event_row.get('title', 'School Event') or 'School Event').strip()
    desc = str(event_row.get('description', '') or '').strip()
    event_id = str(event_row.get('event_id', '') or '').strip()
    start_at = str(event_row.get('start_at', '') or '').strip()
    end_at = str(event_row.get('end_at', '') or '').strip()
    teacher_usernames = list(event_row.get('teacher_usernames', []) or [])
    section_keys = [normalize_section_key(s) for s in list(event_row.get('section_keys', []) or []) if str(s or '').strip()]
    if not start_at or not end_at or not event_id or not section_keys:
        return []

    try:
        start_dt = datetime.strptime(start_at, '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end_at, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return []

    if end_dt <= start_dt:
        return []

    if not teacher_usernames:
        teacher_usernames = ['']

    teachers_involved = []
    for u in teacher_usernames:
        tu = (db_get_user(u) if u else {}) or {}
        teachers_involved.append(str(tu.get('full_name', u) or u).strip())
    teachers_involved = sorted({t for t in teachers_involved if t})

    programs_involved = sorted({str(sk).split('|')[0] for sk in section_keys if '|' in str(sk) and str(sk).split('|')[0]})
    years_involved = sorted({str(sk).split('|')[1] for sk in section_keys if len(str(sk).split('|')) > 1 and str(sk).split('|')[1]})
    sections_involved = sorted({str(sk).split('|')[2] for sk in section_keys if len(str(sk).split('|')) > 2 and str(sk).split('|')[2]})

    rows = []
    for teacher_username in teacher_usernames:
        teacher = (db_get_user(teacher_username) if teacher_username else {}) or {}
        teacher_name = teacher.get('full_name', teacher_username or 'Event Monitor')
        for section_key in section_keys:
            schedule_id = f"event:{event_id}:{teacher_username}:{normalize_section_key(section_key)}"
            rows.append(
                {
                    'schedule_id': schedule_id,
                    'section_key': normalize_section_key(section_key),
                    'subject_id': f"event:{event_id}",
                    'subject_name': title,
                    'course_code': 'EVENT',
                    'teacher_username': teacher_username,
                    'teacher_name': teacher_name,
                    'day_of_week': start_dt.weekday(),
                    'start_time': start_dt.strftime('%H:%M'),
                    'end_time': end_dt.strftime('%H:%M'),
                    'class_type': 'school_event',
                    'grace_minutes': 0,
                    'is_active': 1,
                    'is_event': 1,
                    'event_id': event_id,
                    'event_title': title,
                    'event_description': desc,
                    'event_date': start_dt.strftime('%Y-%m-%d'),
                    'event_start_at': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_end_at': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'teachers_involved': teachers_involved,
                    'programs_involved': programs_involved,
                    'years_involved': years_involved,
                    'sections_involved': sections_involved,
                    'section_keys_involved': section_keys,
                }
            )
    return rows


def _event_schedule_rows_for_all():
    rows = []
    for ev in db_get_all_event_schedules():
        rows.extend(_event_schedule_to_rows(ev))
    return rows


def _event_schedule_rows_for_teacher(username):
    username_norm = str(username or '').strip().lower()
    rows = []
    for ev in db_get_all_event_schedules():
        teacher_usernames = [str(u or '').strip() for u in list(ev.get('teacher_usernames', []) or []) if str(u or '').strip()]
        if username_norm not in {u.lower() for u in teacher_usernames}:
            continue

        section_keys = [normalize_section_key(s) for s in list(ev.get('section_keys', []) or []) if str(s or '').strip()]
        if not section_keys:
            continue

        try:
            start_dt = datetime.strptime(str(ev.get('start_at', '') or '').strip(), '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(str(ev.get('end_at', '') or '').strip(), '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue

        if end_dt <= start_dt:
            continue

        # Keep schedule_id compatible with runtime sessions by anchoring to one
        # concrete section schedule key.
        representative_section = section_keys[0]
        schedule_id = f"event:{ev.get('event_id', '')}:{username_norm}:{representative_section}"

        teacher = db_get_user(username_norm) or {}
        teacher_name = teacher.get('full_name', username_norm)

        teachers_involved = []
        for u in teacher_usernames:
            tu = db_get_user(u) or {}
            teachers_involved.append(str(tu.get('full_name', u) or u).strip())
        teachers_involved = sorted({t for t in teachers_involved if t})

        programs = sorted({str(sk).split('|')[0] for sk in section_keys if '|' in str(sk) and str(sk).split('|')[0]})
        years = sorted({str(sk).split('|')[1] for sk in section_keys if len(str(sk).split('|')) > 1 and str(sk).split('|')[1]})
        sections = sorted({str(sk).split('|')[2] for sk in section_keys if len(str(sk).split('|')) > 2 and str(sk).split('|')[2]})

        section_key_set = set(section_keys)
        students_count = 0
        for st in db_get_all_students():
            if build_student_section_key(st) in section_key_set:
                students_count += 1

        rows.append(
            {
                'schedule_id': schedule_id,
                'section_key': representative_section,
                'subject_id': f"event:{ev.get('event_id', '')}",
                'subject_name': str(ev.get('title', 'School Event') or 'School Event').strip(),
                'course_code': 'EVENT',
                'teacher_username': username_norm,
                'teacher_name': teacher_name,
                'day_of_week': start_dt.weekday(),
                'start_time': start_dt.strftime('%H:%M'),
                'end_time': end_dt.strftime('%H:%M'),
                'class_type': 'school_event',
                'grace_minutes': 0,
                'is_active': 1,
                'is_event': 1,
                'event_id': str(ev.get('event_id', '') or '').strip(),
                'event_title': str(ev.get('title', 'School Event') or 'School Event').strip(),
                'event_description': str(ev.get('description', '') or '').strip(),
                'event_date': start_dt.strftime('%Y-%m-%d'),
                'event_start_at': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'event_end_at': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'teachers_involved': teachers_involved,
                'programs_involved': programs,
                'years_involved': years,
                'sections_involved': sections,
                'section_keys_involved': section_keys,
                'students_involved_count': students_count,
            }
        )
    return rows

def db_get_all_schedules():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE is_active=1 ORDER BY day_of_week, start_time"
        ).fetchall()
    regular_rows = [dict(r) for r in rows]
    event_rows = _event_schedule_rows_for_all()
    merged = regular_rows + event_rows
    merged.sort(key=lambda r: (int(r.get('day_of_week', 0)), str(r.get('start_time', ''))))
    return merged

def db_get_schedules_for_teacher(username):
    username_norm = str(username or '').strip().lower()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules "
            "WHERE lower(trim(teacher_username))=? AND is_active=1 "
            "ORDER BY day_of_week, start_time",
            (username_norm,)
        ).fetchall()
    regular_rows = [dict(r) for r in rows]
    event_rows = _event_schedule_rows_for_teacher(username_norm)
    merged = regular_rows + event_rows
    merged.sort(key=lambda r: (int(r.get('day_of_week', 0)), str(r.get('start_time', ''))))
    return merged

def db_get_schedule(schedule_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
    return dict(row) if row else None

def db_save_schedule(s: dict) -> str:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    sid = s.get('schedule_id') or str(uuid.uuid4())
    class_type = str(s.get('class_type', 'lecture')).strip().lower()
    if class_type not in ('lecture', 'laboratory', 'school_event'):
        class_type = 'lecture'
    day_of_week = int(s.get('day_of_week', 0) or 0)
    if day_of_week < 0 or day_of_week > 6:
        day_of_week = 0
    with get_db() as conn:
        conn.execute(
            "INSERT INTO schedules "
            "(schedule_id,section_key,subject_id,subject_name,course_code,"
            " teacher_username,teacher_name,day_of_week,start_time,end_time,semester,class_type,"
            " grace_minutes,is_active,created_by,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?) "
            "ON CONFLICT(schedule_id) DO UPDATE SET "
            "section_key=excluded.section_key, subject_id=excluded.subject_id, "
            "subject_name=excluded.subject_name, course_code=excluded.course_code, "
            "teacher_username=excluded.teacher_username, teacher_name=excluded.teacher_name, "
            "day_of_week=excluded.day_of_week, start_time=excluded.start_time, "
            "end_time=excluded.end_time, semester=excluded.semester, class_type=excluded.class_type, "
            "grace_minutes=excluded.grace_minutes, "
            "updated_at=excluded.updated_at",
            (sid,
             normalize_section_key(s.get('section_key', '')),
             s.get('subject_id', ''), s.get('subject_name', ''), s.get('course_code', ''),
             s.get('teacher_username', ''), s.get('teacher_name', ''),
             day_of_week,
             s.get('start_time', ''), s.get('end_time', ''),
             s.get('semester', ''),
             class_type,
             int(s.get('grace_minutes', 15)),
             s.get('created_by', ''), now, now)
        )
    return sid

def db_delete_session(sess_id):
    with get_db() as conn:
        conn.execute("DELETE FROM attendance_logs WHERE sess_id=?", (sess_id,))
        conn.execute("DELETE FROM excuse_requests WHERE sess_id=?", (sess_id,))
        conn.execute("DELETE FROM sessions WHERE sess_id=?", (sess_id,))
    if sess_id in sessions_db:
        del sessions_db[sess_id]

def db_delete_schedule(schedule_id):
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    schedule_id = str(schedule_id or '').strip()
    
    if schedule_id.startswith('event:'):
        # Extract the real event_id from 'event:EVENT_ID' or 'event:EVENT_ID:...'
        parts = schedule_id.split(':')
        if len(parts) >= 2:
            event_id = parts[1]
            with get_db() as conn:
                conn.execute(
                    "UPDATE event_schedules SET is_active=0, updated_at=? WHERE event_id=?",
                    (now, event_id)
                )
        return

    with get_db() as conn:
        conn.execute(
            "UPDATE schedules SET is_active=0, updated_at=? WHERE schedule_id=?",
            (now, schedule_id)
        )


def db_get_all_event_schedules():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM event_schedules WHERE is_active=1 ORDER BY start_at"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['teacher_usernames'] = json.loads(d.get('teacher_usernames_json', '[]') or '[]')
        except Exception:
            d['teacher_usernames'] = []
        try:
            d['section_keys'] = json.loads(d.get('section_keys_json', '[]') or '[]')
        except Exception:
            d['section_keys'] = []
        out.append(d)
    return out


def db_get_event_schedule_by_id(event_id):
    event_id = str(event_id or '').strip()
    if not event_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM event_schedules WHERE event_id=? LIMIT 1",
            (event_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d['teacher_usernames'] = json.loads(d.get('teacher_usernames_json', '[]') or '[]')
    except Exception:
        d['teacher_usernames'] = []
    try:
        d['section_keys'] = json.loads(d.get('section_keys_json', '[]') or '[]')
    except Exception:
        d['section_keys'] = []
    return d


def db_save_event_schedule(e: dict) -> str:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    event_id = str(e.get('event_id') or str(uuid.uuid4())).strip()
    teacher_usernames = list(dict.fromkeys(
        str(u).strip() for u in e.get('teacher_usernames', []) if str(u).strip()
    ))
    section_keys = list(dict.fromkeys(
        normalize_section_key(s) for s in e.get('section_keys', []) if str(s).strip()
    ))
    title = str(e.get('title', '')).strip()
    description = str(e.get('description', '')).strip()
    start_at = str(e.get('start_at', '')).strip()
    end_at = str(e.get('end_at', '')).strip()
    created_by = str(e.get('created_by', '')).strip()
    if not event_id or not title or not start_at or not end_at or not teacher_usernames or not section_keys:
        raise ValueError('Missing required event schedule fields.')
    with get_db() as conn:
        conn.execute(
            "INSERT INTO event_schedules "
            "(event_id,title,description,teacher_usernames_json,section_keys_json,start_at,end_at,is_active,created_by,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,1,?,?,?) "
            "ON CONFLICT(event_id) DO UPDATE SET "
            "title=excluded.title, description=excluded.description, "
            "teacher_usernames_json=excluded.teacher_usernames_json, "
            "section_keys_json=excluded.section_keys_json, "
            "start_at=excluded.start_at, end_at=excluded.end_at, updated_at=excluded.updated_at",
            (
                event_id,
                title,
                description,
                json.dumps(teacher_usernames),
                json.dumps(section_keys),
                start_at,
                end_at,
                created_by,
                now,
                now,
            ),
        )
        saved = conn.execute(
            "SELECT event_id FROM event_schedules WHERE event_id=? LIMIT 1",
            (event_id,),
        ).fetchone()
        if not saved:
            raise RuntimeError('Event schedule insert did not persist.')
    return event_id


def db_get_all_no_class_days():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM no_class_days WHERE is_active=1 ORDER BY from_date, to_date"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['teacher_usernames'] = json.loads(d.get('teacher_usernames_json', '[]') or '[]')
        except Exception:
            d['teacher_usernames'] = []
        d['apply_all_teachers'] = int(d.get('apply_all_teachers') or 0)
        out.append(d)
    return out


def _no_class_applies_to_teacher(item: dict, teacher_username: str) -> bool:
    if int(item.get('apply_all_teachers') or 0) == 1:
        return True
    usernames = [str(u or '').strip().lower() for u in list(item.get('teacher_usernames', []) or []) if str(u or '').strip()]
    if not usernames:
        return True
    teacher_norm = str(teacher_username or '').strip().lower()
    return bool(teacher_norm and teacher_norm in usernames)


def db_get_no_class_days_for_date(date_ymd, teacher_username=''):
    d = str(date_ymd or '').strip()
    if not d:
        return []
    base_items = db_get_all_no_class_days()
    return [
        item for item in base_items
        if str(item.get('from_date', '')).strip() <= d <= str(item.get('to_date', '')).strip()
        and _no_class_applies_to_teacher(item, teacher_username)
    ]


def db_save_no_class_day(item: dict) -> int:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    teacher_usernames = [str(u).strip() for u in list(item.get('teacher_usernames', []) or []) if str(u).strip()]
    apply_all_teachers = 1 if item.get('apply_all_teachers') else 0
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO no_class_days "
            "(title,description,from_date,to_date,teacher_usernames_json,apply_all_teachers,is_active,created_by,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,1,?,?,?)",
            (
                str(item.get('title', '')).strip(),
                str(item.get('description', '')).strip(),
                str(item.get('from_date', '')).strip(),
                str(item.get('to_date', '')).strip(),
                json.dumps(teacher_usernames),
                apply_all_teachers,
                str(item.get('created_by', '')).strip(),
                now,
                now,
            ),
        )
        return int(cur.lastrowid or 0)


def db_delete_no_class_day(no_class_day_id: int) -> None:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as conn:
        conn.execute(
            "UPDATE no_class_days SET is_active=0, updated_at=? WHERE id=?",
            (now, int(no_class_day_id)),
        )

def get_todays_schedules(username=None):
    """Return schedules that fall on today's weekday (0=Mon). If username provided, filter by it."""
    today_dow = _now_local().weekday()
    if username:
        return [s for s in db_get_schedules_for_teacher(username)
                if int(s['day_of_week']) == today_dow]
    return [s for s in db_get_all_schedules()
            if int(s['day_of_week']) == today_dow]

def db_get_teacher_sessions(username):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE teacher_username=? ORDER BY started_at DESC",
            (username,)
        ).fetchall()
    return [_session_row_with_logs(conn, r) for r in rows]

def _normalize_hhmm(value):
    """Normalize schedule time values to HH:MM (supports HH:MM, HH:MM:SS, and AM/PM formats)."""
    raw = str(value or '').strip()
    if not raw:
        return None
    # 24h HH:MM
    try:
        dt = datetime.strptime(raw, '%H:%M')
        return dt.strftime('%H:%M')
    except Exception:
        pass
    # 24h HH:MM:SS
    try:
        dt = datetime.strptime(raw, '%H:%M:%S')
        return dt.strftime('%H:%M')
    except Exception:
        pass
    # 12h formats, with and without space before AM/PM
    for fmt in ('%I:%M %p', '%I:%M%p'):
        try:
            dt = datetime.strptime(raw.upper(), fmt)
            return dt.strftime('%H:%M')
        except Exception:
            continue
    return None


def _parse_event_schedule_id(schedule_id):
    """Parse schedule ids in form event:<event_id>:<teacher_username>:<section_key>."""
    raw = str(schedule_id or '').strip()
    if not raw.startswith('event:'):
        return None
    parts = raw.split(':', 3)
    if len(parts) != 4:
        return None
    return {
        'event_id': parts[1],
        'teacher_username': parts[2],
        'section_key': normalize_section_key(parts[3]),
    }


def _event_related_session_ids(schedule_id, include_ended=False):
    """Return session ids linked to the same event_id across all teachers/sections."""
    meta = _parse_event_schedule_id(schedule_id)
    if not meta:
        return []
    like_pattern = f"event:{meta['event_id']}:%"
    with get_db() as conn:
        if include_ended:
            rows = conn.execute(
                "SELECT sess_id FROM sessions "
                "WHERE class_type='school_event' AND schedule_id LIKE ? "
                "ORDER BY started_at DESC",
                (like_pattern,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sess_id FROM sessions "
                "WHERE class_type='school_event' AND ended_at IS NULL AND schedule_id LIKE ? "
                "ORDER BY started_at DESC",
                (like_pattern,),
            ).fetchall()
    return [r['sess_id'] for r in rows]

def _time_mins(value):
    hhmm = _normalize_hhmm(value)
    if not hhmm:
        return None
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)

def check_and_start_scheduled_sessions():
    """
    Background-friendly function:
    1. Check for schedules that should have started but don't have an active session.
    2. Check for active sessions that should have ended.
    """
    now_dt = _now_local()
    today_dow = now_dt.weekday()
    current_time_str = now_dt.strftime('%H:%M')
    today_ymd = now_dt.strftime('%Y-%m-%d')
    
    with app.app_context():
        no_class_today = db_get_no_class_days_for_date(today_ymd)
        if no_class_today:
            print(f"[AUTO] No-class day active on {today_ymd}; skipping automatic schedule starts.")

        # Get all active schedules for today
        schedules = [s for s in db_get_all_schedules() if int(s['day_of_week']) == today_dow]
        active_sessions = get_active_sessions()
        
        if schedules:
            print(f"[AUTO] Checking {len(schedules)} schedule(s) for today ({now_dt.strftime('%A %Y-%m-%d %H:%M:%S')})")
        
        for s in schedules:
            start_time = s['start_time']
            end_time   = s['end_time']
            start_hhmm = _normalize_hhmm(start_time)
            end_hhmm = _normalize_hhmm(end_time)
            if not start_hhmm or not end_hhmm:
                print(f"[AUTO WARN] Invalid schedule time format for schedule_id={s.get('schedule_id')} start={start_time} end={end_time}")
                continue
            
            # Start at schedule trigger time if this specific schedule has not run yet today.
            # Using schedule_id avoids false blocks from other sessions with same subject/section.
            today_prefix = now_dt.strftime('%Y-%m-%d') + '%'
            with get_db() as conn:
                schedule_id = s.get('schedule_id')
                if schedule_id:
                    already_ran = conn.execute(
                        "SELECT 1 FROM sessions WHERE schedule_id=? AND started_at LIKE ?",
                        (str(schedule_id), today_prefix)
                    ).fetchone()
                else:
                    # Legacy fallback for rows without schedule_id.
                    already_ran = conn.execute(
                        "SELECT 1 FROM sessions "
                        "WHERE teacher_username=? AND subject_id=? AND section_key=? AND started_at LIKE ?",
                        (
                            s.get('teacher_username', ''),
                            s['subject_id'],
                            normalize_section_key(s['section_key']),
                            today_prefix,
                        )
                    ).fetchone()
            
            start_dt = datetime.strptime(
                f"{now_dt.strftime('%Y-%m-%d')} {start_hhmm}:00",
                '%Y-%m-%d %H:%M:%S'
            )
            end_dt = datetime.strptime(
                f"{now_dt.strftime('%Y-%m-%d')} {end_hhmm}:00",
                '%Y-%m-%d %H:%M:%S'
            )
            if end_dt <= start_dt:
                print(f"[AUTO WARN] Invalid schedule window schedule_id={s.get('schedule_id')} start={start_hhmm} end={end_hhmm}")
                continue

            if db_get_no_class_days_for_date(today_ymd, s.get('teacher_username', '')):
                continue

            if not already_ran and start_dt <= now_dt < end_dt:
                # Automate session start
                sess_id = str(uuid.uuid4())[:13]
                subj = db_get_subject(s['subject_id'])
                late_cutoff_dt = datetime.strptime(start_hhmm, '%H:%M') + timedelta(minutes=s.get('grace_minutes', 15))
                late_cutoff = late_cutoff_dt.strftime('%H:%M')
                
                new_sess = {
                    'sess_id': sess_id,
                    'subject_id': s['subject_id'],
                    'subject_name': s['subject_name'],
                    'course_code': s['course_code'],
                    'semester': s.get('semester', '1st Semester'),
                    'class_type': s.get('class_type', 'lecture'),
                    'units': subj.get('units', 3) if subj else 3,
                    'time_slot': f"{start_hhmm} - {end_hhmm}",
                    'section_key': normalize_section_key(s['section_key']), # Force normalization
                    'teacher_username': s['teacher_username'],
                    'teacher_name': s['teacher_name'],
                    'started_at': now_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'late_cutoff': f"{now_dt.strftime('%Y-%m-%d')} {late_cutoff}:00",
                    'auto_end_at': f"{now_dt.strftime('%Y-%m-%d')} {end_hhmm}:00",
                    'grace_period': int(s.get('grace_minutes', 15)),
                    'schedule_id': s['schedule_id']
                }
                save_session(sess_id, new_sess)
                print(f"[AUTO] Started session {sess_id} for {s['subject_name']} ({s['teacher_username']}) - Section: {new_sess['section_key']}")
            elif already_ran and start_dt <= now_dt < end_dt:
                print(f"[AUTO] Skipped schedule_id={s.get('schedule_id')} (already ran today)")

        # One-time school events: create event sessions for selected teacher/section pairs.
        event_schedules = db_get_all_event_schedules()
        for ev in event_schedules:
            start_raw = str(ev.get('start_at', '')).strip()
            end_raw = str(ev.get('end_at', '')).strip()
            if not start_raw or not end_raw:
                continue
            try:
                start_dt = datetime.strptime(start_raw, '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(end_raw, '%Y-%m-%d %H:%M:%S')
            except Exception:
                continue
            event_blocked = False
            for teacher_username in (ev.get('teacher_usernames', []) or ['']):
                if db_get_no_class_days_for_date(start_dt.strftime('%Y-%m-%d'), teacher_username):
                    event_blocked = True
                    break
            if event_blocked:
                continue
            if not (start_dt <= now_dt < end_dt):
                continue

            teacher_usernames = ev.get('teacher_usernames', []) or []
            section_keys = ev.get('section_keys', []) or []
            if not teacher_usernames:
                teacher_usernames = ['']
            if not section_keys:
                section_keys = ['']

            for teacher_username in teacher_usernames:
                teacher = db_get_user(teacher_username) if teacher_username else {}
                teacher_name = teacher.get('full_name', teacher_username or 'Event Monitor')
                for section_key in section_keys:
                    schedule_key = f"event:{ev.get('event_id')}:{teacher_username}:{normalize_section_key(section_key)}"
                    with get_db() as conn:
                        already_ran = conn.execute(
                            "SELECT 1 FROM sessions WHERE schedule_id=?",
                            (schedule_key,),
                        ).fetchone()
                    if already_ran:
                        continue

                    sess_id = str(uuid.uuid4())[:13]
                    new_sess = {
                        'sess_id': sess_id,
                        'subject_id': f"event:{ev.get('event_id')}",
                        'subject_name': ev.get('title', 'School Event'),
                        'course_code': 'EVENT',
                        'semester': ev.get('semester', '1st Semester'),
                        'class_type': 'school_event',
                        'units': 0,
                        'time_slot': f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}",
                        'section_key': normalize_section_key(section_key),
                        'teacher_username': teacher_username,
                        'teacher_name': teacher_name,
                        'started_at': now_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'late_cutoff': now_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'auto_end_at': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'grace_period': 0,
                        'schedule_id': schedule_key,
                    }
                    save_session(sess_id, new_sess)
                    print(f"[AUTO EVENT] Started session {sess_id} for event {ev.get('event_id')}")

        # 2. End sessions that passed their auto_end_at
        for sid, asess in active_sessions.items():
            auto_end = asess.get('auto_end_at')
            if auto_end:
                try:
                    end_dt = datetime.strptime(auto_end, '%Y-%m-%d %H:%M:%S')
                    if now_dt >= end_dt:
                        result = _finalize_session(
                            sid,
                            ended_time=now_dt.strftime('%Y-%m-%d %H:%M:%S'),
                            async_chain_and_email=True,
                        )
                        if result and not result.get('already_ended'):
                            print(f"[AUTO] Ended session {sid} automatically.")
                except:
                    pass

def check_and_end_expired_sessions():
    """Wrapper — always runs inside an app context so DB helpers work from the background thread."""
    with app.app_context():
        _check_and_end_expired_sessions_impl()


def _check_and_end_expired_sessions_impl():
    """System-wide safety check to end sessions after their own configured end time."""
    now_dt = _now_local()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        active = conn.execute(
            "SELECT sess_id, auto_end_at, schedule_id, subject_id, section_key "
            "FROM sessions WHERE ended_at IS NULL"
        ).fetchall()

    for s in active:
        sess_id = s['sess_id']

        # Primary source of truth: per-session auto_end_at stamped at session creation.
        auto_end_at = (s['auto_end_at'] or '').strip()
        if auto_end_at:
            try:
                end_dt = datetime.strptime(auto_end_at, '%Y-%m-%d %H:%M:%S')
                # now_dt and end_dt are both naive, safe to compare
                if now_dt >= end_dt:
                    result = _finalize_session(sess_id, ended_time=now_str, async_chain_and_email=True)
                    if result and not result.get('already_ended'):
                        print(f"[AUTO] Ended session {sess_id} (Auto End Reached)")
                continue
            except Exception as e:
                # If stored timestamp is malformed, fall back to schedule lookup below.
                pass

        # Fallback for legacy sessions missing auto_end_at: prefer exact schedule_id lookup.
        end_mins = None
        with get_db() as conn:
            schedule_id = (s['schedule_id'] or '').strip()
            sched = None
            if schedule_id:
                sched = conn.execute(
                    "SELECT end_time FROM schedules WHERE schedule_id=? AND is_active=1",
                    (schedule_id,)
                ).fetchone()
            if not sched:
                # Legacy fallback only.
                sched = conn.execute(
                    "SELECT end_time FROM schedules WHERE subject_id=? AND section_key=? AND is_active=1 "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (s['subject_id'], s['section_key'])
                ).fetchone()

        if sched:
            end_mins = _time_mins(sched['end_time'])

        current_time_mins = _time_mins(now_dt.strftime('%H:%M'))
        if end_mins is None or current_time_mins is None:
            continue
        if current_time_mins >= end_mins:
            result = _finalize_session(sess_id, ended_time=now_str, async_chain_and_email=True)
            if result and not result.get('already_ended'):
                print(f"[AUTO] Ended session {sess_id} (Schedule End Time Reached)")

def automation_loop():
    """Single master loop for DAVS automation/synchronization.
    
    Runs every few seconds so scheduled sessions start almost immediately
    after the trigger time while still being lightweight.
    """
    poll_seconds = 5
    last_log_time = 0
    while True:
        try:
            current_time = time.time()
            # Log status every 60 seconds
            if current_time - last_log_time > 60:
                now_dt = _now_local()
                active_count = len(get_active_sessions())
                print(f"[AUTO] Heartbeat: {now_dt.strftime('%Y-%m-%d %H:%M:%S')} | Active sessions: {active_count}")
                last_log_time = current_time
            
            check_and_start_scheduled_sessions()
            check_and_end_expired_sessions()
        except Exception as e:
            import traceback
            print(f"[AUTO ERROR] {e}")
            print(f"[AUTO ERROR] Traceback: {traceback.format_exc()}")
        time.sleep(poll_seconds)

def ensure_automation_thread_running():
    """Start automation loop once per process even under flask/wsgi launch modes."""
    global AUTO_THREAD
    with AUTO_THREAD_LOCK:
        if AUTO_THREAD and AUTO_THREAD.is_alive():
            return
        AUTO_THREAD = Thread(target=automation_loop, daemon=True, name='davs-automation-loop')
        AUTO_THREAD.start()
        print(f'[AUTO] Automation loop started at {_now_local().strftime("%Y-%m-%d %H:%M:%S")} ({APP_TIMEZONE})')

@app.before_request
def _ensure_automation_thread_running():
    ensure_automation_thread_running()

from datetime import timedelta

DOW_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# ── Excuse Request DB helpers ──────────────────────────────────────────────

def _excuse_pk_column(conn) -> str:
    # Standard DAVS excuse_requests table uses 'id' as SERIAL PRIMARY KEY.
    return 'id'

def _excuse_order_expr(conn) -> str:
    cols = [r['name'] for r in conn.execute("PRAGMA table_info(excuse_requests)").fetchall()]
    if 'created_at' in cols and 'submitted_at' in cols:
        return "COALESCE(er.created_at, er.submitted_at, '')"
    if 'created_at' in cols:
        return "er.created_at"
    if 'submitted_at' in cols:
        return "er.submitted_at"
    return "''"

def db_save_excuse_request(data: dict) -> int:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as conn:
        cols = [r['name'] for r in conn.execute("PRAGMA table_info(excuse_requests)").fetchall()]
        insert_cols = [
            'sess_id', 'nfc_id', 'student_name', 'student_id', 'student_email',
            'reason_type', 'reason_detail', 'attachment_file', 'status'
        ]
        values = [
            data.get('sess_id', ''), data.get('nfc_id', ''),
            data.get('student_name', ''), data.get('student_id', ''),
            data.get('student_email', ''), data.get('reason_type', ''),
            data.get('reason_detail', ''), data.get('attachment_file', ''),
            'pending'
        ]

        # Support both legacy and current schemas.
        if 'created_at' in cols:
            insert_cols.append('created_at')
            values.append(now)
        if 'submitted_at' in cols:
            insert_cols.append('submitted_at')
            values.append(now)

        pk_col = _excuse_pk_column(conn)
        placeholders = ','.join(['?'] * len(insert_cols))
        # Use RETURNING to get the inserted ID (works with PostgreSQL compatibility layer)
        returning_clause = f" RETURNING {pk_col}" if pk_col != 'rowid' else ""
        sql = f"INSERT INTO excuse_requests ({','.join(insert_cols)}) VALUES ({placeholders}){returning_clause}"
        cur = conn.execute(sql, tuple(values))
        inserted_id = None
        if returning_clause:
            try:
                row = cur.fetchone()
                if row:
                    inserted_id = row[pk_col] if isinstance(row, dict) else row[0]
            except Exception:
                pass
        if inserted_id is None:
            try:
                # Fallback: query the last inserted row
                row = conn.execute(
                    f"SELECT {pk_col} AS pk FROM excuse_requests ORDER BY {pk_col} DESC LIMIT 1"
                ).fetchone()
                inserted_id = row['pk'] if row else 1
            except Exception:
                inserted_id = 1
        return inserted_id

def db_get_all_excuse_requests(status_filter=None):
    try:
        with get_db() as conn:
            pk_col = _excuse_pk_column(conn)
            order_expr = _excuse_order_expr(conn)
            pk_select = f"er.{pk_col}"
            # Explicitly alias er.id to avoid any column shadowing from JOIN
            base_sql = (
                f"SELECT {pk_select} AS id, er.sess_id, er.nfc_id, "
                "er.student_name, er.student_id, er.student_email, "
                "er.reason_type, er.reason_detail, er.attachment_file, "
                "er.status, er.reviewed_by, er.reviewed_at, "
                "COALESCE(er.created_at, er.submitted_at, '') AS created_at, "
                "s.subject_name AS session_subject, "
                "s.section_key AS session_section "
                "FROM excuse_requests er "
                "LEFT JOIN sessions s ON er.sess_id = s.sess_id "
            )
            if status_filter:
                rows = conn.execute(
                    base_sql + f"WHERE er.status=? ORDER BY {order_expr} DESC",
                    (status_filter,)
                ).fetchall()
            else:
                rows = conn.execute(
                    base_sql + f"ORDER BY {order_expr} DESC"
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f'[DB] db_get_all_excuse_requests error: {e}')
        return []

def db_get_excuse_request(excuse_id):
    with get_db() as conn:
        pk_col = _excuse_pk_column(conn)
        row = conn.execute(
            f"SELECT *, {pk_col} AS id FROM excuse_requests WHERE {pk_col}=?",
            (excuse_id,)
        ).fetchone()
    if not row:
        return None
    return dict(row)

def db_resolve_excuse(excuse_id: int, resolution: str, reviewed_by: str) -> dict | None:
    now = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    session_sync = None
    with get_db() as conn:
        pk_col = _excuse_pk_column(conn)
        row = conn.execute(
            f"SELECT *, {pk_col} AS id FROM excuse_requests WHERE {pk_col}=?",
            (excuse_id,)
        ).fetchone()
        if not row:
            return None
        row_dict = dict(row)
        row_dict['id'] = row_dict.get(pk_col)
        conn.execute(
            f"UPDATE excuse_requests SET status=?, reviewed_by=?, reviewed_at=? WHERE {pk_col}=?",
            (resolution, reviewed_by, now, excuse_id)
        )
        if resolution == 'approved':
            r_type = row_dict.get('reason_type', 'others')
            r_label = dict(EXCUSE_REASONS).get(r_type, r_type.title())
            r_detail = row_dict.get('reason_detail', '')
            note = f"{r_label}{' — ' + r_detail if r_detail else ''}"
            resolved_excuse_id = row_dict.get('id') or excuse_id
            
            # ✅ CRITICAL FIX: Use UPSERT to create record if student hasn't tapped yet
            # If student has no attendance_logs record, INSERT will create one
            # If record exists, UPDATE will mark it as excused
            conn.execute(
                "INSERT INTO attendance_logs "
                 "(sess_id, nfc_id, student_name, student_id, status, class_type, tap_time, "
                 " tx_hash, block_number, excuse_note, excuse_request_id, created_at) "
                 "VALUES (?, ?, ?, ?, 'excused', "
                 " COALESCE((SELECT class_type FROM sessions WHERE sess_id=?), 'lecture'),"
                 " ?, '', 0, ?, ?, ?) "
                "ON CONFLICT(sess_id, nfc_id) DO UPDATE SET "
                 "status='excused', class_type=excluded.class_type, excuse_note=excluded.excuse_note, "
                "excuse_request_id=excluded.excuse_request_id",
                 (row_dict['sess_id'], row_dict['nfc_id'], row_dict['student_name'], row_dict['student_id'],
                  row_dict['sess_id'], now, note, resolved_excuse_id, now)
            )
            # Defer session save_session sync until after this DB transaction closes.
            session_sync = {
                'sess_id': row_dict['sess_id'],
                'nfc_id': row_dict['nfc_id'],
                'note': note,
            }
    # Sync with live session if active (outside transaction to avoid DB write lock).
    if session_sync:
        sess = load_session(session_sync['sess_id'])
        if sess:
            excused = sess.setdefault('excused', [])
            if session_sync['nfc_id'] not in excused:
                excused.append(session_sync['nfc_id'])
            if session_sync['nfc_id'] in sess.get('absent', []):
                sess['absent'].remove(session_sync['nfc_id'])
            sess.setdefault('excuse_notes', {})[session_sync['nfc_id']] = session_sync['note']
            save_session(session_sync['sess_id'], sess)
            sessions_db[session_sync['sess_id']] = sess
    return row_dict

def _resolve_excuse_attachment_path(stored_value: str) -> str | None:
    """Resolve attachment paths across legacy/new storage styles."""
    raw = str(stored_value or '').strip()
    if not raw:
        return None
    raw_norm = raw.replace('\\', '/').lstrip('/')
    base = os.path.basename(raw_norm)
    candidates = [
        os.path.join(UPLOAD_FOLDER_EXCUSES, raw_norm),
        os.path.join(UPLOAD_FOLDER_EXCUSES, base),
        os.path.join(BASE_DIR, 'uploads', 'excuses', base),
        os.path.join(BASE_DIR, 'static', 'uploads', 'excuses', base),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _save_excuse_attachment(file_storage) -> str:
    """Save uploaded excuse file; returns stored filename. Raises ValueError on bad input."""
    orig = file_storage.filename or ''
    ext  = orig.rsplit('.', 1)[-1].lower() if '.' in orig else ''
    if ext not in ALLOWED_EXCUSE_EXTS:
        raise ValueError(f"Invalid file type '.{ext}'. Allowed: pdf, jpg, jpeg, png")
    data = file_storage.read()
    if len(data) > MAX_EXCUSE_FILE_MB * 1024 * 1024:
        raise ValueError(f"File too large (max {MAX_EXCUSE_FILE_MB} MB)")
    fname = f"{uuid.uuid4().hex}.{ext}"
    path  = os.path.join(UPLOAD_FOLDER_EXCUSES, fname)
    with open(path, 'wb') as fout:
        fout.write(data)
    return fname

def load_student_names():
    for s in db_get_all_students():
        student_name_map[s['nfcId']] = s['name']
    if student_name_map:
        print(f"[INFO] Loaded {len(student_name_map)} student names from PostgreSQL.")

try:
    init_db()
except Exception as e:
    print("\n" + "="*80)
    print(f"DATABASE INITIALIZATION FAILED: {e}")
    if IS_RAILWAY:
        print("\nDIAGNOSTIC FOR RAILWAY:")
        print("1. Ensure you have added a PostgreSQL service to your project.")
        print("2. Ensure DATABASE_URL is present in your app's Variables tab.")
        print("3. If using Railway's default PostgreSQL, it should be auto-injected.")
        print("4. Check if the PostgreSQL service is 'Healthy' in the Railway dashboard.")
    print("="*80 + "\n")
    # If we are in production, we should probably exit so Railway knows it failed
    if IS_PROD:
        import sys
        sys.exit(3)
migrate_json_to_postgres()
sessions_db = load_sessions()

student_name_map = {}
load_student_names()
recent_attendance = deque(maxlen=50)

DEPARTMENTS = {'DIT': {'label':'Department of Information Technology','courses':['BS Computer Science','BS Information Technology']}}
YEAR_LEVELS  = ['1st Year','2nd Year','3rd Year','4th Year']
SECTIONS     = ['A','B','C','D']

def fmt_time(dt_str):
    if not dt_str: return '—'
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        res = dt.strftime('%b %d, %Y · %I:%M %p')
        return res.replace(' · 0', ' · ').replace(' 0', ' ')
    except:
        return dt_str

def fmt_time_short(dt_str):
    if not dt_str: return '—'
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        res = dt.strftime('%I:%M %p')
        return res.lstrip('0')
    except:
        return dt_str

def fmt_timeslot(slot):
    if not slot or ' - ' not in slot:
        return slot
    try:
        parts = slot.split(' - ')
        res = []
        for p in parts:
            dt = datetime.strptime(p.strip(), '%H:%M')
            res.append(dt.strftime('%I:%M %p').lstrip('0'))
        return " - ".join(res)
    except:
        return slot

# Register Jinja2 filters after functions are defined
app.jinja_env.filters['from_json'] = lambda s: _json_mod.loads(s) if s else []
app.jinja_env.filters['fmt_timeslot'] = fmt_timeslot
app.jinja_env.filters['fmt_time'] = fmt_time
app.jinja_env.filters['fmt_time_short'] = fmt_time_short

# ── Role constants ────────────────────────────────────────────────────────
SUPER_ADMIN_ROLE = 'super_admin'
ADMIN_ROLES  = {'admin', 'super_admin'}
STAFF_ROLES  = {'teacher', 'admin', 'super_admin'}

EXCUSE_REASONS = [
    ('sickness',    'Sickness / Illness'),
    ('lbm',         'LBM (Loose Bowel Movement)'),
    ('emergency',   'Family/Personal Emergency'),
    ('bereavement', 'Bereavement (Death in Family)'),
    ('medical',     'Medical Appointment / Check-up'),
    ('accident',    'Accident or Injury'),
    ('official',    'Official School Business / Event'),
    ('weather',     'Extreme Weather / Calamity'),
    ('transport',   'Transportation Problem'),
    ('others',      'Others (please specify)'),
]

ALLOWED_EXCUSE_EXTS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_EXCUSE_FILE_MB  = 5
UPLOAD_FOLDER_EXCUSES = os.path.join(BASE_DIR, 'static', 'uploads', 'excuses')
os.makedirs(UPLOAD_FOLDER_EXCUSES, exist_ok=True)

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        return f(*a,**kw)
    return dec

def admin_required(f):
    """Allows admin and super_admin (backwards-compatible)."""
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session: return redirect(url_for('login'))
        if session.get('role') not in ADMIN_ROLES:
            flash('Admin access required.')
            return redirect(url_for('teacher_dashboard'))
        return f(*a,**kw)
    return dec

def super_admin_required(f):
    """Restricts access to super_admin role only."""
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session: return redirect(url_for('login'))
        if session.get('role') != 'super_admin':
            flash('Super Admin access required.', 'danger')
            return redirect(url_for('teacher_dashboard'))
        return f(*a,**kw)
    return dec

def staff_required(f):
    """Any authenticated staff member (teacher/admin/super_admin)."""
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session: return redirect(url_for('login'))
        if session.get('role') not in STAFF_ROLES:
            flash('Staff access required.')
            return redirect(url_for('login'))
        return f(*a,**kw)
    return dec


@app.before_request
def _sync_session_identity():
    """Keep session role/full_name aligned with DB to avoid stale-role sidebars/routes."""
    username = session.get('username')
    if not username:
        return
    user = db_get_user(username)
    if not user:
        session.clear()
        return
    canonical_role = _canonical_role(user.get('role', 'teacher'))
    if session.get('role') != canonical_role:
        session['role'] = canonical_role
    full_name = user.get('full_name', '')
    if session.get('full_name') != full_name:
        session['full_name'] = full_name

def get_current_user(): return db_get_user(session.get('username',''))

def parse_student(raw):
    parts = raw.split(' | ')
    r = {'name':parts[0],'student_id':'','course':'','year_level':'','section':'',
         'adviser':'','email':'','contact':'','semester':'','school_year':'',
         'date_registered':'','major':''}
    for p in parts[1:]:
        if   p.startswith('ID:'):       r['student_id']      = p[3:]
        elif p.startswith('Course:'):   r['course']          = p[7:]
        elif p.startswith('Year:'):     r['year_level']      = p[5:]
        elif p.startswith('Sec:'):      r['section']         = p[4:].upper()
        elif p.startswith('Adviser:'):  r['adviser']         = p[8:]
        elif p.startswith('Email:'):    r['email']           = p[6:]
        elif p.startswith('Tel:'):      r['contact']         = p[4:]
        elif p.startswith('Sem:'):      r['semester']        = p[4:]
        elif p.startswith('SY:'):       r['school_year']     = p[3:]
        elif p.startswith('RegDate:'): r['date_registered'] = p[8:]
        elif p.startswith('Major:'):    r['major']           = p[6:]
    return r

def get_all_students():
    cached = db_get_all_students()
    if not cached:
        return []
    for s in cached:
        ov = db_get_override(s['nfcId'])
        if ov.get('full_name'):       s['name']            = ov['full_name']
        if ov.get('student_id'):      s['student_id']      = ov['student_id']
        if ov.get('email'):           s['email']           = ov['email']
        if ov.get('contact'):         s['contact']         = ov['contact']
        if ov.get('adviser'):         s['adviser']         = ov['adviser']
        if ov.get('major'):           s['major']           = ov['major']
        if ov.get('semester'):        s['semester']        = ov['semester']
        if ov.get('school_year'):     s['school_year']     = ov['school_year']
        if ov.get('date_registered'): s['date_registered'] = ov['date_registered']
        if ov.get('course'):          s['course']          = ov['course']
        if ov.get('year_level'):      s['year_level']      = ov['year_level']
        if ov.get('section'):         s['section']         = ov['section'].upper()
        s['section'] = (s.get('section') or '').strip().upper()
    return cached

def get_attendance_records(nfc_id):
    try:
        ts, statuses = contract.functions.getAttendance(nfc_id).call()
        out = []
        for t, code in zip(ts, statuses):
            # Legacy contract returns bool; upgraded contract returns uint8.
            if isinstance(code, bool):
                status = 'present' if code else 'absent'
            else:
                status = {0: 'present', 1: 'late', 2: 'absent', 3: 'excused'}.get(int(code), 'absent')
            out.append((datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'), status in ('present', 'late')))
        return out
    except:
        return []


def get_student_session_rows_for_export(nfc_id):
    reason_labels = {
        'sickness': 'Sickness / Illness',
        'lbm': 'LBM',
        'emergency': 'Family Emergency',
        'bereavement': 'Bereavement',
        'medical': 'Medical Appointment',
        'accident': 'Accident / Injury',
        'official': 'Official School Business',
        'weather': 'Extreme Weather / Calamity',
        'transport': 'Transportation Problem',
        'others': 'Others',
    }

    with get_db() as conn:
        log_rows = conn.execute(
            "SELECT al.status, al.tx_hash, al.block_number, al.tap_time, al.excuse_note, "
            "al.sess_id, s.subject_name, s.course_code, s.class_type, s.teacher_name, s.time_slot, s.started_at "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "WHERE al.nfc_id=? "
            "ORDER BY s.started_at DESC",
            (nfc_id,),
        ).fetchall()
        exc_rows = conn.execute(
            "SELECT sess_id, reason_type, reason_detail, attachment_file "
            "FROM excuse_requests "
            "WHERE nfc_id=? AND status='approved'",
            (nfc_id,),
        ).fetchall()

    exc_map = {}
    for ex in exc_rows:
        exc_map[ex['sess_id']] = {
            'reason_type': ex['reason_type'] or '',
            'reason_detail': ex['reason_detail'] or '',
            'attachment_file': ex['attachment_file'] or '',
        }

    rows = []
    for lg in log_rows:
        ex = exc_map.get(lg['sess_id'], {})
        excuse_reason = ''
        if ex.get('reason_type'):
            excuse_reason = reason_labels.get(ex['reason_type'], ex['reason_type'])
            if ex.get('reason_detail'):
                excuse_reason += f" ({ex['reason_detail']})"
        elif lg['excuse_note']:
            excuse_reason = lg['excuse_note']

        rows.append(
            {
                'code': lg['course_code'] or '',
                'subject': lg['subject_name'] or '',
                'class_type': (lg['class_type'] or 'lecture').capitalize(),
                'teacher': lg['teacher_name'] or '',
                'date': lg['started_at'] or '',
                'time_slot': lg['time_slot'] or '',
                'tx_hash': lg['tx_hash'] or '—',
                'block': str(lg['block_number']) if lg['block_number'] else '—',
                'status': (lg['status'] or '').capitalize(),
                'excuse': excuse_reason or '—',
                'document': ex.get('attachment_file') or '—',
            }
        )

    return rows

def chain_status_code(status: str) -> int:
    return {
        'present': 0,
        'late': 1,
        'absent': 2,
        'excused': 3,
    }.get((status or '').lower(), 0)

def send_contract_tx(contract_fn):
    if not (BLOCKCHAIN_ONLINE and contract and admin_account):
        raise RuntimeError('Blockchain tx unavailable: missing connection, contract, or signer.')
    if ADMIN_PRIVATE_KEY:
        for attempt in range(3):
            with BLOCKCHAIN_LOCK:
                nonce = web3.eth.get_transaction_count(admin_account, 'pending')
                tx = contract_fn.build_transaction({
                    'from': admin_account,
                    'nonce': nonce,
                    'chainId': int(web3.eth.chain_id),
                })
                
                # Estimate gas
                try:
                    tx['gas'] = int(web3.eth.estimate_gas(tx) * 1.3)
                except:
                    tx['gas'] = 1000000

                # Set gas prices with extra padding for speed
                try:
                    latest = web3.eth.get_block('latest')
                    base = latest.get('baseFeePerGas', 0)
                    priority = int(web3.eth.max_priority_fee * 1.5) # 50% more priority
                    tx['maxPriorityFeePerGas'] = priority
                    tx['maxFeePerGas'] = int(base * 2 + priority)
                    if 'gasPrice' in tx: del tx['gasPrice']
                except:
                    tx['gasPrice'] = int(web3.eth.gas_price * 1.2) # 20% buffer

                try:
                    signed = web3.eth.account.sign_transaction(tx, ADMIN_PRIVATE_KEY)
                    raw = getattr(signed, 'raw_transaction', None) or signed.rawTransaction
                    return web3.eth.send_raw_transaction(raw)
                except Exception as e:
                    err_msg = str(e).lower()
                    if 'underpriced' in err_msg or 'nonce' in err_msg or 'already known' in err_msg:
                        print(f"[BLOCKCHAIN] Nonce collision/underpriced (Attempt {attempt+1}). Retrying...")
                        time.sleep(1.0) # Wait for mempool to settle
                        continue
                    raise e
        return None

    return contract_fn.transact({'from': admin_account})

def ensure_student_registered_on_chain(nfc_id: str, name: str):
    """Checks if a student is registered on-chain and registers them if not."""
    if not (BLOCKCHAIN_ONLINE and contract and admin_account):
        return False
    try:
        # Check registration status
        st_info = contract.functions.studentsByNfc(nfc_id).call()
        # st_info is (name, nfcId, isRegistered)
        if st_info[2]: # isRegistered
            return True
            
        print(f"[BLOCKCHAIN] Auto-registering student {nfc_id} ({name}) on-chain...")
        tx = send_contract_tx(
            contract.functions.registerStudent(
                "0x0000000000000000000000000000000000000000", # No address needed for this simplified version
                nfc_id,
                name
            )
        )
        if tx:
            web3.eth.wait_for_transaction_receipt(tx)
            return True
    except Exception as e:
        print(f"[BLOCKCHAIN ERROR] Auto-registration failed for {nfc_id}: {e}")
    return False

def mark_attendance_on_chain(nfc_id: str, status: str):
    if not (BLOCKCHAIN_ONLINE and contract and admin_account):
        return "", 0
    try:
        # Auto-register if needed
        st = get_student_by_nfc_cached(nfc_id)
        if st:
            ensure_student_registered_on_chain(nfc_id, st.get('name', 'Unknown'))
            
        tx = send_contract_tx(
            contract.functions.markAttendanceWithStatus(
                nfc_id, chain_status_code(status)
            )
        )
        receipt = web3.eth.wait_for_transaction_receipt(tx)
        return receipt['transactionHash'].hex(), receipt['blockNumber']
    except Exception as e:
        print(f"[BLOCKCHAIN ERROR] mark_attendance_on_chain for {nfc_id}: {e}")
        return "", 0

def mask_teacher_name(name):
    if not name: return ""
    parts = name.split()
    masked = []
    for p in parts:
        if len(p) <= 2:
            masked.append(p[0] + "*")
        else:
            # Mask middle: J**** N***** or J***s N****o
            masked.append(p[0] + "*" * (len(p)-2) + p[-1])
    return " ".join(masked)

def record_session_on_chain(session_id: str, subject_name: str, teacher_name: str, 
                            start_val, end_val, students_data: list,
                            course_code="", class_type="", section_key="", semester=""):
    """
    Record entire session attendance data to blockchain using recordSession().
    students_data = [(nfc_id1, 'present'), (nfc_id2, 'late'), ...]
    start_val/end_val can be ISO strings or Unix timestamps.
    Returns (tx_hash, block_number, error_msg)
    """
    if not (BLOCKCHAIN_ONLINE and contract and admin_account):
        reason = []
        if not BLOCKCHAIN_ONLINE: reason.append("RPC Offline")
        if not contract: reason.append("Contract NULL")
        if not admin_account: reason.append("Admin Account NULL")
        return None, None, f"Blockchain unavailable: {', '.join(reason)}"
        
    try:
        # Parse timestamps → Unix
        if isinstance(start_val, str):
            start_dt = datetime.strptime(start_val, '%Y-%m-%d %H:%M:%S')
            start_ts = int(start_dt.timestamp())
        else:
            start_ts = int(start_val)
            
        if isinstance(end_val, str):
            end_dt = datetime.strptime(end_val, '%Y-%m-%d %H:%M:%S')
            end_ts = int(end_dt.timestamp())
        else:
            end_ts = int(end_val)
            
        if end_ts <= start_ts:
            end_ts = start_ts + 1
        
        # ── Build logData for blockchain event ─────────────────────────
        m_teacher = mask_teacher_name(teacher_name)
        log_date = ""
        try:
            if isinstance(start_val, str):
                dt = datetime.strptime(start_val, '%Y-%m-%d %H:%M:%S')
                log_date = dt.strftime('%B %d %Y')
            else:
                dt = datetime.fromtimestamp(start_val)
                log_date = dt.strftime('%B %d %Y')
        except:
            log_date = _now_local().strftime('%B %d %Y')

        # Include course code and subject in the first line of logData
        # Instructor Name: J***s N****o,
        # Course Code: COSC80,
        # Class Type: (lab or lecture),
        # Program, Year, Sem, Section,
        # April 21 2026 (Date of the session),
        
        sec_parts = section_key.replace('|', ', ') if section_key else "—"
        log_lines = [
            f"Instructor Name: {m_teacher}",
            f"Course Code: {course_code or '—'}",
            f"Class Type: {(class_type or 'lecture').upper()}",
            f"{sec_parts}{', ' + semester if semester else ''}",
            f"{log_date}",
            "Attendance Log (ID - NFC - STATUS):"
        ]
        
        nfc_ids = []
        status_codes = []
        for item in students_data:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                print(f"[BLOCKCHAIN ERROR] Invalid student data item: {item}")
                continue
                
            nfc_id, status = item[0], item[1]
            nfc_ids.append(nfc_id)
            status_codes.append(chain_status_code(status))
            
            # Fetch student_id if possible for the log
            st = get_student_by_nfc_cached(nfc_id)
            sid = st.get('student_id', 'N/A') if st else 'N/A'
            log_lines.append(f"{sid}({nfc_id} - {status.upper()})")
            
        log_data = "\n".join(log_lines)
        
        print(f"[BLOCKCHAIN] Recording session {session_id}: {len(nfc_ids)} students")
        
        tx_hash_obj = send_contract_tx(
            contract.functions.recordSession(
                session_id,
                subject_name,
                teacher_name,
                start_ts,
                end_ts,
                nfc_ids,
                status_codes,
                log_data
            )
        )
        
        if not tx_hash_obj:
            return None, None, "Transaction submission failed (send_contract_tx returned None)"
            
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash_obj)
        tx_hash = receipt['transactionHash'].hex()
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash
        block_num = receipt['blockNumber']
        
        print(f"[BLOCKCHAIN] Session {session_id} recorded: TX={tx_hash[:16]}... Block={block_num}")
        return tx_hash, block_num, None
        
    except Exception as e:
        err = str(e)
        print(f"[ERROR] record_session_on_chain {session_id}: {err}")
        import traceback
        traceback.print_exc()
        return None, None, err

def get_student_by_nfc_cached(nfc_id: str):
    st = db_get_student(nfc_id)
    if st:
        return st
    return next((s for s in get_all_students() if s.get('nfcId') == nfc_id), None)

def get_student_attendance_stats(nfc_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT al.status FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "WHERE al.nfc_id=? AND s.ended_at IS NOT NULL",
            (nfc_id,)
        ).fetchall()
    total = late = excused = present = absent = 0
    for row in rows:
        status = row['status']
        total += 1
        if   status == 'excused': excused += 1
        elif status == 'late':    late    += 1
        elif status == 'present': present += 1
        else:                     absent  += 1
    attended = present + late
    rate = round(attended / total * 100, 1) if total else 0
    return {'total': total, 'present': present + late, 'late': late,
            'excused': excused, 'absent': absent, 'rate': rate}

# Course name alias map was moved to module load phase for initialize access


def student_matches_section(student, allowed_keys: set) -> bool:
    """
    Returns True if the student belongs to any section in allowed_keys.
    Handles course-name alias mismatches (e.g. BSIT vs BS Information Technology).
    """
    key = build_student_section_key(student)
    if key is None:
        return False
    if key in allowed_keys:
        return True
    # Try with canonical course name
    course = normalize_course_name(student.get('course') or '')
    year   = (student.get('year_level') or '').strip()
    sec    = (student.get('section') or '').strip().upper()
    if course and year and sec:
        normalized_key = normalize_section_key(f"{course}|{year}|{sec}")
        if normalized_key in allowed_keys:
            return True
    return False


def teacher_students(user):
    if not user: return []
    full_name = str(user.get('full_name', '')).strip().lower()
    if not full_name: return []
    
    all_students = db_get_all_students() or get_all_students()
    # Filter students where the 'adviser' field matches the teacher's full name
    return [
        s for s in all_students 
        if str(s.get('adviser') or '').strip().lower() == full_name
    ]

def get_active_sessions():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
        result = {}
        for r in rows:
            s = _session_row_with_logs(conn, r)
            result[r['sess_id']] = s
    return result

def _prepare_session_blockchain_data(sess_id, sess):
    """
    ═══════════════════════════════════════════════════════════════════
    Prepare and record comprehensive session attendance data on blockchain.
    
    Records entire session metadata with:
    - Session ID, subject, teacher, timing
    - Total enrolled/present/late/absent/excused counts
    - Individual student statuses in single transaction
    ═══════════════════════════════════════════════════════════════════
    """
    try:
        with get_db() as conn:
            # Get all attendance records for this session
            records = conn.execute(
                """SELECT nfc_id, status, tap_time, tx_hash, block_number 
                   FROM attendance_logs WHERE sess_id=? ORDER BY tap_time""",
                (sess_id,)
            ).fetchall()
            
            # Calculate summary stats
            summary = {
                'sess_id': sess_id,
                'subject_name': sess.get('subject_name', ''),
                'subject_id': sess.get('subject_id', ''),
                'teacher_name': sess.get('teacher_name', ''),
                'teacher_username': sess.get('teacher', ''),
                'section_key': sess.get('section_key', ''),
                'started_at': sess.get('started_at', ''),
                'ended_at': sess.get('ended_at', ''),
                'class_type': sess.get('class_type', 'lecture'),
                'attendance_records': len(records),
                'on_chain_records': len([r for r in records if r.get('tx_hash')]),
            }
            
            # Count by status
            status_counts = {}
            for status in ['present', 'late', 'absent', 'excused']:
                count = len([r for r in records if r.get('status') == status])
                summary[f'total_{status}'] = count
                status_counts[status] = count
            
            # Prepare arrays for blockchain recording
            student_nfc_ids = [r['nfc_id'] for r in records]
            student_statuses = [r['status'] for r in records]
            
            # Record session to blockchain if online
            tx_hash = None
            block_number = None
            
            if BLOCKCHAIN_ONLINE and contract and admin_account and student_nfc_ids:
                try:
                    # Convert ISO datetime to Unix timestamp
                    start_dt = datetime.strptime(sess.get('started_at', '2000-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(sess.get('ended_at', '2000-01-01 00:00:01'), '%Y-%m-%d %H:%M:%S')
                    start_timestamp = int(start_dt.timestamp())
                    end_timestamp = int(end_dt.timestamp())
                    
                    # Prepare students data as a list of tuples (nfc_id, status)
                    students_data = list(zip(student_nfc_ids, student_statuses))
                    
                    tx_hash, block_number = record_session_on_chain(
                        sess_id,
                        summary['subject_name'],
                        summary['teacher_name'],
                        start_timestamp,
                        end_timestamp,
                        students_data
                    )
                    
                    if tx_hash:
                        # Update session with transaction hash
                        conn.execute(
                            "UPDATE sessions SET session_tx_hash=?, session_block_number=? WHERE sess_id=?",
                            (tx_hash, block_number, sess_id)
                        )
                        summary['session_tx_hash'] = tx_hash
                        summary['session_block_number'] = block_number
                        print(f"[BLOCKCHAIN] Session {sess_id} recorded: TX={tx_hash[:16]}... Block={block_number}")
                    else:
                        print(f"[BLOCKCHAIN] Failed to record session {sess_id} to blockchain")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to record session to blockchain: {e}")
            
            # Store session summary for auditing
            conn.execute(
                """INSERT OR REPLACE INTO sessions 
                   (sess_id, started_at, ended_at) 
                   VALUES (?, ?, ?)""",
                (sess_id, summary.get('started_at'), summary.get('ended_at'))
            )
            
        print(f"[SESSION] Session {sess_id} blockchain data prepared: "
              f"Present={summary.get('total_present')}, "
              f"Late={summary.get('total_late')}, "
              f"Absent={summary.get('total_absent')}, "
              f"Excused={summary.get('total_excused')}, "
              f"TxHash={tx_hash[:16] + '...' if tx_hash else 'PENDING'}")
        
        return summary
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare session blockchain data: {e}")
        return None



def _finalize_session(sess_id, ended_time=None, async_chain_and_email=True):
    """Finalize a live session and keep DB/UI/blockchain/email in sync."""
    sess = load_session(sess_id)
    if not sess:
        return None
        
    # Check if already has tx_hash in DB before anything else
    with get_db() as conn:
        db_sess = conn.execute("SELECT session_tx_hash, session_block_number, ended_at FROM sessions WHERE sess_id=?", (sess_id,)).fetchone()
        if db_sess and db_sess['session_tx_hash']:
            print(f"[FINALIZE] Session {sess_id} already has TX in DB: {db_sess['session_tx_hash']}")
            return {
                'already_ended': True,
                'ended_at': db_sess['ended_at'],
                'tx_hash': db_sess['session_tx_hash'],
                'present_count': len(sess.get('present', [])),
                'late_count': len(sess.get('late', [])),
                'absent_count': len(sess.get('absent', [])),
                'excused_count': len(sess.get('excused', [])),
            }

    if sess.get('ended_at'):
        return {'already_ended': True, 'ended_at': sess.get('ended_at', '')}

    all_students_list = get_all_students()
    section_key = normalize_section_key(sess.get('section_key', ''))
    sess_semester = normalize_semester(sess.get('semester') or '')
    
    # Filter students belonging to this section & semester
    section_students = [
        s for s in all_students_list 
        if build_student_section_key(s) == section_key
        and (not sess_semester or not normalize_semester(s.get('semester')) or normalize_semester(s.get('semester')) == sess_semester)
    ]
    
    if not section_students:
        print(f"[DEBUG] _finalize_session {sess_id}: NO STUDENTS FOUND for section='{section_key}', sem='{sess_semester}'")
        # Log a sample student to see why it doesn't match
        if all_students_list:
            s0 = all_students_list[0]
            print(f"[DEBUG] Sample Student Key: '{build_student_section_key(s0)}', Sem: '{str(s0.get('semester') or '').strip().lower()}'")

    present_set = set(sess.get('present', []))
    late_set = set(sess.get('late', []))
    excused_set = set(sess.get('excused', []))

    with get_db() as conn:
        excused_from_db = conn.execute(
            "SELECT DISTINCT nfc_id FROM attendance_logs WHERE sess_id=? AND status='excused'",
            (sess_id,)
        ).fetchall()
        approved_excuse_requests = conn.execute(
            "SELECT DISTINCT nfc_id FROM excuse_requests WHERE sess_id=? AND status='approved'",
            (sess_id,)
        ).fetchall()
    excused_set.update([row['nfc_id'] for row in excused_from_db])
    excused_set.update([row['nfc_id'] for row in approved_excuse_requests])

    ended_at = ended_time or _now_local().strftime('%Y-%m-%d %H:%M:%S')
    absent_ids = []
    for st in section_students:
        nid = st['nfcId']
        if nid in present_set or nid in excused_set:
            continue
        db_save_attendance_log(
            sess_id=sess_id,
            nfc_id=nid,
            student_name=st.get('name', ''),
            student_id=st.get('student_id', ''),
            status='absent',
            tap_time=ended_at,
            tx_hash='',
            block_number=0,
        )
        absent_ids.append(nid)

    # ── Step 1: Mark session as ended in DB immediately ─────────────────────
    # IMPORTANT: This MUST run before the blockchain call so that sessions are
    # always marked as ended even if the blockchain call fails or times out.
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET total_enrolled=?, ended_at=? WHERE sess_id=?",
            (len(section_students), ended_at, sess_id)
        )

    sess['ended_at'] = ended_at
    sess['absent'] = absent_ids
    sessions_db[sess_id] = sess
    print(f"[FINALIZE] Session {sess_id} marked ended_at={ended_at} in DB.")

    # ── Step 2: Fetch logs and record to blockchain ───────────────────────────
    # Blockchain call is now outside the DB context manager to avoid holding
    # a connection open during a potentially slow/blocking blockchain operation.
    tx_hash = None
    block_num = None
    bc_error = None
    try:
        with get_db() as conn:
            logs = conn.execute(
                "SELECT nfc_id, status FROM attendance_logs WHERE sess_id=?",
                (sess_id,)
            ).fetchall()
        students_data = [(row['nfc_id'], row['status']) for row in logs]
        start_iso = sess.get('started_at', ended_at)
        tx_hash, block_num, bc_error = record_session_on_chain(
            session_id=sess_id,
            subject_name=sess.get('subject_name', 'Class Session'),
            teacher_name=sess.get('teacher_name', 'Teacher'),
            start_val=start_iso,
            end_val=ended_at,
            students_data=students_data,
            course_code=sess.get('course_code', ''),
            class_type=sess.get('class_type', ''),
            section_key=sess.get('section_key', ''),
            semester=sess.get('semester', '')
        )
        if tx_hash:
            print(f"[\u2705 BLOCKCHAIN] Session {sess_id} TX={tx_hash[:16]}...")
        else:
            print(f"[\u26a0\ufe0f ] Session {sess_id} blockchain record skipped/failed: {bc_error}")
    except Exception as _bc_err:
        bc_error = str(_bc_err)
        print(f"[\u26a0\ufe0f BLOCKCHAIN] Session {sess_id} blockchain call raised: {_bc_err}")

    # ── Step 3: Persist TX hash and sync attendance logs ─────────────────────
    if tx_hash:
        with get_db() as conn:
            conn.execute(
                "UPDATE sessions SET session_tx_hash=?, session_block_number=? WHERE sess_id=?",
                (tx_hash, block_num or 0, sess_id)
            )
            # Synchronize all attendance logs with session TX hash and block number
            conn.execute(
                "UPDATE attendance_logs SET tx_hash=?, block_number=? WHERE sess_id=?",
                (tx_hash, block_num or 0, sess_id)
            )
        print(f"[✅ BLOCKCHAIN] Session {sess_id} synced with TX={tx_hash[:16]}...")
    else:
        print(f"[⚠️] Session {sess_id} blockchain skipped/failed: {bc_error}")

    # Reload to get latest state (including TX hash if blockchain succeeded)
    sess = load_session(sess_id)
    save_session(sess_id, sess)
    sessions_db[sess_id] = sess

    def _post_finalize_worker():
        with app.app_context():
            # REDUNDANT: Individual "Absent" marks are now avoided to prevent blockchain congestion.
            # The record_session_on_chain call already includes status for all students.

            for st in section_students:
                nid = st['nfcId']
                if nid in present_set or nid in excused_set:
                    continue
                try:
                    with get_db() as conn:
                        lg = conn.execute(
                            "SELECT tx_hash, block_number FROM attendance_logs WHERE sess_id=? AND nfc_id=?",
                            (sess_id, nid)
                        ).fetchone()
                    send_student_attendance_receipt(
                        student_name=st.get('name', nid),
                        student_email=st.get('email', ''),
                        student_id=st.get('student_id', ''),
                        subject_name=sess.get('subject_name', ''),
                        section_key=sess.get('section_key', ''),
                        teacher_name=sess.get('teacher_name', ''),
                        tap_time=ended_at,
                        status='absent',
                        tx_hash=lg['tx_hash'] if lg else '',
                        block_num=lg['block_number'] if lg else '',
                        sess_id=sess_id,
                        nfc_id=nid,
                        semester=sess.get('semester'),
                        time_slot=sess.get('time_slot'),
                    )
                except Exception as e:
                    print(f"[EMAIL] Failed absence email for {nid}: {e}")

            # Send final receipts to all students (Present, Late, Excused) with the session TX hash
            for st in section_students:
                nid = st['nfcId']
                if nid in absent_ids: # Already handled above
                    continue
                try:
                    with get_db() as conn:
                        lg = conn.execute(
                            "SELECT status, tap_time, tx_hash, block_number FROM attendance_logs WHERE sess_id=? AND nfc_id=?",
                            (sess_id, nid)
                        ).fetchone()
                    if lg:
                        send_student_attendance_receipt(
                            student_name=st.get('name', nid),
                            student_email=st.get('email', ''),
                            student_id=st.get('student_id', ''),
                            subject_name=sess.get('subject_name', ''),
                            section_key=sess.get('section_key', ''),
                            teacher_name=sess.get('teacher_name', ''),
                            tap_time=lg['tap_time'] or ended_at,
                            status=lg['status'],
                            tx_hash=lg['tx_hash'] or tx_hash or '',
                            block_num=lg['block_number'] or block_num or 0,
                            sess_id=sess_id,
                            nfc_id=nid,
                            semester=sess.get('semester'),
                            time_slot=sess.get('time_slot'),
                        )
                except Exception as e:
                    print(f"[EMAIL] Failed final receipt email for {nid}: {e}")

            try:
                users = db_get_all_users()
                teacher_username = sess.get('teacher_username', '') or sess.get('teacher', '')
                teacher_email = users.get(teacher_username, {}).get('email', '')
                if teacher_email:
                    logs = {lg['nfc_id']: lg for lg in db_get_session_attendance(sess_id)}
                    present_count = late_count = absent_count = excused_count = 0
                    rows = []
                    for st in section_students:
                        nid = st['nfcId']
                        lg = logs.get(nid, {})
                        st_status = (lg.get('status') or 'absent').lower() if lg else 'absent'
                        if st_status == 'late':
                            late_count += 1
                        elif st_status == 'present':
                            present_count += 1
                        elif st_status == 'excused':
                            excused_count += 1
                        else:
                            absent_count += 1
                        rows.append({
                            'name': st.get('name', '—'),
                            'student_id': st.get('student_id', ''),
                            'status': st_status,
                            'tap_time': lg.get('tap_time', '—') if lg else '—',
                            'tx_hash': lg.get('tx_hash', '') if lg else '',
                            'block_num': lg.get('block_number', '') if lg else '',
                        })
                    
                    # Reload session to get the latest TX hash/block
                    fresh_sess = load_session(sess_id)
                    session_tx_hash = fresh_sess.get('session_tx_hash', '')
                    session_block_number = fresh_sess.get('session_block_number', 0)
                    
                    send_teacher_session_summary(
                        teacher_email=teacher_email,
                        teacher_name=sess.get('teacher_name', ''),
                        subject_name=sess.get('subject_name', ''),
                        section_key=sess.get('section_key', ''),
                        time_slot=sess.get('time_slot', ''),
                        started_at=sess.get('started_at', ''),
                        ended_at=ended_at,
                        present_count=present_count,
                        late_count=late_count,
                        absent_count=absent_count,
                        excused_count=excused_count,
                        student_rows=rows,
                        session_tx_hash=session_tx_hash,
                        session_block_number=session_block_number,
                        course_code=sess.get('course_code', ''),
                        semester=sess.get('semester', ''),
                    )
            except Exception as e:
                print(f"[EMAIL] Teacher summary error: {e}")

    if async_chain_and_email:
        Thread(target=_post_finalize_worker, daemon=True).start()
    else:
        _post_finalize_worker()

    return {
        'already_ended': False,
        'ended_at': ended_at,
        'present_count': len([n for n in present_set if n not in late_set]),
        'late_count': len(late_set),
        'absent_count': len(absent_ids),
        'excused_count': len(excused_set),
        'total_enrolled': len(section_students),
        'tx_hash': tx_hash,
        'bc_error': bc_error,
    }

def get_active_session_for_nfc(nfc_id, preferred_sess_id=None):
    all_students = get_all_students()
    student = next((s for s in all_students if s['nfcId'] == nfc_id), None)
    if not student: return None, None
    student_key = build_student_section_key(student)
    if not student_key: return None, None

    student_semester = normalize_semester(student.get('semester'))

    preferred = str(preferred_sess_id or '').strip()
    if preferred:
        with get_db() as conn:
            pref_row = conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL AND sess_id=? LIMIT 1",
                (preferred,),
            ).fetchone()

            if pref_row:
                pref_dict = dict(pref_row)
                pref_section = normalize_section_key(pref_dict.get('section_key', ''))
                pref_semester = normalize_semester(pref_dict.get('semester'))
                pref_class_type = str(pref_dict.get('class_type', 'lecture') or 'lecture').strip().lower()

                # Normal schedules must match both student's section AND semester.
                if pref_section == student_key and (not pref_semester or not student_semester or pref_semester == student_semester):
                    s = _session_row_with_logs(get_db(), pref_row)
                    return pref_row['sess_id'], s

                # School events can have sibling sessions (same event_id) for other sections.
                if pref_class_type == 'school_event':
                    meta = _parse_event_schedule_id(pref_dict.get('schedule_id', ''))
                    if meta and meta.get('event_id'):
                        pattern = f"event:{meta['event_id']}:%:{student_key}"
                        sibling = conn.execute(
                            "SELECT * FROM sessions "
                            "WHERE ended_at IS NULL AND class_type='school_event' AND schedule_id LIKE ? "
                            "ORDER BY started_at DESC LIMIT 1",
                            (pattern,),
                        ).fetchone()
                        if sibling:
                            # For school events, we might be more lenient with semester, 
                            # but let's check it anyway if it's available.
                            sib_dict = dict(sibling)
                            sib_semester = normalize_semester(sib_dict.get('semester'))
                            if not student_semester or not sib_semester or student_semester == sib_semester:
                                s = _session_row_with_logs(get_db(), sibling)
                                return sibling['sess_id'], s

                # Preferred session provided but doesn't match this student's context.
                return None, None

        return None, None

    with get_db() as conn:
        # Strict match: same section key AND same semester (with leniency for missing data)
        if student_semester:
            row = conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL AND section_key=? "
                "AND (semester IS NULL OR semester = '' OR lower(trim(semester)) = ?) "
                "ORDER BY started_at DESC LIMIT 1",
                (student_key, student_semester)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL AND section_key=? "
                "ORDER BY started_at DESC LIMIT 1",
                (student_key,)
            ).fetchone()
    if row:
        s = _session_row_with_logs(get_db(), row)
        return row['sess_id'], s
    return None, None

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index') if session.get('role') in ADMIN_ROLES else url_for('teacher_dashboard'))
    if request.method == 'POST':
        u    = request.form['username'].strip().lower()
        p    = request.form['password']
        user = db_get_user(u)
        if not user or user['password'] != hash_password(p):
            flash('Invalid username or password.'); return redirect(url_for('login'))
        if user['status'] == 'pending':
            flash('Your account is pending admin approval.'); return redirect(url_for('login'))
        if user['status'] == 'rejected':
            flash('Your account was rejected.'); return redirect(url_for('login'))
        session.update({'username':u,'role':user['role'],'full_name':user['full_name']})
        return redirect(url_for('index') if user['role'] in ADMIN_ROLES else url_for('teacher_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    flash('Self-signup is disabled. Please contact your administrator for account creation.')
    return redirect(url_for('login'))

# ── ADMIN MAIN ────────────────────────────────────────────────────────────────

@app.route('/')
@admin_required
def index():
    raw_active = get_active_sessions()

    def _event_id(sess):
        class_type = str((sess or {}).get('class_type', 'lecture') or 'lecture').strip().lower()
        if class_type != 'school_event':
            return None
        schedule_id = str((sess or {}).get('schedule_id', '') or '').strip()
        if schedule_id.startswith('event:'):
            parts = schedule_id.split(':', 3)
            if len(parts) == 4:
                return parts[1]
        subject_id = str((sess or {}).get('subject_id', '') or '').strip()
        if subject_id.startswith('event:'):
            return subject_id.split(':', 1)[1]
        return None

    unified_active = {}
    event_buckets = {}
    for sid, sess in raw_active.items():
        ev_id = _event_id(sess)
        if not ev_id:
            unified_active[sid] = sess
            continue

        if ev_id not in event_buckets:
            base = dict(sess or {})
            event_buckets[ev_id] = {
                'sid': sid,
                'base': base,
                'sections': set(),
                'teachers': set(),
                'present_ids': set(str(x) for x in (base.get('present') or [])),
            }

        bucket = event_buckets[ev_id]
        section_key = str((sess or {}).get('section_key', '') or '').strip()
        teacher_name = str((sess or {}).get('teacher_name', '') or '').strip()
        if section_key:
            bucket['sections'].add(section_key)
        if teacher_name:
            bucket['teachers'].add(teacher_name)
        for pid in (sess or {}).get('present') or []:
            bucket['present_ids'].add(str(pid))

    for bucket in event_buckets.values():
        merged = bucket['base']
        if bucket['sections']:
            merged['section_key'] = ' | '.join(sorted(bucket['sections']))
        if bucket['teachers']:
            merged['teacher_name'] = ', '.join(sorted(bucket['teachers']))
        merged['present'] = sorted(bucket['present_ids'])
        unified_active[bucket['sid']] = merged

    all_students = get_all_students()
    active_students = [s for s in all_students if s.get('student_status', 'active').lower() == 'active']

    return render_template('index.html',
                           active_sessions=unified_active,
                           subjects_db=db_get_all_subjects(),
                           users_db=db_get_all_users(),
                           active_student_count=len(active_students))

def _register_save_pending_subjects(req, sess):
    import json as _json
    from datetime import datetime as _dt
    import uuid as _uuid
    pending_raw = req.form.get('pending_subjects_json', '[]').strip()
    try:
        pending = _json.loads(pending_raw) if pending_raw else []
    except Exception:
        pending = []
    if not pending:
        return 0
    all_existing = db_get_all_subjects()
    existing_codes = {v.get('course_code', '').upper(): k for k, v in all_existing.items()}
    saved_count = 0
    for subj in pending:
        code_upper = (subj.get('course_code') or '').upper().strip()
        name_val   = (subj.get('name') or '').strip()
        if not name_val:
            continue
        if code_upper and code_upper in existing_codes:
            continue
        new_id = str(_uuid.uuid4())[:8]
        db_save_subject(new_id, {
            'name':        name_val,
            'course_code': subj.get('course_code', ''),
            'units':       str(subj.get('units', '3')),
            'created_by':  sess.get('username', 'admin'),
            'created_at':  _dt.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        if code_upper:
            existing_codes[code_upper] = new_id
        saved_count += 1
    return saved_count

@app.route('/admin/settings', methods=['GET'])
@admin_required
def admin_settings():
    cfg = get_email_config()
    return render_template('admin_settings.html', cfg=cfg)
 
@app.route('/admin/settings/save', methods=['POST'])
@admin_required
def admin_settings_save():
    cfg = {
        'smtp_host':     request.form.get('smtp_host',     'smtp.gmail.com').strip(),
        'smtp_port':     request.form.get('smtp_port',     '587').strip(),
        'smtp_user':     request.form.get('smtp_user',     '').strip(),
        'smtp_password': request.form.get('smtp_password', '').strip(),
        'smtp_from':     request.form.get('smtp_from',     '').strip(),
        'enabled':       '1' if request.form.get('enabled') else '0',
    }
    save_email_config(cfg)
    flash('Email settings saved successfully.')
    return redirect(url_for('admin_settings'))
 
@app.route('/admin/settings/test', methods=['POST'])
@admin_required
def admin_settings_test():
    """Send a test email to verify SMTP config."""
    cfg = get_email_config()
    test_to = request.form.get('test_email', '').strip()
    if not test_to or '@' not in test_to:
        return jsonify({'ok': False, 'message': 'Invalid email address.'})
    if cfg.get('enabled') != '1':
        return jsonify({'ok': False, 'message': 'Email notifications are disabled. Enable them first.'})
    if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
        return jsonify({'ok': False, 'message': 'SMTP credentials not configured.'})
    try:
        host = cfg.get('smtp_host', 'smtp.gmail.com').lower().strip()
        test_to = request.form.get('test_email', '').strip()
        from_email = cfg.get('smtp_from') or cfg['smtp_user']
        
        html_content = f'''
        <div style="font-family:Arial,sans-serif;padding:24px;max-width:480px;">
          <div style="font-size:20px;font-weight:700;color:#1E4A1A;margin-bottom:8px;">
            ✓ DAVS Email Test Successful
          </div>
          <p style="color:#555;font-size:13px;">
            Your configuration is working correctly!<br>
            Email notifications will be sent from:
            <strong>{from_email}</strong>
          </p>
        </div>'''

        # ── SENDGRID HTTP API BYPASS ──
        if 'sendgrid.net' in host or cfg.get('smtp_user') == 'apikey':
            import urllib.request
            import json
            
            url = "https://api.sendgrid.com/v3/mail/send"
            headers = {
                "Authorization": f"Bearer {cfg['smtp_password'].strip()}",
                "Content-Type": "application/json"
            }
            data = {
                "personalizations": [{"to": [{"email": test_to}]}],
                "from": {"email": from_email},
                "subject": "[DAVS] Test Email — SendGrid API Verified",
                "content": [{"type": "text/html", "value": html_content}]
            }
            
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            try:
                urllib.request.urlopen(req, timeout=10)
                return jsonify({'ok': True, 'message': f'Test email sent instantly via SendGrid API (Port 443 Bypass).'})
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                return jsonify({'ok': False, 'message': f'SendGrid API Error: {e.code} - {err_body}'})
            except Exception as e:
                return jsonify({'ok': False, 'message': f'API Network Error: {str(e)}'})

        # ── STANDARD SMTP ROUTE (Gmail, etc.) ──
        import smtplib, ssl, threading, socket
        from email.mime.multipart import MIMEMultipart
        from email.mime.text      import MIMEText
        
        msg            = MIMEMultipart('alternative')
        msg['Subject'] = '[DAVS] Test Email — SMTP Configuration Verified'
        msg['From']    = from_email
        msg['To']      = test_to
        msg.attach(MIMEText(html_content, 'html'))

        result_box = {'ok': False, 'message': 'Test timed out.'}
        
        def _test_worker():
            try:
                ctx  = ssl.create_default_context()
                port = int(cfg.get('smtp_port', 587))
                
                try:
                    addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                    target_ip = addr_info[0][4][0]
                except Exception:
                    target_ip = host

                if port == 465:
                    srv = smtplib.SMTP_SSL(target_ip, port, context=ctx, timeout=10)
                else:
                    srv = smtplib.SMTP(target_ip, port, timeout=10)
                    srv.ehlo()
                    if srv.has_ext('STARTTLS'):
                        srv._host = host 
                        srv.starttls(context=ctx)
                        srv.ehlo()

                with srv:
                    srv.login(cfg['smtp_user'], cfg['smtp_password'])
                    srv.sendmail(msg['From'], [test_to], msg.as_string())
                
                result_box['ok'] = True
                result_box['message'] = f'Test email sent to {test_to}'
            except Exception as e:
                result_box['message'] = f'Network Error: {str(e)}'

        t = threading.Thread(target=_test_worker, daemon=True)
        t.start()
        t.join(timeout=15)
        
        if t.is_alive():
             return jsonify({'ok': False, 'message': f'Connection Timed Out. Port {cfg.get("smtp_port")} is completely blocked by your host.'})
        
        return jsonify(result_box)
    except Exception as e:
        return jsonify({'ok': False, 'message': f'System Error: {str(e)}'})


# ═══════════════════════════════════════════════════════════════════════════
# ALUMNI & STUDENT MANAGEMENT ROUTES
# NOTE: Student management UI has been integrated into /dashboard (Students tab)
# These API endpoints support the alumni/semester features in Students & Faculty
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/students', methods=['GET'])
@admin_required
def admin_students():
    """Redirect to dashboard for student management."""
    return redirect(url_for('dashboard'))


@app.route('/api/students/all', methods=['GET'])
@admin_required
def api_get_all_students():
    """Fetch all students with status and enrollment info."""
    try:
        with get_db() as conn:
            students = conn.execute(
                """SELECT nfcId, full_name, student_id, email, 
                           semester, school_year, student_status 
                   FROM students ORDER BY full_name"""
            ).fetchall()
        
        return jsonify({
            'ok': True,
            'students': [dict(row) for row in students]
        })
    except Exception as e:
        print(f"[ERROR] Failed to fetch students: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/student/update-status/<nfc_id>', methods=['POST'])
@admin_required
def api_update_student_status(nfc_id):
    """Update a student's status (active/graduated/alumni)."""
    try:
        nfc_id = nfc_id.strip().upper()
        new_status = request.json.get('status', 'active')
        
        # Validate status
        if new_status not in ['active', 'graduated', 'alumni']:
            return jsonify({'ok': False, 'message': 'Invalid status'}), 400
        
        with get_db() as conn:
            # Check student exists
            student = conn.execute(
                "SELECT full_name FROM students WHERE nfcId=?",
                (nfc_id,)
            ).fetchone()
            
            if not student:
                return jsonify({'ok': False, 'message': 'Student not found'}), 404
            
            # Update status
            conn.execute(
                "UPDATE students SET student_status=? WHERE nfcId=?",
                (new_status, nfc_id)
            )
        
        print(f"[STUDENT] {student['full_name']} status changed to {new_status}")
        return jsonify({
            'ok': True,
            'message': f'Status updated to {new_status}',
            'status': new_status
        })
    
    except Exception as e:
        print(f"[ERROR] Failed to update student status: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/students/delete/<nfc_id>', methods=['POST'])
@admin_required
def api_delete_student(nfc_id):
    try:
        with get_db() as conn:
            # Delete attendance records first
            conn.execute("DELETE FROM attendance_logs WHERE nfc_id = ?", (nfc_id,))
            # Delete photos
            conn.execute("DELETE FROM photos WHERE person_id = ?", (nfc_id,))
            # Delete student
            conn.execute("DELETE FROM students WHERE nfc_id = ?", (nfc_id,))
        return jsonify({'success': True, 'message': 'Student and all associated records deleted successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/student/move-semester/<nfc_id>', methods=['POST'])
@admin_required
def api_move_student_semester(nfc_id):
    """Move student to next semester and update their enrollment."""
    try:
        nfc_id = nfc_id.strip().upper()
        data = request.json or {}
        
        new_semester = data.get('new_semester', '').strip()
        new_school_year = data.get('new_school_year', '').strip()
        
        # Validate inputs
        if new_semester not in ['First', 'Second', 'Summer']:
            return jsonify({'ok': False, 'message': 'Invalid semester'}), 400
        
        if not new_school_year or not new_school_year.replace('-', '').isdigit():
            return jsonify({'ok': False, 'message': 'Invalid school year format'}), 400
        
        with get_db() as conn:
            # Get student info
            student = conn.execute(
                """SELECT full_name, student_id, nfcId, semester, school_year 
                   FROM students WHERE nfcId=?""",
                (nfc_id,)
            ).fetchone()
            
            if not student:
                return jsonify({'ok': False, 'message': 'Student not found'}), 404
            
            old_sem = student.get('semester')
            old_year = student.get('school_year')
            
            # Update semester and school year
            conn.execute(
                """UPDATE students SET semester=?, school_year=? WHERE nfcId=?""",
                (new_semester, new_school_year, nfc_id)
            )
            
            # Log semester progression
            print(f"[SEMESTER] {student['full_name']} moved from {old_sem} {old_year} "
                  f"to {new_semester} {new_school_year}")
        
        return jsonify({
            'ok': True,
            'message': f'Moved to {new_semester} Semester {new_school_year}',
            'new_semester': new_semester,
            'new_school_year': new_school_year
        })
    
    except Exception as e:
        print(f"[ERROR] Failed to move student semester: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/students/move-up-all', methods=['POST'])
@admin_required
def api_move_up_all_students():
    """Move all active students to next semester with program-specific Summer handling.
    
    CS/IT Progression: 1st Year 1st → 1st Year 2nd → 2nd Year 1st → 2nd Year 2nd 
                      → 3rd Year 1st → 3rd Year 2nd → Summer/OJT → 4th Year 1st → 4th Year 2nd → Graduated
    
    Other Programs:    1st Year 1st → 1st Year 2nd → 2nd Year 1st → 2nd Year 2nd 
                      → 3rd Year 1st → 3rd Year 2nd → 4th Year 1st → 4th Year 2nd 
                      → Summer → Graduated
    """
    print("[API] Starting move-up-all operation...")
    
    CS_PROGRAMS = ['BS Computer Science', 'BS Information Technology', 'BS Information Systems']
    
    try:
        # Base progression (same for all)
        base_progression = [
            ('1st Year', 'First'),
            ('1st Year', 'Second'),
            ('2nd Year', 'First'),
            ('2nd Year', 'Second'),
            ('3rd Year', 'First'),
            ('3rd Year', 'Second'),
        ]
        
        # CS/IT specific progression
        cs_progression = base_progression + [
            ('3rd Year', 'Summer'),    # Summer/OJT for CS/IT
            ('4th Year', 'First'),
            ('4th Year', 'Second'),
        ]
        
        # Other programs progression
        other_progression = base_progression + [
            ('4th Year', 'First'),
            ('4th Year', 'Second'),
            ('4th Year', 'Summer'),    # Summer for other programs (after 4th year)
        ]
        
        conn = get_db()
        
        # Get all active students with their program
        students = conn.execute(
            """SELECT nfc_id, full_name, year_level, semester, school_year, program
               FROM students 
               WHERE student_status='active' 
               ORDER BY nfc_id"""
        ).fetchall()
        
        updated_count = 0
        skipped_count = 0
        graduated_count = 0
        
        print(f"[API] Found {len(students)} active students")
        
        for student in students:
            year_level = (student.get('year_level') or '').strip()
            current_sem = (student.get('semester') or 'First').strip()
            school_year = (student.get('school_year') or '2024-2025').strip()
            program = (student.get('program') or '').strip()
            nfc_id = student.get('nfc_id')
            full_name = student.get('full_name') or ''
            
            print(f"[API] Processing: {full_name} (Program: {program}, YL: {year_level}, SEM: {current_sem})")
            
            # Select progression based on program
            is_cs = any(cs_prog in program for cs_prog in CS_PROGRAMS)
            progression = cs_progression if is_cs else other_progression
            
            # Find current position in progression
            current_pos = None
            for idx, (yr_lvl, sem) in enumerate(progression):
                if yr_lvl == year_level and sem == current_sem:
                    current_pos = idx
                    break
            
            if current_pos is None:
                print(f"[API] SKIP: {full_name} - not in standard progression")
                skipped_count += 1
                continue
            
            next_pos = current_pos + 1
            
            if next_pos >= len(progression):
                # Graduated
                print(f"[API] UPDATE {full_name}: -> GRADUATED")
                conn.execute(
                    """UPDATE students SET student_status=%s WHERE nfc_id=%s""",
                    ('graduated', nfc_id)
                )
                graduated_count += 1
            else:
                next_year_level, next_sem = progression[next_pos]
                
                # Calculate new school year
                if next_sem == 'First' and current_sem == 'Second':
                    try:
                        [start, end] = school_year.split('-')
                        next_year = f"{int(end)}-{int(end) + 1}"
                    except:
                        next_year = school_year
                elif current_sem == 'Summer':
                    # Moving from Summer to next year's 1st sem
                    try:
                        [start, end] = school_year.split('-')
                        next_year = f"{int(end)}-{int(end) + 1}"
                    except:
                        next_year = school_year
                else:
                    next_year = school_year
                
                print(f"[API] UPDATE {full_name}: {year_level} {current_sem} -> {next_year_level} {next_sem}")
                conn.execute(
                    """UPDATE students SET year_level=%s, semester=%s, school_year=%s WHERE nfc_id=%s""",
                    (next_year_level, next_sem, next_year, nfc_id)
                )
                updated_count += 1
        
        # Commit
        print(f"[API] Committing {updated_count + graduated_count} changes...")
        conn._conn.commit()
        conn._conn.close()
        
        print(f"[API] Complete! Updated: {updated_count}, Graduated: {graduated_count}, Skipped: {skipped_count}")
        
        return jsonify({
            'ok': True,
            'message': f'Successfully moved {updated_count + graduated_count} students',
            'updated_count': updated_count + graduated_count
        })
    
    except Exception as e:
        print(f"[API] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/register', methods=['GET','POST'])
@admin_required
def register():
    if request.method == 'POST':
        nfc_id = request.form['nfc_id'].strip().upper()
        name   = request.form['name'].strip()
        
        # ── Check for duplicate NFC ID ──────────────────────────────────
        existing_student = db_get_student(nfc_id)
        if existing_student:
            flash(f'⚠ NFC ID {nfc_id} is already registered to {existing_student.get("full_name", "Unknown")}. Use a different NFC card or update the existing student.', 'warning')
            return render_template('enroll.html', subjects_db=db_get_all_subjects(), users_db=db_get_all_users())
        
        extras = []
        raw_date = request.form.get('date_registered','').strip()
        if raw_date:
            try:
                d = datetime.strptime(raw_date, '%Y-%m')
                raw_date = d.strftime('%B %Y')
            except:
                pass
        section_val = request.form.get('section','').strip().upper()
        
        # Generate CVSU email if not provided or empty
        email_val = request.form.get('email','').strip()
        if not email_val:
            # Generate CVSU pattern email: sc.firstname.lastname@cvsu.edu.ph
            clean = re.sub(r'\b[A-Za-z]\.\s*', '', name).strip()
            clean = re.sub(r'\b(JR|SR|II|III|IV)\.?\b', '', clean, flags=re.IGNORECASE).strip()
            clean = re.sub(r'\s+', ' ', clean)
            words = clean.split()
            if len(words) >= 2:
                first_slug = ''.join(re.sub(r'[^a-z]', '', w.lower()) for w in words[:-1])
                last_slug  = re.sub(r'[^a-z]', '', words[-1].lower())
                if first_slug and last_slug:
                    email_val = f'sc.{first_slug}.{last_slug}@cvsu.edu.ph'
        
        for k,prefix in [('student_id','ID'),('course','Course'),('year_level','Year'),
                          ('adviser','Adviser'),('contact','Tel'),
                          ('semester','Sem'),('school_year','SY')]:
            v = request.form.get(k,'').strip()
            if v: extras.append(f"{prefix}:{v}")
        
        # Add generated/provided email
        if email_val: extras.append(f"Email:{email_val}")
        if section_val: extras.append(f"Sec:{section_val}")
        if raw_date: extras.append(f"RegDate:{raw_date}")
        major = request.form.get('major','').strip() or 'N/A'
        extras.append(f"Major:{major}")
        on_chain = name + (' | ' + ' | '.join(extras) if extras else '')
        p = parse_student(on_chain)
        student_name_map[nfc_id] = name
        # ── Blockchain Registration ─────────────────────────────────────
        reg_tx = ''
        reg_block = 0
        student_address = request.form.get('eth_address', '0x0000000000000000000000000000000000000000').strip() or '0x0000000000000000000000000000000000000000'
        
        if BLOCKCHAIN_ONLINE and contract and admin_account:
            try:
                print(f"[BLOCKCHAIN] Registering student {name} ({nfc_id}) on-chain...")
                tx_hash = send_contract_tx(
                    contract.functions.registerStudent(
                        student_address,
                        nfc_id,
                        name
                    )
                )
                if tx_hash:
                    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                    reg_tx = receipt['transactionHash'].hex()
                    reg_block = receipt['blockNumber']
                    print(f"[BLOCKCHAIN] Student {nfc_id} registered on-chain: TX={reg_tx[:16]}")
            except Exception as e:
                print(f"[BLOCKCHAIN ERROR] Failed on-chain registration for {nfc_id}: {e}")

        db_save_student({**p, 'nfcId': nfc_id, 'raw_name': on_chain,
                         'address': student_address, 'tx_hash': reg_tx, 'reg_block': reg_block})
        send_student_welcome_email(
            student_name=name,
            student_email=email_val,
            nfc_id=nfc_id,
            student_id=request.form.get('student_id', '').strip(),
            course=request.form.get('course', '').strip(),
            year_level=request.form.get('year_level', '').strip(),
            section=section_val,
        )
        photo_file = request.files.get('student_photo')
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1].lower()
            if ext in ('.jpg','.jpeg','.png','.gif','.webp'):
                fname = f"photo_{nfc_id.replace(' ','_')}{ext}"
                photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
                db_save_photo(nfc_id, fname)
        saved_subj = _register_save_pending_subjects(request, session)
        if saved_subj:
            print(f"[INFO] {saved_subj} subject(s) added to catalogue from registration.")
        flash(f'Student {name} registered successfully.')
        return redirect(url_for('index'))
    return render_template('enroll.html', subjects_db=db_get_all_subjects(), users_db=db_get_all_users())


@app.route('/parse_registration_pdf', methods=['POST'])
@admin_required
def parse_registration_pdf():
    import traceback
 
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    if not (f.filename or '').lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400
 
    try:
        raw_bytes = f.read()
        if not raw_bytes:
            return jsonify({'error': 'Uploaded file is empty'}), 400
 
        full = _parse_cvsu_pdf_text(raw_bytes)
        if not full.strip():
            return jsonify({
                'error': 'Could not extract text. Install pypdf: pip install pypdf'
            }), 400
 
        print(f'[PDF] {len(full)} chars from "{f.filename}"')
        print(f'[PDF] PREVIEW:\n{full[:600]}\n[PDF] END')
 
        result = _extract_cvsu_fields(full)
 
        print(f'[PDF] name="{result["name"]}" id="{result["student_id"]}" '
              f'course="{result["course"]}" year="{result["year_level"]}" '
              f'sec="{result["section"]}" subjects={len(result["subjects"])} '
              f'email="{result["email"]}"')
 
        return jsonify({**result, 'added_to_catalogue': []})
 
    except Exception as e:
        tb = traceback.format_exc()
        print(f'[parse_registration_pdf ERROR]\n{tb}')
        return jsonify({'error': f'{type(e).__name__}: {str(e)}'}), 500

@app.route('/batch_register', methods=['GET', 'POST'])
@admin_required
def batch_register():
    if request.method == 'GET':
        return render_template('batch_register.html',
                               subjects_db=db_get_all_subjects(),
                               users_db=db_get_all_users())
 
    # POST: receive JSON list of students with nfc_id already assigned
    students_json = request.form.get('students_data', '[]')
    try:
        students_in = json.loads(students_json)
    except Exception:
        flash('Invalid student data payload.')
        return redirect(url_for('batch_register'))
 
    # Filter to only students that have an nfc_id (skipped ones are excluded)
    students_in = [s for s in students_in if s.get('nfc_id')]
 
    success_count  = 0
    errors         = []
    subjects_saved = 0
 
    # ── Save all subjects across all students to the catalogue ────────────
    existing_subj  = db_get_all_subjects()
    existing_codes = {
        v.get('course_code', '').upper(): k
        for k, v in existing_subj.items()
        if v.get('course_code')
    }
    for student in students_in:
        for subj in (student.get('subjects') or []):
            code_upper = (subj.get('course_code') or '').upper().strip()
            name_val   = (subj.get('name') or '').strip()
            if not name_val:
                continue
            if code_upper and code_upper in existing_codes:
                continue
            new_id = str(uuid.uuid4())[:8]
            db_save_subject(new_id, {
                'name':        name_val,
                'course_code': subj.get('course_code', ''),
                'units':       str(subj.get('units', '3')),
                'created_by':  session.get('username', 'admin'),
                'created_at':  _now_local().strftime('%Y-%m-%d %H:%M:%S'),
            })
            if code_upper:
                existing_codes[code_upper] = new_id
            subjects_saved += 1
 
    # ── Register each student ─────────────────────────────────────────────
    for student in students_in:
        try:
            nfc_id = student.get('nfc_id', '').strip().upper()
            name   = (student.get('name') or '').strip()
 
            if not nfc_id:
                errors.append(f"Missing NFC ID for {name or 'Unknown'}")
                continue
            if not name:
                errors.append(f"Missing name for NFC {nfc_id}")
                continue
            
            # ── Check for duplicate NFC ID ──────────────────────────────
            existing_student = db_get_student(nfc_id)
            if existing_student:
                errors.append(f"NFC ID {nfc_id} is already registered to {existing_student.get('full_name', 'Unknown')}. Skipped.")
                continue

            # Build normalized payload string for parse_student()
            extras    = []
            email_val = (student.get('email') or '').strip()
            if not email_val:
                email_val = _generate_cvsu_email(name)
 
            for field, prefix in [
                ('student_id',  'ID'),
                ('course',      'Course'),
                ('year_level',  'Year'),
                ('adviser',     'Adviser'),
                ('contact',     'Tel'),
                ('semester',    'Sem'),
                ('school_year', 'SY'),
            ]:
                v = (student.get(field) or '').strip()
                if v:
                    extras.append(f"{prefix}:{v}")
 
            if email_val:
                extras.append(f"Email:{email_val}")
 
            section_val = (student.get('section') or '').strip().upper()
            if section_val:
                extras.append(f"Sec:{section_val}")
 
            date_reg = (student.get('date_registered') or '').strip()
            if date_reg:
                extras.append(f"RegDate:{date_reg}")
 
            major = (student.get('major') or 'N/A').strip()
            extras.append(f"Major:{major}")
 
            on_chain = name + (' | ' + ' | '.join(extras) if extras else '')
 
            # Parse and save to PostgreSQL
            p = parse_student(on_chain)
            student_name_map[nfc_id] = name
            db_save_student({
                **p,
                'nfcId':      nfc_id,
                'raw_name':   on_chain,
                'address':    '',
                'tx_hash':    '',
                'photo_file': student.get('photo_file', ''),
            })
            send_student_welcome_email(
                student_name=name,
                student_email=email_val,
                nfc_id=nfc_id,
                student_id=(student.get('student_id') or '').strip(),
                course=(student.get('course') or '').strip(),
                year_level=(student.get('year_level') or '').strip(),
                section=section_val,
            )
            success_count += 1
 
        except Exception as e:
            errors.append(f"Error registering {student.get('name', 'Unknown')}: {e}")
 
    # Flash results
    if success_count:
        subj_note  = f" {subjects_saved} subject(s) added to catalogue." if subjects_saved else ""
        flash(f"Registered {success_count} student(s) successfully.{subj_note}")
 
    if errors:
        flash("Errors: " + " | ".join(errors[:5]) +
              (f" (+{len(errors)-5} more)" if len(errors) > 5 else ""))
 
    return redirect(url_for('dashboard'))

@app.route('/parse_batch_pdfs', methods=['POST'])
@admin_required
def parse_batch_pdfs():
    import traceback
 
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
 
    files     = request.files.getlist('files')
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No PDF files found in the upload'}), 400
 
    students = []
    errors   = []
 
    for f in pdf_files:
        filename = f.filename or 'unknown.pdf'
        try:
            raw_bytes = f.read()
            if not raw_bytes:
                errors.append(f'Empty file: {filename}')
                continue
 
            full = _parse_cvsu_pdf_text(raw_bytes)
            if not full.strip():
                errors.append(f'Could not extract text from: {filename}')
                continue
 
            result = _extract_cvsu_fields(full)
 
            # Fallback: derive name from filename if PDF gave nothing
            # Handles:  LASTNAME_FIRSTNAME MIDDLE.pdf
            #           AMBATA_JHAY VIC_GUILLERMO.pdf
            if not result['name']:
                base = re.sub(r'\.pdf$', '', filename, flags=re.IGNORECASE)
                if '_' in base:
                    parts  = base.split('_', 1)
                    last   = parts[0].replace('-', ' ').strip().title()
                    first  = parts[1].replace('_', ' ').replace('-', ' ').strip().title()
                    result['name'] = f"{first} {last}"
                else:
                    result['name'] = base.replace('-', ' ').replace('_', ' ').strip().title()
 
                if result['name']:
                    print(f'[BATCH PDF] Name from filename: "{result["name"]}"')
                    if not result['email']:
                        result['email'] = _generate_cvsu_email(result['name'])
 
            if not result['name'] and not result['student_id']:
                errors.append(f'No usable data extracted from: {filename}')
                continue
 
            result['filename'] = filename
            students.append(result)
 
            print(f'[BATCH PDF] OK  "{filename}" -> "{result["name"]}" '
                  f'id="{result["student_id"]}" yr="{result["year_level"]}" '
                  f'sec="{result["section"]}" subj={len(result["subjects"])}')
 
        except Exception as e:
            tb = traceback.format_exc()
            print(f'[BATCH PDF ERROR] {filename}\n{tb}')
            errors.append(f'{filename}: {type(e).__name__} — {str(e)}')
 
    if not students:
        return jsonify({
            'error':   'No valid student data could be extracted.',
            'details': errors,
        }), 400
 
    # Sort alphabetically by surname (e.g. Ambata before Berongoy)
    students.sort(key=_surname_sort_key)
    for i, s in enumerate(students):
        s['sort_order'] = i + 1
 
    return jsonify({
        'students':     students,
        'total_parsed': len(students),
        'errors':       errors,
        'sorted_by':    'surname_first',
    })

def _mark_attendance_async(nfc_id, sess_id=None):
    """Background task: submit attendance to blockchain and update DB with tx_hash."""
    if not (BLOCKCHAIN_ONLINE and contract and admin_account):
        return
    try:
        tx = send_contract_tx(
            contract.functions.markAttendanceWithStatus(
                nfc_id, chain_status_code('present')
            )
        )
        receipt = web3.eth.wait_for_transaction_receipt(tx, timeout=120)
        tx_hash = receipt['transactionHash'].hex()
        block_num = receipt['blockNumber']
        if sess_id:
            with get_db() as conn:
                conn.execute(
                    "UPDATE attendance_logs SET tx_hash=?, block_number=? "
                    "WHERE sess_id=? AND nfc_id=?",
                    (tx_hash, block_num, sess_id, nfc_id)
                )
    except Exception as e:
        print(f"[WARN] Async blockchain write failed for {nfc_id}: {e}")

@app.route('/mark', methods=['POST'])
@login_required
def mark():
    nfc_id = request.form['nfc_id'].strip().upper()
    sess_id = request.form.get('sess_id', '').strip()
    try:
        name = student_name_map.get(nfc_id,"Unknown")
        
        # Record to database immediately (no blockchain wait)
        if sess_id:
            db_save_attendance_log(
                sess_id, nfc_id, name, '',
                status='present', tap_time=_now_local().strftime('%Y-%m-%d %H:%M:%S'),
                tx_hash='', block_number=0
            )
        
        recent_attendance.append({'nfc_id':nfc_id,'name':name,'timestamp':time.time()})
        flash(f'Attendance marked for {name}')
        
        # Submit blockchain write in background (non-blocking)
        if BLOCKCHAIN_ONLINE and contract and admin_account:
            from threading import Thread
            Thread(target=_mark_attendance_async, args=(nfc_id, sess_id), daemon=True).start()
    except Exception as e:
        flash(f'Error: {e}')
    return redirect(url_for('index'))

@app.route('/dashboard')
@admin_required
def dashboard():
    return _dashboard_page_impl(
        get_all_students=get_all_students,
        db_get_all_users=db_get_all_users,
        get_db=get_db,
        render_template=render_template,
        fmt_time=fmt_time,
    )

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    return _upload_photo_impl(
        request=request,
        jsonify=jsonify,
        os_module=os,
        upload_folder=UPLOAD_FOLDER,
        db_save_photo=db_save_photo,
    )

@app.route('/get_my_photo')
@login_required
def get_my_photo():
    return _get_my_photo_impl(
        username=session.get('username', ''),
        db_get_photo=db_get_photo,
        jsonify=jsonify,
    )

@app.route('/api/my_profile')
@login_required
def api_my_profile():
    return _api_my_profile_impl(
        username=session.get('username', ''),
        db_get_user=db_get_user,
        db_get_photo=db_get_photo,
        jsonify=jsonify,
    )


@app.route('/request_password_change_otp', methods=['POST'])
@login_required
def request_password_change_otp():
    ok, payload, status = request_password_change_otp_for_current_user()
    if not ok:
        return jsonify({'ok': False, 'error': payload}), status
    return jsonify({'ok': True, 'sent_to': payload})

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    return _update_profile_impl(
        username=session.get('username'),
        request=request,
        session_obj=session,
        db_get_user=db_get_user,
        db_save_user=db_save_user,
        db_delete_user=db_delete_user,
        db_get_photo=db_get_photo,
        db_save_photo=db_save_photo,
        db_delete_photo=db_delete_photo,
        hash_password=hash_password,
        validate_password_otp_fn=validate_password_change_otp_for_current_user,
        send_password_changed_email_fn=send_password_changed_success_email,
        jsonify=jsonify,
    )

@app.route('/delete_photo', methods=['POST'])
@login_required
def delete_photo():
    return _delete_photo_impl(
        person_id=request.form.get('person_id', '').strip(),
        db_get_photo=db_get_photo,
        upload_folder=UPLOAD_FOLDER,
        db_delete_photo=db_delete_photo,
        os_module=os,
        jsonify=jsonify,
    )

@app.route('/reports')
@admin_required
def attendance_report():
    return _attendance_report_impl(redirect=redirect, url_for=url_for)

@app.route('/view/<nfc_id>')
@login_required
def view_attendance(nfc_id):
    return _view_attendance_impl(
        nfc_id=nfc_id,
        role=session.get('role'),
        get_current_user=get_current_user,
        teacher_students=teacher_students,
        flash=flash,
        redirect=redirect,
        url_for=url_for,
        get_attendance_records=get_attendance_records,
        get_all_students=get_all_students,
        render_template=render_template,
        fmt_time=fmt_time,
    )

@app.route('/api/student_sessions/<nfc_id>')
@login_required
def student_sessions_api(nfc_id):
    return _student_sessions_api_impl(
        nfc_id=nfc_id,
        get_db=get_db,
        excuse_pk_column=_excuse_pk_column,
        url_for=url_for,
        get_all_students=get_all_students,
        build_student_section_key=build_student_section_key,
        row_to_dict=_row_to_dict,
        normalize_section_key=normalize_section_key,
        jsonify=jsonify,
    )

@app.route('/update_student', methods=['POST'])
@admin_required
def update_student():
    return _update_student_impl(
        request=request,
        datetime_now=datetime.now,
        get_db=get_db,
        db_save_override=db_save_override,
        jsonify=jsonify,
    )

@app.route('/update_faculty', methods=['POST'])
@admin_required
def update_faculty():
    return _update_faculty_impl(
        request=request,
        session_obj=session,
        db_get_user=db_get_user,
        db_save_user=db_save_user,
        db_delete_user=db_delete_user,
        db_rename_photo_key=db_rename_photo_key,
        normalize_section_key=normalize_section_key,
        hash_password=hash_password,
        jsonify=jsonify,
    )

@app.route('/export')
@login_required
def export_page():
    return render_template('export.html',
        students=get_all_students(), users_db=db_get_all_users(),
        subjects_db=db_get_all_subjects(), active_sessions=get_active_sessions(),
        fmt_time=fmt_time)

@app.route('/export/all.csv')
@admin_required
def export_csv_all():
    return _export_csv_all_impl(
        get_all_students_fn=get_all_students,
        get_attendance_records_fn=get_attendance_records,
        get_student_session_rows_fn=get_student_session_rows_for_export,
    )

@app.route('/export/<nfc_id>.csv')
@login_required
def export_csv_single(nfc_id):
    return _export_csv_single_impl(
        nfc_id=nfc_id,
        student_name_map_obj=student_name_map,
        get_attendance_records_fn=get_attendance_records,
        get_student_session_rows_fn=get_student_session_rows_for_export,
    )

@app.route('/admin/users')
@admin_required
def manage_users():
    return redirect(url_for('index', tab='faculty'))


@app.route('/admin/approve/<username>', methods=['POST'])
@app.route('/admin/users/<username>/approve', methods=['POST'])
@admin_required
def approve_user(username):
    user = db_get_user(username)
    if user: user['status']='approved'; db_save_user(username,user); flash(f'{user["full_name"]} approved.')
    return redirect(url_for('manage_users'))

@app.route('/admin/reject/<username>', methods=['POST'])
@app.route('/admin/users/<username>/reject', methods=['POST'])
@admin_required
def reject_user(username):
    user = db_get_user(username)
    if user: user['status']='rejected'; db_save_user(username,user); flash(f'{user["full_name"]} rejected.')
    return redirect(url_for('manage_users'))

@app.route('/admin/delete/<username>', methods=['POST'])
@app.route('/admin/users/<username>/delete', methods=['POST'])
@admin_required
def delete_user(username):
    user = db_get_user(username)
    if user and username != 'admin':
        role = user.get('role')
        db_delete_user(username); flash(f'{user["full_name"]} deleted.', 'success')
        if role == 'teacher':
            return redirect(url_for('index', tab='faculty'))
    return redirect(url_for('index'))

@app.route('/admin/subjects')
@admin_required
def manage_subjects():
    return render_template('admin_subjects.html', subjects=db_get_all_subjects(), fmt_time=fmt_time)

@app.route('/admin/subjects/add', methods=['POST'])
@admin_required
def add_subject():
    name = request.form.get('name','').strip()
    if not name: flash('Subject name cannot be empty.'); return redirect(url_for('manage_subjects'))
    for s in db_get_all_subjects().values():
        if s['name'].lower() == name.lower():
            flash(f'Subject "{name}" already exists.'); return redirect(url_for('manage_subjects'))
    course_code = request.form.get('course_code','').strip().upper()
    units = request.form.get('units','3').strip()
    if units not in ('2','3'): units = '3'
    sid = str(uuid.uuid4())[:8]
    db_save_subject(sid, {'name':name,'course_code':course_code,'units':units,
                          'created_by':session.get('username',''),
                          'created_at':_now_local().strftime('%Y-%m-%d %H:%M:%S')})
    flash(f'Subject "{name}" added.')
    return redirect(url_for('manage_subjects'))

@app.route('/admin/subjects/<sid>/rename', methods=['POST'])
@app.route('/admin/subjects/rename/<sid>', methods=['POST'])
@admin_required
def rename_subject(sid):
    if request.is_json:
        data     = request.get_json()
        new_name = (data.get('name') or '').strip()
        if not new_name: return jsonify({'error':'Name cannot be empty'}), 400
        subj = db_get_subject(sid)
        if not subj: return jsonify({'error':'Subject not found'}), 404
        subj['name'] = new_name
        if 'course_code' in data: subj['course_code'] = data['course_code'].strip().upper()
        if 'units' in data and str(data['units']) in ('2','3'): subj['units'] = str(data['units'])
        db_save_subject(sid, subj)
        return jsonify({'ok':True})
    new_name = request.form.get('name','').strip()
    if not new_name: flash('Name cannot be empty.'); return redirect(url_for('manage_subjects'))
    subj = db_get_subject(sid)
    if subj:
        old = subj['name']; subj['name'] = new_name
        db_save_subject(sid, subj); flash(f'"{old}" renamed to "{new_name}".')
    return redirect(url_for('manage_subjects'))

@app.route('/admin/subjects/delete/<sid>', methods=['POST'])
@app.route('/admin/subjects/<sid>/delete', methods=['POST'])
@admin_required
def delete_subject(sid):
    for s in get_active_sessions().values():
        if s.get('subject_id') == sid:
            flash('Cannot delete — a live session is using this subject.'); return redirect(url_for('manage_subjects'))
    subj = db_get_subject(sid)
    if subj:
        db_delete_subject(sid)
        with get_db() as conn:
            rows = conn.execute("SELECT username, my_subjects_json FROM users").fetchall()
        for row in rows:
            my_s  = json.loads(row['my_subjects_json'] or '[]')
            new_s = [ms for ms in my_s if ms.get('subject_id') != sid]
            if len(new_s) != len(my_s):
                with get_db() as conn:
                    conn.execute("UPDATE users SET my_subjects_json=? WHERE username=?",
                                 (json.dumps(new_s), row['username']))
        flash(f'Subject "{subj["name"]}" deleted.')
    return redirect(url_for('manage_subjects'))

@app.route('/admin/sessions')
@admin_required
def admin_sessions():
    return _admin_sessions_page_impl(
        get_db=get_db,
        session_row_with_logs=_session_row_with_logs,
        render_template=render_template,
        db_get_all_subjects=db_get_all_subjects,
        fmt_time=fmt_time,
    )

@app.route('/admin/session/<sess_id>/delete', methods=['POST'])
@admin_required
def admin_delete_session(sess_id):
    sess = load_session(sess_id)
    if sess is None:
        flash('Session not found.', 'danger'); return redirect(url_for('admin_sessions'))
    
    db_delete_session(sess_id)
    flash('Session deleted successfully.', 'success')
    return redirect(url_for('admin_sessions'))

def _build_teacher_context(user):
    if not user: return {}, [], []
    students = teacher_students(user)
    sections = {}
    for key in user.get('sections', []):
        norm_key = normalize_section_key(key)
        parts    = norm_key.split('|')
        sec_stud = [s for s in students if build_student_section_key(s) == norm_key]
        sections[norm_key] = {
            'label':   f"{parts[2]} — {parts[1]}" if len(parts)==3 else norm_key,
            'course':  parts[0] if parts else '',
            'year':    parts[1] if len(parts)>1 else '',
            'section': parts[2] if len(parts)>2 else '',
            'students': sec_stud, 'count': len(sec_stud)
        }
    all_subj = db_get_all_subjects()
    my_subjects = []
    for ms in user.get('my_subjects', []):
        sid  = ms.get('subject_id')
        skey = normalize_section_key(ms.get('section_key',''))
        if not sid or sid not in all_subj: continue
        ms_sem = normalize_semester(ms.get('semester', ''))
        for sess_id, sess_obj in get_active_sessions().items():
            if (sess_obj.get('subject_id')==sid
                    and normalize_section_key(sess_obj.get('section_key',''))==skey
                    and normalize_semester(sess_obj.get('semester'))==ms_sem
                    and sess_obj.get('teacher')==session['username']):
                active_sid = sess_id; break
        parts = skey.split('|')
        subj_info = all_subj[sid]
        # Get student count from ALL students matching this section key
        # (not just from teacher.sections dict which may be empty)
        all_stu_for_section = [
            s for s in db_get_all_students() 
            if build_student_section_key(s) == skey
            and (not ms_sem or normalize_semester(s.get('semester')) == ms_sem)
        ]
        sec_count = len(all_stu_for_section)
        if skey in sections:
            sec_label = sections[skey]['label']
        else:
            sec_label = f"{parts[2]} — {parts[1]}" if len(parts)==3 else skey
        my_subjects.append({
            'subject_id':   sid,
            'subject_name': subj_info['name'],
            'course_code':  subj_info.get('course_code',''),
            'units':        subj_info.get('units','3'),
            'section_key':  skey,
            'section_label': sec_label,
            'course':       parts[0] if parts else '',
            'year':         parts[1] if len(parts)>1 else '',
            'section':      parts[2] if len(parts)>2 else '',
            'active_session_id': active_sid,
            'student_count':     sec_count,
            'semester':          ms_sem
        })
    return sections, my_subjects, all_subj

@app.route('/teacher')
@login_required
def teacher_dashboard():
    return _teacher_dashboard_page_impl(
        session_obj=session,
        redirect=redirect,
        url_for=url_for,
        get_current_user=get_current_user,
        clear_session=session.clear,
        build_teacher_context=_build_teacher_context,
        get_active_sessions=get_active_sessions,
        get_db=get_db,
        teacher_students=teacher_students,
        render_template=render_template,
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )

@app.route('/teacher/sessions-students')
@login_required
def teacher_sessions_students():
    return _teacher_sessions_students_page_impl(
        session_obj=session,
        redirect=redirect,
        url_for=url_for,
        get_current_user=get_current_user,
        get_db=get_db,
        session_row_with_logs=_session_row_with_logs,
        teacher_students=teacher_students,
        get_student_attendance_stats=get_student_attendance_stats,
        render_template=render_template,
        datetime_cls=datetime,
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )

@app.route('/teacher/create-session')
@login_required
def teacher_create_session():
    return redirect(url_for('teacher_schedule'))

@app.route('/teacher/records')
@login_required
def teacher_records():
    return _teacher_records_page_impl(
        session_obj=session,
        redirect=redirect,
        url_for=url_for,
        get_current_user=get_current_user,
        get_db=get_db,
        session_row_with_logs=_session_row_with_logs,
        get_all_students=get_all_students,
        render_template=render_template,
        fmt_time=fmt_time,
    )

@app.route('/api/session_attendance/<sess_id>')
@login_required
def api_session_attendance(sess_id):
    try:
        sess = load_session(sess_id)
        if sess is None:
            return jsonify({'error': 'Session not found'}), 404
        if not _is_my_session(sess):
            return jsonify({'error': 'Access denied'}), 403
        class_type = str(sess.get('class_type', 'lecture')).strip().lower()
        is_school_event = class_type == 'school_event'

        related_ids = [sess_id]
        related_sessions = [sess]
        section_keys = {normalize_section_key(sess.get('section_key', ''))}
        teachers_involved = [str(sess.get('teacher_name', '') or '').strip()]

        if is_school_event:
            related_ids = _event_related_session_ids(sess.get('schedule_id', ''), include_ended=True)
            if not related_ids:
                related_ids = [sess_id]
            related_sessions = []
            for rid in related_ids:
                rs = load_session(rid)
                if rs:
                    related_sessions.append(rs)
                    sk = normalize_section_key(rs.get('section_key', ''))
                    if sk:
                        section_keys.add(sk)
                    tname = str(rs.get('teacher_name', '') or '').strip()
                    if tname:
                        teachers_involved.append(tname)

            sched_meta = _parse_event_schedule_id(sess.get('schedule_id', ''))
            ev = db_get_event_schedule_by_id(sched_meta.get('event_id')) if sched_meta else None
            if ev:
                for sk in list(ev.get('section_keys', []) or []):
                    skn = normalize_section_key(sk)
                    if skn:
                        section_keys.add(skn)
                for uname in list(ev.get('teacher_usernames', []) or []):
                    u = db_get_user(uname)
                    tname = str((u or {}).get('full_name', uname) or '').strip()
                    if tname:
                        teachers_involved.append(tname)

        teachers_involved = sorted({t for t in teachers_involved if t})

        logs = []
        if is_school_event and related_ids:
            with get_db() as _conn:
                ph = ','.join(['?'] * len(related_ids))
                logs_rows = _conn.execute(
                    "SELECT * FROM attendance_logs WHERE sess_id IN (" + ph + ") ORDER BY created_at, tap_time",
                    tuple(related_ids),
                ).fetchall()
            logs = [dict(r) for r in logs_rows]
        else:
            logs = db_get_session_attendance(sess_id)

        logs_by_nfc = {lg['nfc_id']: lg for lg in logs}
        section_key = normalize_section_key(sess.get('section_key', ''))
        sk_parts    = section_key.split('|')
        program     = sk_parts[0] if len(sk_parts) > 0 else ''
        year_level  = sk_parts[1] if len(sk_parts) > 1 else ''
        section_val = sk_parts[2] if len(sk_parts) > 2 else ''

        # Get excuse request details
        excuse_details = {}
        with get_db() as _conn:
            if is_school_event and related_ids:
                ph = ','.join(['?'] * len(related_ids))
                excuses = _conn.execute(
                    "SELECT nfc_id, reason_type, reason_detail, attachment_file FROM excuse_requests "
                    "WHERE sess_id IN (" + ph + ") AND status='approved'",
                    tuple(related_ids),
                ).fetchall()
            else:
                excuses = _conn.execute(
                    "SELECT nfc_id, reason_type, reason_detail, attachment_file FROM excuse_requests WHERE sess_id=? AND status='approved'",
                    (sess_id,)
                ).fetchall()
            for exc in excuses:
                excuse_details[exc['nfc_id']] = {
                    'reason': exc['reason_type'],
                    'reason_detail': exc['reason_detail'],
                    'attachment_file': exc['attachment_file'],
                }

        # Historical-first view:
        # - always include students who have logs in this session (even if moved section later)
        # - also include currently enrolled students with no logs as "absent"
        students_map = {}

        for lg in logs:
            nid = lg['nfc_id']
            st  = get_student_by_nfc_cached(nid) or {}
            excuse_info = excuse_details.get(nid, {})
            origin = (
                str(st.get('course') or '').strip(),
                str(st.get('year_level') or '').strip(),
                str(st.get('section') or '').strip(),
            )
            section_origin = '-'.join([x for x in origin if x]) or '-'
            students_map[nid] = {
                'nfc_id':     nid,
                'name':       lg.get('student_name') or st.get('name') or nid,
                'student_id': lg.get('student_id')   or st.get('student_id', ''),
                'section_origin': section_origin,
                'program': st.get('course', ''),
                'year_level': st.get('year_level', ''),
                'section': st.get('section', ''),
                'status':     ('present' if is_school_event and (str(lg.get('status') or '').lower() in ('present', 'late')) else (lg.get('status') or 'absent').lower()),
                'class_type': (lg.get('class_type') or sess.get('class_type', 'lecture')).lower(),
                'tx_hash':    lg.get('tx_hash') or '',
                'block':      str(lg.get('block_number') or ''),
                'time':       lg.get('tap_time') or '',
                'reason':     excuse_info.get('reason') or lg.get('excuse_note') or '',
                'reason_detail': excuse_info.get('reason_detail') or '',
                'attachment_url': url_for('admin_excuse_attachment', excuse_id=lg.get('excuse_request_id')) if lg.get('excuse_request_id') else '',
            }

        # Primary approach: use get_all_students() and match by section_key
        # This is more reliable as it handles both blockchain-sourced and database students
        all_students = get_all_students()
        all_students = get_all_students()
        sess_semester = normalize_semester(sess.get('semester') or '')
        if is_school_event:
            enrolled = [
                s for s in all_students 
                if build_student_section_key(s) in section_keys 
                and (not sess_semester or not normalize_semester(s.get('semester')) or normalize_semester(s.get('semester')) == sess_semester)
            ]
        else:
            enrolled = [
                s for s in all_students 
                if build_student_section_key(s) == section_key 
                and (not sess_semester or not normalize_semester(s.get('semester')) or normalize_semester(s.get('semester')) == sess_semester)
            ]

        # Fallback: if no students found via section_key, try exact database query
        if (not is_school_event) and (not enrolled) and program and year_level and section_val:
            with get_db() as _conn:
                if sess_semester:
                    _rows = _conn.execute(
                        "SELECT * FROM students WHERE program=? AND year_level=? AND section=? AND lower(trim(semester))=?",
                        (program, year_level, section_val, sess_semester)
                    ).fetchall()
                else:
                    _rows = _conn.execute(
                        "SELECT * FROM students WHERE program=? AND year_level=? AND section=?",
                        (program, year_level, section_val)
                    ).fetchall()
            enrolled = [_student_row(r) for r in _rows]

        for s in enrolled:
            nid = s['nfcId']
            if nid in students_map:
                continue
            section_origin = '-'.join([
                str(s.get('course') or '').strip(),
                str(s.get('year_level') or '').strip(),
                str(s.get('section') or '').strip(),
            ]).strip('-') or '-'
            students_map[nid] = {
                'nfc_id':     nid,
                'name':       s.get('name', nid),
                'student_id': s.get('student_id', ''),
                'section_origin': section_origin,
                'program': s.get('course', ''),
                'year_level': s.get('year_level', ''),
                'section': s.get('section', ''),
                'status':     'absent',
                'class_type': str(sess.get('class_type', 'lecture')).lower(),
                'tx_hash':    '',
                'block':      '',
                'time':       '',
                'reason':     '',
                'reason_detail': '',
                'attachment_url': '',
            }

        students_out = sorted(students_map.values(), key=lambda x: (x.get('name') or 'Unknown').lower())
        return jsonify({
            'students':     students_out,
            'subject_name': sess.get('subject_name', ''),
            'course_code':  sess.get('course_code', ''),
            'class_type':   sess.get('class_type', 'lecture'),
            'section_key':  section_key,
            'sections_involved': sorted([sk for sk in section_keys if sk]),
            'teachers_involved': teachers_involved,
            'students_involved_count': len(students_out),
            'time_slot':    sess.get('time_slot', ''),
            'started_at':   sess.get('started_at', ''),
            'session_tx_hash': sess.get('session_tx_hash', ''),
            'session_block_number': sess.get('session_block_number', ''),
            'ended_at':     sess.get('ended_at', ''),
        })
    except Exception as e:
        import traceback
        print(f"[ERROR api_session_attendance] {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/teacher/subjects/add', methods=['POST'])
@login_required
def teacher_add_subject():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user       = get_current_user()
    subject_id = request.form.get('subject_id','').strip()
    section_key= normalize_section_key(request.form.get('section_key','').strip())
    semester   = normalize_semester(request.form.get('semester', '').strip())
    if not subject_id or not section_key:
        flash('Please select both a subject and a section.'); return redirect(url_for('teacher_create_session'))
    subj = db_get_subject(subject_id)
    if not subj: flash('Subject not found.'); return redirect(url_for('teacher_create_session'))
    for ms in user.get('my_subjects',[]):
        if ms['subject_id']==subject_id and normalize_section_key(ms['section_key'])==section_key and normalize_semester(ms.get('semester'))==semester:
            flash('Already assigned with this semester.'); return redirect(url_for('teacher_create_session'))
    user.setdefault('my_subjects',[]).append({'subject_id':subject_id,'section_key':section_key,'semester':semester})
    db_save_user(session['username'], user)
    flash(f'Subject "{subj["name"]}" added to your schedule.')
    return redirect(url_for('teacher_create_session'))

@app.route('/teacher/subjects/<subject_id>/<path:section_key>/remove', methods=['POST'])
@login_required
def teacher_remove_subject(subject_id, section_key):
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user = get_current_user()
    norm_key = normalize_section_key(section_key)
    user['my_subjects'] = [ms for ms in user.get('my_subjects',[])
                           if not (ms['subject_id']==subject_id
                                   and normalize_section_key(ms['section_key'])==norm_key)]
    db_save_user(session['username'], user)
    flash('Subject removed from your schedule.')
    return redirect(url_for('teacher_create_session'))

def _parse_time_slot_end(time_slot_str, reference_dt):
    """
    Parse a time slot like '9:00 AM – 11:00 AM' and return
    a datetime for the END time on the same date as reference_dt.
    Returns None if parsing fails.
    """
    if not time_slot_str:
        return None
    try:
        # Handle both '–' (en-dash) and '-' (hyphen) separators
        sep = '–' if '–' in time_slot_str else '-'
        parts = time_slot_str.split(sep)
        if len(parts) < 2:
            return None
        end_str = parts[1].strip()
        # Parse end time — e.g. "11:00 AM"
        end_t   = datetime.strptime(end_str, '%I:%M %p').time()
        return reference_dt.replace(
            hour=end_t.hour, minute=end_t.minute,
            second=0, microsecond=0
        )
    except Exception as _pe:
        print(f"[WARN] Could not parse time slot end: {_pe}")
        return None
 
 
def _parse_time_slot_start(time_slot_str, reference_dt):
    """Parse the START time of a time slot string."""
    if not time_slot_str:
        return None
    try:
        sep     = '–' if '–' in time_slot_str else '-'
        parts   = time_slot_str.split(sep)
        start_s = parts[0].strip()
        start_t = datetime.strptime(start_s, '%I:%M %p').time()
        return reference_dt.replace(
            hour=start_t.hour, minute=start_t.minute,
            second=0, microsecond=0
        )
    except Exception:
        return None
 
 
def _auto_end_session_thread(sess_id, auto_end_at_str, app_context):
    """
    Background thread: waits until auto_end_at then ends the session
    automatically (same logic as end_session route).
    Teacher can still end early by clicking End Session.
    """
    import threading as _th
    try:
        auto_end_dt = datetime.strptime(auto_end_at_str, '%Y-%m-%d %H:%M:%S')
        wait_secs   = (auto_end_dt - _now_local()).total_seconds()
        if wait_secs > 0:
            print(f"[AUTO-END] Session {sess_id} will auto-end in {int(wait_secs)}s at {auto_end_at_str}")
            _th.Event().wait(timeout=wait_secs)
 
        # Check if already ended manually by teacher
        with app_context:
            current = load_session(sess_id)
            if not current or current.get('ended_at'):
                print(f"[AUTO-END] Session {sess_id} already ended — skipping auto-end.")
                return
 
            print(f"[AUTO-END] Auto-ending session {sess_id}...")
            result = _finalize_session(
                sess_id,
                ended_time=_now_local().strftime('%Y-%m-%d %H:%M:%S'),
                async_chain_and_email=True,
            )
            if result and not result.get('already_ended'):
                print(f"[AUTO-END] Session {sess_id} ended automatically at {result.get('ended_at')}")
 
    except Exception as _ate:
        print(f"[AUTO-END] Error in auto-end thread for {sess_id}: {_ate}")
 
 
@app.route('/teacher/session/start', methods=['POST'])
@login_required
def start_session():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    subject_id  = request.form.get('subject_id','').strip()
    section_key = normalize_section_key(request.form.get('section_key','').strip())
    semester    = normalize_semester(request.form.get('semester', '').strip())
    
    if not semester:
        # Fallback: try to find a semester from the teacher's schedules for this subject/section
        try:
            with get_db() as conn:
                sched = conn.execute(
                    "SELECT semester FROM schedules WHERE subject_id=? AND section_key=? AND teacher_username=? LIMIT 1",
                    (subject_id, section_key, session['username'])
                ).fetchone()
                if sched:
                    semester = normalize_semester(sched['semester'])
        except:
            pass
    
    if not subject_id or not section_key:
        flash('Missing subject or section.'); return redirect(url_for('teacher_create_session'))
    for s in get_active_sessions().values():
        if (s.get('teacher')==session['username']
                and normalize_section_key(s.get('section_key',''))==section_key):
            flash('You already have an active session for that section.')
            return redirect(url_for('teacher_create_session'))
 
    time_slot    = request.form.get('time_slot','').strip()
    grace_period = int(request.form.get('grace_period', 15) or 15)
    grace_period = max(1, min(grace_period, 120))  # clamp 1–120 min
 
    subj_data = db_get_subject(subject_id) or {}
    units     = int(subj_data.get('units', 3))
    now       = _now_local()
    from datetime import timedelta
 
    # ── Late cutoff: based on actual session start + grace period ─────────────
    # Teacher sets grace period (default 15 min). Students tapping after
    # this cutoff are marked LATE instead of PRESENT.
    late_cutoff_dt = now.replace(second=0, microsecond=0) + timedelta(minutes=grace_period)
 
    # ── Auto-end: derived from time slot end time ─────────────────────────────
    # If teacher selects "9:00 AM – 11:00 AM", session auto-ends at 11:00 AM.
    # Teacher can still end early by clicking End Session.
    auto_end_dt  = _parse_time_slot_end(time_slot, now)
    auto_end_str = auto_end_dt.strftime('%Y-%m-%d %H:%M:%S') if auto_end_dt else None
 
    sess_id  = str(uuid.uuid4())[:12]
    new_sess = {
        'subject_id':    subject_id,
        'subject_name':  subj_data.get('name',''),
        'course_code':   subj_data.get('course_code',''),
        'class_type':    'lecture',
        'units':         units,
        'time_slot':     time_slot,
        'section_key':   section_key,
        'semester':      semester,
        'teacher':       session['username'],
        'teacher_name':  session['full_name'],
        'started_at':    now.strftime('%Y-%m-%d %H:%M:%S'),
        'late_cutoff':   late_cutoff_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'auto_end_at':   auto_end_str,
        'grace_period':  grace_period,
        'ended_at':      None,
        'present':[],'late':[],'excused':[],'warned':[],'absent':[],
        'tap_log':[],'warn_log':[],'invalid_log':[],'excuse_notes':{},'tx_hashes':{}
    }
    save_session(sess_id, new_sess)
    sessions_db[sess_id] = new_sess
 
    # ── Launch auto-end background thread ─────────────────────────────────────
    if auto_end_str:
        import threading as _th
        ctx = app.app_context()
        t   = _th.Thread(
            target=_auto_end_session_thread,
            args=(sess_id, auto_end_str, ctx),
            daemon=True
        )
        t.start()
        flash(f'Session started. Auto-ends at {auto_end_dt.strftime("%I:%M %p")}. Grace period: {grace_period} min.')
    else:
        flash(f'Classroom session started for {subj_data.get("name","")}.')
 
    return redirect(url_for('live_session', sess_id=sess_id))

@app.route('/api/blockchain_status')
def blockchain_status():
    global BLOCKCHAIN_ONLINE
    try:
        BLOCKCHAIN_ONLINE = web3.is_connected()
    except:
        BLOCKCHAIN_ONLINE = False
    student_count = len(db_get_all_students())
    return jsonify({
        'online': BLOCKCHAIN_ONLINE,
        'student_cache_count': student_count,
        'message': 'Blockchain online' if BLOCKCHAIN_ONLINE else f'Offline — {student_count} students loaded from cache'
    })

@app.route('/api/diagnostics')
@login_required
def diagnostics():
    """
    Debug endpoint: shows server state and session information.
    Helps diagnose why sessions might not be starting on Railway.
    """
    now_dt = _now_local()
    active = get_active_sessions()
    
    with get_db() as conn:
        schedules_today = conn.execute(
            "SELECT schedule_id, subject_name, teacher_username, start_time, end_time "
            "FROM schedules WHERE day_of_week=? AND is_active=1",
            (now_dt.weekday(),)
        ).fetchall()
        
        all_sessions = conn.execute(
            "SELECT sess_id, subject_name, teacher_username, started_at, ended_at "
            "FROM sessions WHERE started_at LIKE ? ORDER BY started_at DESC LIMIT 20",
            (f"{now_dt.strftime('%Y-%m-%d')}%",)
        ).fetchall()
    
    automation_running = AUTO_THREAD and AUTO_THREAD.is_alive()
    
    return jsonify({
        'server_time': now_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'server_weekday': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][now_dt.weekday()],
        'active_sessions_count': len(active),
        'active_sessions': [
            {
                'sess_id': sid,
                'subject': s.get('subject_name'),
                'teacher': s.get('teacher'),
                'section': s.get('section_key'),
                'started_at': s.get('started_at'),
                'auto_end_at': s.get('auto_end_at'),
            }
            for sid, s in list(active.items())[:10]
        ],
        'schedules_today': [dict(s) for s in schedules_today],
        'sessions_today': [dict(s) for s in all_sessions],
        'automation_running': automation_running,
        'automation_thread_name': AUTO_THREAD.name if AUTO_THREAD else 'None',
    })

@app.route('/api/active_sessions')
def api_active_sessions():
    """
    Public endpoint: returns all active sessions (for monitoring dashboards).
    Does NOT require login.
    """
    active = get_active_sessions()
    return jsonify({
        'active_count': len(active),
        'sessions': [
            {
                'sess_id': sid,
                'subject': s.get('subject_name'),
                'teacher': s.get('teacher'),
                'section': s.get('section_key'),
                'started_at': s.get('started_at'),
                'students_present': len(s.get('present', [])),
                'students_late': len(s.get('late', [])),
            }
            for sid, s in active.items()
        ]
    })

def _is_my_session(sess):
    """
    Return True if the current logged-in user owns this session.
    Checks both teacher_username (new) and teacher_name (fallback for old records),
    so sessions created before the schema migration still work.
    """
    if session.get('role') in ('admin', 'super_admin'):
        return True
    username   = session.get('username', '')
    full_name  = session.get('full_name', '')
    # sess['teacher'] is set by _session_row_with_logs from teacher_username column
    # sess['teacher_name'] is the display name column
    teacher_u  = sess.get('teacher', '') or ''
    teacher_n  = sess.get('teacher_name', '') or ''
    return (teacher_u == username) or (teacher_n and teacher_n == full_name)


@app.route('/teacher/session/<sess_id>')
@login_required
def live_session(sess_id):
    sess = load_session(sess_id)
    if sess is None: flash('Session not found.'); return redirect(url_for('teacher_dashboard'))
    if not _is_my_session(sess):
        flash('Access denied.'); return redirect(url_for('teacher_dashboard'))
    all_students     = get_all_students()
    section_key      = sess.get('section_key','')
    is_school_event = str(sess.get('class_type', 'lecture')).strip().lower() == 'school_event'
    section_keys_for_view = {normalize_section_key(section_key)} if section_key else set()
    related_event_sessions = [sess]

    if is_school_event:
        related_ids = _event_related_session_ids(sess.get('schedule_id', ''), include_ended=True)
        if not related_ids:
            related_ids = [sess_id]
        related_event_sessions = []
        for rid in related_ids:
            rs = load_session(rid)
            if rs:
                related_event_sessions.append(rs)
                sessions_db[rid] = rs

        sched_meta = _parse_event_schedule_id(sess.get('schedule_id', ''))
        ev = db_get_event_schedule_by_id(sched_meta.get('event_id')) if sched_meta else None
        if ev:
            section_keys = [normalize_section_key(s) for s in list(ev.get('section_keys', []) or []) if str(s or '').strip()]
            if section_keys:
                section_keys_for_view = set(section_keys)

    sess_semester = normalize_semester(sess.get('semester') or '')
    section_students = [
        s for s in all_students
        if build_student_section_key(s) in section_keys_for_view
        and (s.get('student_status') or 'active') != 'graduated'
        and (not sess_semester or not normalize_semester(s.get('semester')) or normalize_semester(s.get('semester')) == sess_semester)
    ]
    
    

    # Ensure live view always has a usable student display name.
    normalized_students = []
    for st in section_students:
        sd = dict(st or {})
        display_name = str(sd.get('name') or sd.get('full_name') or '').strip()
        if not display_name:
            raw_name = str(sd.get('raw_name') or '').strip()
            if raw_name:
                display_name = raw_name.split('|', 1)[0].strip()
        if not display_name:
            display_name = str(sd.get('student_id') or sd.get('nfcId') or 'Unknown').strip()
        sd['name'] = display_name
        normalized_students.append(sd)
    section_students = normalized_students

    present_set  = set()
    late_set     = set()
    excused_set  = set()
    excuse_notes = {}
    for src in related_event_sessions:
        present_set.update(src.get('present', []))
        late_set.update(src.get('late', []))
        excused_set.update(src.get('excused', []))
        for k, v in (src.get('excuse_notes', {}) or {}).items():
            excuse_notes[k] = v

    if not is_school_event:
        # For normal schedules use only the current session state.
        present_set = set(sess.get('present', []))
        late_set = set(sess.get('late', []))
        excused_set = set(sess.get('excused', []))
        excuse_notes = sess.get('excuse_notes', {})

    student_statuses = []
    for s in section_students:
        nid = s['nfcId']
        if is_school_event:
            status = 'present' if (nid in present_set or nid in late_set) else 'absent'
        else:
            if   nid in excused_set: status = 'excused'
            elif nid in late_set:    status = 'late'
            elif nid in present_set: status = 'present'
            else:                    status = 'absent'
        student_statuses.append({**s, 'status': status, 'reason': excuse_notes.get(nid, '')})
    session_meta = None
    class_type_label = 'Lecture'
    class_type_raw = str(sess.get('class_type', 'lecture') or 'lecture').strip().lower()
    if class_type_raw == 'laboratory':
        class_type_label = 'Laboratory'
    elif class_type_raw == 'school_event':
        class_type_label = 'School Event'

    def _fmt_session_date(dt_raw):
        try:
            dt = datetime.strptime(str(dt_raw or '').strip(), '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%B %d, %Y')
        except Exception:
            return ''

    def _fmt_session_time(dt_raw):
        try:
            dt = datetime.strptime(str(dt_raw or '').strip(), '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%I:%M %p').lstrip('0')
        except Exception:
            return ''

    if is_school_event:
        sched_meta = _parse_event_schedule_id(sess.get('schedule_id', ''))
        if sched_meta:
            ev = db_get_event_schedule_by_id(sched_meta.get('event_id'))
            if ev:
                teacher_names = []
                for uname in list(ev.get('teacher_usernames', []) or []):
                    u = db_get_user(uname)
                    teacher_names.append((u or {}).get('full_name', uname))
                section_keys = [normalize_section_key(s) for s in list(ev.get('section_keys', []) or []) if str(s or '').strip()]
                programs = sorted({str(s).split('|')[0] for s in section_keys if '|' in str(s) and str(s).split('|')[0]})
                years = sorted({str(s).split('|')[1] for s in section_keys if len(str(s).split('|')) > 1 and str(s).split('|')[1]})
                sections = sorted({str(s).split('|')[2] for s in section_keys if len(str(s).split('|')) > 2 and str(s).split('|')[2]})
                start_at = str(ev.get('start_at', '') or '').strip()
                end_at = str(ev.get('end_at', '') or '').strip()
                start_dt = None
                end_dt = None
                try:
                    start_dt = datetime.strptime(start_at, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    start_dt = None
                try:
                    end_dt = datetime.strptime(end_at, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    end_dt = None
                session_meta = {
                    'title': str(ev.get('title', '') or '').strip() or sess.get('subject_name', 'School Event'),
                    'description': str(ev.get('description', '') or '').strip(),
                    'teachers': teacher_names,
                    'programs': programs,
                    'years': years,
                    'sections': sections,
                    'students': sorted([str(s.get('name', '') or '').strip() for s in section_students if str(s.get('name', '') or '').strip()]),
                    'section_keys': section_keys,
                    'date': (start_dt.strftime('%B %d, %Y') if start_dt else ''),
                    'start_time': (start_dt.strftime('%I:%M %p').lstrip('0') if start_dt else ''),
                    'end_time': (end_dt.strftime('%I:%M %p').lstrip('0') if end_dt else ''),
                    'class_type': 'School Event',
                }
    if not session_meta:
        section_key_norm = normalize_section_key(section_key)
        sk_parts = section_key_norm.split('|')
        program = sk_parts[0] if len(sk_parts) > 0 else ''
        year = sk_parts[1] if len(sk_parts) > 1 else ''
        section_name = sk_parts[2] if len(sk_parts) > 2 else ''
        teacher_name = str(sess.get('teacher_name', '') or '').strip()
        time_slot = str(sess.get('time_slot', '') or '').strip()
        start_time = ''
        end_time = ''
        if time_slot:
            slot_parts = [p.strip() for p in time_slot.replace(' to ', '-').split('-', 1)]
            if len(slot_parts) == 2:
                start_time, end_time = slot_parts[0], slot_parts[1]
            else:
                start_time = time_slot
        if not start_time:
            start_time = _fmt_session_time(sess.get('started_at', ''))
        if not end_time:
            end_time = _fmt_session_time(sess.get('auto_end_at', ''))
        session_meta = {
            'title': str(sess.get('subject_name', '') or '').strip() or 'Class Session',
            'description': 'Regular class attendance session based on scheduled subject and section.',
            'teachers': [teacher_name] if teacher_name else [],
            'programs': [program] if program else [],
            'years': [year] if year else [],
            'sections': [section_name] if section_name else [],
            'students': sorted([str(s.get('name', '') or '').strip() for s in section_students if str(s.get('name', '') or '').strip()]),
            'section_keys': [section_key_norm] if section_key_norm else [],
            'date': _fmt_session_date(sess.get('started_at', '')),
            'start_time': start_time,
            'end_time': end_time,
            'class_type': class_type_label,
        }
    return render_template('session_live.html', sess=sess, sess_id=sess_id,
                           section_students=section_students,
                           student_statuses=student_statuses,
                           present_list=[s for s in section_students if s['nfcId'] in present_set or (is_school_event and s['nfcId'] in late_set)],
                           absent_list=[s for s in section_students if ((s['nfcId'] not in present_set and s['nfcId'] not in late_set) if is_school_event else (s['nfcId'] not in present_set and s['nfcId'] not in excused_set))],
                           tap_log=sess.get('tap_log',[]),
                           is_active=not sess.get('ended_at'),
                           is_school_event=is_school_event,
                           session_meta=session_meta,
                           can_end_early=(not is_school_event),
                           fmt_time=fmt_time, fmt_time_short=fmt_time_short)

@app.route('/teacher/session/<sess_id>/end', methods=['POST'])
@login_required
def end_session(sess_id):
    sess = load_session(sess_id)
    if sess is None:
        flash('Session not found.'); return redirect(url_for('teacher_dashboard'))
    
    if not _is_my_session(sess):
        flash('Access denied.'); return redirect(url_for('teacher_dashboard'))
    if str(sess.get('class_type', 'lecture')).strip().lower() == 'school_event':
        flash('School event sessions end automatically at the scheduled end time.')
        return redirect(url_for('live_session', sess_id=sess_id))
    result = _finalize_session(
        sess_id,
        ended_time=_now_local().strftime('%Y-%m-%d %H:%M:%S'),
        async_chain_and_email=True,
    )
    if not result:
        flash('Session not found.'); return redirect(url_for('teacher_dashboard'))

    if result.get('tx_hash'):
        flash(
            f"Session ended. Blockchain TX: {result.get('tx_hash')[:10]}... | {result.get('present_count', 0)} present, "
            f"{result.get('late_count', 0)} late, {result.get('absent_count', 0)} absent.")
    else:
        err = result.get('bc_error') or "Skipped"
        flash(
            f"Session ended, but Blockchain recording failed ({err}). | {result.get('present_count', 0)} present, "
            f"{result.get('late_count', 0)} late, {result.get('absent_count', 0)} absent.")
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/session/<sess_id>/delete', methods=['POST'])
@login_required
def teacher_delete_session(sess_id):
    sess = load_session(sess_id)
    if sess is None:
        flash('Session not found.'); return redirect(url_for('teacher_sessions'))
    if not _is_my_session(sess):
        flash('Access denied.'); return redirect(url_for('teacher_sessions'))
    
    db_delete_session(sess_id)
    flash('Session deleted successfully.', 'success')
    return redirect(url_for('teacher_sessions'))

@app.route('/teacher/session/<sess_id>/excuse', methods=['POST'])
@login_required
def excuse_student(sess_id):
    nfc_id = request.form.get('nfc_id', '').strip().upper()
    reason_type = request.form.get('reason_type', '').strip()
    reason_detail = request.form.get('reason_detail', '').strip()
    sess = load_session(sess_id)
    if sess is None:
        return jsonify({'error': 'Session not found'}), 404
    if not _is_my_session(sess):
        return jsonify({'error': 'Access denied'}), 403
    if not nfc_id:
        return jsonify({'error': 'Missing NFC ID'}), 400
    if reason_type not in dict(EXCUSE_REASONS):
        return jsonify({'error': f'Invalid reason type: {reason_type}'}), 400
    if reason_type == 'others' and not reason_detail.strip():
        return jsonify({'error': 'Details required for "Others"'}), 400
    
    # Handle multiple file uploads — save the first valid one for DB record
    attachment_file = ''
    uploaded_files = request.files.getlist('attachments')
    for uploaded in uploaded_files:
        if uploaded and uploaded.filename:
            try:
                attachment_file = _save_excuse_attachment(uploaded)
                break  # save first valid attachment
            except ValueError as ve:
                return jsonify({'error': str(ve)}), 400
    
    student = db_get_student(nfc_id) or get_student_by_nfc_cached(nfc_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    reason_label = dict(EXCUSE_REASONS).get(reason_type, reason_type.title())

    excuse_id = db_save_excuse_request({
        'sess_id':        sess_id,
        'nfc_id':         nfc_id,
        'student_name':   student.get('name', nfc_id),
        'student_id':     student.get('student_id', ''),
        'student_email':  student.get('email', ''),
        'reason_type':    reason_type,
        'reason_detail':  reason_detail,
        'attachment_file': attachment_file,
    })
    db_resolve_excuse(excuse_id, 'approved', session.get('username', ''))
    sess = load_session(sess_id) or sess
    
    # Blockchain attendance write only (identity data stays in PostgreSQL)
    exc_tx = ''; exc_block = 0
    if BLOCKCHAIN_ONLINE and contract and admin_account:
        try:
            tx_res, block_res = mark_attendance_on_chain(nfc_id, 'excused')
            exc_tx = tx_res or ''
            exc_block = block_res or 0
        except Exception as _e:
            print(f"[WARN] excused blockchain tx failed: {_e}")
            exc_tx = ''
            exc_block = 0
    
    db_save_attendance_log(
        sess_id=sess_id, nfc_id=nfc_id,
        student_name=student.get('name', nfc_id),
        student_id=student.get('student_id', ''),
        status='excused',
        tap_time=_now_local().strftime('%Y-%m-%d %H:%M:%S'),
        tx_hash=exc_tx, block_number=exc_block,
        excuse_note=f"{reason_label}{' — ' + reason_detail if reason_detail else ''}"
    )
    with get_db() as conn:
        conn.execute(
            "UPDATE attendance_logs SET excuse_request_id=? WHERE sess_id=? AND nfc_id=?",
            (excuse_id, sess_id, nfc_id)
        )
    
    send_student_attendance_receipt(
        student_name=student.get('name', ''),
        student_email=student.get('email', ''),
        student_id=student.get('student_id', ''),
        subject_name=sess.get('subject_name', ''),
        section_key=sess.get('section_key', ''),
        teacher_name=sess.get('teacher_name', ''),
        tap_time=_now_local().strftime('%B %d, %Y  %I:%M %p'),
        status='excused',
        tx_hash=exc_tx,
        block_num=exc_block,
    )
    
    name = student.get('name', nfc_id)
    return jsonify({'status': 'ok', 'name': name, 'nfc_id': nfc_id, 'reason': reason_label})

@app.route('/teacher/sessions')
@login_required
def teacher_sessions():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    with get_db() as _conn:
        _rows = _conn.execute("SELECT * FROM sessions WHERE teacher_username=? ORDER BY started_at DESC",
                              (session['username'],)).fetchall()
    my_sessions = {r['sess_id']: _row_to_dict(r) for r in _rows}
    return render_template('teacher_sessions.html', my_sessions=my_sessions, fmt_time=fmt_time)

@app.route('/teacher/reports')
@login_required
def teacher_reports():
    if session.get('role') == 'admin': return redirect(url_for('admin_sessions'))
    user   = get_current_user()
    report = []
    for s in teacher_students(user):
        stats = get_student_attendance_stats(s['nfcId'])
        report.append({**s, **stats})
    return render_template('teacher_reports.html', user=user,
                           students=sorted(report, key=lambda x: -x['rate']))

@app.route('/teacher/export/section.csv')
@login_required
def teacher_export():
    return _teacher_export_section_csv_impl(
        user_obj=get_current_user(),
        sec_key=request.args.get('section', ''),
        teacher_students_fn=teacher_students,
        normalize_section_key_fn=normalize_section_key,
        build_student_section_key_fn=build_student_section_key,
        get_attendance_records_fn=get_attendance_records,
        get_student_session_rows_fn=get_student_session_rows_for_export,
    )

@app.route('/api/attendance/recent')
@login_required
def recent_attendance_api():
    since = request.args.get('since', type=float, default=0)
    user  = get_current_user()
    evts  = [e for e in recent_attendance if e['timestamp'] > since]
    if user and user.get('role') == 'teacher':
        my_nfcs = {s['nfcId'] for s in teacher_students(user)}
        evts    = [e for e in evts if e['nfc_id'] in my_nfcs]
    return jsonify(evts)

@app.route('/api/session/<sess_id>/poll')
@login_required
def poll_session(sess_id):
    """
    Poll for new taps.

    KEY FIX: Uses server-side time (returned as 'server_time') so the frontend
    never relies on the browser clock. Browser clocks can be ahead of the server
    which caused taps to be permanently missed (since_dt > created_at → never found).

    Tap detection uses attendance_logs.created_at (real DB timestamp) instead of
    tap_log[].timestamp which is always 0 when loaded from DB.
    """
    since = request.args.get('since', type=float, default=0)
    now_ts = time.time()  # server time — returned to client so they stay in sync

    # Reload session from DB so present/late/excused lists are always fresh
    sess = load_session(sess_id)
    if sess is None:
        return jsonify({'error': 'not found', 'active': False}), 404
    sessions_db[sess_id] = sess
    is_school_event = str(sess.get('class_type', 'lecture')).strip().lower() == 'school_event'

    related_ids = [sess_id]
    related_sessions = [sess]
    if is_school_event:
        related_ids = _event_related_session_ids(sess.get('schedule_id', ''), include_ended=False)
        if not related_ids:
            related_ids = [sess_id]
        related_sessions = []
        for rid in related_ids:
            rs = load_session(rid)
            if rs:
                related_sessions.append(rs)
                sessions_db[rid] = rs
        if not related_sessions:
            related_sessions = [sess]
            related_ids = [sess_id]

    new_taps     = []
    new_warnings = []
    new_invalids = []

    if since > 0:
        # Subtract 2 seconds as a buffer to handle sub-second timing edge cases
        # and any minor clock drift between DB writes and poll timing
        since_buffered = since - 2
        since_dt = datetime.fromtimestamp(since_buffered).strftime('%Y-%m-%d %H:%M:%S')

        with get_db() as conn:
            if is_school_event and related_ids:
                placeholders = ','.join(['?'] * len(related_ids))
                query = (
                    "SELECT al.nfc_id, al.student_name, al.student_id, al.status, "
                    "al.tap_time, al.tx_hash, al.block_number, al.created_at "
                    "FROM attendance_logs al "
                    f"WHERE al.sess_id IN ({placeholders}) "
                    "  AND al.status IN ('present','late') "
                    "  AND al.created_at > ? "
                    "ORDER BY al.created_at ASC"
                )
                tap_rows = conn.execute(query, tuple(related_ids) + (since_dt,)).fetchall()
            else:
                tap_rows = conn.execute(
                    "SELECT al.nfc_id, al.student_name, al.student_id, al.status, "
                    "al.tap_time, al.tx_hash, al.block_number, al.created_at "
                    "FROM attendance_logs al "
                    "WHERE al.sess_id = ? "
                    "  AND al.status IN ('present','late') "
                    "  AND al.created_at > ? "
                    "ORDER BY al.created_at ASC",
                    (sess_id, since_dt)
                ).fetchall()

        for row in tap_rows:
            try:
                ts = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S').timestamp()
            except Exception:
                ts = since + 1
            new_taps.append({
                'nfc_id':     row['nfc_id'],
                'name':       row['student_name'],
                'student_id': row['student_id'],
                'time':       row['tap_time'],
                'timestamp':  ts,
                'tx_hash':    row['tx_hash'],
                'block':      row['block_number'],
                'is_late':    row['status'] == 'late',
            })

        # Warnings/invalids from in-memory (not in DB) — use in-memory session
        if is_school_event:
            merged_warn = []
            merged_invalid = []
            for rs in related_sessions:
                merged_warn.extend(rs.get('warn_log', []))
                merged_invalid.extend(rs.get('invalid_log', []))
            new_warnings = [t for t in merged_warn if t.get('timestamp', 0) > since_buffered]
            new_invalids = [t for t in merged_invalid if t.get('timestamp', 0) > since_buffered]
        else:
            mem_sess = sessions_db.get(sess_id, sess)
            new_warnings = [t for t in mem_sess.get('warn_log', [])
                            if t.get('timestamp', 0) > since_buffered]
            new_invalids = [t for t in mem_sess.get('invalid_log', [])
                            if t.get('timestamp', 0) > since_buffered]

    present_ids = []
    late_ids = []
    excused_ids = []
    warned_ids = []
    if is_school_event:
        ps, ls, es, ws = set(), set(), set(), set()
        for rs in related_sessions:
            ps.update(rs.get('present', []))
            ls.update(rs.get('late', []))
            es.update(rs.get('excused', []))
            ws.update(rs.get('warned', []))
        present_ids = list(ps)
        late_ids = list(ls)
        excused_ids = list(es)
        warned_ids = list(ws)
    else:
        present_ids = list(sess.get('present', []))
        late_ids = list(sess.get('late', []))
        excused_ids = list(sess.get('excused', []))
        warned_ids = list(sess.get('warned', []))

    return jsonify({
        'present_count': len(present_ids),
        'late_count':    len(late_ids),
        'excused_count': len(excused_ids),
        'warned_count':  len(warned_ids),
        'new_taps':      new_taps,
        'new_warnings':  new_warnings,
        'new_invalids':  new_invalids,
        'active':        any(not rs.get('ended_at') for rs in related_sessions),
        'late_ids':      late_ids,
        'excused_ids':   excused_ids,
        'present_ids':   present_ids,
        'server_time':   now_ts,
        'auto_end_at':   sess.get('auto_end_at'),
        'grace_period':  sess.get('grace_period', 15),
    })

@app.route('/api/attendance/stats')
@login_required
def attendance_stats():
    return _attendance_stats_impl(
        request_obj=request,
        session_obj=session,
        get_db_fn=get_db,
        normalize_section_key_fn=normalize_section_key,
        jsonify_fn=jsonify,
        now_local_fn=_now_local,
    )

@app.route('/api/block_number')
def api_block_number():
    try: return jsonify({'block':web3.eth.block_number})
    except: return jsonify({'block':None})


def _network_name_from_chain_id(chain_id: int) -> str:
    if chain_id == 31337:
        return 'Hardhat Local'
    if chain_id == 1337:
        return 'Local Dev Chain'
    if chain_id == 1:
        return 'Ethereum Mainnet'
    if chain_id == 11155111:
        return 'Sepolia Testnet'
    return f'Chain {chain_id}'


@app.route('/blockchain-visualization')
def public_blockchain_visualization():
    return render_template('public_blockchain_visualization.html')


@app.route('/api/public/blockchain/visualization')
def api_public_blockchain_visualization():
    """
    Public-safe blockchain visualization payload.

    IMPORTANT: exposes no student identities or attendance payload details.
    Only block metadata and transaction hashes are returned.
    """
    limit = request.args.get('limit', type=int, default=20) or 20
    limit = max(5, min(limit, 100))
    subject = (request.args.get('subject') or '').strip()
    year = (request.args.get('year') or '').strip()

    available_subjects = []
    available_years = []
    filtered_tx_hashes = set()
    context_summary = {
        'subject': subject or 'All Subjects',
        'year': year or 'All Years',
        'attendance_logs': 0,
        'attendance_logs_on_chain': 0,
        'subject_options': [],
        'year_options': [],
        'is_filtered': bool(subject or year),
        'note': 'This blockchain view uses the same DAVS smart contract used to anchor attendance transaction hashes.',
    }

    try:
        with get_db() as conn:
            available_subjects = [
                r['subject_name'] for r in conn.execute(
                    "SELECT DISTINCT subject_name FROM sessions WHERE TRIM(subject_name) <> '' ORDER BY subject_name"
                ).fetchall()
            ]
            available_years = [
                r['year'] for r in conn.execute(
                    "SELECT DISTINCT substr(tap_time,1,4) AS year "
                    "FROM attendance_logs "
                    "WHERE LENGTH(tap_time) >= 4 AND tap_time GLOB '[0-9][0-9][0-9][0-9]*' "
                    "ORDER BY year DESC"
                ).fetchall()
                if r['year']
            ]

            where_parts = ["1=1"]
            params = []
            if subject:
                where_parts.append("s.subject_name = ?")
                params.append(subject)
            if year:
                where_parts.append("substr(a.tap_time,1,4) = ?")
                params.append(year)
            where_sql = " AND ".join(where_parts)

            totals = conn.execute(
                "SELECT COUNT(*) AS total_logs, "
                "SUM(CASE WHEN TRIM(COALESCE(a.tx_hash,'')) <> '' THEN 1 ELSE 0 END) AS onchain_logs "
                "FROM attendance_logs a "
                "JOIN sessions s ON s.sess_id = a.sess_id "
                "WHERE " + where_sql,
                params,
            ).fetchone()

            context_summary['attendance_logs'] = int((totals['total_logs'] or 0) if totals else 0)
            context_summary['attendance_logs_on_chain'] = int((totals['onchain_logs'] or 0) if totals else 0)

            context_summary['subject_options'] = available_subjects
            context_summary['year_options'] = available_years

            if subject or year:
                tx_rows = conn.execute(
                    "SELECT DISTINCT lower(TRIM(COALESCE(a.tx_hash,''))) AS tx_hash "
                    "FROM attendance_logs a "
                    "JOIN sessions s ON s.sess_id = a.sess_id "
                    "WHERE " + where_sql + " AND TRIM(COALESCE(a.tx_hash,'')) <> ''",
                    params,
                ).fetchall()
                filtered_tx_hashes = {r['tx_hash'] for r in tx_rows if r['tx_hash']}
    except Exception:
        # Keep this endpoint resilient for public access.
        context_summary['subject_options'] = []
        context_summary['year_options'] = []

    if not web3.is_connected():
        return jsonify({
            'ok': False,
            'online': False,
            'message': 'Blockchain node is offline.',
            'network': 'Offline',
            'latest_block': None,
            'chain_valid': False,
            'blocks': [],
            'context': context_summary,
        }), 200

    try:
        chain_id = int(web3.eth.chain_id)
        latest_block = int(web3.eth.block_number)
        start_block = max(0, latest_block - limit + 1)

        contract_addr = ''
        try:
            if contract is not None:
                contract_addr = (contract.address or '').lower()
            else:
                cdata = globals().get('contract_data')
                if isinstance(cdata, dict):
                    contract_addr = (cdata.get('address') or '').lower()
        except Exception:
            contract_addr = ''

        blocks = []
        prev_hash = None
        chain_valid = True

        for n in range(start_block, latest_block + 1):
            b = web3.eth.get_block(n, full_transactions=False)
            block_hash = b.hash.hex()
            parent_hash = b.parentHash.hex()
            all_tx_hashes = [tx.hex() for tx in b.transactions]

            project_tx_hashes = []
            if contract_addr:
                for txh in all_tx_hashes:
                    try:
                        r = web3.eth.get_transaction_receipt(txh)
                        to_addr = (r.get('to') or '').lower() if isinstance(r, dict) else (getattr(r, 'to', '') or '').lower()
                        c_addr = (r.get('contractAddress') or '').lower() if isinstance(r, dict) else (getattr(r, 'contractAddress', '') or '').lower()
                        logs = r.get('logs', []) if isinstance(r, dict) else getattr(r, 'logs', [])

                        is_project_tx = (to_addr == contract_addr) or (c_addr == contract_addr)
                        if not is_project_tx:
                            for lg in logs:
                                lg_addr = (lg.get('address') or '').lower() if isinstance(lg, dict) else (getattr(lg, 'address', '') or '').lower()
                                if lg_addr == contract_addr:
                                    is_project_tx = True
                                    break
                        if is_project_tx:
                            txh_l = txh.lower()
                            if filtered_tx_hashes and txh_l not in filtered_tx_hashes:
                                continue
                            project_tx_hashes.append(txh)
                    except Exception:
                        continue
            else:
                if filtered_tx_hashes:
                    project_tx_hashes = [txh for txh in all_tx_hashes if txh.lower() in filtered_tx_hashes]
                else:
                    project_tx_hashes = all_tx_hashes

            if prev_hash is not None and parent_hash != prev_hash:
                chain_valid = False
            prev_hash = block_hash

            blocks.append({
                'number': int(b.number),
                'timestamp': datetime.fromtimestamp(int(b.timestamp)).strftime('%Y-%m-%d %H:%M:%S'),
                'hash': block_hash,
                'previous_hash': parent_hash,
                'tx_hashes': project_tx_hashes,
                'tx_count': len(project_tx_hashes),
            })

        return jsonify({
            'ok': True,
            'online': True,
            'network': _network_name_from_chain_id(chain_id),
            'latest_block': latest_block,
            'chain_valid': chain_valid,
            'blocks': blocks,
            'context': context_summary,
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'online': False,
            'message': f'Unable to load blockchain data: {e}',
            'network': 'Unknown',
            'latest_block': None,
            'chain_valid': False,
            'blocks': [],
            'context': context_summary,
        }), 500

# ── MARK PICO (NFC tap handler) ───────────────────────────────────────────────

@app.route('/mark_pico', methods=['POST'])
def mark_pico():
    data=request.get_json()
    if not data or 'nfc_id' not in data: return jsonify({'status':'error'}), 400
    nfc_id=data['nfc_id'].strip().upper()
    preferred_sess_id = str(data.get('sess_id', '') or '').strip()
    print(f"[NFC TAP] {nfc_id}")

    if nfc_is_waiting():
        nfc_set_uid(nfc_id)
        return jsonify({'status':'registration','uid':nfc_id})

    # ✅ FIX: Check DB for excused students instead of in-memory sessions_db
    # This ensures that after app restart, excused students are still blocked
    with get_db() as conn:
        excused_logs = conn.execute(
            "SELECT DISTINCT sess_id FROM attendance_logs "
            "WHERE nfc_id=? AND status='excused'",
            (nfc_id,)
        ).fetchall()
    
    # Check if any of those sessions are still active
    if excused_logs:
        active_sessions = get_active_sessions()
        for log in excused_logs:
            if log['sess_id'] in active_sessions:
                return jsonify({'status': 'excused',
                                'message': 'This student is marked as Excused and cannot tap in.',
                                'nfc_id': nfc_id})

    sess_id, sess = get_active_session_for_nfc(nfc_id, preferred_sess_id=preferred_sess_id)
    if not sess:
        all_s   = get_all_students()
        student = next((s for s in all_s if s['nfcId']==nfc_id), None)
        active  = get_active_sessions()
        invalid_entry={'nfc_id':nfc_id,'timestamp':time.time(),
                       'reason':'Student not registered' if not student else 'No active session for this section'}
        for sid, asess in active.items():
            asess.setdefault('invalid_log',[]).append(invalid_entry)
            save_session(sid, asess)
        return jsonify({'status':'no_session',
                        'message':"No active session for this student's section.",
                        'debug_student':student,
                        'debug_active_sessions':list(active.keys())})

    name        = student_name_map.get(nfc_id,'Unknown')
    all_s       = get_all_students()
    student_info= next((s for s in all_s if s['nfcId']==nfc_id),{})
    student_id  = student_info.get('student_id','')

    # Check duplicate tap
    if nfc_id in sess.get('present',[]):
        warn_entry={'nfc_id':nfc_id,'name':name,'student_id':student_id,'timestamp':time.time()}
        if nfc_id not in sess.get('warned',[]): sess.setdefault('warned',[]).append(nfc_id)
        sess.setdefault('warn_log',[]).append(warn_entry)
        save_session(sess_id, sess)
        sessions_db[sess_id] = sess
        return jsonify({'status':'already_marked','name':name,'student_id':student_id,
                        'message':f'{name} is already marked present.'})

    # Determine late status
    now_dt       = _now_local()
    late_cutoff  = sess.get('late_cutoff','')
    is_late      = False
    is_school_event = str(sess.get('class_type', 'lecture')).strip().lower() == 'school_event'
    if (not is_school_event) and late_cutoff:
        try:
            cutoff_dt = datetime.strptime(late_cutoff, '%Y-%m-%d %H:%M:%S')
            is_late   = now_dt > cutoff_dt
        except:
            is_late = False

    # Record attendance to database immediately (blockchain write happens in background)
    tap_time_db   = _now_local().strftime('%Y-%m-%d %H:%M:%S')
    tap_time      = _now_local().strftime('%H:%M:%S')
    tap_timestamp = time.time()
    status_label  = 'late' if is_late else 'present'
    if is_school_event:
        # School events only track present/absent.
        status_label = 'present'
        is_late = False

    # Save to attendance_logs table immediately (tx_hash empty, will be filled by async task)
    db_save_attendance_log(
        sess_id=sess_id, nfc_id=nfc_id,
        student_name=name, student_id=student_id,
        status=status_label, tap_time=tap_time_db,
        tx_hash='', block_number=0
    )
    
    # Submit blockchain write in background (non-blocking)
    tx_hash=None; block_num=None
    if BLOCKCHAIN_ONLINE and contract and admin_account:
        from threading import Thread
        Thread(target=_mark_attendance_async, args=(nfc_id, sess_id), daemon=True).start()

    # Keep in-memory session dict in sync for live polling
    sess.setdefault('present',[]).append(nfc_id)
    if is_late and nfc_id not in sess.get('late',[]):
        sess.setdefault('late',[]).append(nfc_id)

    # FIX: always set tap_timestamp so poll_session can detect new taps
    # Note: tx_hash/block empty initially, will be filled when blockchain confirms
    sess.setdefault('tap_log',[]).append({
        'nfc_id':     nfc_id,
        'name':       name,
        'time':       tap_time,
        'timestamp':  tap_timestamp,
        'tx_hash':    '',
        'block':      0,
        'student_id': student_id,
        'is_late':    is_late,
    })
    sess.setdefault('tx_hashes',{})[nfc_id] = {
        'tx_hash': '', 'block': 0, 'time': tap_time
    }
    save_session(sess_id, sess)
    sessions_db[sess_id] = sess

    # Keep all teacher-linked school-event sessions synchronized so taps from one
    # teacher account immediately reflect in other assigned teacher accounts.
    schedule_meta = _parse_event_schedule_id(sess.get('schedule_id', '')) if is_school_event else None
    if schedule_meta:
        pattern = f"event:{schedule_meta['event_id']}:%"
        with get_db() as conn:
            sibling_rows = conn.execute(
                "SELECT sess_id FROM sessions "
                "WHERE ended_at IS NULL AND class_type='school_event' AND schedule_id LIKE ?",
                (pattern,),
            ).fetchall()
        for sr in sibling_rows:
            sibling_id = sr['sess_id']
            if sibling_id == sess_id:
                continue
            sibling = load_session(sibling_id)
            if not sibling or sibling.get('ended_at'):
                continue
            db_save_attendance_log(
                sess_id=sibling_id,
                nfc_id=nfc_id,
                student_name=name,
                student_id=student_id,
                status='present',
                tap_time=tap_time_db,
                tx_hash=tx_hash or '',
                block_number=block_num or 0,
                class_type='school_event',
            )
            if nfc_id not in sibling.get('present', []):
                sibling.setdefault('present', []).append(nfc_id)
            if nfc_id in sibling.get('late', []):
                sibling['late'].remove(nfc_id)
            sibling.setdefault('tap_log', []).append(
                {
                    'nfc_id': nfc_id,
                    'name': name,
                    'time': tap_time,
                    'timestamp': tap_timestamp,
                    'tx_hash': tx_hash,
                    'block': block_num,
                    'student_id': student_id,
                    'is_late': False,
                }
            )
            sibling.setdefault('tx_hashes', {})[nfc_id] = {
                'tx_hash': tx_hash,
                'block': block_num,
                'time': tap_time,
            }
            save_session(sibling_id, sibling)
            sessions_db[sibling_id] = sibling

    recent_attendance.append({
        'nfc_id':    nfc_id,
        'name':      name,
        'timestamp': tap_timestamp,
        'subject':   sess.get('subject_name',''),
        'is_late':   is_late,
    })
    
    # ── Email: send attendance receipt to student ─────────────────────────
    student_email = student_info.get('email', '')
    send_student_attendance_receipt(
        student_name   = name,
        student_email  = student_email,
        student_id     = student_id,
        subject_name   = sess.get('subject_name', ''),
        section_key    = sess.get('section_key', ''),
        teacher_name   = sess.get('teacher_name', ''),
        tap_time       = tap_time_db,
        status         = status_label,
        tx_hash        = tx_hash or '',
        block_num      = block_num or '',
        sess_id        = sess_id,
        nfc_id         = nfc_id,
        semester       = sess.get('semester'),
        time_slot      = sess.get('time_slot'),
    )

    return jsonify({
        'status':'ok','name':name,'student_id':student_id,
        'time':tap_time,'subject':sess.get('subject_name',''),
        'tx_hash':tx_hash,'block':block_num,
        'attendance_status': status_label,
        'is_late': is_late
    })

@app.route('/debug/tap/<nfc_id>')
def debug_tap(nfc_id):
    nfc_id=nfc_id.strip().upper()
    all_students=get_all_students()
    student=next((s for s in all_students if s['nfcId']==nfc_id),None)
    active=get_active_sessions()
    student_key=build_student_section_key(student) if student else None
    matching_session=None
    for sid,s in active.items():
        if normalize_section_key(s.get('section_key',''))==student_key:
            matching_session={**s,'session_id':sid}; break
    result={
        '1_nfc_id_received':nfc_id,
        '2_student_found':student is not None,
        '3_student_info':student,
        '4_student_section_key':student_key,
        '5_active_sessions':[{
            'session_id':sid,'subject':s.get('subject_name'),
            'section_key':s.get('section_key'),'teacher':s.get('teacher_name')
        } for sid,s in active.items()],
        '6_matching_session':matching_session,
        '7_verdict':('STUDENT NOT REGISTERED' if not student
                     else 'NO ACTIVE SESSION' if not matching_session
                     else 'SHOULD WORK')
    }
    from flask import current_app
    resp=current_app.response_class(json.dumps(result,indent=2),mimetype='application/json')
    return resp

# ── EXPORT ROUTES ─────────────────────────────────────────────────────────────

@app.route('/export/student_sessions/<nfc_id>')
@login_required
def export_student_sessions(nfc_id):
    return _export_student_sessions_impl(
        nfc_id,
        get_all_students_fn=get_all_students,
        get_db_fn=get_db,
        xl_helpers_fn=_xl_helpers,
        viewer_role=session.get('role', ''),
    )


@app.route('/export/session/<sess_id>')
@login_required
def export_session_attendance(sess_id):
    return _export_session_attendance_impl(
        sess_id,
        load_session_fn=load_session,
        is_my_session_fn=_is_my_session,
        get_all_students_fn=get_all_students,
        normalize_section_key_fn=normalize_section_key,
        build_student_section_key_fn=build_student_section_key,
        db_get_session_attendance_fn=db_get_session_attendance,
        get_db_fn=get_db,
        xl_helpers_fn=_xl_helpers,
    )


@app.route('/export/stats.xlsx')
@app.route('/export/stats/xlsx', methods=['POST'])
@login_required
def export_stats_xlsx():
    return _export_stats_xlsx_impl(
        request_obj=request,
        session_obj=session,
        build_stats_export_dataset_fn=_build_stats_export_dataset,
        load_sessions_fn=load_sessions,
        db_get_all_students_fn=db_get_all_students,
        db_get_override_fn=db_get_override,
        normalize_section_key_fn=normalize_section_key,
        build_student_section_key_fn=build_student_section_key,
        fmt_time_fn=fmt_time,
        db_get_session_attendance_fn=db_get_session_attendance,
        get_db_fn=get_db,
        xl_helpers_fn=_xl_helpers,
        now=_now_local(),
    )


@app.route('/export/stats.csv')
@login_required
def export_stats_csv():
    return _export_stats_csv_impl(
        request_obj=request,
        session_obj=session,
        get_db_fn=get_db,
        normalize_section_key_fn=normalize_section_key,
    )

@app.route('/request_registration_scan', methods=['POST'])
@admin_required
def request_registration_scan():
    try:
        nfc_set_waiting(session.get('username','admin'))
        return jsonify({'status':'ready'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

@app.route('/get_scanned_uid')
@login_required
def get_scanned_uid():
    uid = nfc_get_uid()
    if uid:
        return jsonify({'uid': uid})
    return jsonify({'uid': None})

@app.route('/registration_status')
def registration_status():
    return jsonify({'waiting': nfc_is_waiting()})

@app.route('/receive_pico_uid', methods=['POST'])
def receive_pico_uid():
    data=request.get_json()
    if not data or 'uid' not in data: return jsonify({'status':'error'}), 400
    uid=data['uid'].strip().upper()
    nfc_set_uid(uid)
    return jsonify({'status':'ok','uid':uid})


# ══════════════════════════════════════════════════════════════════════════════
# SUPER ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/superadmin/users')
@super_admin_required
def superadmin_users():
    users = db_get_all_users()
    super_admin_count = sum(1 for u in users.values() if u.get('role') == 'super_admin')
    return render_template('superadmin_users.html',
                           users=users,
                           ADMIN_ROLES=ADMIN_ROLES,
                           super_admin_count=super_admin_count,
                           is_super_admin=True,
                           can_change_role=True,
                           create_user_url=url_for('superadmin_create_user'),
                           create_button_label='Create Account')

@app.route('/superadmin/create-user', methods=['GET', 'POST'])
@super_admin_required
def superadmin_create_user():
    if request.method == 'POST':
        username  = request.form.get('username', '').strip().lower()
        fullname  = request.form.get('full_name', '').strip()
        email     = request.form.get('email', '').strip()
        role      = request.form.get('role', 'teacher')
        password  = request.form.get('password', '').strip() or 'test12345'
        if not username or not fullname:
            flash('Username and full name are required.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        if role not in {'teacher', 'admin', 'super_admin'}:
            flash('Invalid role.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        # Prevent duplicate Super Admin
        if role == 'super_admin':
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT * FROM users WHERE role='super_admin'"
                ).fetchone()
            if existing:
                flash('A Super Admin already exists. Only one Super Admin is allowed.', 'danger')
                return redirect(url_for('superadmin_create_user'))
        if db_get_user(username):
            flash(f'Username "{username}" is already taken.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        db_save_user(username, {
            'username': username, 'password': hash_password(password),
            'role': role, 'full_name': fullname, 'email': email,
            'status': 'approved', 'sections': [], 'my_subjects': [],
            'created_at': _now_local().strftime('%Y-%m-%d %H:%M:%S')
        })
        send_staff_welcome_email(
            full_name=fullname,
            email=email,
            username=username,
            role=role,
            initial_password=password,
        )
        flash(f'Account "{username}" ({role}) created successfully.', 'success')
        return redirect(url_for('superadmin_users'))
    # Check if Super Admin exists for frontend
    with get_db() as conn:
        super_admin_exists = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE role='super_admin'"
        ).fetchone()['cnt'] > 0
    return render_template('superadmin_create_user.html', show_super_admin=not super_admin_exists)

@app.route('/superadmin/promote/<username>', methods=['POST'])
@super_admin_required
def superadmin_promote(username):
    u = db_get_user(username)
    if not u:
        flash('User not found.', 'danger')
        return redirect(url_for('superadmin_users'))
    new_role = request.form.get('role', 'teacher')
    if new_role not in {'teacher', 'admin', 'super_admin'}:
        flash('Invalid role.', 'danger')
        return redirect(url_for('superadmin_users'))
    # Prevent creating a second super_admin via promote
    if new_role == 'super_admin' and u.get('role') != 'super_admin':
        with get_db() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE role='super_admin'"
            ).fetchone()['cnt']
        if existing >= 1:
            flash('A Super Admin already exists. Only one Super Admin is allowed.', 'danger')
            return redirect(url_for('superadmin_users'))
    u['role'] = new_role
    u['password'] = u.get('password', '')
    db_save_user(username, u)
    flash(f'"{username}" role changed to {new_role}.', 'success')
    return redirect(url_for('superadmin_users'))

# ── Admin: create instructor (admin can create teachers, not other admins) ──

@app.route('/admin/create-instructor', methods=['GET', 'POST'])
@admin_required
def admin_create_instructor():
    if session.get('role') != 'admin':
        flash('Normal admin access required.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        fullname = request.form.get('full_name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip() or 'test12345'
        if not username or not fullname:
            flash('Username and full name are required.', 'danger')
            return redirect(url_for('admin_create_instructor'))
        if db_get_user(username):
            flash(f'Username "{username}" is already taken.', 'danger')
            return redirect(url_for('admin_create_instructor'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('admin_create_instructor'))
        db_save_user(username, {
            'username': username, 'password': hash_password(password),
            'role': 'teacher', 'full_name': fullname, 'email': email,
            'status': 'approved', 'sections': [], 'my_subjects': [],
            'created_at': _now_local().strftime('%Y-%m-%d %H:%M:%S')
        })
        send_staff_welcome_email(
            full_name=fullname,
            email=email,
            username=username,
            role='teacher',
            initial_password=password,
        )
        flash(f'Instructor account "{username}" created successfully.', 'success')
        return redirect(url_for('dashboard', tab='faculty'))
    return render_template('admin_create_instructor.html')

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN SCHEDULING ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/schedules')
@admin_required
def admin_schedules():
    return _admin_schedules_page_impl(
        db_get_all_schedules=db_get_all_schedules,
        db_get_all_subjects=db_get_all_subjects,
        db_get_all_users=db_get_all_users,
        db_get_all_no_class_days=db_get_all_no_class_days,
        get_all_section_keys=_get_all_section_keys,
        session_obj=session,
        render_template=render_template,
        dow_names=DOW_NAMES,
        admin_roles=ADMIN_ROLES,
    )

@app.route('/admin/schedules/create', methods=['POST'])
@admin_required
def admin_schedule_create():
    return _admin_schedule_create_impl(
        request=request,
        flash=flash,
        redirect=redirect,
        url_for=url_for,
        db_get_subject=db_get_subject,
        db_get_user=db_get_user,
        normalize_section_key=normalize_section_key,
        time_mins=_time_mins,
        db_save_schedule=db_save_schedule,
        session_obj=session,
    )


@app.route('/admin/event-schedules/create', methods=['POST'])
@admin_required
def admin_event_schedule_create():
    try:
        def _parse_csv_or_json(field_name: str) -> list[str]:
            raw = request.form.get(field_name, '')
            raw = (raw or '').strip()
            if not raw:
                return []
            if raw.startswith('['):
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        return [str(x).strip() for x in data if str(x).strip()]
                except Exception:
                    pass
            return [x.strip() for x in raw.split(',') if x.strip()]

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_dt_local = request.form.get('start_at', '').strip()
        end_dt_local = request.form.get('end_at', '').strip()
        teacher_usernames = _parse_csv_or_json('selected_teachers')
        section_keys_raw = _parse_csv_or_json('selected_sections')

        if not title:
            flash('Event title is required.', 'danger')
            return redirect(url_for('admin_schedules'))
        if not start_dt_local or not end_dt_local:
            flash('Event start and end date/time are required.', 'danger')
            return redirect(url_for('admin_schedules'))

        try:
            start_dt = datetime.strptime(start_dt_local, '%Y-%m-%dT%H:%M')
            end_dt = datetime.strptime(end_dt_local, '%Y-%m-%dT%H:%M')
        except Exception:
            flash('Invalid event date/time format.', 'danger')
            return redirect(url_for('admin_schedules'))

        if end_dt <= start_dt:
            flash('Event end time must be later than start time.', 'danger')
            return redirect(url_for('admin_schedules'))

        teacher_usernames = list(dict.fromkeys(teacher_usernames))
        section_keys = list(dict.fromkeys(
            normalize_section_key(s.strip()) for s in section_keys_raw if s.strip()
        ))
        if not teacher_usernames:
            flash('Please add at least one teacher for the event.', 'danger')
            return redirect(url_for('admin_schedules'))
        if not section_keys:
            flash('Please add at least one section for the event.', 'danger')
            return redirect(url_for('admin_schedules'))

        db_save_event_schedule(
            {
                'title': title,
                'description': description,
                'teacher_usernames': teacher_usernames,
                'section_keys': section_keys,
                'start_at': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'end_at': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': session.get('username', ''),
            }
        )
        flash('School event schedule created successfully.', 'success')
    except Exception as exc:
        print(f"[EVENT] create failed: {exc}")
        flash(f'Error creating event schedule: {exc}', 'danger')
    return redirect(url_for('admin_schedules'))


@app.route('/admin/no-class-days/create', methods=['POST'])
@admin_required
def admin_no_class_day_create():
    try:
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        from_date = request.form.get('from_date', '').strip()
        to_date = request.form.get('to_date', '').strip()

        if not title:
            flash('No-class title is required.', 'danger')
            return redirect(url_for('admin_schedules'))
        if not from_date or not to_date:
            flash('No-class date range is required.', 'danger')
            return redirect(url_for('admin_schedules'))

        try:
            fd = datetime.strptime(from_date, '%Y-%m-%d').date()
            td = datetime.strptime(to_date, '%Y-%m-%d').date()
        except Exception:
            flash('Invalid no-class date format.', 'danger')
            return redirect(url_for('admin_schedules'))

        if td < fd:
            flash('No-class end date must be on or after start date.', 'danger')
            return redirect(url_for('admin_schedules'))

        db_save_no_class_day(
            {
                'title': title,
                'description': description,
                'from_date': fd.strftime('%Y-%m-%d'),
                'to_date': td.strftime('%Y-%m-%d'),
                'teacher_usernames': [u.strip() for u in request.form.get('selected_teachers', '').split(',') if u.strip()],
                'apply_all_teachers': bool(request.form.get('apply_all_teachers')),
                'created_by': session.get('username', ''),
            }
        )
        flash('No-class date range saved successfully.', 'success')
    except Exception as exc:
        flash(f'Error saving no-class date range: {exc}', 'danger')
    return redirect(url_for('admin_schedules'))


@app.route('/admin/no-class-days/<int:no_class_day_id>/delete', methods=['POST'])
@admin_required
def admin_no_class_day_delete(no_class_day_id):
    try:
        db_delete_no_class_day(no_class_day_id)
        flash('No-class range removed successfully.', 'success')
    except Exception as exc:
        flash(f'Error removing no-class range: {exc}', 'danger')
    return redirect(url_for('admin_schedules'))

@app.route('/admin/schedules/<schedule_id>/edit', methods=['POST'])
@admin_required
def admin_schedule_edit(schedule_id):
    return _admin_schedule_edit_impl(
        schedule_id=schedule_id,
        request=request,
        flash=flash,
        redirect=redirect,
        url_for=url_for,
        db_get_schedule=db_get_schedule,
        datetime_cls=datetime,
        db_get_subject=db_get_subject,
        db_get_user=db_get_user,
        normalize_section_key=normalize_section_key,
        time_mins=_time_mins,
        db_save_schedule=db_save_schedule,
    )

@app.route('/admin/schedules/<schedule_id>/delete', methods=['POST'])
@admin_required
def admin_schedule_delete(schedule_id):
    return _admin_schedule_delete_impl(
        schedule_id=schedule_id,
        db_delete_schedule=db_delete_schedule,
        flash=flash,
        redirect=redirect,
        url_for=url_for,
    )

@app.route('/api/schedules/today')
@login_required
def api_schedules_today():
    return _api_schedules_today_impl(
        session_obj=session,
        get_todays_schedules=get_todays_schedules,
        jsonify=jsonify,
        dow_names=DOW_NAMES,
    )


@app.route('/api/schedules/search')
@admin_required
def api_schedules_search():
    return _api_schedules_search_impl(
        request=request,
        db_get_all_users=db_get_all_users,
        db_get_all_subjects=db_get_all_subjects,
        jsonify=jsonify,
    )

@app.route('/api/active_sessions_info')
@login_required
def api_active_sessions_info():
    return _api_active_sessions_info_impl(
        get_active_sessions=get_active_sessions,
        session_obj=session,
        admin_roles=ADMIN_ROLES,
        is_my_session=_is_my_session,
        normalize_section_key=normalize_section_key,
        jsonify=jsonify,
    )


@app.route('/excuse/submit/<sess_id>/<nfc_id>', methods=['GET', 'POST'])
def excuse_submit(sess_id, nfc_id):
    sess = load_session(sess_id)
    if not sess:
        return jsonify({'status':'error', 'message':'Session not found'}), 404
    
    student = db_get_student(nfc_id)
    if not student:
        return jsonify({'status':'error', 'message':'Student not found'}), 404

    if request.method == 'GET':
        # Render the submission form for students
        return render_template('excuse_form.html', 
                               sess_id=sess_id, 
                               nfc_id=nfc_id, 
                               student=student, 
                               sess=sess,
                               excuse_reasons=EXCUSE_REASONS)

    reason_type   = request.form.get('reason_type', 'others')
    reason_detail = request.form.get('reason_detail', '').strip()
    
    if reason_type not in dict(EXCUSE_REASONS):
        return jsonify({'status':'error', 'message':'Invalid reason selected'}), 400
    if reason_type == 'others' and not reason_detail:
        return jsonify({'status':'error', 'message':'Please provide details for "Others"'}), 400

    attachment_file = ''
    uploaded = request.files.get('attachment')
    if not uploaded and 'attachments' in request.files:
        uploaded = request.files['attachments']
        
    if uploaded and uploaded.filename:
        try:
            attachment_file = _save_excuse_attachment(uploaded)
        except ValueError as ve:
            return jsonify({'status':'error', 'message':str(ve)}), 400

    excuse_id = db_save_excuse_request({
        'sess_id':       sess_id,
        'nfc_id':        nfc_id,
        'student_name':  student.get('name', ''),
        'student_id':    student.get('student_id', ''),
        'student_email': student.get('email', ''),
        'reason_type':   reason_type,
        'reason_detail': reason_detail,
        'attachment_file': attachment_file,
    })

    # Auto-approve if submitted by teacher for their own session or by any admin
    is_admin = session.get('role') in ADMIN_ROLES
    is_teacher = sess.get('teacher') == session.get('username', '')
    
    if is_admin or is_teacher:
        res = db_resolve_excuse(excuse_id, 'approved', session.get('username', 'system'))
        msg = 'Student marked as excused successfully.'
        reason_text = res.get('reason_detail', '') # fallback
        # Wait, db_resolve_excuse returns the row. 
        # Actually I can get the note from attendance_logs after resolve.
        with get_db() as conn:
            log_row = conn.execute("SELECT excuse_note FROM attendance_logs WHERE excuse_request_id=?", (excuse_id,)).fetchone()
            reason_text = log_row['excuse_note'] if log_row else ''
    else:
        # Notify student via email
        _send_excuse_received_email(
            student.get('email', ''), student.get('name', ''),
            sess.get('subject_name', ''), reason_type, excuse_id
        )
        msg = 'Excuse request submitted and is pending review.'
        reason_text = ''

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.accept_mimetypes:
        return jsonify({'status': 'ok', 'message': msg, 'nfc_id': nfc_id, 'reason': reason_text})
    
    flash(msg, 'success')
    return redirect(url_for('admin_sessions') if is_admin else url_for('teacher_records'))

@app.route('/admin/excuses/<int:excuse_id>/attachment')
@login_required
def admin_excuse_attachment(excuse_id):
    exc = db_get_excuse_request(excuse_id)
    if not exc or not exc.get('attachment_file'):
        flash('Attachment not found.', 'danger')
        return redirect(url_for('dashboard'))
    role = session.get('role', '')
    if role not in ADMIN_ROLES:
        sess = load_session(exc.get('sess_id', '')) if exc.get('sess_id') else None
        if role != 'teacher' or not sess or not _is_my_session(sess):
            flash('Access denied.', 'danger')
            return redirect(url_for('teacher_sessions_students'))
    fpath = _resolve_excuse_attachment_path(exc['attachment_file'])
    if not fpath or not os.path.exists(fpath):
        flash('Attachment file missing from server.', 'danger')
        return redirect(url_for('dashboard' if role in ADMIN_ROLES else 'teacher_sessions_students'))
    from flask import send_file
    return send_file(fpath, as_attachment=False)

# ── Excuse email helpers ───────────────────────────────────────────────────

def _send_excuse_received_email(email, student_name, subject_name, reason_type, excuse_id):
        _send_excuse_received_email_template(
                email=email,
                student_name=student_name,
                subject_name=subject_name,
                reason_type=reason_type,
                excuse_id=excuse_id,
                reason_labels=dict(EXCUSE_REASONS),
                send_email_fn=_send_email,
        )

def _send_excuse_resolved_email(email, student_name, reason_type, resolution):
        _send_excuse_resolved_email_template(
                email=email,
                student_name=student_name,
                reason_type=reason_type,
                resolution=resolution,
                reason_labels=dict(EXCUSE_REASONS),
                send_email_fn=_send_email,
        )

# ── helper: collect all existing section keys ────────────────────────────────
def _get_all_section_keys():
    with get_db() as conn:
        sess_rows = conn.execute(
            "SELECT DISTINCT section_key FROM sessions WHERE section_key != ''"
        ).fetchall()
        stu_rows  = conn.execute(
            "SELECT DISTINCT program, year_level, section FROM students "
            "WHERE program != '' AND year_level != '' AND section != ''"
        ).fetchall()
    keys = set()
    for r in sess_rows:
        keys.add(normalize_section_key(r['section_key']))
    for r in stu_rows:
        k = normalize_section_key(f"{r['program']}|{r['year_level']}|{r['section']}")
        if k: keys.add(k)
    return sorted(keys)

def _save_excuse_attachment(uploaded):
    """Saves an excuse attachment file and returns the secure filename."""
    if not uploaded or not uploaded.filename:
        return ''
    
    ext = uploaded.filename.rsplit('.', 1)[1].lower() if '.' in uploaded.filename else ''
    if ext not in ALLOWED_EXTENSIONS_EXCUSES:
        raise ValueError(f"File extension '.{ext}' not allowed.")
    
    fname = f"excuse_{uuid.uuid4().hex[:8]}_{secure_filename(uploaded.filename)}"
    fpath = os.path.join(UPLOAD_FOLDER_EXCUSES, fname)
    uploaded.save(fpath)
    return fname

@app.route('/teacher/schedule')
@staff_required
def teacher_schedule():
    if session.get('role') != 'teacher':
        return redirect(url_for('admin_schedules'))
    return _teacher_schedule_page_impl(
        username=session.get('username'),
        db_get_schedules_for_teacher=db_get_schedules_for_teacher,
        db_get_all_subjects=db_get_all_subjects,
        render_template=render_template,
        dow_names=DOW_NAMES,
    )

@app.route('/api/schedules/upcoming')
@login_required
def api_schedules_upcoming():
    """Upcoming schedules for notification (5-min lead time)."""
    if session.get('role') != 'teacher':
        return jsonify({'upcoming': []})
    return _api_schedules_upcoming_impl(
        username=session.get('username'),
        now_dt=_now_local(),
        db_get_schedules_for_teacher=db_get_schedules_for_teacher,
        jsonify=jsonify,
        timedelta=timedelta,
    )

def _row_to_dict(row):
    return dict(row) if row else {}

import subprocess as _sp
import os as _os
import sys as _sys


def _env_flag(name, default=False):
    value = (_os.getenv(name) or '').strip().lower()
    if not value:
        return default
    return value in ('1', 'true', 'yes', 'on')

def _launch_nfc_listener():
    if not _env_flag('ENABLE_NFC_LISTENER', default=False):
        print('[NFC] Auto-launch disabled. Set ENABLE_NFC_LISTENER=1 to enable locally.')
        return
    listener = _os.path.join(_os.path.dirname(__file__), 'nfc_listener.py')
    if not _os.path.exists(listener):
        print("[NFC] nfc_listener.py not found — skipping auto-launch.")
        return
    # Kill any existing nfc_listener process first
    if _sys.platform == 'win32':
        _sp.run(['taskkill', '/F', '/IM', 'python.exe', '/FI',
                 f'WINDOWTITLE eq nfc_listener'],
                capture_output=True)
        proc = _sp.Popen(
            [_sys.executable, listener],
            creationflags=0x00000008 | 0x08000000,  # DETACHED_PROCESS + CREATE_NO_WINDOW
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            close_fds=True,
        )
    else:
        proc = _sp.Popen(
            [_sys.executable, listener],
            start_new_session=True,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
        )
    print(f"[NFC] Listener started in background (PID {proc.pid})")
    print("[NFC] Check nfc_listener.log for tap activity.")

# Ensure automation loop runs under WSGI servers (e.g., Gunicorn on Railway),
# not only after the first request.
if os.getenv('DISABLE_AUTO_THREAD', '0') != '1':
    try:
        ensure_automation_thread_running()
    except Exception as _auto_boot_err:
        print(f"[AUTO] Startup thread init failed: {_auto_boot_err}")

if __name__ == '__main__':
    # Only launch NFC listener in development
    if os.getenv('FLASK_ENV') != 'production':
        _launch_nfc_listener()
    
    # Get port from environment variable
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') != 'production'

    app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)