import io
import re
from datetime import datetime

try:
    import pypdf  # type: ignore[import-not-found]
except Exception:
    pypdf = None


def _parse_cvsu_pdf_text(raw_bytes: bytes) -> str:
    """Extract plain text from a CvSU PDF. Tries pypdf, falls back to pdfminer."""
    full = ''
    try:
        if pypdf is None:
            raise ImportError('pypdf not installed')
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        full = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception as exc:
        print(f'[PDF] pypdf failed: {exc}')
    if not full.strip():
        try:
            from pdfminer.high_level import extract_text as _pm
            full = _pm(io.BytesIO(raw_bytes))
        except Exception as exc:
            print(f'[PDF] pdfminer failed: {exc}')
    return full


def _generate_cvsu_email(name: str) -> str:
    """sc.firstname.lastname@cvsu.edu.ph from a full name string."""
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


def _surname_sort_key(student: dict) -> tuple:
    """
    (surname_lower, firstnames_lower) for alphabetical-by-surname sorting.
    Handles "First Mid Last" and "Last, First Mid" formats.
    """
    name = (student.get('name') or '').strip()
    if not name:
        return ('', '')
    if ',' in name:
        parts = name.split(',', 1)
        surname = parts[0].strip()
        firsts = parts[1].strip()
    else:
        parts = name.split()
        surname = parts[-1] if len(parts) > 1 else parts[0]
        firsts = ' '.join(parts[:-1])
    clean = lambda s: re.sub(r'[^a-z ]', '', s.lower()).strip()
    return (clean(surname), clean(firsts))


