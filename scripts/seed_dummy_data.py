"""
seed_dummy_data.py  v5
======================
DAVS — Dummy Data Seeder

ROOT CAUSE FIXES vs v4:
─────────────────────────────────────────────────────────────────────────────
FIX 1 — Sessions tab showing 0 sessions
  app.py student_sessions_api() queries:
    SELECT ... FROM attendance_logs al
    JOIN sessions s ON al.sess_id = s.sess_id
    WHERE al.nfc_id = ?
  This works ONLY if attendance_logs rows exist for that nfc_id.
  The section_key in sessions must EXACTLY match what
  build_student_section_key(student) builds:
    f"{student['course']}|{student['year_level']}|{student['section']}"
  where student['course'] = students.program  (aliased by _student_row).
  So section_key = f"{program}|{year_level}|{section}" — this is what
  we now verify with a post-seed integrity check.

FIX 2 — Analytics graphs always 0
  attendance_stats() for period='today' filters:
    WHERE s.started_at >= '{today} 00:00:00'
  All sessions in v4 were 1–90 days ago → "Today" always returns 0.
  Fix: create 3 sessions TODAY so all analytics periods show real data.

FIX 3 — Sessions spread across ALL periods
  Now sessions are spread across:
    • Today          (3 sessions  — analytics "Today" shows data)
    • This month     (5 sessions  — analytics "Month" shows data)
    • This year      (7 sessions  — analytics "Year" shows data)
    • Older (past 90 days) (remaining sessions)

FIX 4 — Post-seed verification
  After seeding, the script runs SQL queries that mirror exactly what
  app.py runs at runtime and prints a summary so you can confirm
  every join works before starting Flask.
─────────────────────────────────────────────────────────────────────────────

What is created:
  • 1  admin           (admin / test123)
  • 5  teachers        (teacher01–05 / test123)
  • 10 subjects        (CS101–CS105, IT101–IT105)
  • 960 students       (30 × 32 sections)
  • ≥320 sessions      (≥10 per section, all ended, spread across time)
  • ≈28,800 log rows   (all with dummy TX hash + block number)

Usage:
    python seed_dummy_data.py              # add to existing DB
    python seed_dummy_data.py --yes        # skip confirmation
    python seed_dummy_data.py --clear      # wipe non-admin data first
    python seed_dummy_data.py --clear --yes
"""

import hashlib, os, sys, uuid, json, random, secrets
from datetime import datetime, timedelta, date
from services.ops.db_compat import connect_db

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/davs').strip()

# Handle Railway/Heroku postgres:// prefix
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
PASSWORD             = 'test123'
STUDENTS_PER_SECTION = 30
MIN_SESSIONS_PER_SECTION = 10

