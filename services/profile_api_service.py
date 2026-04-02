def api_my_profile_impl(*, username, db_get_user, db_get_photo, jsonify):
    """Return profile payload for the currently authenticated user."""
    user = db_get_user(username)
    if not user:
        return jsonify({'error': 'Not found'}), 404

    return jsonify({
        'username': user.get('username', ''),
        'full_name': user.get('full_name', ''),
        'email': user.get('email', ''),
        'role': user.get('role', ''),
        'status': user.get('status', ''),
        'created': user.get('created_at', ''),
        'sections': user.get('sections', []),
        'photo': db_get_photo(username) or '',
    })
