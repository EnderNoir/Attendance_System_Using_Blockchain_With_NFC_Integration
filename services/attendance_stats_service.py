from datetime import datetime
import calendar as _cal


def attendance_stats_impl(
    *,
    request_obj,
    session_obj,
    get_db_fn,
    normalize_section_key_fn,
    jsonify_fn,
    now_local_fn,
):
    period = request_obj.args.get('period', 'today')
    f_month = request_obj.args.get('month', '').strip()
    f_year_num = request_obj.args.get('year_num', '').strip()
    f_subject = request_obj.args.get('subject', '').strip()
    f_section = request_obj.args.get('section_key', request_obj.args.get('section', '')).strip()
    f_year_lvl = request_obj.args.get('year_level', '').strip()
    f_program = request_obj.args.get('program', '').strip()
    f_sec_ltr = request_obj.args.get('section_letter', '').strip()
    f_instr = request_obj.args.get('instructor', '').strip()
    f_tod = request_obj.args.get('time_of_day', '').strip()
    f_class_type = request_obj.args.get('class_type', '').strip().lower()
    f_semester = request_obj.args.get('semester', '').strip()
    f_enrollment = request_obj.args.get('enrollment_type', '').strip()
    role = session_obj.get('role')
    username = session_obj.get('username')
    now = now_local_fn()

    if not f_year_num:
        # Backward compatibility for older clients still using `year`.
        f_year_num = request_obj.args.get('year', '').strip() if period in ('month', 'year') else ''

    if period == 'today':
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
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

    # Direct string comparison on s.started_at
    where = ["s.started_at >= ?"]
    params = [start_dt.strftime('%Y-%m-%d %H:%M:%S')]
    if end_dt:
        where.append("s.started_at <= ?")
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
    if f_class_type in ('lecture', 'laboratory', 'school_event'):
        where.append('LOWER(COALESCE(s.class_type,\'lecture\')) = ?')
        params.append(f_class_type)
    if f_semester:
        where.append('LOWER(s.semester) = ?')
        params.append(f_semester.lower())
    if f_tod and ':' in f_tod:
        where.append('s.time_slot = ?')
        params.append(f_tod)

    # enrollment_type is handled separately (only applies to attendance_log queries, not session counts)
    enroll_where_clause = ''
    enroll_params_extra = []
    if f_enrollment:
        enroll_where_clause = "AND LOWER(COALESCE(st.enrollment_status, 'regular')) = ?"
        enroll_params_extra = [f_enrollment.lower()]

    wsql = ' AND '.join(where)

    if period == 'today':
        tkey_expr = "SUBSTR(s.started_at, 12, 2) || ':00'"
    elif period == 'month':
        tkey_expr = "SUBSTR(s.started_at, 6, 5)"
    elif period == 'year':
        tkey_expr = "SUBSTR(s.started_at, 6, 2)"
    else:
        tkey_expr = "SUBSTR(s.started_at, 1, 4)"

    params = tuple(params)

    with get_db_fn() as conn:
        donut_rows = conn.execute(
            "SELECT al.status, COUNT(*) as cnt "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
            "WHERE " + wsql + ' ' + enroll_where_clause + ' GROUP BY al.status',
            tuple(params) + tuple(enroll_params_extra),
        ).fetchall()
        trend_rows = conn.execute(
            "SELECT " + tkey_expr + " as tkey, al.status, COUNT(*) as cnt "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
            "WHERE " + wsql + ' ' + enroll_where_clause + ' GROUP BY tkey, al.status ORDER BY tkey',
            tuple(params) + tuple(enroll_params_extra),
        ).fetchall()
        subj_rows = conn.execute(
            "SELECT s.subject_name, s.course_code, al.status, COUNT(*) as cnt "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
            "WHERE " + wsql + ' ' + enroll_where_clause + ' GROUP BY s.subject_name, s.course_code, al.status',
            tuple(params) + tuple(enroll_params_extra),
        ).fetchall()

        # Session count and subject labels use base wsql only (no enrollment filter)
        count_sql = (
            "SELECT COUNT(DISTINCT s.sess_id) as cnt "
            "FROM sessions s "
            "LEFT JOIN attendance_logs al ON s.sess_id = al.sess_id "
            "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
            "WHERE " + wsql
        )
        sess_count_row = conn.execute(count_sql, tuple(params)).fetchone()
        sess_count = sess_count_row['cnt'] if sess_count_row else 0

        # Fixed: subject labels query must join necessary tables for filtering
        subj_labels_rows = conn.execute(
            "SELECT DISTINCT s.subject_name, s.course_code FROM sessions s "
            "LEFT JOIN attendance_logs al ON s.sess_id = al.sess_id "
            "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
            "WHERE " + wsql + ' ORDER BY s.subject_name',
            tuple(params),
        ).fetchall()

    donut = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0}
    for r in donut_rows:
        if r['status'] in donut:
            donut[r['status']] = r['cnt']

    trend_buckets = {}
    for r in trend_rows:
        key = r['tkey']
        if key not in trend_buckets:
            trend_buckets[key] = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0}
        if r['status'] in trend_buckets[key]:
            trend_buckets[key][r['status']] = r['cnt']

    subjects_breakdown = {}
    for r in subj_rows:
        code = r['course_code']
        label = f"[{code}] {r['subject_name']}" if code else r['subject_name']
        if label not in subjects_breakdown:
            subjects_breakdown[label] = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'sessions': 0}
        if r['status'] in subjects_breakdown[label]:
            subjects_breakdown[label][r['status']] = r['cnt']

    subj_labels_out = [
        (f"[{r['course_code']}] {r['subject_name']}" if r['course_code'] else r['subject_name'])
        for r in subj_labels_rows
    ]

    resp = jsonify_fn(
        {
            'role': role,
            'period': period,
            'donut': donut,
            'trend': trend_buckets,
            'subjects': subjects_breakdown,
            'all_subjects': subj_labels_out,
            'session_count': sess_count,
        }
    )
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp
