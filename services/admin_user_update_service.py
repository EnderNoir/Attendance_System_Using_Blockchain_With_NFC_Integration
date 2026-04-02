def update_student_impl(*, request, datetime_now, get_db, db_save_override, jsonify):
    data = request.get_json()
    nfc_id = data.get('nfc_id', '').strip()
    if not nfc_id:
        return jsonify({'error': 'Missing nfc_id'}), 400

    fields = [
        'full_name', 'student_id', 'email', 'contact', 'adviser', 'major',
        'semester', 'school_year', 'date_registered', 'course', 'year_level', 'section'
    ]
    update_data = {f: (data.get(f) or '').strip() for f in fields}
    if update_data.get('section'):
        update_data['section'] = update_data['section'].strip().upper()

    now = datetime_now().strftime('%Y-%m-%d %H:%M:%S')
    set_parts = []
    params = []
    db_col_map = {
        'full_name': 'full_name',
        'student_id': 'student_id',
        'email': 'email',
        'contact': 'contact',
        'adviser': 'adviser',
        'major': 'major',
        'semester': 'semester',
        'school_year': 'school_year',
        'date_registered': 'date_registered',
        'course': 'program',
        'year_level': 'year_level',
        'section': 'section',
    }

    for field, db_col in db_col_map.items():
        val = update_data.get(field, '')
        if val:
            set_parts.append(f"{db_col}=?")
            params.append(val)

    if set_parts:
        set_parts.append('updated_at=?')
        params.append(now)
        params.append(nfc_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE students SET {', '.join(set_parts)} WHERE nfc_id=?",
                params,
            )

    override_data = {f: update_data[f] for f in fields if update_data.get(f)}
    if override_data:
        db_save_override(nfc_id, override_data)

    return jsonify({'ok': True})


def update_faculty_impl(
    *,
    request,
    session_obj,
    db_get_user,
    db_save_user,
    db_delete_user,
    db_rename_photo_key,
    normalize_section_key,
    hash_password,
    jsonify,
):
    data = request.get_json()
    username = data.get('username', '').strip()
    user = db_get_user(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    requester_role = session_obj.get('role', '')
    if requester_role != 'super_admin':
        return jsonify({'error': 'Only Super Admin can edit user accounts.'}), 403

    if data.get('full_name'):
        user['full_name'] = data['full_name'].strip()
    if data.get('email') is not None:
        user['email'] = data['email'].strip()

    new_role = data.get('role', '')
    if new_role:
        if new_role in ('teacher', 'admin', 'super_admin'):
            user['role'] = new_role
        else:
            return jsonify({'error': 'Invalid role.'}), 400

    if data.get('status') in ('approved', 'pending', 'rejected'):
        user['status'] = data['status']

    if 'sections' in data and isinstance(data['sections'], list):
        user['sections'] = [normalize_section_key(s) for s in data['sections']]

    new_pw = (data.get('new_password') or '').strip()
    if new_pw:
        if len(new_pw) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user['password'] = hash_password(new_pw)

    new_username = (data.get('new_username') or '').strip().lower()
    if new_username and new_username != username:
        if db_get_user(new_username):
            return jsonify({'error': f'Username "{new_username}" is already taken'}), 409
        user['username'] = new_username
        db_save_user(new_username, user)
        db_delete_user(username)
        db_rename_photo_key(username, new_username)
    else:
        db_save_user(username, user)

    return jsonify({'ok': True})