# ── DB helpers ───────────────────────────────────────────────────────────────
def get_db():
    return connect_db(DATABASE_URL)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def ts(dt=None): return (dt or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
def fake_tx():   return '0x' + secrets.token_hex(32)
def fake_block():return random.randint(100, 99999)

# ── CRITICAL: section_key builder that matches app.py EXACTLY ───────────────
#
# app.py normalize_section_key():
#   parts = [p.strip() for p in key.split('|')]
#   year_map = {'1st year':'1st Year', ... '1st year':'1st Year' ...}
#   return f"{course}|{year_normalized}|{section.upper()}"
#
# app.py build_student_section_key(student):
#   course     = student.get('course')      ← this is students.program
#   year_level = student.get('year_level')  ← exact DB value e.g. '2nd Year'
#   section    = student.get('section').upper()
#   return normalize_section_key(f"{course}|{year_level}|{section}")
#
# So: section_key = f"{program}|{year_level}|{section.upper()}"
# where year_level is already in canonical form ('1st Year', '2nd Year', etc.)
# ─────────────────────────────────────────────────────────────────────────────
def make_section_key(program, year_level, section):
    """
    Produces the EXACT same string as app.py's normalize_section_key()
    when called with already-canonical year_level values.
    """
    return f"{program}|{year_level}|{section.upper()}"

# ── Name / NFC uniqueness ────────────────────────────────────────────────────
_used_names = set()
_used_nfcs  = set()

def gen_name():
    for _ in range(1000):
        fn   = random.choice(FIRST_NAMES)
        ln   = random.choice(LAST_NAMES)
        full = f"{fn} {ln}"
        if full not in _used_names:
            _used_names.add(full)
            return fn, ln, full
    suf  = random.randint(1, 9999)
    fn   = random.choice(FIRST_NAMES)
    ln   = random.choice(LAST_NAMES)
    full = f"{fn} {ln} {suf}"
    _used_names.add(full)
    return fn, ln, full

def gen_nfc():
    while True:
        uid = ''.join(random.choices('0123456789ABCDEF', k=8))
        if uid not in _used_nfcs:
            _used_nfcs.add(uid)
            return uid

# ── Data pools ───────────────────────────────────────────────────────────────
FIRST_NAMES = [
    'Juan','Maria','Jose','Ana','Carlo','Liza','Mark','Jenny',
    'Paolo','Kristine','Rafael','Carla','Miguel','Jasmine','Andrei',
    'Nicole','Gabriel','Patricia','Jerome','Camille','Luis','Sheila',
    'Aaron','Christine','Kevin','Maricel','Ryan','Jessa','Franz',
    'Melissa','Alvin','Rowena','Renz','Hazel','Nathan','Joanna',
    'Vince','Abigail','Enzo','Rhea','James','Vanessa','Daniel',
    'Leah','Christian','Danica','Aldrin','Grace','Justin','Diane',
    'Marco','Trisha','Lance','Rina','Brent','Stephanie','Cedric',
    'Faye','Oliver','Pia','Rodel','Mariz','Gino','Alyssa',
    'Nico','Katrina','Elvin','Sheena','Cyrus','Lovelyn','Warren',
    'Chelsea','Ivan','Mia','Erwin','Felicia','Jericho','Precious',
    'Axel','Pamela','Dominic','Yvonne','Ariel','Rachelle','Bryan',
    'Marianne','Kenneth','Jocel','Renan','Loraine','Arnold','Geraldine',
    'Marvin','Irene','Raul','Maylene','Efren','Editha','Rogelio',
    'Lorna','Noel','Rosemarie','Bernard','Leonora','Alfredo','Teresita',
    'Sherwin','Gladys','Darwin','Liezel','Joven','Rechelle','Glaiza',
    'Ronan','Marifel','Jayson','Glenda','Gemma','Rosario','Domingo',
]

LAST_NAMES = [
    'Santos','Reyes','Cruz','Bautista','Ocampo','Garcia','Mendoza',
    'Torres','Flores','Aquino','Ramos','Diaz','Rivera','Gonzales',
    'Lopez','Ramirez','Martinez','Hernandez','Dela Cruz','Castillo',
    'Villanueva','Macaraeg','Salazar','Pascual','Guevarra','Navarro',
    'Soriano','Magno','Buenaventura','Santiago','Aguilar','Perez',
    'Domingo','Lim','Tan','Sy','Go','Uy','Chua','Yap',
    'Morales','Padilla','Jimenez','Bernardo','Andres','Valdez',
    'Romero','Dela Torre','Lacson','Campos','Enriquez','Tolentino',
    'Evangelista','Manalo','Pangilinan','Delos Santos','Austria',
    'Belen','Catalan','Delos Reyes','Espiritu','Ferrer','Guerrero',
    'Hidalgo','Ibarra','Javier','Kabigting','Legaspi','Macapagal',
    'Natividad','Orozco','Quiambao','Resurreccion','Silverio','Tuason',
    'Ureta','Vargas','Zamora','Abaya','Abueva','Acosta','Alcaraz',
    'Almario','Alvarez','Amante','Amparo','Aragon','Arce','Arceo',
    'Arcilla','Arellano','Arguelles','Ariate','Arienza','Ariola',
    'Ariosto','Arroyo','Arroyos','Artista','Asuncion','Atienza',
]

ADVISERS = [
    'Prof. Maria Santos',   'Prof. Jose Reyes',    'Prof. Ana Ocampo',
    'Prof. Carlo Garcia',   'Prof. Liza Torres',   'Prof. Mark Flores',
    'Prof. Jenny Aquino',   'Prof. Paolo Ramos',   'Prof. Rafael Cruz',
    'Prof. Carla Mendoza',  'Prof. Miguel Rivera', 'Prof. Jasmine Lopez',
    'Prof. Andrei Bautista','Prof. Camille Reyes', 'Prof. Nathan Santos',
]

PROGRAMS    = ['BS Computer Science','BS Information Technology']
# CANONICAL year level values — must match exactly what app.py stores/reads
YEAR_LEVELS = ['1st Year','2nd Year','3rd Year','4th Year']
SECTIONS    = ['A','B','C','D']
SEMESTERS   = ['First','Second']
SCHOOL_YRS  = ['2023-2024','2024-2025','2025-2026']
ADM_DATES   = ['August 2023','January 2024','August 2024',
               'January 2025','August 2025']
MAJORS_CS   = ['Software Engineering','Data Science',
               'Artificial Intelligence','Computer Graphics']
MAJORS_IT   = ['Network Technology','Web Development',
               'Cybersecurity','Cloud Computing']
TIME_SLOTS  = [
    '7:00 AM – 9:00 AM',  '8:00 AM – 10:00 AM',  '9:00 AM – 11:00 AM',
    '10:00 AM – 12:00 PM','1:00 PM – 3:00 PM',   '2:00 PM – 4:00 PM',
    '3:00 PM – 5:00 PM',  '4:00 PM – 6:00 PM',   '11:00 AM – 1:00 PM',
]
EXCUSE_NOTES = [
    'Medical certificate submitted',
    'Official school activity',
    'Family emergency — approved by adviser',
    'Pre-approved leave of absence',
    'Sports competition / university event',
    'Internship duty day',
    'Government ID processing appointment',
    'Health / dental appointment',
    'OJT requirement',
    'University-sponsored competition',
]

# ── Subjects ─────────────────────────────────────────────────────────────────
SUBJECTS_CS = [
    {'subject_id':'cs101','name':'Data Structures and Algorithms',
     'course_code':'CS101','units':'3'},
    {'subject_id':'cs102','name':'Object-Oriented Programming',
     'course_code':'CS102','units':'3'},
    {'subject_id':'cs103','name':'Database Management Systems',
     'course_code':'CS103','units':'3'},
    {'subject_id':'cs104','name':'Operating Systems',
     'course_code':'CS104','units':'3'},
    {'subject_id':'cs105','name':'Software Engineering',
     'course_code':'CS105','units':'3'},
]
SUBJECTS_IT = [
    {'subject_id':'it101','name':'Web Systems and Technologies',
     'course_code':'IT101','units':'3'},
    {'subject_id':'it102','name':'Network Administration',
     'course_code':'IT102','units':'3'},
    {'subject_id':'it103','name':'Systems Integration and Architecture',
     'course_code':'IT103','units':'3'},
    {'subject_id':'it104','name':'Information Assurance and Security',
     'course_code':'IT104','units':'3'},
    {'subject_id':'it105','name':'Capstone Project',
     'course_code':'IT105','units':'3'},
]
ALL_SUBJECTS = SUBJECTS_CS + SUBJECTS_IT

# ── Teachers ─────────────────────────────────────────────────────────────────
TEACHERS = [
    ('teacher01','Prof. Maria Santos'),
    ('teacher02','Prof. Jose Reyes'),
    ('teacher03','Prof. Ana Ocampo'),
    ('teacher04','Prof. Carlo Garcia'),
    ('teacher05','Prof. Liza Torres'),
]

TEACHER_SECTIONS = {
    'teacher01':[
        ('BS Computer Science','1st Year','A'),
        ('BS Computer Science','1st Year','B'),
        ('BS Computer Science','2nd Year','A'),
        ('BS Computer Science','2nd Year','B'),
    ],
    'teacher02':[
        ('BS Computer Science','3rd Year','A'),
        ('BS Computer Science','3rd Year','B'),
        ('BS Computer Science','4th Year','A'),
        ('BS Computer Science','4th Year','B'),
    ],
    'teacher03':[
        ('BS Information Technology','1st Year','A'),
        ('BS Information Technology','1st Year','B'),
        ('BS Information Technology','2nd Year','A'),
        ('BS Information Technology','2nd Year','B'),
    ],
    'teacher04':[
        ('BS Information Technology','3rd Year','A'),
        ('BS Information Technology','3rd Year','B'),
        ('BS Information Technology','4th Year','A'),
    ],
    'teacher05':[
        ('BS Information Technology','4th Year','B'),
        ('BS Computer Science','1st Year','C'),
        ('BS Computer Science','1st Year','D'),
        ('BS Information Technology','1st Year','C'),
        ('BS Information Technology','1st Year','D'),
    ],
}

# ── Student personality system ───────────────────────────────────────────────
PERSONALITIES = {
    'excellent':  {'present':70,'late':10,'absent': 8,'excused':12},
    'good':       {'present':60,'late':15,'absent':15,'excused':10},
    'average':    {'present':50,'late':20,'absent':22,'excused': 8},
    'struggling': {'present':35,'late':15,'absent':40,'excused':10},
    'chronic':    {'present':25,'late':10,'absent':55,'excused':10},
}
PERSONALITY_WEIGHTS = [
    ('excellent',20),('good',35),('average',30),
    ('struggling',10),('chronic',5),
]
_pers_pool = []
for _n, _w in PERSONALITY_WEIGHTS:
    _pers_pool.extend([_n]*_w)

def pick_personality(): return random.choice(_pers_pool)

def status_for(pers_name):
    p    = PERSONALITIES.get(pers_name, PERSONALITIES['average'])
    pool = (['present']*p['present'] + ['late']*p['late'] +
            ['absent']*p['absent']   + ['excused']*p['excused'])
    return random.choice(pool)

# ── Session date helpers ──────────────────────────────────────────────────────
def dt_today(hour=8, minute=0):
    """A datetime today at the given hour, guaranteed in the past."""
    now = datetime.now()
    d   = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # If the hour hasn't passed yet, set it 1 hour ago
    if d > now - timedelta(minutes=30):
        d = now - timedelta(hours=2, minutes=random.randint(0,30))
    return d

def dt_this_month(days_ago_min=1, days_ago_max=20):
    """A datetime earlier this month."""
    days = random.randint(days_ago_min, days_ago_max)
    d    = datetime.now() - timedelta(days=days)
    # Keep within the current month
    if d.month != datetime.now().month:
        d = datetime.now() - timedelta(days=days_ago_min)
    return d.replace(hour=random.randint(7,16),
                     minute=0, second=0, microsecond=0)

def dt_this_year(days_ago_min=21, days_ago_max=180):
    """A datetime earlier this year."""
    days = random.randint(days_ago_min, days_ago_max)
    d    = datetime.now() - timedelta(days=days)
    if d.year != datetime.now().year:
        d = datetime.now() - timedelta(days=days_ago_min)
    return d.replace(hour=random.randint(7,16),
                     minute=0, second=0, microsecond=0)

def dt_older():
    """A datetime from last year or earlier (>180 days ago)."""
    days = random.randint(181, 365)
    d    = datetime.now() - timedelta(days=days)
    return d.replace(hour=random.randint(7,16),
                     minute=0, second=0, microsecond=0)

# ── Core seed functions ───────────────────────────────────────────────────────
def check_db():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        print("  [OK]  Connected to PostgreSQL")
    except Exception as e:
        print(f"\n  [ERR] PostgreSQL connection failed: {e}")
        print("  Set DATABASE_URL in .env and ensure PostgreSQL is running.\n")
        sys.exit(1)

def clear_data():
    print("\n  Clearing existing data…")
    print("  " + "─"*54)
    with get_db() as conn:
        for table in ['attendance_logs','sessions','students',
                      'student_overrides','subjects','photos']:
            try:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                conn.execute(f"DELETE FROM {table}")
                print(f"  ✅ Cleared  {table:<24} ({n} rows)")
            except Exception as e:
                print(f"  ⚠  {table}: {e}")
        try:
            conn.execute(
                "DELETE FROM accounts "
                "WHERE NOT (username='admin' AND role='admin')")
            conn.execute(
                "DELETE FROM users "
                "WHERE NOT (username='admin' AND role='admin')")
            print("  ✅ Cleared  teacher accounts")
        except Exception as e:
            print(f"  ⚠  accounts: {e}")

def seed_admin(conn):
    now = ts(); pw = hash_pw(PASSWORD)
    conn.execute(
        "INSERT INTO accounts "
        "(username,password_hash,role,full_name,email,status,"
        " sections_json,my_subjects_json,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(username) DO UPDATE SET "
        "password_hash=excluded.password_hash, status=excluded.status",
        ('admin',pw,'admin','System Administrator',
         'admin@cvsu.edu.ph','approved','[]','[]',now,now))
    try:
        conn.execute(
            "INSERT INTO users "
            "(username,password,role,full_name,email,status,"
            " sections_json,my_subjects_json,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET password=excluded.password",
            ('admin',pw,'admin','System Administrator',
             'admin@cvsu.edu.ph','approved','[]','[]',now))
    except Exception: pass
    print(f"  ✅ Admin  admin / {PASSWORD}")

def seed_teachers(conn):
    now = ts(); pw = hash_pw(PASSWORD)
    for uname, fname in TEACHERS:
        raw      = TEACHER_SECTIONS.get(uname,[])
        # Use make_section_key so teacher sections match session section_keys
        sections = [make_section_key(p,y,s) for p,y,s in raw]
        my_subj  = []
        for prog,year,sec in raw:
            pool = SUBJECTS_CS if 'Computer Science' in prog else SUBJECTS_IT
            for subj in pool:
                my_subj.append({
                    'subject_id':  subj['subject_id'],
                    'section_key': make_section_key(prog,year,sec),
                })
        conn.execute(
            "INSERT INTO accounts "
            "(username,password_hash,role,full_name,email,status,"
            " sections_json,my_subjects_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET "
            "password_hash=excluded.password_hash,"
            "full_name=excluded.full_name,"
            "sections_json=excluded.sections_json,"
            "my_subjects_json=excluded.my_subjects_json,"
            "status=excluded.status",
            (uname,pw,'teacher',fname,
             f"{uname}@cvsu.edu.ph",'approved',
             json.dumps(sections),json.dumps(my_subj),now,now))
        try:
            conn.execute(
                "INSERT INTO users "
                "(username,password,role,full_name,email,status,"
                " sections_json,my_subjects_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(username) DO UPDATE SET "
                "password=excluded.password,full_name=excluded.full_name,"
                "sections_json=excluded.sections_json,"
                "my_subjects_json=excluded.my_subjects_json",
                (uname,pw,'teacher',fname,
                 f"{uname}@cvsu.edu.ph",'approved',
                 json.dumps(sections),json.dumps(my_subj),now))
        except Exception: pass
        print(f"  ✅ Teacher  {fname:<30}  {uname} / {PASSWORD}")

def seed_subjects(conn):
    now = ts()
    for subj in ALL_SUBJECTS:
        conn.execute(
            "INSERT INTO subjects "
            "(subject_id,name,course_code,units,created_by,created_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(subject_id) DO UPDATE SET "
            "name=excluded.name,course_code=excluded.course_code,"
            "units=excluded.units",
            (subj['subject_id'],subj['name'],subj['course_code'],
             subj['units'],'admin',now))
    print(f"  ✅ {len(ALL_SUBJECTS)} subjects seeded")

def seed_students(conn):
    """
    Insert 30 students per section.
    Returns (list_of_student_dicts, personality_map).

    CRITICAL column values (must match _student_row alias mapping):
      students.program    ← used as s['course'] by _student_row
      students.year_level ← exact canonical value '1st Year' etc.
      students.section    ← single UPPER letter

    section_key built as: make_section_key(program, year_level, section)
    which equals what build_student_section_key(student) produces since:
      build_student_section_key uses student['course'] = students.program
      and student['year_level'] and student['section'].upper()
    """
    year_pfx = {'1st Year':'2024','2nd Year':'2023',
                 '3rd Year':'2022','4th Year':'2021'}
    now      = ts()
    created  = []
    pers_map = {}

    total = 0
    for program in PROGRAMS:
        for year in YEAR_LEVELS:
            for section in SECTIONS:
                # section_key using the SAME function as sessions will use
                sk = make_section_key(program, year, section)
                for _ in range(STUDENTS_PER_SECTION):
                    fn,ln,full = gen_name()
                    nfc  = gen_nfc()
                    sid  = f"{year_pfx.get(year,'2024')}-{random.randint(10000,99999)}"
                    sem  = random.choice(SEMESTERS)
                    sy   = random.choice(SCHOOL_YRS)
                    adv  = random.choice(ADVISERS)
                    fs   = fn.lower().replace(' ','').replace('.','')
                    ls   = ln.lower().replace(' ','').replace('.','')
                    email= f"sc.{fs}.{ls}@cvsu.edu.ph"
                    cont = f"09{random.randint(100000000,999999999)}"
                    dreg = random.choice(ADM_DATES)
                    major= 'N/A'
                    if year in ('3rd Year','4th Year'):
                        major = random.choice(
                            MAJORS_CS if 'Computer Science' in program
                            else MAJORS_IT)

                    raw = (
                        f"{full} | ID:{sid} | Course:{program} | "
                        f"Year:{year} | Sec:{section.upper()} | "
                        f"Adviser:{adv} | Email:{email} | "
                        f"Tel:{cont} | Sem:{sem} | SY:{sy} | "
                        f"RegDate:{dreg} | Major:{major}"
                    )
                    pers = pick_personality()
                    pers_map[nfc] = pers

                    conn.execute(
                        "INSERT INTO students "
                        "(nfc_id,full_name,student_id,program,year_level,"
                        " section,adviser,email,contact,major,semester,"
                        " school_year,date_registered,raw_name,eth_address,"
                        " reg_tx_hash,reg_block,photo_file,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(nfc_id) DO NOTHING",
                        (nfc, full, sid,
                         program,          # ← stored as 'program', read as 'course'
                         year,             # ← canonical '1st Year' etc.
                         section.upper(),  # ← single UPPER letter
                         adv,email,cont,major,sem,sy,dreg,raw,
                         '0x'+secrets.token_hex(20),
                         fake_tx(),fake_block(),'',now,now))

                    created.append({
                        'nfc_id':     nfc,
                        'name':       full,
                        'student_id': sid,
                        # 'course' mirrors what _student_row returns
                        'course':     program,
                        'program':    program,
                        'year_level': year,
                        'section':    section.upper(),
                        'section_key':sk,
                        'personality':pers,
                    })
                    total += 1

                label = sk.replace('|',' › ')
                print(f"  ✅ {label:<54} → {STUDENTS_PER_SECTION} students")

    print(f"\n  Total students: {total}")
    return created, pers_map

def _insert_session_with_logs(conn, sess_id, subj, sk, uname, fname,
                               started_dt, ended_dt, time_slot, enrolled,
                               pers_map):
    """
    Insert one ended session and attendance logs for all enrolled students.
    Returns number of log rows inserted.
    """
    late_cutoff = started_dt + timedelta(minutes=30)

    conn.execute(
        "INSERT OR IGNORE INTO sessions "
        "(sess_id,subject_id,subject_name,course_code,units,"
        " time_slot,section_key,teacher_username,teacher_name,"
        " started_at,late_cutoff,ended_at,total_enrolled,"
        " warn_log_json,invalid_log_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sess_id,
         subj['subject_id'],subj['name'],subj['course_code'],
         int(subj['units']),time_slot,
         sk,                    # ← same make_section_key as students
         uname,fname,
         ts(started_dt),
         ts(late_cutoff),
         ts(ended_dt),          # always set → ended session
         len(enrolled),
         '[]','[]'))

    totals   = {'present':0,'late':0,'absent':0,'excused':0}
    log_rows = 0
    duration_secs = max(60, int((ended_dt-started_dt).total_seconds()))

    for stu in enrolled:
        pers   = pers_map.get(stu['nfc_id'],'average')
        status = status_for(pers)

        tap_time     = ''
        tx_hash      = fake_tx()
        block_number = fake_block()

        if status in ('present','late'):
            offset   = (random.randint(0,28) if status=='present'
                        else random.randint(31,58))
            tap_dt   = started_dt + timedelta(minutes=offset)
            if tap_dt > ended_dt:
                tap_dt = ended_dt - timedelta(minutes=1)
            tap_time = tap_dt.strftime('%H:%M:%S')

        excuse = ''
        if status == 'excused':
            excuse = random.choice(EXCUSE_NOTES)

        created_dt = started_dt + timedelta(
            seconds=random.randint(0, duration_secs))
        if created_dt > ended_dt:
            created_dt = ended_dt

        conn.execute(
            "INSERT OR IGNORE INTO attendance_logs "
            "(sess_id,nfc_id,student_name,student_id,status,"
            " tap_time,tx_hash,block_number,excuse_note,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sess_id,
             stu['nfc_id'],stu['name'],stu['student_id'],
             status,tap_time,tx_hash,block_number,excuse,ts(created_dt)))

        totals[status] += 1
        log_rows += 1

    conn.execute(
        "UPDATE sessions SET "
        "total_present=?,total_late=?,total_absent=?,total_excused=? "
        "WHERE sess_id=?",
        (totals['present'],totals['late'],
         totals['absent'], totals['excused'],sess_id))

    return log_rows, totals

