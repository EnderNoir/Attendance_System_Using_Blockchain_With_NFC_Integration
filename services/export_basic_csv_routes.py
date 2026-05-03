from datetime import datetime, timedelta
import csv
import io
import re

from flask import Response


def _parse_dt(value):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def _fmt_date_dash(value):
    dt = _parse_dt(value)
    if not dt:
        return '—'
    return dt.strftime('%B-%d-%Y')


def _fmt_time_hms_ampm(value):
    dt = _parse_dt(value)
    if not dt:
        return '—'
    return dt.strftime('%I:%M:%S %p')


def _normalize_time_token(value):
    if value is None:
        return '—'
    raw = str(value).strip()
    if not raw:
        return '—'
    if 'AM' in raw.upper() or 'PM' in raw.upper():
        return raw.upper()
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', raw)
    if not m:
        return raw
    h = int(m.group(1))
    mm = m.group(2)
    period = 'PM' if h >= 12 else 'AM'
    hh = 12 if h % 12 == 0 else (h % 12)
    return f"{hh:02d}:{mm} {period}"


def _normalize_time_slot(value):
    if not value:
        return '—'
    raw = str(value).strip()
    if not raw:
        return '—'
    if 'AM' in raw.upper() or 'PM' in raw.upper():
        return raw.upper()
    if '–' in raw:
        parts = [p.strip() for p in raw.split('–', 1)]
    elif '-' in raw:
        parts = [p.strip() for p in raw.split('-', 1)]
    else:
        parts = [raw]
    if len(parts) == 2:
        return f"{_normalize_time_token(parts[0])} - {_normalize_time_token(parts[1])}"
    return _normalize_time_token(parts[0])


def _fallback_rows(nfc_id, get_attendance_records_fn):
    rows = []
    for ts, is_present in (get_attendance_records_fn(nfc_id) or []):
        rows.append(
            {
                'code': '—',
                'subject': '—',
                'teacher': '—',
                'date': _fmt_date_dash(ts),
                'time_slot': _fmt_time_hms_ampm(ts),
                'tx_hash': '—',
                'block': '—',
                'status': 'Present' if is_present is True else ('Absent' if is_present is False else '—'),
                'excuse': '—',
                'document': '—',
            }
        )
    return rows


def _normalize_rows(nfc_id, get_student_session_rows_fn, get_attendance_records_fn):
    if get_student_session_rows_fn:
        raw_rows = get_student_session_rows_fn(nfc_id) or []
        rows = []
        for row in raw_rows:
            rows.append(
                {
                    'code': row.get('code') or '—',
                    'subject': row.get('subject') or '—',
                    'teacher': row.get('teacher') or '—',
                    'date': _fmt_date_dash(row.get('date') or row.get('started_at') or row.get('tap_time') or ''),
                    'time_slot': _normalize_time_slot(row.get('time_slot') or ''),
                    'tx_hash': row.get('tx_hash') or '—',
                    'block': str(row.get('block')) if row.get('block') not in (None, '') else '—',
                    'status': (row.get('status') or '—').capitalize(),
                    'excuse': row.get('excuse') or '—',
                    'document': row.get('document') or '—',
                }
            )
        if rows:
            return rows
    return _fallback_rows(nfc_id, get_attendance_records_fn)


def export_csv_all_impl(*, get_all_students_fn, get_attendance_records_fn, get_student_session_rows_fn=None):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            'Name',
            'NFC ID',
            'Student ID',
            'Course',
            'Year',
            'Section',
            'Course Code',
            'Subject Name',
            'Instructor Name',
            'Date',
            'Time Slot',
            'Transaction Number (TX)',
            'Block Number',
            'Status',
            'Excused Reason',
            'Document',
        ]
    )
    for s in get_all_students_fn():
        rows = _normalize_rows(s['nfcId'], get_student_session_rows_fn, get_attendance_records_fn) or [
            {
                'code': '—',
                'subject': '—',
                'teacher': '—',
                'date': '—',
                'time_slot': '—',
                'tx_hash': '—',
                'block': '—',
                'status': '—',
                'excuse': '—',
                'document': '—',
            }
        ]
        for row in rows:
            w.writerow(
                [
                    s['name'],
                    s['nfcId'],
                    s['student_id'],
                    s['course'],
                    s['year_level'],
                    s['section'],
                    row['code'],
                    row['subject'],
                    row['teacher'],
                    row['date'],
                    row['time_slot'],
                    row['tx_hash'],
                    row['block'],
                    row['status'],
                    row['excuse'],
                    row['document'],
                ]
            )
    out.seek(0)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_all_{(datetime.utcnow() + timedelta(hours=8)).strftime("%Y%m%d")}.csv'},
    )


def export_csv_single_impl(*, nfc_id, student_name_map_obj, get_attendance_records_fn, get_student_session_rows_fn=None):
    name = student_name_map_obj.get(nfc_id, 'Unknown')
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            'Student Name',
            'NFC ID',
            'Course Code',
            'Subject Name',
            'Instructor Name',
            'Date',
            'Time Slot',
            'Transaction Number (TX)',
            'Block Number',
            'Status',
            'Excused Reason',
            'Document',
        ]
    )
    rows = _normalize_rows(nfc_id, get_student_session_rows_fn, get_attendance_records_fn)
    for row in rows:
        w.writerow(
            [
                name,
                nfc_id,
                row['code'],
                row['subject'],
                row['teacher'],
                row['date'],
                row['time_slot'],
                row['tx_hash'],
                row['block'],
                row['status'],
                row['excuse'],
                row['document'],
            ]
        )
    out.seek(0)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_{nfc_id}.csv'},
    )


def teacher_export_section_csv_impl(
    *,
    user_obj,
    sec_key,
    teacher_students_fn,
    normalize_section_key_fn,
    build_student_section_key_fn,
    get_attendance_records_fn,
    get_student_session_rows_fn=None,
):
    students = teacher_students_fn(user_obj)
    if sec_key:
        norm_key = normalize_section_key_fn(sec_key)
        students = [s for s in students if build_student_section_key_fn(s) == norm_key]

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            'Name',
            'NFC ID',
            'Student ID',
            'Course',
            'Year',
            'Section',
            'Course Code',
            'Subject Name',
            'Instructor Name',
            'Date',
            'Time Slot',
            'Transaction Number (TX)',
            'Block Number',
            'Status',
            'Excused Reason',
            'Document',
        ]
    )
    for s in students:
        rows = _normalize_rows(s['nfcId'], get_student_session_rows_fn, get_attendance_records_fn) or [
            {
                'code': '—',
                'subject': '—',
                'teacher': '—',
                'date': '—',
                'time_slot': '—',
                'tx_hash': '—',
                'block': '—',
                'status': '—',
                'excuse': '—',
                'document': '—',
            }
        ]
        for row in rows:
            w.writerow(
                [
                    s['name'],
                    s['nfcId'],
                    s['student_id'],
                    s['course'],
                    s['year_level'],
                    s['section'],
                    row['code'],
                    row['subject'],
                    row['teacher'],
                    row['date'],
                    row['time_slot'],
                    row['tx_hash'],
                    row['block'],
                    row['status'],
                    row['excuse'],
                    row['document'],
                ]
            )
    out.seek(0)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=section_{(datetime.utcnow() + timedelta(hours=8)).strftime("%Y%m%d")}.csv'},
    )
