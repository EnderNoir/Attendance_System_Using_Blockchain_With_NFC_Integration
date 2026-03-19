from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
from web3 import Web3
from datetime import datetime
from functools import wraps
import json, os, secrets, time, csv, io, hashlib, uuid, re, sqlite3, calendar as _cal
from collections import deque
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
    PDF_READY = True
except ImportError:
    PDF_READY = False

app = Flask(__name__)
app.secret_key = 'davs-super-secret-2024'

@app.context_processor
def inject_globals():
    return dict(
        photos_db     = db_get_all_photos(),
        pending_count = db_pending_count(),
        fmt_time      = fmt_time,
        fmt_time_short= fmt_time_short,
    )

hardhat_url = "http://127.0.0.1:8545"
web3 = Web3(Web3.HTTPProvider(hardhat_url))
if not web3.is_connected():
    raise Exception("Cannot connect to Hardhat.")
print("Connected to Hardhat Network")

contract_data_path = os.path.join(os.path.dirname(__file__), 'attendance-contract.json')
with open(contract_data_path) as f:
    contract_data = json.load(f)
contract      = web3.eth.contract(address=contract_data['address'], abi=contract_data['abi'])
admin_account = web3.eth.accounts[0]

BASE_DIR      = os.path.dirname(__file__)
DB_FILE       = os.path.join(BASE_DIR, 'davs.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── SECTION KEY NORMALIZER ────────────────────────────────────────────────────
# FIX #1, #2, #3: Normalize all section keys to consistent format
# "BS Computer Science|1st Year|A" — no extra spaces, consistent casing

def normalize_section_key(key):
    """Normalize a section key to consistent format: 'Course|Year Level|Section'"""
    if not key:
        return key
    parts = [p.strip() for p in key.split('|')]
    if len(parts) == 3:
        course    = parts[0].strip()
        year      = parts[1].strip()
        section   = parts[2].strip().upper()
        # Normalize year level format
        year_map = {
            '1': '1st Year', '2': '2nd Year', '3': '3rd Year', '4': '4th Year', '5': '5th Year',
            '1st': '1st Year', '2nd': '2nd Year', '3rd': '3rd Year', '4th': '4th Year',
            '1st year': '1st Year', '2nd year': '2nd Year', '3rd year': '3rd Year',
            '4th year': '4th Year', '5th year': '5th Year',
        }
        year_normalized = year_map.get(year.lower(), year)
        return f"{course}|{year_normalized}|{section}"
    return key

def build_student_section_key(student):
    """Build normalized section key from student data."""
    course     = (student.get('course') or '').strip()
    year_level = (student.get('year_level') or '').strip()
    section    = (student.get('section') or '').strip().upper()
    if not course or not year_level or not section:
        return None
    return normalize_section_key(f"{course}|{year_level}|{section}")

# ── SQLite ────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS users ("
            "  username TEXT PRIMARY KEY, password TEXT NOT NULL,"
            "  role TEXT NOT NULL DEFAULT 'teacher', full_name TEXT NOT NULL DEFAULT '',"
            "  email TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',"
            "  sections_json TEXT NOT NULL DEFAULT '[]',"
            "  my_subjects_json TEXT NOT NULL DEFAULT '[]',"
            "  created_at TEXT NOT NULL DEFAULT ''"
            ");"
            "CREATE TABLE IF NOT EXISTS subjects ("
            "  subject_id TEXT PRIMARY KEY, name TEXT NOT NULL,"
            "  course_code TEXT NOT NULL DEFAULT '', units TEXT NOT NULL DEFAULT '3',"
            "  created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT ''"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_subj_code ON subjects(course_code);"
            "CREATE TABLE IF NOT EXISTS photos ("
            "  person_id TEXT PRIMARY KEY, filename TEXT NOT NULL"
            ");"
            "CREATE TABLE IF NOT EXISTS student_overrides ("
            "  nfc_id TEXT PRIMARY KEY, full_name TEXT DEFAULT '',"
            "  student_id TEXT DEFAULT '', email TEXT DEFAULT '',"
            "  contact TEXT DEFAULT '', adviser TEXT DEFAULT '',"
            "  major TEXT DEFAULT '', semester TEXT DEFAULT '',"
            "  school_year TEXT DEFAULT '', date_registered TEXT DEFAULT '',"
            "  course TEXT DEFAULT '', year_level TEXT DEFAULT '',"
            "  section TEXT DEFAULT ''"
            ");"
            "CREATE TABLE IF NOT EXISTS sessions ("
            "  sess_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL,"
            "  subject_name TEXT NOT NULL DEFAULT '', course_code TEXT NOT NULL DEFAULT '',"
            "  units INTEGER NOT NULL DEFAULT 3, time_slot TEXT NOT NULL DEFAULT '',"
            "  section_key TEXT NOT NULL DEFAULT '', teacher TEXT NOT NULL DEFAULT '',"
            "  teacher_name TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL,"
            "  late_cutoff TEXT NOT NULL DEFAULT '', ended_at TEXT,"
            "  present_json TEXT NOT NULL DEFAULT '[]', late_json TEXT NOT NULL DEFAULT '[]',"
            "  excused_json TEXT NOT NULL DEFAULT '[]', warned_json TEXT NOT NULL DEFAULT '[]',"
            "  absent_json TEXT NOT NULL DEFAULT '[]',"
            "  tap_log_json TEXT NOT NULL DEFAULT '[]', warn_log_json TEXT NOT NULL DEFAULT '[]',"
            "  invalid_log_json TEXT NOT NULL DEFAULT '[]',"
            "  excuse_notes_json TEXT NOT NULL DEFAULT '{}',"
            "  tx_hashes_json TEXT NOT NULL DEFAULT '{}'"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_sess_teacher  ON sessions(teacher);"
            "CREATE INDEX IF NOT EXISTS idx_sess_ended    ON sessions(ended_at);"
            "CREATE INDEX IF NOT EXISTS idx_sess_section  ON sessions(section_key);"
            # FIX #9: Replace flag files with DB table for NFC registration mode
            "CREATE TABLE IF NOT EXISTS nfc_registration ("
            "  id INTEGER PRIMARY KEY CHECK (id = 1),"
            "  waiting INTEGER NOT NULL DEFAULT 0,"
            "  scanned_uid TEXT NOT NULL DEFAULT '',"
            "  requested_by TEXT NOT NULL DEFAULT '',"
            "  requested_at TEXT NOT NULL DEFAULT ''"
            ");"
            "INSERT OR IGNORE INTO nfc_registration (id, waiting, scanned_uid) VALUES (1, 0, '');"
        )
    print("[DB] SQLite tables ready ->", DB_FILE)

def _row_to_dict(row):
    if row is None: return None
    d = dict(row)
    for col in ('present_json','late_json','excused_json','warned_json','absent_json',
                'tap_log_json','warn_log_json','invalid_log_json'):
        key = col.replace('_json','')
        d[key] = json.loads(d.pop(col,'[]') or '[]')
    d['excuse_notes'] = json.loads(d.pop('excuse_notes_json','{}') or '{}')
    d['tx_hashes']    = json.loads(d.pop('tx_hashes_json',   '{}') or '{}')
    # Normalize section_key on read
    if d.get('section_key'):
        d['section_key'] = normalize_section_key(d['section_key'])
    return d

def load_sessions():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sessions").fetchall()
    return {r['sess_id']: _row_to_dict(r) for r in rows}

