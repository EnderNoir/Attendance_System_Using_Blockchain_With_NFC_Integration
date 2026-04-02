def upload_photo_impl(*, request, jsonify, os_module, upload_folder, db_save_photo):
    person_id = request.form.get('person_id', '').strip()
    if not person_id or 'photo' not in request.files:
        return jsonify({'error': 'Missing data'}), 400

    uploaded = request.files['photo']
    if not uploaded or uploaded.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = os_module.path.splitext(uploaded.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'error': 'Only image files allowed'}), 400

    filename = f"photo_{person_id.replace(' ', '_')}{ext}"
    uploaded.save(os_module.path.join(upload_folder, filename))
    db_save_photo(person_id, filename)
    return jsonify({'ok': True, 'filename': filename, 'url': f'/static/uploads/{filename}'})


def get_my_photo_impl(*, username, db_get_photo, jsonify):
    photo = db_get_photo(username)
    if photo:
        return jsonify({'url': f'/static/uploads/{photo}'})
    return jsonify({'url': None})


def update_profile_impl(
    *,
    username,
    request,
    session_obj,
    db_get_user,
    db_save_user,
    db_delete_user,
    db_get_photo,
    db_save_photo,
    db_delete_photo,
    hash_password,
    validate_password_otp_fn,
    send_password_changed_email_fn,
    jsonify,
):
    user = db_get_user(username)
    if not user:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    if data.get('full_name'):
        user['full_name'] = data['full_name'].strip()
        session_obj['full_name'] = user['full_name']
    if data.get('email'):
        user['email'] = data['email'].strip()
    password_updated = False
    password_val = (data.get('password') or '')
    if password_val:
        if len(password_val) < 6:
            return jsonify({'error': 'Password must be at least 6 characters.'}), 400
        otp_code = (data.get('password_otp') or '').strip()
        if not callable(validate_password_otp_fn):
            return jsonify({'error': 'Password OTP validation is unavailable.'}), 500
        otp_ok, otp_err = validate_password_otp_fn(otp_code)
        if not otp_ok:
            return jsonify({'error': otp_err or 'Invalid OTP code.'}), 403
        user['password'] = hash_password(password_val)
        password_updated = True

    new_username = (data.get('new_username') or '').strip().lower()
    if new_username and new_username != username:
        if db_get_user(new_username):
            return jsonify({'error': 'Username already taken'}), 409

        db_save_user(new_username, user)
        db_delete_user(username)
        try:
            photo = db_get_photo(username)
            if photo:
                db_save_photo(new_username, photo)
                db_delete_photo(username)
        except Exception:
            pass

        session_obj['username'] = new_username
        username = new_username
    else:
        db_save_user(username, user)

    if password_updated and callable(send_password_changed_email_fn):
        try:
            send_password_changed_email_fn(
                full_name=user.get('full_name', username),
                email=user.get('email', ''),
                username=username,
                role=user.get('role', ''),
            )
        except Exception:
            pass

    return jsonify({'ok': True, 'full_name': user['full_name'], 'username': session_obj.get('username', username)})


def delete_photo_impl(*, person_id, db_get_photo, upload_folder, db_delete_photo, os_module, jsonify):
    existing = db_get_photo(person_id)
    if existing:
        old_file = os_module.path.join(upload_folder, existing)
        if os_module.path.exists(old_file):
            try:
                os_module.remove(old_file)
            except Exception:
                pass
        db_delete_photo(person_id)
    return jsonify({'ok': True})
