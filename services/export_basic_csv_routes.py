from datetime import datetime
import csv
import io

from flask import Response


def export_csv_all_impl(*, get_all_students_fn, get_attendance_records_fn):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Name', 'NFC ID', 'Student ID', 'Course', 'Year', 'Section', 'Adviser', 'Email', 'Contact', 'Date & Time', 'Status'])
    for s in get_all_students_fn():
        records = get_attendance_records_fn(s['nfcId']) or [('No records', '')]
        for ts, p in records:
            w.writerow(
                [
                    s['name'],
                    s['nfcId'],
                    s['student_id'],
                    s['course'],
                    s['year_level'],
                    s['section'],
                    s['adviser'],
                    s['email'],
                    s['contact'],
                    ts,
                    'Present' if p is True else ('Absent' if p is False else ''),
                ]
            )
    out.seek(0)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_all_{datetime.now().strftime("%Y%m%d")}.csv'},
    )


def export_csv_single_impl(*, nfc_id, student_name_map_obj, get_attendance_records_fn):
    name = student_name_map_obj.get(nfc_id, 'Unknown')
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Student Name', 'NFC ID', 'Date & Time', 'Status'])
    for ts, p in get_attendance_records_fn(nfc_id):
        w.writerow([name, nfc_id, ts, 'Present' if p else 'Absent'])
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
):
    students = teacher_students_fn(user_obj)
    if sec_key:
        norm_key = normalize_section_key_fn(sec_key)
        students = [s for s in students if build_student_section_key_fn(s) == norm_key]

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Name', 'NFC ID', 'Student ID', 'Course', 'Year', 'Section', 'Date & Time', 'Status'])
    for s in students:
        records = get_attendance_records_fn(s['nfcId']) or [('No records', '')]
        for ts, p in records:
            w.writerow(
                [
                    s['name'],
                    s['nfcId'],
                    s['student_id'],
                    s['course'],
                    s['year_level'],
                    s['section'],
                    ts,
                    'Present' if p is True else ('Absent' if p is False else ''),
                ]
            )
    out.seek(0)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=section_{datetime.now().strftime("%Y%m%d")}.csv'},
    )