def load_session(sess_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE sess_id=?", (sess_id,)).fetchone()
    return _row_to_dict(row)

def save_session(sess_id, s):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO sessions (
                sess_id,subject_id,subject_name,course_code,units,time_slot,
                section_key,teacher,teacher_name,started_at,late_cutoff,ended_at,
                present_json,late_json,excused_json,warned_json,absent_json,
                tap_log_json,warn_log_json,invalid_log_json,
                excuse_notes_json,tx_hashes_json
            ) VALUES (
                :sess_id,:subject_id,:subject_name,:course_code,:units,:time_slot,
                :section_key,:teacher,:teacher_name,:started_at,:late_cutoff,:ended_at,
                :present_json,:late_json,:excused_json,:warned_json,:absent_json,
                :tap_log_json,:warn_log_json,:invalid_log_json,
                :excuse_notes_json,:tx_hashes_json
            )
            ON CONFLICT(sess_id) DO UPDATE SET
                subject_id=excluded.subject_id, subject_name=excluded.subject_name,
                course_code=excluded.course_code, units=excluded.units,
                time_slot=excluded.time_slot, section_key=excluded.section_key,
                teacher=excluded.teacher, teacher_name=excluded.teacher_name,
                started_at=excluded.started_at, late_cutoff=excluded.late_cutoff,
                ended_at=excluded.ended_at,
                present_json=excluded.present_json, late_json=excluded.late_json,
                excused_json=excluded.excused_json, warned_json=excluded.warned_json,
                absent_json=excluded.absent_json,
                tap_log_json=excluded.tap_log_json, warn_log_json=excluded.warn_log_json,
                invalid_log_json=excluded.invalid_log_json,
                excuse_notes_json=excluded.excuse_notes_json,
                tx_hashes_json=excluded.tx_hashes_json
        """, {
            'sess_id':       sess_id,
            'subject_id':    s.get('subject_id',''),
            'subject_name':  s.get('subject_name',''),
            'course_code':   s.get('course_code',''),
            'units':         s.get('units',3),
            'time_slot':     s.get('time_slot',''),
            'section_key':   normalize_section_key(s.get('section_key','')),
            'teacher':       s.get('teacher',''),
            'teacher_name':  s.get('teacher_name',''),
            'started_at':    s.get('started_at',''),
            'late_cutoff':   s.get('late_cutoff',''),
            'ended_at':      s.get('ended_at'),
            'present_json':  json.dumps(s.get('present',[])),
            'late_json':     json.dumps(s.get('late',[])),
            'excused_json':  json.dumps(s.get('excused',[])),
            'warned_json':   json.dumps(s.get('warned',[])),
            'absent_json':   json.dumps(s.get('absent',[])),
            'tap_log_json':  json.dumps(s.get('tap_log',[])),
            'warn_log_json': json.dumps(s.get('warn_log',[])),
            'invalid_log_json': json.dumps(s.get('invalid_log',[])),
            'excuse_notes_json': json.dumps(s.get('excuse_notes',{})),
            'tx_hashes_json':    json.dumps(s.get('tx_hashes',{})),
        })

def save_sessions(sessions_dict):
    for sid, s in sessions_dict.items():
        save_session(sid, s)

def migrate_json_to_sqlite():
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
            'created_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

# ── USER helpers ──────────────────────────────────────────────────────────────

def _user_row(row):
    if row is None: return None
    d = dict(row)
    raw_sections    = json.loads(d.pop('sections_json','[]') or '[]')
    d['my_subjects'] = json.loads(d.pop('my_subjects_json','[]') or '[]')
    # FIX #1: Normalize all section keys when loading user
    d['sections'] = [normalize_section_key(s) for s in raw_sections]
    return d

def db_get_all_users():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    return {r['username']: _user_row(r) for r in rows}

def db_get_user(username):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return _user_row(row)

def db_save_user(username, u):
    # Normalize sections before saving
    sections = [normalize_section_key(s) for s in u.get('sections', [])]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (username,password,role,full_name,email,status,"
            "sections_json,my_subjects_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(username) DO UPDATE SET"
            " password=excluded.password, role=excluded.role,"
            " full_name=excluded.full_name, email=excluded.email,"
            " status=excluded.status, sections_json=excluded.sections_json,"
            " my_subjects_json=excluded.my_subjects_json, created_at=excluded.created_at",
            (username, u.get('password',''), u.get('role','teacher'),
             u.get('full_name',''), u.get('email',''), u.get('status','pending'),
             json.dumps(sections), json.dumps(u.get('my_subjects',[])),
             u.get('created_at',''))
        )

def db_delete_user(username):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username=?", (username,))

def db_pending_count():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0]

# ── SUBJECT helpers ───────────────────────────────────────────────────────────

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

# ── PHOTO helpers ─────────────────────────────────────────────────────────────

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

# ── STUDENT OVERRIDE helpers ──────────────────────────────────────────────────

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

# ── NFC REGISTRATION MODE (DB-based, FIX #9) ─────────────────────────────────

def nfc_set_waiting(username):
    with get_db() as conn:
        conn.execute(
            "UPDATE nfc_registration SET waiting=1, scanned_uid='', requested_by=?, requested_at=? WHERE id=1",
            (username, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )

def nfc_is_waiting():
    with get_db() as conn:
        row = conn.execute("SELECT waiting FROM nfc_registration WHERE id=1").fetchone()
    return bool(row and row['waiting'])

def nfc_set_uid(uid):
    with get_db() as conn:
        conn.execute(
            "UPDATE nfc_registration SET waiting=0, scanned_uid=? WHERE id=1",
            (uid,)
        )

def nfc_get_uid():
    with get_db() as conn:
        row = conn.execute("SELECT scanned_uid FROM nfc_registration WHERE id=1").fetchone()
    if row and row['scanned_uid']:
        uid = row['scanned_uid']
        conn.execute("UPDATE nfc_registration SET scanned_uid='' WHERE id=1")
        return uid
    return None

def nfc_clear():
    with get_db() as conn:
        conn.execute("UPDATE nfc_registration SET waiting=0, scanned_uid='' WHERE id=1")

# ── Startup ───────────────────────────────────────────────────────────────────

def load_student_names():
    try:
        ef = contract.events.StudentRegistered.create_filter(from_block=0, to_block=web3.eth.block_number)
        for e in ef.get_all_entries():
            student_name_map[e['args']['nfcId']] = e['args']['name'].split(' | ')[0]
    except Exception as ex:
        print(f"Warning: {ex}")

init_db()
migrate_json_to_sqlite()
sessions_db = load_sessions()

student_name_map = {}
load_student_names()
recent_attendance = deque(maxlen=50)

DEPARTMENTS = {'DIT': {'label':'Department of Information Technology','courses':['BS Computer Science','BS Information Technology']}}
YEAR_LEVELS  = ['1st Year','2nd Year','3rd Year','4th Year']
SECTIONS     = ['A','B','C','D']

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_time(dt_str):
    if not dt_str: return '—'
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%b %d, %Y · %I:%M %p')
    except:
        return dt_str

def fmt_time_short(dt_str):
    if not dt_str: return '—'
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%I:%M %p').lstrip('0')
    except:
        return dt_str

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        return f(*a,**kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if 'username' not in session: return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.')
            return redirect(url_for('teacher_dashboard'))
        return f(*a,**kw)
    return dec

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
    try:
        ef = contract.events.StudentRegistered.create_filter(from_block=0, to_block=web3.eth.block_number)
        entries = ef.get_all_entries()
    except:
        return []
    students, seen = [], set()
    for e in entries:
        a = e['args']
        if a['nfcId'] in seen: continue
        seen.add(a['nfcId'])
        p = parse_student(a['name'])
        s = {**p,'raw_name':a['name'],'nfcId':a['nfcId'],'address':a['studentAddr'],'tx_hash':e['transactionHash'].hex()}
        ov = db_get_override(a['nfcId'])
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
        # FIX #1: Normalize section field to just the letter (A, B, C, D)
        s['section'] = s['section'].strip().upper()
        students.append(s)
    return students

def get_attendance_records(nfc_id):
    try:
        ts,pf = contract.functions.getAttendance(nfc_id).call()
        return [(datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'),p) for t,p in zip(ts,pf)]
    except:
        return []

# FIX #4: Calculate attendance rate from sessions, not raw blockchain taps
def get_student_attendance_stats(nfc_id):
    """
    Calculate attendance stats from SQLite sessions — the real source of truth.
    Returns dict with total, present, late, excused, absent, rate.
    """
    all_students = get_all_students()
    student = next((s for s in all_students if s['nfcId'] == nfc_id), None)
    if not student:
        return {'total': 0, 'present': 0, 'late': 0, 'excused': 0, 'absent': 0, 'rate': 0}

    student_key = build_student_section_key(student)
    if not student_key:
        return {'total': 0, 'present': 0, 'late': 0, 'excused': 0, 'absent': 0, 'rate': 0}

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE ended_at IS NOT NULL AND section_key=?",
            (student_key,)
        ).fetchall()

    total = late = excused = present = absent = 0
    for row in rows:
        s = _row_to_dict(row)
        total += 1
        if   nfc_id in s.get('excused', []): excused += 1
        elif nfc_id in s.get('late',    []): late    += 1
        elif nfc_id in s.get('present', []): present += 1
        else:                                absent  += 1

    attended = present + late
    rate = round(attended / total * 100, 1) if total else 0
    return {'total': total, 'present': present + late, 'late': late,
            'excused': excused, 'absent': absent, 'rate': rate}

def teacher_students(user):
    allowed = set(user.get('sections', []))
    # Normalize allowed sections
    allowed = {normalize_section_key(s) for s in allowed}
    result = []
    for s in get_all_students():
        key = build_student_section_key(s)
        if key and key in allowed:
            result.append(s)
    return result

def get_active_sessions():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
    return {r['sess_id']: _row_to_dict(r) for r in rows}

def get_active_session_for_nfc(nfc_id):
    """FIX #3: Use normalized section key matching to find active session."""
    all_students = get_all_students()
    student = next((s for s in all_students if s['nfcId'] == nfc_id), None)
    if not student: return None, None

    student_key = build_student_section_key(student)
    if not student_key: return None, None

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE ended_at IS NULL AND section_key=?",
            (student_key,)
        ).fetchone()
    if row:
        s = _row_to_dict(row)
        return row['sess_id'], s
    return None, None

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index') if session.get('role')=='admin' else url_for('teacher_dashboard'))
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
        return redirect(url_for('index') if user['role']=='admin' else url_for('teacher_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        confirm  = request.form['confirm_password']
        fullname = request.form['full_name'].strip()
        email    = request.form['email'].strip()
        role     = request.form['role']
        # FIX #1: Normalize sections on signup
        raw_sections = request.form.getlist('sections')
        sections = [normalize_section_key(s) for s in raw_sections]

        if db_get_user(username):    flash('Username already taken.'); return redirect(url_for('signup'))
        if password != confirm:      flash('Passwords do not match.'); return redirect(url_for('signup'))
        if len(password) < 6:        flash('Password must be at least 6 characters.'); return redirect(url_for('signup'))
        if role=='teacher' and not sections:
            flash('Teachers must select at least one section.'); return redirect(url_for('signup'))
        db_save_user(username, {
            'username':username,'password':hash_password(password),'role':role,
            'full_name':fullname,'email':email,'status':'pending','sections':sections,
            'my_subjects':[],'created_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        photo_file = request.files.get('profile_photo')
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1].lower()
            if ext in ('.jpg','.jpeg','.png','.gif','.webp'):
                fname = f"photo_{username}{ext}"
                photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
                db_save_photo(username, fname)
        flash('Account created! Waiting for admin approval.'); return redirect(url_for('login'))
    return render_template('signup.html', departments=DEPARTMENTS, year_levels=YEAR_LEVELS, sections=SECTIONS)

# ── ADMIN MAIN ────────────────────────────────────────────────────────────────

@app.route('/')
@admin_required
def index():
    return render_template('index.html',
                           active_sessions=get_active_sessions(),
                           subjects_db=db_get_all_subjects(),
                           users_db=db_get_all_users())

@app.route('/register', methods=['GET','POST'])
@admin_required
def register():
    if request.method == 'POST':
        nfc_id = request.form['nfc_id'].strip().upper()
        name   = request.form['name'].strip()
        extras = []
        raw_date = request.form.get('date_registered','').strip()
        if raw_date:
            try:
                d = datetime.strptime(raw_date, '%Y-%m')
                raw_date = d.strftime('%B %Y')
            except:
                pass

        # FIX #1: Normalize section to uppercase single letter on registration
        section_val = request.form.get('section','').strip().upper()

        for k,prefix in [('student_id','ID'),('course','Course'),('year_level','Year'),
                          ('adviser','Adviser'),('email','Email'),('contact','Tel'),
                          ('semester','Sem'),('school_year','SY')]:
            v = request.form.get(k,'').strip()
            if v: extras.append(f"{prefix}:{v}")

        # Add normalized section
        if section_val: extras.append(f"Sec:{section_val}")
        if raw_date: extras.append(f"RegDate:{raw_date}")
        major = request.form.get('major','').strip() or 'N/A'
        extras.append(f"Major:{major}")

        on_chain = name + (' | ' + ' | '.join(extras) if extras else '')
        pk = "0x" + secrets.token_hex(32)
        addr = web3.eth.account.from_key(pk).address
        try:
            tx = contract.functions.registerStudent(addr,nfc_id,on_chain).transact({'from':admin_account})
            web3.eth.wait_for_transaction_receipt(tx)
            student_name_map[nfc_id] = name
            photo_file = request.files.get('student_photo')
            if photo_file and photo_file.filename:
                ext = os.path.splitext(photo_file.filename)[1].lower()
                if ext in ('.jpg','.jpeg','.png','.gif','.webp'):
                    fname = f"photo_{nfc_id.replace(' ','_')}{ext}"
                    photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
                    db_save_photo(nfc_id, fname)
            flash(f'Student {name} registered successfully.')
        except Exception as e:
            flash('NFC ID already registered.' if 'already' in str(e).lower() else f'Error: {e}')
        return redirect(url_for('index'))
    return render_template('register.html', subjects_db=db_get_all_subjects(), users_db=db_get_all_users())


@app.route('/parse_registration_pdf', methods=['POST'])
@admin_required
def parse_registration_pdf():
    import traceback
    if not PDF_READY:
        return jsonify({'error': 'Run: pip install pdfminer.six'}), 500
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    if not (f.filename or '').lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    course_map = {
        'BSCS':'BS Computer Science','BSIT':'BS Information Technology',
        'BSIS':'BS Information Systems','BSCOE':'BS Computer Engineering',
        'BSECE':'BS Electronics Engineering','BSEE':'BS Electrical Engineering',
        'BSCE':'BS Civil Engineering','BSME':'BS Mechanical Engineering',
        'BSED':'BS Education','BSN':'BS Nursing','BSA':'BS Accountancy',
        'BSBA':'BS Business Administration',
    }
    year_map = {'1st':'1st Year','2nd':'2nd Year','3rd':'3rd Year',
                '4th':'4th Year','5th':'5th Year'}

    result = {
        'student_id':'','name':'','course':'','year_level':'',
        'section':'','adviser':'','email':'','contact':'',
        'semester':'','school_year':'','date_registered':'','major':'',
        'subjects':[]
    }

    try:
        raw_bytes = f.read()
        if not raw_bytes:
            return jsonify({'error': 'Uploaded file is empty'}), 400

        text = pdf_extract_text(io.BytesIO(raw_bytes))
        if not text or not text.strip():
            return jsonify({'error': 'Could not extract text — PDF may be a scanned image'}), 400

        text  = re.sub(r'\t', ' ', text)
        text  = re.sub(r' +', ' ', text)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        full  = '\n'.join(lines)

        def grab(pattern):
            m = re.search(pattern, full, re.IGNORECASE)
            return m.group(1).strip() if m else ''

        result['student_id']  = grab(r'Student Number:\s*(\S+)')
        result['semester']    = grab(r'Semester:\s*([A-Za-z]+)').title()
        result['school_year'] = grab(r'School Year:\s*(\d{4}-\d{4})')
        # FIX #1: Normalize section to uppercase single letter from PDF
        raw_section = grab(r'Section:\s*(\S+)')
        result['section'] = raw_section.strip().upper() if raw_section else ''

        m = re.search(r'Student Name:\s*(.+)', full)
        if m:
            raw_name = m.group(1).strip().upper()
            result['name'] = raw_name.title()
            clean = re.sub(r'\b[A-Z]\.\s*', '', raw_name)
            name_parts = clean.split()
            if len(name_parts) >= 2:
                last  = name_parts[-1].lower()
                first = ''.join(p.lower() for p in name_parts[:-1])
                result['email'] = f"sc.{first}.{last}@cvsu.edu.ph"

        m = re.search(r'Date:\s*(.+)', full)
        if m:
            _raw = m.group(1).strip().split('|')[0].strip()
            _date_val = ''
            _m2 = re.search(r'([A-Za-z]+)\s+(\d{4})', _raw)
            if _m2:
                try:
                    _d = datetime.strptime(f"{_m2.group(1)} {_m2.group(2)}", "%B %Y")
                    _date_val = _d.strftime('%Y-%m')
                except:
                    pass
            if not _date_val:
                _m3 = re.search(r'([A-Za-z]+)\s+(\d{1,2})[,\s]+(\d{4})', _raw)
                if _m3:
                    try:
                        _d = datetime.strptime(f"{_m3.group(1)} {_m3.group(2)} {_m3.group(3)}", "%B %d %Y")
                        _date_val = _d.strftime('%Y-%m')
                    except:
                        pass
            if not _date_val:
                _m4 = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', _raw)
                if _m4:
                    try:
                        _d = datetime(int(_m4.group(3)), int(_m4.group(1)), int(_m4.group(2)))
                        _date_val = _d.strftime('%Y-%m')
                    except:
                        pass
            result['date_registered'] = _date_val or _raw

        m = re.search(r'Course:\s*(\S+)', full)
        if m: result['course'] = course_map.get(m.group(1).strip(), m.group(1).strip())

        m = re.search(r'(?<!School )Year:\s*(1st|2nd|3rd|4th|5th)', full)
        if m: result['year_level'] = year_map.get(m.group(1).strip(), m.group(1).strip())

        m = re.search(r'Major:\s*(.+)', full)
        if m:
            maj = m.group(1).strip()
            result['major'] = '' if maj.upper() in ('N/A','NA','') else maj

        hdr_m  = re.search(r'Units Lec Lab Hour', full)
        fees_m = re.search(r'Laboratory Fees', full)
        new_subjects = []
        if hdr_m and fees_m:
            subj_block = full[hdr_m.end():fees_m.start()]
            subj_lines = [l.strip() for l in subj_block.split('\n') if l.strip()]
            course_codes, descriptions, units_list = [], [], []
            for ln in subj_lines:
                if re.match(r'^\d{9}$', ln): pass
                elif re.match(r'^[A-Z]{2,5}\d[A-Z0-9]*$', ln): pass
                elif re.match(r'^[A-Z]+\s*[\d]+\w*$', ln): course_codes.append(ln)
                elif re.match(r'^\d+\.\d{2}$', ln): units_list.append(ln)
                elif re.match(r'^[A-Z][A-Z0-9\s]+$', ln) and len(ln) > 3: descriptions.append(ln)
            n = min(len(course_codes), len(descriptions), len(units_list))
            for i in range(n):
                try: u_val = str(round(float(units_list[i])))
                except: u_val = '3'
                new_subjects.append({'course_code':course_codes[i],'name':descriptions[i].title(),'units':u_val})

        result['subjects'] = new_subjects

        added_to_catalogue = []
        all_s = db_get_all_subjects()
        existing_codes = {v.get('course_code','').upper():k for k,v in all_s.items()}
        for subj in new_subjects:
            code_upper = subj['course_code'].upper()
            if code_upper not in existing_codes:
                new_id = str(uuid.uuid4())[:8]
                db_save_subject(new_id, {
                    'name':subj['name'],'course_code':subj['course_code'],
                    'units':subj['units'],'created_by':session.get('username','admin'),
                    'created_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                existing_codes[code_upper] = new_id
                added_to_catalogue.append(subj['course_code'])

        return jsonify({**result, 'added_to_catalogue': added_to_catalogue})

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[parse_registration_pdf ERROR]\n{tb}")
        return jsonify({'error': f'{type(e).__name__}: {str(e)}'}), 500

@app.route('/mark', methods=['POST'])
@login_required
def mark():
    nfc_id = request.form['nfc_id'].strip().upper()
    try:
        tx = contract.functions.markAttendance(nfc_id).transact({'from':admin_account})
        web3.eth.wait_for_transaction_receipt(tx)
        name = student_name_map.get(nfc_id,"Unknown")
        recent_attendance.append({'nfc_id':nfc_id,'name':name,'timestamp':time.time()})
        flash(f'Attendance marked for {name}')
    except Exception as e:
        flash(f'Error: {e}')
    return redirect(url_for('index'))

@app.route('/dashboard')
@admin_required
def dashboard():
    students  = get_all_students()
    all_users = db_get_all_users()
    teachers  = {u:d for u,d in all_users.items() if d.get('role') in ('admin','teacher')}
    return render_template('dashboard.html', students=students, teachers=teachers, fmt_time=fmt_time)

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    person_id = request.form.get('person_id','').strip()
    if not person_id or 'photo' not in request.files:
        return jsonify({'error':'Missing data'}), 400
    f = request.files['photo']
    if not f or f.filename == '':
        return jsonify({'error':'No file selected'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ('.jpg','.jpeg','.png','.gif','.webp'):
        return jsonify({'error':'Only image files allowed'}), 400
    filename = f"photo_{person_id.replace(' ','_')}{ext}"
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    db_save_photo(person_id, filename)
    return jsonify({'ok':True,'filename':filename,'url':f'/static/uploads/{filename}'})

@app.route('/get_my_photo')
@login_required
def get_my_photo():
    photo = db_get_photo(session.get('username',''))
    if photo: return jsonify({'url':f'/static/uploads/{photo}'})
    return jsonify({'url':None})

@app.route('/api/my_profile')
@login_required
def api_my_profile():
    user = db_get_user(session.get('username',''))
    if not user: return jsonify({'error':'Not found'}), 404
    return jsonify({
        'username':  user.get('username',''),
        'full_name': user.get('full_name',''),
        'email':     user.get('email',''),
        'role':      user.get('role',''),
        'status':    user.get('status',''),
        'created':   user.get('created_at',''),
        'sections':  user.get('sections',[]),
        'photo':     db_get_photo(session.get('username','')) or '',
    })

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = session.get('username')
    user = db_get_user(username)
    if not user: return jsonify({'error':'Not logged in'}), 401
    data = request.get_json()
    if data.get('full_name'):
        user['full_name'] = data['full_name'].strip()
        session['full_name'] = user['full_name']
    if data.get('email'):
        user['email'] = data['email'].strip()
    if data.get('password') and len(data['password']) >= 6:
        user['password'] = hash_password(data['password'])
    db_save_user(username, user)
    return jsonify({'ok':True,'full_name':user['full_name']})

@app.route('/delete_photo', methods=['POST'])
@login_required
def delete_photo():
    person_id = request.form.get('person_id','').strip()
    existing  = db_get_photo(person_id)
    if existing:
        old_file = os.path.join(UPLOAD_FOLDER, existing)
        if os.path.exists(old_file):
            try: os.remove(old_file)
            except: pass
        db_delete_photo(person_id)
    return jsonify({'ok':True})

@app.route('/reports')
@admin_required
def attendance_report():
    # FIX #4: Use session-based stats instead of raw blockchain taps
    report = []
    for s in get_all_students():
        stats = get_student_attendance_stats(s['nfcId'])
        report.append({**s, **stats})
    return render_template('attendance_report.html',
                           students=sorted(report, key=lambda x: -x['rate']),
                           subjects_db=db_get_all_subjects(), fmt_time=fmt_time)

@app.route('/view/<nfc_id>')
@login_required
def view_attendance(nfc_id):
    if session.get('role') == 'teacher':
        user = get_current_user()
        if not any(s['nfcId']==nfc_id for s in teacher_students(user)):
            flash('Access denied.'); return redirect(url_for('teacher_dashboard'))
    records      = get_attendance_records(nfc_id)
    student_info = next((s for s in get_all_students() if s['nfcId']==nfc_id), {})
    return render_template('attendance.html', nfc_id=nfc_id, records=records,
                           student=student_info, fmt_time=fmt_time)

@app.route('/api/student_sessions/<nfc_id>')
@login_required
def student_sessions_api(nfc_id):
    all_students    = get_all_students()
    student         = next((x for x in all_students if x['nfcId']==nfc_id), None)
    student_section = ''
    if student:
        student_section = build_student_section_key(student) or ''

    with get_db() as _conn:
        _all_rows = _conn.execute(
            "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY started_at DESC"
        ).fetchall()
    result = []
    for row in _all_rows:
        s   = _row_to_dict(row)
        sec = s.get('section_key','')
        # FIX #3: Use normalized key comparison
        if student_section and normalize_section_key(sec) != student_section: continue
        status = None
        if   nfc_id in s.get('excused', []): status = 'excused'
        elif nfc_id in s.get('late',    []): status = 'late'
        elif nfc_id in s.get('present', []): status = 'present'
        elif student_section == normalize_section_key(sec): status = 'absent'
        if not status: continue
        tx_info = s.get('tx_hashes',{}).get(nfc_id,{})
        result.append({
            'subject_name': s.get('subject_name',''),
            'course_code':  s.get('course_code',''),
            'teacher_name': s.get('teacher_name',''),
            'section_key':  sec,
            'time_slot':    s.get('time_slot',''),
            'date':         s.get('started_at','')[:10] if s.get('started_at') else '',
            'started_at':   s.get('started_at',''),
            'status':       status,
            'tx_hash':      tx_info.get('tx_hash',''),
            'block':        str(tx_info.get('block','')),
        })
    result.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(result)

@app.route('/update_student', methods=['POST'])
@admin_required
def update_student():
    data   = request.get_json()
    nfc_id = data.get('nfc_id','').strip()
    if not nfc_id: return jsonify({'error':'Missing nfc_id'}), 400
    fields = ['full_name','student_id','email','contact','adviser','major',
              'semester','school_year','date_registered','course','year_level','section']
    override_data = {f: data.get(f,'').strip() for f in fields if data.get(f)}
    # FIX #1: Normalize section to uppercase
    if 'section' in override_data:
        override_data['section'] = override_data['section'].upper()
    db_save_override(nfc_id, override_data)
    return jsonify({'ok':True})

@app.route('/update_faculty', methods=['POST'])
@admin_required
def update_faculty():
    data     = request.get_json()
    username = data.get('username','').strip()
 
    # Security: non-admins can only edit their own account
    if session.get('role') != 'admin' and session.get('username') != username:
        return jsonify({'error': 'Access denied'}), 403
 
    user = db_get_user(username)
    if not user: return jsonify({'error': 'User not found'}), 404
 
    if data.get('full_name'):  user['full_name'] = data['full_name'].strip()
    if data.get('email') is not None: user['email'] = data['email'].strip()
 
    # Admins can change role/status; teachers cannot change their own role/status
    if session.get('role') == 'admin':
        if data.get('role') in ('admin','teacher'):   user['role']   = data['role']
        if data.get('status') in ('approved','pending','rejected'): user['status'] = data['status']
 
    # Sections — admin only
    if session.get('role') == 'admin' and 'sections' in data and isinstance(data['sections'], list):
        user['sections'] = [normalize_section_key(s) for s in data['sections']]
 
    new_pw = (data.get('new_password') or '').strip()
    if new_pw:
        if len(new_pw) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user['password'] = hash_password(new_pw)
 
    new_username = (data.get('new_username') or '').strip().lower()
    if new_username and new_username != username:
        if db_get_user(new_username):
            return jsonify({'error': f'Username "{new_username}" is already taken'}), 409
        user['username'] = new_username
        db_save_user(new_username, user)
        db_delete_user(username)
        db_rename_photo_key(username, new_username)
        # Update session if the user is editing their own profile
        if session.get('username') == username:
            session['username']  = new_username
            session['full_name'] = user['full_name']
    else:
        db_save_user(username, user)
        if session.get('username') == username:
            session['full_name'] = user['full_name']
 
    # Return full_name so the frontend can update the sidebar immediately
    return jsonify({'ok': True, 'full_name': user['full_name']})

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
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(['Name','NFC ID','Student ID','Course','Year','Section','Adviser','Email','Contact','Date & Time','Status'])
    for s in get_all_students():
        for ts,p in (get_attendance_records(s['nfcId']) or [('No records','')]):
            w.writerow([s['name'],s['nfcId'],s['student_id'],s['course'],s['year_level'],s['section'],
                        s['adviser'],s['email'],s['contact'],ts,'Present' if p is True else ('Absent' if p is False else '')])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition':f'attachment; filename=attendance_all_{datetime.now().strftime("%Y%m%d")}.csv'})

@app.route('/export/<nfc_id>.csv')
@login_required
def export_csv_single(nfc_id):
    name = student_name_map.get(nfc_id,'Unknown'); out = io.StringIO(); w = csv.writer(out)
    w.writerow(['Student Name','NFC ID','Date & Time','Status'])
    for ts,p in get_attendance_records(nfc_id):
        w.writerow([name,nfc_id,ts,'Present' if p else 'Absent'])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition':f'attachment; filename=attendance_{nfc_id}.csv'})

# ── ADMIN USER MANAGEMENT ─────────────────────────────────────────────────────

@app.route('/admin/users')
@admin_required
def manage_users():
    all_u    = db_get_all_users()
    pending  = {u:d for u,d in all_u.items() if d['status']=='pending'}
    approved = {u:d for u,d in all_u.items() if d['status']=='approved' and u!='admin'}
    rejected = {u:d for u,d in all_u.items() if d['status']=='rejected'}
    return render_template('admin_users.html', pending=pending, approved=approved,
                           rejected=rejected, fmt_time=fmt_time)

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
        db_delete_user(username); flash(f'{user["full_name"]} deleted.')
    return redirect(url_for('manage_users'))

# ── ADMIN SUBJECT MANAGEMENT ──────────────────────────────────────────────────

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
                          'created_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
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
    with get_db() as _conn:
        _active_rows = _conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
        _ended_rows  = _conn.execute("SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC").fetchall()
    active = {r['sess_id']: _row_to_dict(r) for r in _active_rows}
    ended  = {r['sess_id']: _row_to_dict(r) for r in _ended_rows}
    return render_template('admin_sessions.html', active=active, ended=ended,
                           subjects_db=db_get_all_subjects(), fmt_time=fmt_time)

# ── TEACHER ───────────────────────────────────────────────────────────────────

def _build_teacher_context(user):
    """Shared helper: build sections + my_subjects for a teacher."""
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
        if sid in all_subj and skey in sections:
            active_sid = None
            for sess_id, sess_obj in get_active_sessions().items():
                if (sess_obj.get('subject_id')==sid
                        and normalize_section_key(sess_obj.get('section_key',''))==skey
                        and sess_obj.get('teacher')==session['username']):
                    active_sid = sess_id; break
            parts = skey.split('|')
            subj_info = all_subj[sid]
            my_subjects.append({
                'subject_id':   sid,
                'subject_name': subj_info['name'],
                'course_code':  subj_info.get('course_code',''),
                'units':        subj_info.get('units','3'),
                'section_key':  skey,
                'section_label':sections[skey]['label'],
                'course':       parts[0] if parts else '',
                'year':         parts[1] if len(parts)>1 else '',
                'section':      parts[2] if len(parts)>2 else '',
                'active_session_id': active_sid,
                'student_count':     sections[skey]['count']
            })
    return sections, my_subjects, all_subj

@app.route('/teacher')
@login_required
def teacher_dashboard():
    """Teacher home page — overview stats, live sessions, quick actions."""
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user = get_current_user()
    sections, my_subjects, _ = _build_teacher_context(user)

    # Live sessions for this teacher
    live_sessions = {sid: s for sid, s in get_active_sessions().items()
                     if s.get('teacher') == session['username']}

    # Total completed sessions
    with get_db() as conn:
        total_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE teacher=? AND ended_at IS NOT NULL",
            (session['username'],)
        ).fetchone()[0]

    # Total students across all sections
    all_teacher_students = teacher_students(user)
    total_students = len(all_teacher_students)

    return render_template('teacher_dashboard.html',
        user=user,
        sections=sections,
        my_subjects=my_subjects,
        live_sessions=live_sessions,
        total_sessions=total_sessions,
        total_students=total_students,
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )


@app.route('/teacher/sessions-students')
@login_required
def teacher_sessions_students():
    """Combined Sessions & Students page — separate from dashboard."""
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user = get_current_user()

    # All sessions for this teacher
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE teacher=? ORDER BY started_at DESC",
            (session['username'],)
        ).fetchall()
    sessions_data = {r['sess_id']: _row_to_dict(r) for r in rows}

    # Subject names for filter dropdown
    subjects = sorted(set(
        s.get('subject_name', '') for s in sessions_data.values() if s.get('subject_name')
    ))

    # Student standing data
    report = []
    for s in teacher_students(user):
        stats = get_student_attendance_stats(s['nfcId'])
        report.append({**s, **stats})
    students = sorted(report, key=lambda x: -x['rate'])

    now_str = datetime.now().strftime('%Y')

    return render_template('teacher_sessions_students.html',
        user=user,
        sessions_data=sessions_data,
        sessions_json={sid: {
            'subject_name': s.get('subject_name', ''),
            'course_code':  s.get('course_code', ''),
            'section_key':  s.get('section_key', ''),
            'teacher_name': s.get('teacher_name', ''),
            'started_at':   s.get('started_at', ''),
            'ended_at':     s.get('ended_at', ''),
            'time_slot':    s.get('time_slot', ''),
            'present':      s.get('present', []),
            'late':         s.get('late', []),
            'excused':      s.get('excused', []),
            'tx_hashes':    s.get('tx_hashes', {}),
        } for sid, s in sessions_data.items()},
        subjects=subjects,
        students=students,
        now=now_str,
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )

@app.route('/teacher/create-session')
@login_required
def teacher_create_session():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user = get_current_user()
    sections, my_subjects, all_subj = _build_teacher_context(user)
    return render_template('teacher_create_session.html', user=user, sections=sections,
                           my_subjects=my_subjects, subjects_db=all_subj)

@app.route('/teacher/records')
@login_required
def teacher_records():
    if session.get('role') == 'admin': return redirect(url_for('attendance_report'))
    user = get_current_user()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE teacher=? AND ended_at IS NOT NULL ORDER BY started_at DESC",
            (session['username'],)
        ).fetchall()
    teacher_sessions_data = {r['sess_id']: _row_to_dict(r) for r in rows}
    subjects = sorted(set(s.get('subject_name','') for s in teacher_sessions_data.values() if s.get('subject_name')))
    all_students = get_all_students()
    return render_template('teacher_records.html', user=user,
                           sessions_data=teacher_sessions_data, subjects=subjects,
                           all_students=all_students, fmt_time=fmt_time)

@app.route('/api/session_attendance/<sess_id>')
@login_required
def api_session_attendance(sess_id):
    """
    Returns full attendance list for a session — all enrolled students
    with their present/late/absent/excused status and tx hash.
    Used by teacher_sessions_students.html modal loader.
    """
    sess = load_session(sess_id)
    if sess is None:
        return jsonify({'error': 'Session not found'}), 404
    if session.get('role') != 'admin' and sess.get('teacher') != session.get('username'):
        return jsonify({'error': 'Access denied'}), 403

    all_students = get_all_students()
    section_key  = normalize_section_key(sess.get('section_key', ''))
    enrolled     = [s for s in all_students if build_student_section_key(s) == section_key]

    present_ids = set(sess.get('present', []))
    late_ids    = set(sess.get('late',    []))
    excused_ids = set(sess.get('excused', []))
    tx_hashes   = sess.get('tx_hashes', {})

    students_out = []
    for s in sorted(enrolled, key=lambda x: x['name']):
        nid = s['nfcId']
        if   nid in excused_ids: status = 'excused'
        elif nid in late_ids:    status = 'late'
        elif nid in present_ids: status = 'present'
        else:                    status = 'absent'
        tx_info = tx_hashes.get(nid, {})
        students_out.append({
            'nfc_id':     nid,
            'name':       s['name'],
            'student_id': s.get('student_id', ''),
            'status':     status,
            'tx_hash':    tx_info.get('tx_hash', ''),
            'block':      str(tx_info.get('block', '')),
            'time':       tx_info.get('time', ''),
        })

    return jsonify({
        'students':     students_out,
        'subject_name': sess.get('subject_name', ''),
        'course_code':  sess.get('course_code', ''),
        'section_key':  section_key,
        'time_slot':    sess.get('time_slot', ''),
        'started_at':   sess.get('started_at', ''),
        'ended_at':     sess.get('ended_at', ''),
    })


@app.route('/teacher/subjects/add', methods=['POST'])
@login_required
def teacher_add_subject():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    user       = get_current_user()
    subject_id = request.form.get('subject_id','').strip()
    section_key= normalize_section_key(request.form.get('section_key','').strip())
    if not subject_id or not section_key:
        flash('Please select both a subject and a section.'); return redirect(url_for('teacher_create_session'))
    subj = db_get_subject(subject_id)
    if not subj: flash('Subject not found.'); return redirect(url_for('teacher_create_session'))
    for ms in user.get('my_subjects',[]):
        if ms['subject_id']==subject_id and normalize_section_key(ms['section_key'])==section_key:
            flash('Already assigned.'); return redirect(url_for('teacher_create_session'))
    user.setdefault('my_subjects',[]).append({'subject_id':subject_id,'section_key':section_key})
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

@app.route('/teacher/session/start', methods=['POST'])
@login_required
def start_session():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    subject_id  = request.form.get('subject_id','').strip()
    section_key = normalize_section_key(request.form.get('section_key','').strip())
    if not subject_id or not section_key:
        flash('Missing subject or section.'); return redirect(url_for('teacher_create_session'))
    for s in get_active_sessions().values():
        if (s.get('teacher')==session['username']
                and normalize_section_key(s.get('section_key',''))==section_key):
            flash('You already have an active session for that section.')
            return redirect(url_for('teacher_create_session'))
    time_slot = request.form.get('time_slot','').strip()
    subj_data = db_get_subject(subject_id) or {}
    units     = int(subj_data.get('units', 3))
    now       = datetime.now()
    from datetime import timedelta
    late_cutoff_dt = now.replace(second=0, microsecond=0) + timedelta(minutes=30)
    sess_id   = str(uuid.uuid4())[:12]
    new_sess  = {
        'subject_id':   subject_id,
        'subject_name': subj_data.get('name',''),
        'course_code':  subj_data.get('course_code',''),
        'units':        units,
        'time_slot':    time_slot,
        'section_key':  section_key,
        'teacher':      session['username'],
        'teacher_name': session['full_name'],
        'started_at':   now.strftime('%Y-%m-%d %H:%M:%S'),
        'late_cutoff':  late_cutoff_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'ended_at':     None,
        'present':[],'late':[],'excused':[],'warned':[],'absent':[],
        'tap_log':[],'warn_log':[],'invalid_log':[],'excuse_notes':{},'tx_hashes':{}
    }
    save_session(sess_id, new_sess)
    sessions_db[sess_id] = new_sess
    flash(f'Classroom session started for {subj_data.get("name","")}.')
    return redirect(url_for('live_session', sess_id=sess_id))

@app.route('/teacher/session/<sess_id>')
@login_required
def live_session(sess_id):
    sess = load_session(sess_id)
    if sess is None: flash('Session not found.'); return redirect(url_for('teacher_dashboard'))
    if session.get('role')!='admin' and sess.get('teacher')!=session['username']:
        flash('Access denied.'); return redirect(url_for('teacher_dashboard'))

    all_students     = get_all_students()
    section_key      = sess.get('section_key','')
    # FIX #1, #3: Use normalized key matching for enrolled students
    section_students = [s for s in all_students
                        if build_student_section_key(s) == normalize_section_key(section_key)]

    present_set  = set(sess.get('present',[]))
    late_set     = set(sess.get('late',[]))
    excused_set  = set(sess.get('excused',[]))
    student_statuses = []
    for s in section_students:
        nid = s['nfcId']
        if   nid in excused_set: status = 'excused'
        elif nid in late_set:    status = 'late'
        elif nid in present_set: status = 'present'
        else:                    status = 'absent'
        student_statuses.append({**s,'status':status})

    return render_template('session_live.html', sess=sess, sess_id=sess_id,
                           section_students=section_students,
                           student_statuses=student_statuses,
                           present_list=[s for s in section_students if s['nfcId'] in present_set],
                           absent_list=[s for s in section_students if s['nfcId'] not in present_set and s['nfcId'] not in excused_set],
                           tap_log=sess.get('tap_log',[]),
                           is_active=not sess.get('ended_at'),
                           fmt_time=fmt_time, fmt_time_short=fmt_time_short)

@app.route('/teacher/session/<sess_id>/end', methods=['POST'])
@login_required
def end_session(sess_id):
    if sess_id not in sessions_db: flash('Session not found.'); return redirect(url_for('teacher_dashboard'))
    sess = sessions_db[sess_id]
    if session.get('role')!='admin' and sess.get('teacher')!=session['username']:
        flash('Access denied.'); return redirect(url_for('teacher_dashboard'))

    # FIX #7: On session end, permanently record absent students
    all_students    = get_all_students()
    section_key     = sess.get('section_key','')
    section_students= [s for s in all_students
                       if build_student_section_key(s) == normalize_section_key(section_key)]
    present_set = set(sess.get('present', []))
    excused_set = set(sess.get('excused', []))
    absent_list = [s['nfcId'] for s in section_students
                   if s['nfcId'] not in present_set and s['nfcId'] not in excused_set]
    sess['absent']    = absent_list
    sess['ended_at']  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_session(sess_id, sess)
    sessions_db[sess_id] = sess

    present_count = len([n for n in present_set if n not in sess.get('late',[])])
    late_count    = len(sess.get('late', []))
    flash(f'Session ended. {present_count} present, {late_count} late, {len(absent_list)} absent.')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/session/<sess_id>/excuse', methods=['POST'])
@login_required
def excuse_student(sess_id):
    nfc_id = request.form.get('nfc_id','').strip()
    note   = request.form.get('note','Excused').strip()
    sess   = load_session(sess_id)
    if sess is None: return jsonify({'error':'not found'}), 404
    if session.get('role')!='admin' and sess.get('teacher')!=session['username']:
        return jsonify({'error':'access denied'}), 403
    excused       = sess.setdefault('excused', [])
    excuse_notes  = sess.setdefault('excuse_notes', {})
    if nfc_id not in excused: excused.append(nfc_id)
    # Also remove from absent if already marked
    if nfc_id in sess.get('absent', []):
        sess['absent'].remove(nfc_id)
    excuse_notes[nfc_id] = note
    save_session(sess_id, sess)
    sessions_db[sess_id] = sess
    name = student_name_map.get(nfc_id, nfc_id)
    return jsonify({'status':'ok','name':name,'nfc_id':nfc_id,'note':note})

@app.route('/teacher/sessions')
@login_required
def teacher_sessions():
    if session.get('role') == 'admin': return redirect(url_for('index'))
    with get_db() as _conn:
        _rows = _conn.execute("SELECT * FROM sessions WHERE teacher=? ORDER BY started_at DESC",
                              (session['username'],)).fetchall()
    my_sessions = {r['sess_id']: _row_to_dict(r) for r in _rows}
    return render_template('teacher_sessions.html', my_sessions=my_sessions, fmt_time=fmt_time)

@app.route('/teacher/reports')
@login_required
def teacher_reports():
    if session.get('role') == 'admin': return redirect(url_for('attendance_report'))
    user   = get_current_user()
    # FIX #4: Use session-based stats for teacher reports
    report = []
    for s in teacher_students(user):
        stats = get_student_attendance_stats(s['nfcId'])
        report.append({**s, **stats})
    return render_template('teacher_reports.html', user=user,
                           students=sorted(report, key=lambda x: -x['rate']))

@app.route('/teacher/export/section.csv')
@login_required
def teacher_export():
    user     = get_current_user()
    sec_key  = request.args.get('section','')
    students = teacher_students(user)
    if sec_key:
        norm_key = normalize_section_key(sec_key)
        students = [s for s in students if build_student_section_key(s) == norm_key]
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(['Name','NFC ID','Student ID','Course','Year','Section','Date & Time','Status'])
    for s in students:
        for ts,p in (get_attendance_records(s['nfcId']) or [('No records','')]):
            w.writerow([s['name'],s['nfcId'],s['student_id'],s['course'],s['year_level'],s['section'],
                        ts,'Present' if p is True else ('Absent' if p is False else '')])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition':f'attachment; filename=section_{datetime.now().strftime("%Y%m%d")}.csv'})

# ── SHARED API ────────────────────────────────────────────────────────────────

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
    sess  = load_session(sess_id)
    if sess is None: return jsonify({'error':'not found'}), 404
    since = request.args.get('since', type=float, default=0)
    new_taps     = [t for t in sess.get('tap_log',[])      if t.get('timestamp',0)>since]
    new_warnings = [t for t in sess.get('warn_log',[])     if t.get('timestamp',0)>since]
    new_invalids = [t for t in sess.get('invalid_log',[])  if t.get('timestamp',0)>since]
    return jsonify({
        'present_count': len(sess.get('present',[])),
        'late_count':    len(sess.get('late',[])),
        'excused_count': len(sess.get('excused',[])),
        'warned_count':  len(sess.get('warned',[])),
        'new_taps':      new_taps,
        'new_warnings':  new_warnings,
        'new_invalids':  new_invalids,
        'active':        not sess.get('ended_at'),
        'late_ids':      sess.get('late',[]),
        'excused_ids':   sess.get('excused',[]),
        'present_ids':   sess.get('present',[]),
    })

@app.route('/api/attendance/stats')
@login_required
def attendance_stats():
    # FIX #3: Corrected parameter names to match what frontend sends
    period     = request.args.get('period',      'today')
    f_month    = request.args.get('month',       '').strip()
    f_year_num = request.args.get('year_num',    request.args.get('year', '')).strip()
    f_subject  = request.args.get('subject',     '').strip()
    f_section  = request.args.get('section_key', '').strip()
    f_year_lvl = request.args.get('year',        '').strip()
    f_instr    = request.args.get('instructor',  '').strip()
    role       = session.get('role')
    username   = session.get('username')
    now        = datetime.now()

    if period == 'today':
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0); end_dt = None
    elif period == 'month':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        mo = int(f_month)    if f_month    and f_month.isdigit()    else now.month
        start_dt = datetime(yr, mo, 1)
        end_dt   = datetime(yr, mo, _cal.monthrange(yr, mo)[1], 23, 59, 59)
    elif period == 'year':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        start_dt = datetime(yr, 1, 1); end_dt = datetime(yr, 12, 31, 23, 59, 59)
    else:
        start_dt = datetime(2000, 1, 1); end_dt = None

    with get_db() as _sc:
        all_sess = {r['sess_id']: _row_to_dict(r) for r in _sc.execute("SELECT * FROM sessions").fetchall()}

    # Normalize filter section key
    f_section_norm = normalize_section_key(f_section) if f_section else ''

    filtered = {}
    for sid, s in all_sess.items():
        if not s.get('started_at'): continue
        try:    sess_dt = datetime.strptime(s['started_at'], '%Y-%m-%d %H:%M:%S')
        except: continue
        if sess_dt < start_dt:           continue
        if end_dt and sess_dt > end_dt:  continue
        if role == 'teacher' and s.get('teacher') != username: continue
        if f_section_norm and normalize_section_key(s.get('section_key','')) != f_section_norm: continue
        if f_year_lvl:
            parts = s.get('section_key','').split('|')
            if len(parts)<2 or parts[1] != f_year_lvl: continue
        if f_subject and s.get('subject_name','') != f_subject: continue
        if f_instr   and s.get('teacher_name','') != f_instr:   continue
        filtered[sid] = s

    all_students       = get_all_students()
    total              = {'present':0,'late':0,'absent':0,'excused':0}
    trend_buckets      = {}
    subjects_breakdown = {}
    counted_sessions   = 0

    for sid, s in filtered.items():
        sess_dt     = datetime.strptime(s['started_at'], '%Y-%m-%d %H:%M:%S')
        present_ids = set(s.get('present',  []))
        late_ids    = set(s.get('late',     []))
        excused_ids = set(s.get('excused',  []))
        section_key = normalize_section_key(s.get('section_key',''))
        subj_name   = s.get('subject_name','Unknown')
        subj_code   = s.get('course_code','')
        subj_label  = f"[{subj_code}] {subj_name}" if subj_code else subj_name
        # FIX #10: Correct enrolled student counting using normalized key
        enrolled     = [st for st in all_students if build_student_section_key(st) == section_key]
        enrolled_ids = set(st['nfcId'] for st in enrolled)
        sess_counts  = {'present':0,'late':0,'absent':0,'excused':0}
        for nid in enrolled_ids:
            if   nid in excused_ids: sess_counts['excused'] += 1
            elif nid in late_ids:    sess_counts['late']    += 1
            elif nid in present_ids: sess_counts['present'] += 1
            else:                    sess_counts['absent']  += 1
        for k in total: total[k] += sess_counts[k]
        counted_sessions += 1

        if   period=='today': tkey = sess_dt.strftime('%I %p').lstrip('0')
        elif period=='month': tkey = sess_dt.strftime('%b %d')
        elif period=='year':  tkey = sess_dt.strftime('%b')
        else:                 tkey = str(sess_dt.year)

        if tkey not in trend_buckets:
            trend_buckets[tkey] = {'present':0,'late':0,'absent':0,'excused':0}
        for k in sess_counts: trend_buckets[tkey][k] += sess_counts[k]

        if subj_label not in subjects_breakdown:
            subjects_breakdown[subj_label] = {'present':0,'late':0,'absent':0,'excused':0,'sessions':0}
        subjects_breakdown[subj_label]['sessions'] += 1
        for k in sess_counts: subjects_breakdown[subj_label][k] += sess_counts[k]

    all_subj_labels = sorted(set(
        (f"[{s.get('course_code','')}] {s.get('subject_name','')}" if s.get('course_code') else s.get('subject_name',''))
        for s in filtered.values() if s.get('subject_name')
    ))

    return jsonify({'role':role,'period':period,'donut':total,'trend':trend_buckets,
                    'subjects':subjects_breakdown,'all_subjects':all_subj_labels,
                    'session_count':counted_sessions})

@app.route('/api/block_number')
def api_block_number():
    try: return jsonify({'block':web3.eth.block_number})
    except: return jsonify({'block':None})

# ── EXPORT ROUTES ─────────────────────────────────────────────────────────────

@app.route('/export/student_sessions/<nfc_id>')
@login_required
def export_student_sessions(nfc_id):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        f_status  = request.args.get('status','').strip()
        f_subject = request.args.get('subject','').strip()
        stud_name = request.args.get('name','Student').strip()

        all_students    = get_all_students()
        student         = next((x for x in all_students if x['nfcId']==nfc_id), None)
        student_section = build_student_section_key(student) if student else ''

        with get_db() as conn:
            rows = conn.execute("SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY started_at DESC").fetchall()

        sessions = []
        for row in rows:
            s   = _row_to_dict(row)
            sec = normalize_section_key(s.get('section_key',''))
            if student_section and sec != student_section: continue
            if   nfc_id in s.get('excused',[]): status='Excused'
            elif nfc_id in s.get('late',[]):    status='Late'
            elif nfc_id in s.get('present',[]): status='Present'
            elif student_section == sec:         status='Absent'
            else: continue
            if f_status  and status.lower() != f_status:  continue
            if f_subject and s.get('subject_name','') != f_subject: continue
            tx = s.get('tx_hashes',{}).get(nfc_id,{})
            sessions.append({'subject':s.get('subject_name',''),'code':s.get('course_code',''),
                             'teacher':s.get('teacher_name',''),'date':s.get('started_at','')[:10],
                             'time_slot':s.get('time_slot',''),'status':status,
                             'tx_hash':tx.get('tx_hash',''),'block':str(tx.get('block',''))})

        C_DARK='0D1117'; C_WHITE='FFFFFF'; C_HEADER='1E2530'; C_LIGHT='F1F5F9'
        ST_C={'Present':('10B981','0D3D2A'),'Late':('F59E0B','3D3010'),'Absent':('EF4444','3D1010'),'Excused':('60A5FA','102040')}
        def _fill(h):  return PatternFill("solid",fgColor=h)
        def _border():
            s=Side(style='thin',color="CBD5E1"); return Border(left=s,right=s,top=s,bottom=s)
        def _ctr(): return Alignment(horizontal='center',vertical='center',wrap_text=True)
        def _lft(): return Alignment(horizontal='left',vertical='center',wrap_text=True)

        wb=Workbook(); ws=wb.active; ws.title="Session Log"; ws.sheet_view.showGridLines=False
        ws.merge_cells("A1:H1"); c=ws["A1"]; c.value=f"Attendance Record — {stud_name}"
        c.font=Font(name='Arial',size=14,bold=True,color='2D6A27'); c.fill=_fill(C_DARK); c.alignment=_ctr(); ws.row_dimensions[1].height=32
        for col in range(2,9): ws.cell(row=1,column=col).fill=_fill(C_DARK)
        ws.merge_cells("A2:H2"); c=ws["A2"]
        filters=[]
        if f_status: filters.append('Status: '+f_status.capitalize())
        if f_subject: filters.append('Subject: '+f_subject)
        c.value=f"NFC: {nfc_id}  |  Filters: {' | '.join(filters) if filters else 'None'}"
        c.font=Font(name='Arial',size=9,color="94A3B8"); c.fill=_fill(C_DARK); c.alignment=_ctr()
        for col in range(2,9): ws.cell(row=2,column=col).fill=_fill(C_DARK)
        for col in range(1,9): ws.cell(row=3,column=col).fill=_fill("F8FAFC"); ws.row_dimensions[3].height=6
        hdrs=["Subject","Code","Instructor","Date","Time Slot","Status","TX Hash","Block #"]
        ws_=[28,10,24,14,16,10,42,10]
        for ci,(h,w) in enumerate(zip(hdrs,ws_),1):
            ws.column_dimensions[get_column_letter(ci)].width=w
            c=ws.cell(row=4,column=ci,value=h)
            c.font=Font(name='Arial',size=10,bold=True,color=C_WHITE); c.fill=_fill(C_HEADER); c.alignment=_ctr(); c.border=_border()
        ws.row_dimensions[4].height=20
        for ri,s in enumerate(sessions,5):
            ws.row_dimensions[ri].height=17; rf=_fill(C_LIGHT) if ri%2==0 else _fill(C_WHITE)
            vals=[s['subject'],s['code'],s['teacher'],s['date'],s['time_slot'],s['status'],s['tx_hash'],s['block']]
            for ci,val in enumerate(vals,1):
                c=ws.cell(row=ri,column=ci,value=val); c.border=_border(); c.alignment=_ctr() if ci>2 else _lft()
                if ci==6:
                    fg,bg=ST_C.get(val,('FFFFFF','333333')); c.font=Font(name='Arial',size=10,bold=True,color=fg); c.fill=_fill(bg)
                elif ci==7: c.font=Font(name='Arial',size=8,color="6B7280"); c.fill=rf
                else: c.font=Font(name='Arial',size=10); c.fill=rf

        _name_parts = stud_name.split()
        _last  = (_name_parts[-1] if _name_parts else 'student').lower().replace(' ','_')
        _first = ('_'.join(_name_parts[:-1]) if len(_name_parts)>1 else '').lower().replace(' ','_')
        _name_slug = re.sub(r'[^a-z0-9_]','',f"{_last}_{_first}" if _first else _last)
        _filters = []
        if f_status:  _filters.append(f_status)
        if f_subject: _filters.append(re.sub(r'[^a-z0-9]','',f_subject.lower()[:12]))
        _filter_str = ('_'+'_'.join(_filters)) if _filters else ''
        fname = request.args.get('filename') or f"{_name_slug}_attendance_record{_filter_str}_{datetime.now().strftime('%Y%m')}.xlsx"

        output=io.BytesIO(); wb.save(output); output.seek(0)
        return Response(output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition':f'attachment;filename={fname}'})
    except Exception as e:
        import traceback; return Response(f"Export error: {traceback.format_exc()}", status=500, mimetype='text/plain')


@app.route('/export/session/<sess_id>')
@login_required
def export_session_attendance(sess_id):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        sess = load_session(sess_id)
        if not sess: flash('Session not found.'); return redirect(url_for('admin_sessions'))
        if session.get('role')!='admin' and sess.get('teacher')!=session.get('username'):
            flash('Access denied.'); return redirect(url_for('teacher_sessions'))

        all_students = get_all_students()
        section_key  = normalize_section_key(sess.get('section_key',''))
        # FIX #10: Use normalized key for enrolled student list
        enrolled     = [s for s in all_students if build_student_section_key(s) == section_key]
        present_ids  = set(sess.get('present',[]))
        late_ids     = set(sess.get('late',[]))
        excused_ids  = set(sess.get('excused',[]))
        tx_hashes    = sess.get('tx_hashes',{})

        C_DARK='0D1117'; C_HEADER='1E3A1A'; C_WHITE='FFFFFF'; C_LIGHT='F1F5F9'
        ST_MAP={'Present':('10B981','0D3D2A'),'Late':('F59E0B','3D3010'),'Absent':('EF4444','3D1010'),'Excused':('60A5FA','102040')}
        def _fill(h):  return PatternFill('solid',fgColor=h)
        def _border():
            s=Side(style='thin',color='CBD5E1'); return Border(left=s,right=s,top=s,bottom=s)
        def _ctr(): return Alignment(horizontal='center',vertical='center',wrap_text=True)
        def _lft(): return Alignment(horizontal='left',vertical='center',wrap_text=True)

        wb=Workbook(); ws=wb.active; ws.title='Session Attendance'; ws.sheet_view.showGridLines=False
        ws.merge_cells('A1:G1'); c=ws['A1']; c.value='Session Attendance Report'
        c.font=Font(name='Arial',size=14,bold=True,color='2D6A27'); c.fill=_fill(C_DARK); c.alignment=_ctr(); ws.row_dimensions[1].height=32
        for col in range(2,8): ws.cell(row=1,column=col).fill=_fill(C_DARK)
        meta=[
            f"Subject: {sess.get('subject_name','')} {'['+sess.get('course_code','')+']' if sess.get('course_code') else ''}",
            f"Section: {section_key.replace('|',' · ')}  |  Instructor: {sess.get('teacher_name','')}",
            f"Time Slot: {sess.get('time_slot','—')}  |  Started: {sess.get('started_at','—')}  |  Ended: {sess.get('ended_at','Still running')}",
            f"Present: {len(present_ids)}  |  Late: {len(late_ids)}  |  Absent: {len(enrolled)-len(present_ids)-len(excused_ids)}  |  Excused: {len(excused_ids)}",
        ]
        for ri,text in enumerate(meta,2):
            ws.merge_cells(f'A{ri}:G{ri}'); c=ws.cell(row=ri,column=1,value=text)
            c.font=Font(name='Arial',size=9,color='94A3B8'); c.fill=_fill(C_DARK); c.alignment=_ctr(); ws.row_dimensions[ri].height=16
            for col in range(2,8): ws.cell(row=ri,column=col).fill=_fill(C_DARK)
        for col in range(1,8): ws.cell(row=6,column=col).fill=_fill('F8FAFC'); ws.row_dimensions[6].height=6
        col_widths=[4,24,14,18,12,12,44]
        headers=['#','Student Name','Student ID','NFC Card UID','Status','Time','Blockchain TX Hash']
        for ci,(h,w) in enumerate(zip(headers,col_widths),1):
            ws.column_dimensions[get_column_letter(ci)].width=w
            c=ws.cell(row=7,column=ci,value=h); c.font=Font(name='Arial',size=10,bold=True,color=C_WHITE)
            c.fill=_fill(C_HEADER); c.alignment=_ctr(); c.border=_border()
        ws.row_dimensions[7].height=20
        row_n=8
        for idx,st in enumerate(sorted(enrolled,key=lambda x:x['name']),1):
            nid=st['nfcId']
            if   nid in excused_ids: status='Excused'
            elif nid in late_ids:    status='Late'
            elif nid in present_ids: status='Present'
            else:                    status='Absent'
            tx_info=tx_hashes.get(nid,{}); tap_time=tx_info.get('time','—'); tx_hash=tx_info.get('tx_hash','—')
            rf=_fill(C_LIGHT) if row_n%2==0 else _fill(C_WHITE)
            row_vals=[idx,st['name'],st.get('student_id','—'),nid,status,tap_time,tx_hash]
            for ci,val in enumerate(row_vals,1):
                c=ws.cell(row=row_n,column=ci,value=val); c.border=_border()
                c.alignment=_ctr() if ci!=2 else _lft()
                if ci==5:
                    fg,bg=ST_MAP.get(status,(C_WHITE,'333333')); c.font=Font(name='Arial',size=10,bold=True,color=fg); c.fill=_fill(bg)
                elif ci==7: c.font=Font(name='Arial',size=8,color='6B7280'); c.fill=rf
                else: c.font=Font(name='Arial',size=10); c.fill=rf
            ws.row_dimensions[row_n].height=17; row_n+=1

        output=io.BytesIO(); wb.save(output); output.seek(0)
        subj_slug = sess.get('subject_name','session').replace(' ','_').lower()[:20]
        sec_slug  = section_key.split('|')[-1].lower() if section_key else ''
        date_slug = (sess.get('started_at','')[:10]).replace('-','') if sess.get('started_at') else ''
        fname = request.args.get('filename') or f"session_attendance_{subj_slug}_{sec_slug}_{date_slug}.xlsx"
        return Response(output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition':f'attachment;filename={fname}'})
    except Exception as e:
        import traceback; return Response(f"Export error: {traceback.format_exc()}", status=500, mimetype='text/plain')


@app.route('/export/stats.xlsx')
@login_required
def export_stats_xlsx():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        period     = request.args.get('period',      'all')
        f_section  = request.args.get('section_key', '').strip()
        f_year     = request.args.get('year',        '').strip()
        f_subject  = request.args.get('subject',     '').strip()
        f_instr    = request.args.get('instructor',  '').strip()
        f_month    = request.args.get('month',       '').strip()
        f_year_num = request.args.get('year_num',    '').strip()
        role       = session.get('role')
        username   = session.get('username')
        now        = datetime.now()

        if period=='today':
            start_dt=now.replace(hour=0,minute=0,second=0,microsecond=0); end_dt=None; period_label=now.strftime('Today (%b %d, %Y)')
        elif period=='month':
            yr=int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
            mo=int(f_month) if f_month and f_month.isdigit() else now.month
            start_dt=datetime(yr,mo,1); end_dt=datetime(yr,mo,_cal.monthrange(yr,mo)[1],23,59,59); period_label=start_dt.strftime('%B %Y')
        elif period=='year':
            yr=int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
            start_dt=datetime(yr,1,1); end_dt=datetime(yr,12,31,23,59,59); period_label=str(yr)
        else:
            start_dt=datetime(2000,1,1); end_dt=None; period_label='All Time'

        all_sess=load_sessions(); all_stud=get_all_students(); filtered={}
        f_section_norm = normalize_section_key(f_section) if f_section else ''
        for sid,s in all_sess.items():
            if not s.get('started_at'): continue
            try: sess_dt=datetime.strptime(s['started_at'],'%Y-%m-%d %H:%M:%S')
            except: continue
            if sess_dt<start_dt: continue
            if end_dt and sess_dt>end_dt: continue
            if role=='teacher' and s.get('teacher')!=username: continue
            if f_section_norm and normalize_section_key(s.get('section_key',''))!=f_section_norm: continue
            if f_year:
                parts=s.get('section_key','').split('|')
                if len(parts)<2 or parts[1]!=f_year: continue
            if f_subject and s.get('subject_name','')!=f_subject: continue
            if f_instr   and s.get('teacher_name','')!=f_instr:   continue
            filtered[sid]=s

        af=[]
        if f_section: af.append('Section: '+f_section.replace('|',' > '))
        if f_year:    af.append('Year Level: '+f_year)
        if f_subject: af.append('Subject: '+f_subject)
        if f_instr:   af.append('Instructor: '+f_instr)
        filter_str=' | '.join(af) if af else 'None'

        donut_data={"Present":0,"Late":0,"Absent":0,"Excused":0}
        trend_data={}; subject_data={}; sessions_rows=[]; detail_rows=[]

        for sid,s in sorted(filtered.items(),key=lambda x:x[1].get('started_at','')):
            section_key=normalize_section_key(s.get('section_key',''))
            enrolled=[st for st in all_stud if build_student_section_key(st) == section_key]
            enrolled_ids={st['nfcId'] for st in enrolled}
            present_ids=set(s.get('present',[])); late_ids=set(s.get('late',[])); excused_ids=set(s.get('excused',[]))
            cnt={'enrolled':len(enrolled_ids),'present':0,'late':0,'absent':0,'excused':0}
            for nid in enrolled_ids:
                if   nid in excused_ids: cnt['excused']+=1
                elif nid in late_ids:    cnt['late']+=1
                elif nid in present_ids: cnt['present']+=1
                else:                    cnt['absent']+=1
            rate=round((cnt['present']+cnt['late'])/cnt['enrolled']*100,1) if cnt['enrolled'] else 0
            subj_lbl=f"[{s.get('course_code','')}] {s.get('subject_name','')}" if s.get('course_code') else s.get('subject_name','')
            sessions_rows.append([subj_lbl,fmt_time(s['started_at']),section_key.replace('|',' · '),cnt['enrolled'],cnt['present'],cnt['late'],cnt['absent'],cnt['excused'],rate])
            for k in ('present','late','absent','excused'): donut_data[k.capitalize()]+=cnt[k]
            date_key=s['started_at'][:10]
            if date_key not in trend_data: trend_data[date_key]={'present':0,'late':0,'absent':0,'excused':0}
            for k in ('present','late','absent','excused'): trend_data[date_key][k]+=cnt[k]
            sname=s.get('subject_name','Unknown')
            if sname not in subject_data: subject_data[sname]={'present':0,'late':0,'absent':0,'excused':0}
            for k in ('present','late','absent','excused'): subject_data[sname][k]+=cnt[k]
            tx=s.get('tx_hashes',{})
            for st in enrolled:
                nid=st['nfcId']
                if   nid in excused_ids: status='Excused'
                elif nid in late_ids:    status='Late'
                elif nid in present_ids: status='Present'
                else:                    status='Absent'
                tx_info=tx.get(nid,{})
                detail_rows.append([st['name'],st.get('student_id',''),nid,st.get('course',''),st.get('year_level',''),st.get('section',''),subj_lbl,fmt_time(s['started_at']),s.get('time_slot',''),status,tx_info.get('tx_hash',''),str(tx_info.get('block',''))])

        C_DARK='0D1117'; C_ACCENT='2D6A27'; C_WHITE='FFFFFF'; C_HEADER='1E2530'; C_SUB='2D3748'; C_LIGHT='F1F5F9'
        def _fill(h): return PatternFill("solid",fgColor=h)
        def _border():
            s=Side(style='thin',color="CBD5E1"); return Border(left=s,right=s,top=s,bottom=s)
        def _ctr(): return Alignment(horizontal='center',vertical='center',wrap_text=True)
        def _lft(): return Alignment(horizontal='left',vertical='center',wrap_text=True)
        def make_title(ws,row,text,size=14,color=C_ACCENT,bg=C_DARK,cols=9):
            ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=cols)
            c=ws.cell(row=row,column=1,value=text); c.font=Font(name='Arial',size=size,bold=True,color=color)
            c.fill=_fill(bg); c.alignment=_ctr(); ws.row_dimensions[row].height=34 if size>=14 else 18
            for col in range(2,cols+1): ws.cell(row=row,column=col).fill=_fill(bg)

        wb=Workbook(); ws1=wb.active; ws1.title="Summary"; ws1.sheet_view.showGridLines=False
        make_title(ws1,1,"DAVS — Attendance Analytics Report",16,C_ACCENT,C_DARK)
        make_title(ws1,2,"Cavite State University · Silang City, Cavite",10,"94A3B8",C_DARK)
        make_title(ws1,3,f"Period: {period_label}",10,"94A3B8",C_DARK)
        make_title(ws1,4,f"Filters: {filter_str}",10,"94A3B8",C_DARK)
        for col in range(1,10): ws1.cell(row=5,column=col).fill=_fill("F8FAFC"); ws1.row_dimensions[5].height=8
        total_all=sum(donut_data.values())
        stat_defs=[(1,2,"✓  PRESENT",donut_data["Present"],"10B981","0D3D2A"),(3,4,"⏱  LATE",donut_data["Late"],"F59E0B","3D3010"),(5,6,"✕  ABSENT",donut_data["Absent"],"EF4444","3D1010"),(7,8,"◎  EXCUSED",donut_data["Excused"],"60A5FA","102040")]
        for (sc,ec,label,val,fg,bg) in stat_defs:
            for row,height,v,sz,bold in [(6,18,label,9,True),(7,38,val,24,True),(8,18,f"{round(val/total_all*100,1) if total_all else 0}% of total",9,False)]:
                ws1.merge_cells(start_row=row,start_column=sc,end_row=row,end_column=ec)
                c=ws1.cell(row=row,column=sc,value=v); c.font=Font(name='Arial',size=sz,bold=bold,color=fg)
                c.fill=_fill(bg); c.alignment=_ctr(); ws1.row_dimensions[row].height=height
                for col in range(sc+1,ec+1): ws1.cell(row=row,column=col).fill=_fill(bg)
        for r in range(6,9): ws1.cell(row=r,column=9).fill=_fill("F8FAFC")
        for col in range(1,10): ws1.cell(row=9,column=col).fill=_fill("F8FAFC"); ws1.row_dimensions[9].height=10
        col_w=[34,22,36,10,10,10,10,10,10]
        for i,w in enumerate(col_w,1): ws1.column_dimensions[get_column_letter(i)].width=w
        HDR=10; ws1.row_dimensions[HDR].height=22
        for ci,h in enumerate(["Subject","Session Date","Section","Enrolled","Present","Late","Absent","Excused","Rate %"],1):
            c=ws1.cell(row=HDR,column=ci,value=h); c.font=Font(name='Arial',size=10,bold=True,color=C_WHITE)
            c.fill=_fill(C_HEADER); c.alignment=_ctr(); c.border=_border()
        for ri,row_data in enumerate(sessions_rows,HDR+1):
            ws1.row_dimensions[ri].height=18; rf=_fill(C_LIGHT) if ri%2==0 else _fill(C_WHITE)
            sc_=[None,None,None,None,"10B981","F59E0B","EF4444","60A5FA",None]
            for ci,val in enumerate(row_data,1):
                disp=f"{val}%" if ci==9 else val; c=ws1.cell(row=ri,column=ci,value=disp)
                c.fill=rf; c.border=_border(); c.alignment=_ctr() if ci>3 else _lft()
                fg=sc_[ci-1]; c.font=Font(name='Arial',size=10,bold=bool(fg),color=fg or "222222")
        tr=HDR+len(sessions_rows)+1; ws1.row_dimensions[tr].height=20
        tot_row=["TOTAL","","",f"=SUM(D{HDR+1}:D{tr-1})",f"=SUM(E{HDR+1}:E{tr-1})",f"=SUM(F{HDR+1}:F{tr-1})",f"=SUM(G{HDR+1}:G{tr-1})",f"=SUM(H{HDR+1}:H{tr-1})",f'=IFERROR(TEXT((E{tr}+F{tr})/D{tr},"0.0%"),"-")']
        for ci,val in enumerate(tot_row,1):
            c=ws1.cell(row=tr,column=ci,value=val); c.font=Font(name='Arial',size=10,bold=True,color=C_WHITE)
            c.fill=_fill(C_SUB); c.alignment=_ctr() if ci>3 else _lft(); c.border=_border()
        ws1.cell(row=tr+2,column=1,value=f"Generated by DAVS on {now.strftime('%B %d, %Y %I:%M %p')}").font=Font(name='Arial',size=9,italic=True,color="94A3B8")

        ws2=wb.create_sheet("Student Detail"); ws2.sheet_view.showGridLines=False
        make_title(ws2,1,"Student Attendance Detail",14,C_ACCENT,C_DARK,12)
        make_title(ws2,2,f"Period: {period_label}  |  Filters: {filter_str}",9,"94A3B8",C_DARK,12)
        for col in range(1,13): ws2.cell(row=3,column=col).fill=_fill(C_DARK); ws2.row_dimensions[3].height=8
        det_hdrs=["Student Name","Student ID","NFC Card","Course","Year","Section","Subject","Session Date","Time Slot","Status","TX Hash","Block #"]
        det_ws=[28,14,13,26,10,10,30,20,18,10,42,10]
        for ci,(h,w) in enumerate(zip(det_hdrs,det_ws),1):
            ws2.column_dimensions[get_column_letter(ci)].width=w
            c=ws2.cell(row=4,column=ci,value=h); c.font=Font(name='Arial',size=10,bold=True,color=C_WHITE)
            c.fill=_fill(C_HEADER); c.alignment=_ctr(); c.border=_border()
        ws2.row_dimensions[4].height=20
        ST_C2={"Present":("10B981","0D3D2A"),"Late":("F59E0B","3D3010"),"Absent":("EF4444","3D1010"),"Excused":("60A5FA","102040")}
        for ri,row_data in enumerate(detail_rows,5):
            ws2.row_dimensions[ri].height=17; rf=_fill(C_LIGHT) if ri%2==0 else _fill(C_WHITE)
            for ci,val in enumerate(row_data,1):
                c=ws2.cell(row=ri,column=ci,value=val); c.border=_border(); c.alignment=_ctr() if ci>3 else _lft()
                if ci==10:
                    fg,bg=ST_C2.get(val,(C_WHITE,"333333")); c.font=Font(name='Arial',size=10,bold=True,color=fg); c.fill=_fill(bg)
                elif ci==11: c.font=Font(name='Arial',size=8,color="6B7280"); c.fill=rf
                else: c.font=Font(name='Arial',size=10); c.fill=rf

        output=io.BytesIO(); wb.save(output); output.seek(0)
        _period_label={'today':f"today_{now.strftime('%Y%m%d')}","month":f"{now.strftime('%B').lower()}_{f_year_num or now.year}","year":f"year_{f_year_num or now.year}","all":"all_time"}.get(period,period)
        _parts=['attendance_analytics',_period_label]
        if f_section: _parts.append(f_section.split('|')[-1].lower())
        if f_year:    _parts.append(f_year.replace(' ','').lower())
        if f_subject: _parts.append(re.sub(r'[^a-z0-9]','',f_subject.lower()[:15]))
        if f_instr:   _parts.append(f_instr.split()[0].lower())
        _parts.append(f"exported_{now.strftime('%Y%m%d')}")
        fname = request.args.get('filename') or ('_'.join(_parts)+'.xlsx')
        return Response(output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition':f'attachment;filename={fname}'})
    except Exception as e:
        import traceback; return Response(f"Export error: {traceback.format_exc()}", status=500, mimetype='text/plain')

@app.route('/export/stats.csv')
@login_required
def export_stats_csv():
    period   = request.args.get('period','all')
    f_subj   = request.args.get('subject','').strip()
    f_sec    = request.args.get('section_key','').strip()
    role     = session.get('role'); username = session.get('username')
    now      = datetime.now()
    if period=='today': start_dt=now.replace(hour=0,minute=0,second=0,microsecond=0); end_dt=None
    elif period=='month':
        yr=int(request.args.get('year_num',now.year)); mo=int(request.args.get('month',now.month))
        start_dt=datetime(yr,mo,1); end_dt=datetime(yr,mo,_cal.monthrange(yr,mo)[1],23,59,59)
    elif period=='year':
        yr=int(request.args.get('year_num',now.year)); start_dt=datetime(yr,1,1); end_dt=datetime(yr,12,31,23,59,59)
    else: start_dt=datetime(2000,1,1); end_dt=None
    all_sess=load_sessions(); all_stud=get_all_students()
    f_sec_norm = normalize_section_key(f_sec) if f_sec else ''
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(['Session ID','Subject','Section','Instructor','Date','Time Slot','Enrolled','Present','Late','Absent','Excused','Rate%'])
    for sid,s in sorted(all_sess.items(),key=lambda x:x[1].get('started_at','')):
        if not s.get('started_at'): continue
        try: sess_dt=datetime.strptime(s['started_at'],'%Y-%m-%d %H:%M:%S')
        except: continue
        if sess_dt<start_dt: continue
        if end_dt and sess_dt>end_dt: continue
        if role=='teacher' and s.get('teacher')!=username: continue
        if f_subj and s.get('subject_name','')!=f_subj: continue
        if f_sec_norm and normalize_section_key(s.get('section_key',''))!=f_sec_norm: continue
        sec=normalize_section_key(s.get('section_key',''))
        enrolled=[st for st in all_stud if build_student_section_key(st) == sec]
        p=set(s.get('present',[])); l=set(s.get('late',[])); e=set(s.get('excused',[]))
        pres=len([n for n in p if n not in l]); late=len(l); exc=len(e); tot=len(enrolled); ab=max(0,tot-pres-late-exc)
        rate=round((pres+late)/tot*100,1) if tot else 0
        w.writerow([sid[:8],s.get('subject_name',''),sec.replace('|',' · '),s.get('teacher_name',''),s['started_at'][:10],s.get('time_slot',''),tot,pres,late,ab,exc,rate])
    out.seek(0)
    fname=f"attendance_{period}_{now.strftime('%Y%m%d')}.csv"
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment;filename={fname}'})

# ── NFC / HARDWARE (FIX #9 — DB-based registration mode) ─────────────────────

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

@app.route('/mark_pico', methods=['POST'])
def mark_pico():
    data=request.get_json()
    if not data or 'nfc_id' not in data: return jsonify({'status':'error'}), 400
    nfc_id=data['nfc_id'].strip().upper()
    print(f"[NFC TAP] {nfc_id}")

    # FIX #9: Check DB-based registration mode instead of flag file
    if nfc_is_waiting():
        nfc_set_uid(nfc_id)
        return jsonify({'status':'registration','uid':nfc_id})

    sess_id, sess = get_active_session_for_nfc(nfc_id)
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
        return jsonify({'status':'already_marked','name':name,'student_id':student_id,
                        'message':f'{name} is already marked present.'})

    # FIX #5: Determine late status HERE and save it permanently to the session
    now_dt       = datetime.now()
    late_cutoff  = sess.get('late_cutoff','')
    is_late      = False
    if late_cutoff:
        try:
            cutoff_dt = datetime.strptime(late_cutoff, '%Y-%m-%d %H:%M:%S')
            is_late   = now_dt > cutoff_dt
        except:
            is_late = False

    # Record on blockchain
    tx_hash=None; block_num=None
    try:
        tx      = contract.functions.markAttendance(nfc_id).transact({'from':admin_account})
        receipt = web3.eth.wait_for_transaction_receipt(tx)
        tx_hash  = receipt['transactionHash'].hex()
        block_num= receipt['blockNumber']
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

    tap_time = datetime.now().strftime('%H:%M:%S')
    # Add to present list always
    sess.setdefault('present',[]).append(nfc_id)
    # FIX #5: Add to late list immediately and save it permanently
    if is_late and nfc_id not in sess.get('late',[]):
        sess.setdefault('late',[]).append(nfc_id)

    sess.setdefault('tap_log',[]).append({
        'nfc_id':nfc_id,'name':name,'time':tap_time,
        'timestamp':time.time(),'tx_hash':tx_hash,'block':block_num,
        'student_id':student_id,'is_late':is_late
    })
    sess.setdefault('tx_hashes',{})[nfc_id]={'tx_hash':tx_hash,'block':block_num,'time':tap_time}

    save_session(sess_id, sess)
    sessions_db[sess_id] = sess

    recent_attendance.append({
        'nfc_id':nfc_id,'name':name,'timestamp':time.time(),
        'subject':sess.get('subject_name',''),'is_late':is_late
    })

    status_label = 'late' if is_late else 'present'
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)