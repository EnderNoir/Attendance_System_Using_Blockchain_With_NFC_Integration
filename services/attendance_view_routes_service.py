def attendance_report_impl(*, redirect, url_for):
    return redirect(url_for('admin_sessions'))


def view_attendance_impl(
    *,
    nfc_id,
    role,
    get_current_user,
    teacher_students,
    flash,
    redirect,
    url_for,
    get_attendance_records,
    get_all_students,
    render_template,
    fmt_time,
):
    if role == 'teacher':
        user = get_current_user()
        if not any(s['nfcId'] == nfc_id for s in teacher_students(user)):
            flash('Access denied.')
            return redirect(url_for('teacher_dashboard'))

    records = get_attendance_records(nfc_id)
    student_info = next((s for s in get_all_students() if s['nfcId'] == nfc_id), {})
    return render_template(
        'attendance.html',
        nfc_id=nfc_id,
        records=records,
        student=student_info,
        fmt_time=fmt_time,
    )
