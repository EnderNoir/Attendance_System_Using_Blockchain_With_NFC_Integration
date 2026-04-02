def manage_users_impl(*, db_get_all_users, db_get_all_photos, render_template, fmt_time, session_obj):
    all_users = db_get_all_users()
    pending = {username: data for username, data in all_users.items() if data['status'] == 'pending'}
    approved = {
        username: data
        for username, data in all_users.items()
        if data['status'] == 'approved' and username != 'admin'
    }
    rejected = {username: data for username, data in all_users.items() if data['status'] == 'rejected'}
    photos_db = db_get_all_photos()
    return render_template(
        'admin_users.html',
        pending=pending,
        approved=approved,
        rejected=rejected,
        fmt_time=fmt_time,
        photos_db=photos_db,
        can_edit_roles=(session_obj.get('role') == 'super_admin'),
    )


def approve_user_impl(*, username, db_get_user, db_save_user, flash, redirect, url_for):
    user = db_get_user(username)
    if user:
        user['status'] = 'approved'
        db_save_user(username, user)
        flash(f"{user['full_name']} approved.")
    return redirect(url_for('manage_users'))


def reject_user_impl(*, username, db_get_user, db_save_user, flash, redirect, url_for):
    user = db_get_user(username)
    if user:
        user['status'] = 'rejected'
        db_save_user(username, user)
        flash(f"{user['full_name']} rejected.")
    return redirect(url_for('manage_users'))


def delete_user_impl(*, username, db_get_user, db_delete_user, flash, redirect, url_for):
    user = db_get_user(username)
    if user and username != 'admin':
        db_delete_user(username)
        flash(f"{user['full_name']} deleted.")
    return redirect(url_for('manage_users'))


def manage_subjects_impl(*, render_template, db_get_all_subjects, fmt_time):
    return render_template('admin_subjects.html', subjects=db_get_all_subjects(), fmt_time=fmt_time)


def add_subject_impl(
    *,
    request,
    flash,
    redirect,
    url_for,
    db_get_all_subjects,
    db_save_subject,
    uuid_module,
    session_obj,
    datetime_now,
):
    name = request.form.get('name', '').strip()
    if not name:
        flash('Subject name cannot be empty.')
        return redirect(url_for('manage_subjects'))

    for subject in db_get_all_subjects().values():
        if subject['name'].lower() == name.lower():
            flash(f'Subject "{name}" already exists.')
            return redirect(url_for('manage_subjects'))

    course_code = request.form.get('course_code', '').strip().upper()
    units = request.form.get('units', '3').strip()
    if units not in ('2', '3'):
        units = '3'

    subject_id = str(uuid_module.uuid4())[:8]
    db_save_subject(
        subject_id,
        {
            'name': name,
            'course_code': course_code,
            'units': units,
            'created_by': session_obj.get('username', ''),
            'created_at': datetime_now().strftime('%Y-%m-%d %H:%M:%S'),
        },
    )
    flash(f'Subject "{name}" added.')
    return redirect(url_for('manage_subjects'))


def rename_subject_impl(
    *,
    sid,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    db_get_subject,
    db_save_subject,
):
    if request.is_json:
        data = request.get_json()
        new_name = (data.get('name') or '').strip()
        if not new_name:
            return jsonify({'error': 'Name cannot be empty'}), 400
        subject = db_get_subject(sid)
        if not subject:
            return jsonify({'error': 'Subject not found'}), 404
        subject['name'] = new_name
        if 'course_code' in data:
            subject['course_code'] = data['course_code'].strip().upper()
        if 'units' in data and str(data['units']) in ('2', '3'):
            subject['units'] = str(data['units'])
        db_save_subject(sid, subject)
        return jsonify({'ok': True})

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Name cannot be empty.')
        return redirect(url_for('manage_subjects'))

    subject = db_get_subject(sid)
    if subject:
        old_name = subject['name']
        subject['name'] = new_name
        db_save_subject(sid, subject)
        flash(f'"{old_name}" renamed to "{new_name}".')
    return redirect(url_for('manage_subjects'))


def delete_subject_impl(
    *,
    sid,
    get_active_sessions,
    flash,
    redirect,
    url_for,
    db_get_subject,
    db_delete_subject,
    get_db,
    json_module,
):
    for session_obj in get_active_sessions().values():
        if session_obj.get('subject_id') == sid:
            flash('Cannot delete - a live session is using this subject.')
            return redirect(url_for('manage_subjects'))

    subject = db_get_subject(sid)
    if subject:
        db_delete_subject(sid)
        with get_db() as conn:
            rows = conn.execute("SELECT username, my_subjects_json FROM users").fetchall()

        for row in rows:
            my_subjects = json_module.loads(row['my_subjects_json'] or '[]')
            new_subjects = [item for item in my_subjects if item.get('subject_id') != sid]
            if len(new_subjects) != len(my_subjects):
                with get_db() as conn:
                    conn.execute(
                        "UPDATE users SET my_subjects_json=? WHERE username=?",
                        (json_module.dumps(new_subjects), row['username']),
                    )

        flash(f'Subject "{subject["name"]}" deleted.')
    return redirect(url_for('manage_subjects'))