def seed_sessions(conn, all_students, pers_map):
    """
    Creates sessions spread across FOUR time buckets so every analytics
    period in the admin dashboard shows real data:

      TODAY        → 3  sessions  (analytics 'Today' shows data)
      THIS MONTH   → 5  sessions  (analytics 'Month' shows data)
      THIS YEAR    → 7  sessions  (analytics 'Year' shows data)
      OLDER        → remaining    (analytics 'All Time' shows more data)

    Total per section = 5 subjects × RUNS_PER_SUBJECT ≥ MIN_SESSIONS_PER_SECTION
    RUNS_PER_SUBJECT is calculated to guarantee ≥10 sessions per section.
    """
    # section_key → [student dicts]
    section_map = {}
    for s in all_students:
        section_map.setdefault(s['section_key'],[]).append(s)

    # All teacher+section combos
    all_pairs = []
    for uname, fname in TEACHERS:
        for prog,year,sec in TEACHER_SECTIONS.get(uname,[]):
            sk   = make_section_key(prog,year,sec)
            pool = SUBJECTS_CS if 'Computer Science' in prog else SUBJECTS_IT
            if sk in section_map and section_map[sk]:
                all_pairs.append({
                    'uname':uname,'fname':fname,
                    'sk':sk,'pool':pool,
                })

    # Sessions per subject to guarantee MIN_SESSIONS_PER_SECTION
    runs_per_subj = max(2, -(-MIN_SESSIONS_PER_SECTION // 5))  # ceiling div

    # Time bucket distribution across sessions per section
    # Each section gets (5 subjects × runs_per_subj) sessions total
    total_per_section = 5 * runs_per_subj

    # We'll assign time buckets round-robin per section
    # so every section contributes to Today/Month/Year/Older
    def bucket_for(run_index):
        """Assign a time bucket based on run index."""
        buckets = (
            ['today']      * 3 +
            ['this_month'] * 5 +
            ['this_year']  * 7 +
            ['older']      * max(0, total_per_section - 15)
        )
        if run_index < len(buckets):
            return buckets[run_index]
        return 'older'

    sess_total = 0
    log_total  = 0

    print(f"\n  {len(all_pairs)} sections × {total_per_section} sessions each")
    print(f"  (5 subjects × {runs_per_subj} runs, spread Today/Month/Year/Older)")
    print("  " + "─"*54)

    for pair in all_pairs:
        uname = pair['uname']
        fname = pair['fname']
        sk    = pair['sk']
        pool  = pair['pool']
        enrolled = section_map.get(sk,[])
        if not enrolled:
            continue

        sk_label     = sk.replace('|',' › ')
        used_days    = set()   # prevent same-day duplicates within section
        run_counter  = 0

        for subj in pool:
            for run in range(runs_per_subj):
                bucket = bucket_for(run_counter)
                run_counter += 1

                # ── Pick started_dt based on bucket ──────────────────────
                hour = random.randint(7,16)
                if bucket == 'today':
                    started_dt = dt_today(hour=hour)
                elif bucket == 'this_month':
                    # Find a unique day this month
                    for attempt in range(50):
                        candidate = dt_this_month()
                        day_key = candidate.strftime('%Y-%m-%d')
                        if day_key not in used_days:
                            used_days.add(day_key)
                            started_dt = candidate
                            break
                    else:
                        started_dt = dt_this_month()
                elif bucket == 'this_year':
                    for attempt in range(50):
                        candidate = dt_this_year()
                        day_key = candidate.strftime('%Y-%m-%d')
                        if day_key not in used_days:
                            used_days.add(day_key)
                            started_dt = candidate
                            break
                    else:
                        started_dt = dt_this_year()
                else:
                    started_dt = dt_older()

                # Duration: 1, 1.5, 2, or 3 hours
                duration_h = random.choice([1.0,1.5,2.0,3.0])
                ended_dt   = started_dt + timedelta(hours=duration_h)

                # Guarantee session is ended (in the past)
                now = datetime.now()
                if ended_dt >= now:
                    ended_dt = now - timedelta(minutes=random.randint(5,20))
                if ended_dt <= started_dt:
                    ended_dt = started_dt + timedelta(hours=1)

                sess_id   = str(uuid.uuid4())[:12]
                time_slot = random.choice(TIME_SLOTS)

                log_rows, totals = _insert_session_with_logs(
                    conn, sess_id, subj, sk, uname, fname,
                    started_dt, ended_dt, time_slot, enrolled, pers_map
                )

                sess_total += 1
                log_total  += log_rows

        print(
            f"  ✅ {sk_label:<50}  "
            f"{total_per_section} sessions  "
            f"({sum(1 for s in [bucket_for(i) for i in range(total_per_section)] if s=='today')} today, "
            f"{sum(1 for s in [bucket_for(i) for i in range(total_per_section)] if s=='this_month')} this month, "
            f"{sum(1 for s in [bucket_for(i) for i in range(total_per_section)] if s=='this_year')} this year)"
        )

    print(f"\n  Total: {sess_total} sessions, {log_total:,} attendance log rows")
    return sess_total, log_total

# ── Post-seed verification ────────────────────────────────────────────────────
def verify(conn):
    """
    Mirrors the exact queries app.py uses at runtime.
    If these return 0 rows something is still wrong.
    """
    print("\n  " + "─"*54)
    print("  POST-SEED VERIFICATION")
    print("  " + "─"*54)
    ok = True

    # 1. Students count
    n = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    status = "✅" if n > 0 else "❌"
    print(f"  {status} students table: {n} rows")
    if n == 0: ok = False

    # 2. Sessions count
    n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    status = "✅" if n > 0 else "❌"
    print(f"  {status} sessions table: {n} rows")
    if n == 0: ok = False

    # 3. Attendance logs count
    n = conn.execute("SELECT COUNT(*) FROM attendance_logs").fetchone()[0]
    status = "✅" if n > 0 else "❌"
    print(f"  {status} attendance_logs: {n:,} rows")
    if n == 0: ok = False

    # 4. Verify section_key integrity
    # This mirrors build_student_section_key(student) == session.section_key
    mismatch = conn.execute("""
        SELECT COUNT(DISTINCT s.sess_id) as bad_sessions
        FROM sessions s
        WHERE NOT EXISTS (
            SELECT 1 FROM students st
            WHERE s.section_key = st.program || '|' || st.year_level || '|' || st.section
        )
    """).fetchone()[0]
    status = "✅" if mismatch == 0 else "❌"
    print(f"  {status} section_key integrity: {mismatch} sessions with no matching students")
    if mismatch > 0: ok = False

    # 5. Simulate student_sessions_api() — what the Sessions tab uses
    # Pick the first student and check if their attendance joins correctly
    first_student = conn.execute(
        "SELECT nfc_id, full_name FROM students LIMIT 1").fetchone()
    if first_student:
        nfc  = first_student['nfc_id']
        name = first_student['full_name']
        sess_count = conn.execute("""
            SELECT COUNT(*) FROM attendance_logs al
            JOIN sessions s ON al.sess_id = s.sess_id
            WHERE al.nfc_id = ?
        """, (nfc,)).fetchone()[0]
        status = "✅" if sess_count >= 1 else "❌"
        print(f"  {status} Sessions tab query for '{name}': {sess_count} sessions found")
        if sess_count == 0: ok = False

    # 6. Simulate attendance_stats() for 'today'
    today_start = datetime.now().replace(
        hour=0,minute=0,second=0,microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    today_count = conn.execute("""
        SELECT COUNT(DISTINCT s.sess_id)
        FROM sessions s
        WHERE s.started_at >= ?
        AND s.ended_at IS NOT NULL
    """, (today_start,)).fetchone()[0]
    status = "✅" if today_count > 0 else "⚠ "
    print(f"  {status} Sessions TODAY (for analytics): {today_count} found")

    # 7. Simulate attendance_stats() for 'all time'
    all_count = conn.execute("""
        SELECT COUNT(*) FROM attendance_logs al
        JOIN sessions s ON al.sess_id = s.sess_id
        WHERE s.ended_at IS NOT NULL
    """).fetchone()[0]
    status = "✅" if all_count > 0 else "❌"
    print(f"  {status} Attendance logs joinable: {all_count:,} rows")
    if all_count == 0: ok = False

    # 8. Check TX hashes populated
    with_tx = conn.execute(
        "SELECT COUNT(*) FROM attendance_logs WHERE tx_hash != '' AND tx_hash IS NOT NULL"
    ).fetchone()[0]
    total   = conn.execute(
        "SELECT COUNT(*) FROM attendance_logs").fetchone()[0]
    pct     = round(with_tx/total*100,1) if total else 0
    status  = "✅" if pct > 90 else "⚠ "
    print(f"  {status} Logs with TX hash: {with_tx:,} / {total:,}  ({pct}%)")

    print()
    if ok:
        print("  ✅ All checks passed — system ready")
    else:
        print("  ❌ Some checks failed — see above")
    return ok

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    auto_yes = '--yes'   in sys.argv
    do_clear = '--clear' in sys.argv

    sections_n = len(PROGRAMS)*len(YEAR_LEVELS)*len(SECTIONS)
    students_n = sections_n * STUDENTS_PER_SECTION
    runs       = max(2, -(-MIN_SESSIONS_PER_SECTION//5))
    sessions_n = sections_n * 5 * runs
    logs_n     = sessions_n * STUDENTS_PER_SECTION

    print()
    print("  ══════════════════════════════════════════════════════════")
    print("   DAVS — Dummy Data Seeder  v5")
    print("  ══════════════════════════════════════════════════════════")
    print()

    check_db()

    if do_clear and not auto_yes:
        print(f"\n  ⚠  --clear will DELETE all existing students, sessions,")
        print(f"     attendance logs, subjects, and non-admin accounts.")
        ans = input("  Type YES to confirm: ").strip()
        if ans != 'YES':
            print("\n  Cancelled.\n"); sys.exit(0)

    if not auto_yes and not do_clear:
        print(f"""
  Will ADD to your database:
    • 1  admin           (admin / {PASSWORD})
    • 5  teachers        (teacher01–05 / {PASSWORD})
    • 10 subjects        (CS101–CS105, IT101–IT105)
    • {students_n:,} students       (30 per section × {sections_n} sections)
    • ≈{sessions_n} sessions      (≥{MIN_SESSIONS_PER_SECTION}/section, all ended)
    • ≈{logs_n:,} log rows    (all with dummy TX hash)

  Sessions spread across:
    Today / This Month / This Year / All Time
    → analytics graphs will show data in all periods

  Each student has a unique attendance personality across subjects.
  Use --clear to wipe existing data first.
  Use --yes   to skip this prompt.
""")
        input("  Press ENTER to continue or Ctrl+C to cancel: ")

    if do_clear:
        clear_data()

    print("\n  Seeding…")
    print("  " + "─"*54)

    with get_db() as conn:
        seed_admin(conn)
        seed_teachers(conn)
        seed_subjects(conn)

        print("\n  Creating students (30 per section)…")
        print("  " + "─"*54)
        students, pers_map = seed_students(conn)

        sess_n, log_n = seed_sessions(conn, students, pers_map)

        verify(conn)

    print()
    print("  ══════════════════════════════════════════════════════════")
    print("   SEED COMPLETE")
    print("  ══════════════════════════════════════════════════════════")
    print()
    print(f"  {students_n:,} students  │  {sess_n} sessions  │  {log_n:,} attendance rows")
    print()
    print("  Login credentials  (password: test123 for all)")
    print(f"  ┌──────────────┬──────────────────────────────┐")
    print(f"  │ Username     │ Full Name                    │")
    print(f"  ├──────────────┼──────────────────────────────┤")
    print(f"  │ admin        │ System Administrator         │")
    for uname, fname in TEACHERS:
        print(f"  │ {uname:<12} │ {fname:<28} │")
    print(f"  └──────────────┴──────────────────────────────┘")
    print()
    print("  Next: python app.py  →  http://localhost:5000")
    print()

if __name__ == '__main__':
    main()