# Course name alias map (abbreviation <-> full name)
_COURSE_ALIASES: dict[str, list[str]] = {
    'BS Information Technology': ['BSIT', 'B.S. Information Technology', 'BS InfoTech'],
    'BS Computer Science': ['BSCS', 'B.S. Computer Science', 'BS CompSci'],
    'BS Computer Engineering': ['BSCpE', 'BSCOE', 'B.S. Computer Engineering'],
    'BS Information Systems': ['BSIS', 'B.S. Information Systems'],
    'BS Electrical Engineering': ['BSEE', 'B.S. Electrical Engineering'],
    'BS Electronics Engineering': ['BSEcE', 'BSECE', 'B.S. Electronics Engineering'],
    'BS Accountancy': ['BSA', 'B.S. Accountancy'],
    'BS Business Administration': ['BSBA', 'B.S. Business Administration'],
    'BS Education': ['BSEd', 'B.S. Education'],
    'BS Nursing': ['BSN', 'B.S. Nursing'],
    'BS Civil Engineering': ['BSCE', 'B.S. Civil Engineering'],
    'BS Mechanical Engineering': ['BSME', 'B.S. Mechanical Engineering'],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canon, _aliases in _COURSE_ALIASES.items():
    _ALIAS_TO_CANONICAL[_canon.lower()] = _canon
    for _a in _aliases:
        _ALIAS_TO_CANONICAL[_a.lower()] = _canon


def normalize_course_name(course: str) -> str:
    """Return canonical course name if recognized, else return unchanged."""
    return _ALIAS_TO_CANONICAL.get((course or '').strip().lower(), (course or '').strip())


def _extract_cvsu_fields(full: str) -> dict:
    """
    Parse all CvSU registration fields from extracted PDF text.

    CvSU pypdf layout: LABEL LINE\nVALUE LINE
    The value is always on the line immediately after its label.

    Returns dict with keys:
        student_id, name, email, contact, adviser,
        semester, school_year, course, year_level, section,
        major, date_registered, subjects
    """
    abbr_course = {
        'BSCS': 'BS Computer Science', 'BSIT': 'BS Information Technology',
        'BSIS': 'BS Information Systems', 'BSCOE': 'BS Computer Engineering',
        'BSECE': 'BS Electronics Engineering', 'BSEE': 'BS Electrical Engineering',
        'BSCE': 'BS Civil Engineering', 'BSME': 'BS Mechanical Engineering',
        'BSED': 'BS Education', 'BSN': 'BS Nursing',
        'BSA': 'BS Accountancy', 'BSBA': 'BS Business Administration',
    }
    prefix_course = {
        'CS': 'BS Computer Science', 'IT': 'BS Information Technology',
        'IS': 'BS Information Systems', 'COE': 'BS Computer Engineering',
        'ECE': 'BS Electronics Engineering', 'EE': 'BS Electrical Engineering',
        'CE': 'BS Civil Engineering', 'ME': 'BS Mechanical Engineering',
        'ED': 'BS Education', 'N': 'BS Nursing',
        'A': 'BS Accountancy', 'BA': 'BS Business Administration',
    }
    year_map = {
        '1': '1st Year', '2': '2nd Year', '3': '3rd Year',
        '4': '4th Year', '5': '5th Year',
        '1st': '1st Year', '2nd': '2nd Year', '3rd': '3rd Year',
        '4th': '4th Year', '5th': '5th Year',
    }
    sem_map = {
        'FIRST': 'First', 'SECOND': 'Second', 'SUMMER': 'Summer',
        '1ST': 'First', '2ND': 'Second',
    }

    result = {
        'student_id': '', 'name': '', 'email': '', 'contact': '',
        'adviser': '', 'semester': '', 'school_year': '',
        'course': '', 'year_level': '', 'section': '',
        'major': '', 'date_registered': '', 'subjects': [],
    }

    def next_line(label_re):
        m = re.search(label_re + r'[^\n]*\n([^\n]+)', full, re.IGNORECASE)
        if not m:
            return ''
        return (m.group(1) or '').replace('\t', ' ').strip()

    result['student_id'] = next_line(r'Student\s*(?:No\.?|Number|ID)')
    if not result['student_id']:
        m = re.search(r'\b(\d{4}-\d{4,6})\b', full)
        if m:
            result['student_id'] = m.group(1)
    if not result['student_id']:
        m = re.search(r'\b(\d{7,10})\b', full)
        if m:
            result['student_id'] = m.group(1)

    raw_sem = next_line(r'Semester').upper()
    first_w = raw_sem.split()[0] if raw_sem else ''
    result['semester'] = sem_map.get(first_w, raw_sem.title()) if raw_sem else ''

    result['school_year'] = next_line(r'School\s*Year')

    _norm_full = full.replace('\t', ' ')
    _name_m = re.search(
        r'Student\s+Name\s*:\s*((?:[A-Z][A-Z\s.,\'\-]+?)'
        r'(?=\s*(?:Date|Course|Year|Encoder|Major|Section|Address)\s*:|$))',
        _norm_full, re.IGNORECASE | re.DOTALL,
    )
    raw_name = ''
    if _name_m:
        raw_name = re.sub(r'\s+', ' ', _name_m.group(1)).strip()
        if re.match(r'(Date|Course|Year|Encoder)\s*:', raw_name, re.IGNORECASE):
            raw_name = ''
    if not raw_name:
        _fb = re.search(r'Student\s*Name[^\n]*\n([^\n:]+)', _norm_full, re.IGNORECASE)
        if _fb:
            raw_name = _fb.group(1).replace('\t', ' ').strip()
    if raw_name:
        result['name'] = raw_name.title()
        result['email'] = _generate_cvsu_email(raw_name)

    result['adviser'] = next_line(r'Adviser|Advisor')
    result['contact'] = next_line(r'Contact\s*(?:No\.?|Number)')

    raw_date = ''
    for _m in re.finditer(r'Date[^\n]*\n([^\n]+)', full, re.IGNORECASE):
        ctx = full[max(0, _m.start() - 30):_m.start()].upper()
        if any(kw in ctx for kw in ('VALIDAT', 'PAYMENT', 'CONFIR')):
            continue
        raw_date = _m.group(1).replace('\t', ' ').strip()
        break
    if raw_date:
        dm = re.search(r'(\d{1,2})[-\s/]+([A-Za-z]+)[-\s/]+(\d{4})', raw_date)
        if dm:
            try:
                d = datetime.strptime(f"{dm.group(2)} {dm.group(3)}", "%b %Y")
                result['date_registered'] = d.strftime('%Y-%m')
            except Exception:
                pass
        if not result['date_registered']:
            dm2 = re.search(r'([A-Za-z]+)\s+(\d{4})', raw_date)
            if dm2:
                try:
                    d = datetime.strptime(f"{dm2.group(1)} {dm2.group(2)}", "%b %Y")
                    result['date_registered'] = d.strftime('%Y-%m')
                except Exception:
                    pass

    raw_course = next_line(r'Course').strip().upper()
    result['course'] = abbr_course.get(raw_course, '')
    if not result['course']:
        for abbr, cname in abbr_course.items():
            if re.search(r'\b' + abbr + r'\b', full, re.IGNORECASE):
                result['course'] = cname
                break

    raw_section = next_line(r'Section').strip()
    sec_m = re.match(r'^([A-Za-z]+)(\d)([A-Za-z])$', raw_section)
    if sec_m:
        prefix = sec_m.group(1).upper()
        yr_digit = sec_m.group(2)
        result['section'] = sec_m.group(3).upper()
        result['year_level'] = year_map.get(yr_digit, yr_digit + 'th Year')
        if not result['course']:
            result['course'] = prefix_course.get(prefix, '')
    else:
        result['section'] = raw_section[:1].upper() if raw_section else ''
        raw_year = next_line(r'Year\s*(?:Level)?').strip()
        yr_w = raw_year.split()[0].lower() if raw_year else ''
        result['year_level'] = (year_map.get(yr_w) or year_map.get(yr_w.rstrip('thsrnd')) or '')

    raw_major = next_line(r'Major')
    result['major'] = ('' if raw_major.upper().strip() in ('N/A', 'NA', 'NONE', '', '\u2014') else raw_major.title())

    subjects = []
    hdr_m = re.search(r'Schedule\s*Code.*?(?:Course\s*)?Description.*?Hour[s]?\s*\n', full, re.DOTALL | re.IGNORECASE)
    fees_m = re.search(r'Laboratory\s*Fees|Total\s*Units', full, re.IGNORECASE)
    if hdr_m and fees_m and fees_m.start() > hdr_m.end():
        block = full[hdr_m.end():fees_m.start()]
        lines = [l.replace('\t', ' ').strip() for l in block.split('\n') if l.strip()]
        i = 0
        while i < len(lines):
            if re.match(r'^\d{7,12}$', lines[i]) and i + 7 < len(lines):
                code_clean = re.sub(r'\s+', ' ', lines[i + 2]).strip()
                desc_clean = lines[i + 3].title()
                try:
                    units_int = str(round(float(lines[i + 4])))
                except Exception:
                    units_int = '3'
                if units_int == '0':
                    units_int = '3'
                if code_clean and desc_clean:
                    subjects.append({
                        'course_code': code_clean,
                        'name': desc_clean,
                        'units': units_int,
                    })
                i += 8
            else:
                i += 1

    result['subjects'] = subjects
    return result
