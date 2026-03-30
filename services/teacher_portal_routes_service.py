def admin_sessions_page_impl(*, get_db, session_row_with_logs, render_template, db_get_all_subjects, fmt_time):
    with get_db() as conn:
        active_rows = conn.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
        ended_rows = conn.execute(
            "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC"
        ).fetchall()
        active = {row['sess_id']: session_row_with_logs(conn, row) for row in active_rows}
        ended = {row['sess_id']: session_row_with_logs(conn, row) for row in ended_rows}

    return render_template(
        'admin_sessions.html',
        active=active,
        ended=ended,
        subjects_db=db_get_all_subjects(),
        fmt_time=fmt_time,
    )


def teacher_dashboard_page_impl(
    *,
    session_obj,
    redirect,
    url_for,
    get_current_user,
    clear_session,
    build_teacher_context,
    get_active_sessions,
    get_db,
    teacher_students,
    render_template,
    fmt_time,
    fmt_time_short,
):
    if session_obj.get('role') == 'admin':
        return redirect(url_for('index'))

    user = get_current_user()
    if not user:
        clear_session()
        return redirect(url_for('login'))

    sections, my_subjects, _ = build_teacher_context(user)
    live_sessions = {
        sess_id: sess
        for sess_id, sess in get_active_sessions().items()
        if sess.get('teacher') == session_obj['username']
        or sess.get('teacher_name') == session_obj.get('full_name')
    }

    with get_db() as conn:
        total_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions "
            "WHERE (teacher_username=? OR teacher_name=?) AND ended_at IS NOT NULL",
            (session_obj['username'], session_obj.get('full_name', '')),
        ).fetchone()[0]

    total_students = len(teacher_students(user))

    return render_template(
        'teacher_dashboard.html',
        user=user,
        sections=sections,
        my_subjects=my_subjects,
        live_sessions=live_sessions,
        total_sessions=total_sessions,
        total_students=total_students,
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )


def teacher_sessions_students_page_impl(
    *,
    session_obj,
    redirect,
    url_for,
    get_current_user,
    get_db,
    session_row_with_logs,
    teacher_students,
    get_student_attendance_stats,
    render_template,
    datetime_cls,
    fmt_time,
    fmt_time_short,
):
    if session_obj.get('role') == 'admin':
        return redirect(url_for('index'))

    user = get_current_user()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions "
            "WHERE teacher_username=? OR teacher_name=? "
            "ORDER BY started_at DESC",
            (session_obj['username'], session_obj.get('full_name', '')),
        ).fetchall()
        sessions_data = {row['sess_id']: session_row_with_logs(conn, row) for row in rows}

    subjects = sorted(
        set(
            session_data.get('subject_name', '')
            for session_data in sessions_data.values()
            if session_data.get('subject_name')
        )
    )

    report = []
    for student in teacher_students(user):
        stats = get_student_attendance_stats(student['nfcId'])
        report.append({**student, **stats})
    students = sorted(report, key=lambda item: -item['rate'])

    sessions_json = {
        sess_id: {
            'subject_name': session_data.get('subject_name', ''),
            'course_code': session_data.get('course_code', ''),
            'section_key': session_data.get('section_key', ''),
            'teacher_name': session_data.get('teacher_name', ''),
            'started_at': session_data.get('started_at', ''),
            'ended_at': session_data.get('ended_at', ''),
            'time_slot': session_data.get('time_slot', ''),
            'present': session_data.get('present', []),
            'late': session_data.get('late', []),
            'excused': session_data.get('excused', []),
            'tx_hashes': session_data.get('tx_hashes', {}),
        }
        for sess_id, session_data in sessions_data.items()
    }

    return render_template(
        'teacher_sessions_students.html',
        user=user,
        sessions_data=sessions_data,
        sessions_json=sessions_json,
        subjects=subjects,
        students=students,
        now=str(datetime_cls.now().year),
        fmt_time=fmt_time,
        fmt_time_short=fmt_time_short,
    )


def teacher_create_session_page_impl(
    *,
    session_obj,
    redirect,
    url_for,
    get_current_user,
    clear_session,
    build_teacher_context,
    render_template,
):
    if session_obj.get('role') == 'admin':
        return redirect(url_for('index'))

    user = get_current_user()
    if not user:
        clear_session()
        return redirect(url_for('login'))

    sections, my_subjects, all_subjects = build_teacher_context(user)
    return render_template(
        'teacher_create_session.html',
        user=user,
        sections=sections,
        my_subjects=my_subjects,
        subjects_db=all_subjects,
    )


def teacher_records_page_impl(
    *,
    session_obj,
    redirect,
    url_for,
    get_current_user,
    get_db,
    session_row_with_logs,
    get_all_students,
    render_template,
    fmt_time,
):
    if session_obj.get('role') == 'admin':
        return redirect(url_for('admin_sessions'))

    user = get_current_user()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE teacher_username=? AND ended_at IS NOT NULL ORDER BY started_at DESC",
            (session_obj['username'],),
        ).fetchall()
        teacher_sessions_data = {
            row['sess_id']: session_row_with_logs(conn, row) for row in rows
        }

    subjects = sorted(
        set(
            session_data.get('subject_name', '')
            for session_data in teacher_sessions_data.values()
            if session_data.get('subject_name')
        )
    )

    return render_template(
        'teacher_records.html',
        user=user,
        sessions_data=teacher_sessions_data,
        subjects=subjects,
        all_students=get_all_students(),
        fmt_time=fmt_time,
    )
