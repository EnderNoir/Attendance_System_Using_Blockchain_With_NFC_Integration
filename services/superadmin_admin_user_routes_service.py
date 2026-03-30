def superadmin_users_impl(*, db_get_all_users, admin_roles, render_template):
    users = db_get_all_users()
    super_admin_count = sum(1 for u in users.values() if u.get('role') == 'super_admin')
    return render_template(
        'superadmin_users.html',
        users=users,
        ADMIN_ROLES=admin_roles,
        super_admin_count=super_admin_count,
    )


def superadmin_create_user_impl(
    *,
    request,
    flash,
    redirect,
    url_for,
    get_db,
    db_get_user,
    db_save_user,
    hash_password,
    datetime_now,
    render_template,
):
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        fullname = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'teacher')
        password = request.form.get('password', '').strip()

        if not username or not fullname or not password:
            flash('Username, full name, and password are required.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        if role not in {'teacher', 'admin', 'super_admin'}:
            flash('Invalid role.', 'danger')
            return redirect(url_for('superadmin_create_user'))

        if role == 'super_admin':
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT * FROM users WHERE role='super_admin'"
                ).fetchone()
            if existing:
                flash('A Super Admin already exists. Only one Super Admin is allowed.', 'danger')
                return redirect(url_for('superadmin_create_user'))

        if db_get_user(username):
            flash(f'Username "{username}" is already taken.', 'danger')
            return redirect(url_for('superadmin_create_user'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('superadmin_create_user'))

        db_save_user(
            username,
            {
                'username': username,
                'password': hash_password(password),
                'role': role,
                'full_name': fullname,
                'email': email,
                'status': 'approved',
                'sections': [],
                'my_subjects': [],
                'created_at': datetime_now().strftime('%Y-%m-%d %H:%M:%S'),
            },
        )
        flash(f'Account "{username}" ({role}) created successfully.', 'success')
        return redirect(url_for('superadmin_users'))

    with get_db() as conn:
        super_admin_exists = (
            conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE role='super_admin'"
            ).fetchone()['cnt']
            > 0
        )
    return render_template('superadmin_create_user.html', show_super_admin=not super_admin_exists)


def superadmin_promote_impl(
    *,
    username,
    request,
    flash,
    redirect,
    url_for,
    db_get_user,
    get_db,
    db_save_user,
):
    user = db_get_user(username)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('superadmin_users'))

    new_role = request.form.get('role', 'teacher')
    if new_role not in {'teacher', 'admin', 'super_admin'}:
        flash('Invalid role.', 'danger')
        return redirect(url_for('superadmin_users'))

    if new_role == 'super_admin' and user.get('role') != 'super_admin':
        with get_db() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE role='super_admin'"
            ).fetchone()['cnt']
        if existing >= 1:
            flash('A Super Admin already exists. Only one Super Admin is allowed.', 'danger')
            return redirect(url_for('superadmin_users'))

    user['role'] = new_role
    user['password'] = user.get('password', '')
    db_save_user(username, user)
    flash(f'"{username}" role changed to {new_role}.', 'success')
    return redirect(url_for('superadmin_users'))


def admin_create_instructor_impl(
    *,
    request,
    flash,
    redirect,
    url_for,
    db_get_user,
    db_save_user,
    hash_password,
    datetime_now,
    render_template,
):
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        fullname = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not fullname or not password:
            flash('Username, full name, and password are required.', 'danger')
            return redirect(url_for('admin_create_instructor'))
        if db_get_user(username):
            flash(f'Username "{username}" is already taken.', 'danger')
            return redirect(url_for('admin_create_instructor'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('admin_create_instructor'))

        db_save_user(
            username,
            {
                'username': username,
                'password': hash_password(password),
                'role': 'teacher',
                'full_name': fullname,
                'email': email,
                'status': 'approved',
                'sections': [],
                'my_subjects': [],
                'created_at': datetime_now().strftime('%Y-%m-%d %H:%M:%S'),
            },
        )
        flash(f'Instructor account "{username}" created successfully.', 'success')
        return redirect(url_for('manage_users'))

    return render_template('admin_create_instructor.html')
