def api_schedules_upcoming_impl(*, username, now_dt, db_get_schedules_for_teacher, jsonify, timedelta):
    """Build upcoming schedules payload for the current teacher (5-minute lead time)."""
    today_dow = now_dt.weekday()
    target_time = (now_dt + timedelta(minutes=5)).strftime('%H:%M')

    schedules = db_get_schedules_for_teacher(username)
    upcoming = [
        s for s in schedules
        if s['day_of_week'] == today_dow and s['start_time'] == target_time
    ]

    return jsonify({'upcoming': upcoming})
