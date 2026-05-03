from datetime import datetime, timedelta
import calendar as _cal
import csv
import io

from flask import Response


def export_stats_csv_impl(
    *,
    request_obj,
    session_obj,
    get_db_fn,
    normalize_section_key_fn,
):
    period = request_obj.args.get('period', 'all')
    f_month = request_obj.args.get('month', '').strip()
    f_year_num = request_obj.args.get('year_num', '').strip()
    f_section = request_obj.args.get('section_key', request_obj.args.get('section', '')).strip()
    f_year_lvl = request_obj.args.get('year_level', '').strip()
    f_subject = request_obj.args.get('subject', '').strip()
    f_program = request_obj.args.get('program', '').strip()
    f_sec_ltr = request_obj.args.get('section_letter', '').strip()
    f_instr = request_obj.args.get('instructor', '').strip()
    f_tod = request_obj.args.get('time_of_day', '').strip()
    role = session_obj.get('role')
    username = session_obj.get('username')
    now = datetime.utcnow() + timedelta(hours=8)

    if not f_year_num:
        f_year_num = request_obj.args.get('year', '').strip() if period in ('month', 'year') else ''

    if period == 'today':
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = None
    elif period == 'month':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        mo = int(f_month) if f_month and f_month.isdigit() else now.month
        start_dt = datetime(yr, mo, 1)
        end_dt = datetime(yr, mo, _cal.monthrange(yr, mo)[1], 23, 59, 59)
    elif period == 'year':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        start_dt = datetime(yr, 1, 1)
        end_dt = datetime(yr, 12, 31, 23, 59, 59)
    else:
        start_dt = datetime(2000, 1, 1)
        end_dt = None

    where = ['s.started_at >= ?']
    params = [start_dt.strftime('%Y-%m-%d %H:%M:%S')]
    if end_dt:
        where.append('s.started_at <= ?')
        params.append(end_dt.strftime('%Y-%m-%d %H:%M:%S'))
    if role == 'teacher':
        where.append('s.teacher_username = ?')
        params.append(username)
    if f_section:
        where.append('s.section_key = ?')
        params.append(normalize_section_key_fn(f_section))
    if f_program:
        where.append('s.section_key LIKE ?')
        params.append(f_program + '%')
    if f_year_lvl:
        where.append('s.section_key LIKE ?')
        params.append('%|' + f_year_lvl + '|%')
    if f_sec_ltr:
        where.append('s.section_key LIKE ?')
        params.append('%|' + f_sec_ltr)
    if f_subject:
        where.append('s.subject_name = ?')
        params.append(f_subject)
    if f_instr:
        where.append('s.teacher_name = ?')
        params.append(f_instr)
    if f_tod == 'morning':
        where.append("CAST(strftime('%H',s.started_at) AS INTEGER) < 12")
    elif f_tod == 'afternoon':
        where.append("CAST(strftime('%H',s.started_at) AS INTEGER) >= 12")
    elif f_tod and ':' in f_tod:
        where.append('s.time_slot = ?')
        params.append(f_tod)
    wsql = ' AND '.join(where)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Session ID', 'Subject', 'Section', 'Instructor', 'Date', 'Time Slot', 'Total Records', 'Present', 'Late', 'Absent', 'Excused', 'Rate%'])
    with get_db_fn() as conn:
        rows = conn.execute(
            "SELECT s.sess_id, s.subject_name, s.section_key, s.teacher_name, s.started_at, s.time_slot, "
            "SUM(CASE WHEN al.status='present' THEN 1 ELSE 0 END) AS present_count, "
            "SUM(CASE WHEN al.status='late' THEN 1 ELSE 0 END) AS late_count, "
            "SUM(CASE WHEN al.status='absent' THEN 1 ELSE 0 END) AS absent_count, "
            "SUM(CASE WHEN al.status='excused' THEN 1 ELSE 0 END) AS excused_count, "
            "COUNT(*) AS total_count "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "WHERE " + wsql + ' '
            "GROUP BY s.sess_id, s.subject_name, s.section_key, s.teacher_name, s.started_at, s.time_slot "
            "ORDER BY s.started_at",
            params,
        ).fetchall()
    for r in rows:
        total = int(r['total_count'] or 0)
        present = int(r['present_count'] or 0)
        late = int(r['late_count'] or 0)
        absent = int(r['absent_count'] or 0)
        excused = int(r['excused_count'] or 0)
        rate = round((present + late) / total * 100, 1) if total else 0
        w.writerow(
            [
                (r['sess_id'] or '')[:8],
                r['subject_name'] or '',
                normalize_section_key_fn(r['section_key'] or '').replace('|', ' · '),
                r['teacher_name'] or '',
                (r['started_at'] or '')[:10],
                r['time_slot'] or '',
                total,
                present,
                late,
                absent,
                excused,
                rate,
            ]
        )
    out.seek(0)
    fname = f'attendance_{period}_{now.strftime("%Y%m%d")}.csv'
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename={fname}'})
