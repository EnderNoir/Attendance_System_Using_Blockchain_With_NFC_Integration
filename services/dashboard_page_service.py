def dashboard_page_impl(*, get_all_students, db_get_all_users, get_db, render_template, fmt_time, **kwargs):
    """Render admin dashboard with students, faculty map, and cached photos."""
    students = get_all_students()
    all_users = db_get_all_users()
    teachers = {u: d for u, d in all_users.items() if d.get('role') in ('admin', 'teacher')}

    with get_db() as conn:
        photo_rows = conn.execute("SELECT person_id, filename FROM photos").fetchall()
    photos_db = {r['person_id']: r['filename'] for r in photo_rows}

    return render_template(
        'dashboard.html',
        students=students,
        teachers=teachers,
        photos_db=photos_db,
        fmt_time=fmt_time,
        **kwargs
    )
