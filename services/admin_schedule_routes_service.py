def admin_schedules_page_impl(
    *,
    db_get_all_schedules,
    db_get_all_subjects,
    db_get_all_users,
    get_all_section_keys,
    session_obj,
    render_template,
    dow_names,
    admin_roles,
):
    all_schedules = db_get_all_schedules()
    subjects = db_get_all_subjects()
    users = db_get_all_users()
    teachers = {
        username: user
        for username, user in users.items()
        if user.get('role') == 'teacher' and user.get('status') == 'approved'
    }
    sections = get_all_section_keys()
    current_role = session_obj.get('role', '')
    return render_template(
        'admin_schedules.html',
        schedules=all_schedules,
        subjects=subjects,
        teachers=teachers,
        sections=sections,
        dow_names=dow_names,
        is_super_admin=(current_role == 'super_admin'),
        can_manage_schedules=(current_role in admin_roles),
    )


def admin_schedule_create_impl(
    *,
    request,
    flash,
    redirect,
    url_for,
    db_get_subject,
    db_get_user,
    normalize_section_key,
    time_mins,
    db_save_schedule,
    session_obj,
):
    try:
        subject_id = request.form.get('subject_id', '')
        subject = db_get_subject(subject_id)
        if not subject:
            flash('Subject not found.', 'danger')
            return redirect(url_for('admin_schedules'))

        teacher_username = request.form.get('teacher_username', '')
        teacher = db_get_user(teacher_username)
        if not teacher:
            flash('Instructor not found.', 'danger')
            return redirect(url_for('admin_schedules'))

        program = request.form.get('program', '').strip()
        year_level = request.form.get('year_level', '').strip()
        section_letter = (
            request.form.get('section', '')
            or request.form.get('section_letter', '')
        ).strip()
        if program and year_level and section_letter:
            section_key = normalize_section_key(f"{program}|{year_level}|{section_letter}")
        else:
            section_key = normalize_section_key(request.form.get('section_key', ''))

        day_of_week = int(request.form.get('day_of_week', 0))
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        grace_minutes = int(request.form.get('grace_minutes', 15))

        if not section_key or not start_time or not end_time:
            flash('Section, start time, and end time are required.', 'danger')
            return redirect(url_for('admin_schedules'))

        start_mins = time_mins(start_time)
        end_mins = time_mins(end_time)
        if start_mins is None or end_mins is None or end_mins <= start_mins:
            flash('End time must be later than start time.', 'danger')
            return redirect(url_for('admin_schedules'))

        db_save_schedule(
            {
                'section_key': section_key,
                'subject_id': subject_id,
                'subject_name': subject['name'],
                'course_code': subject.get('course_code', ''),
                'teacher_username': teacher_username,
                'teacher_name': teacher.get('full_name', teacher_username),
                'day_of_week': day_of_week,
                'start_time': start_time,
                'end_time': end_time,
                'grace_minutes': grace_minutes,
                'created_by': session_obj.get('username', ''),
            }
        )
        flash('Schedule created successfully.', 'success')
    except Exception as exc:
        flash(f'Error creating schedule: {exc}', 'danger')

    return redirect(url_for('admin_schedules'))


def admin_schedule_edit_impl(
    *,
    schedule_id,
    request,
    flash,
    redirect,
    url_for,
    db_get_schedule,
    datetime_cls,
    db_get_subject,
    db_get_user,
    normalize_section_key,
    time_mins,
    db_save_schedule,
):
    try:
        schedule = db_get_schedule(schedule_id)
        if not schedule:
            flash('Schedule not found.', 'danger')
            return redirect(url_for('admin_schedules'))

        today_dow = datetime_cls.now().weekday()
        if int(schedule['day_of_week']) == today_dow:
            current_time = datetime_cls.now().strftime('%H:%M')
            start_time = schedule['start_time']
            try:
                now_dt = datetime_cls.strptime(current_time, '%H:%M')
                start_dt = datetime_cls.strptime(start_time, '%H:%M')
                time_diff = (start_dt - now_dt).total_seconds() / 60
                if 0 <= time_diff <= 5:
                    flash(
                        'Cannot edit schedule within 5 minutes before start time. Delete and recreate if changes are needed.',
                        'warning',
                    )
                    return redirect(url_for('admin_schedules'))
            except Exception:
                pass

        subject_id = request.form.get('subject_id', schedule['subject_id'])
        subject = db_get_subject(subject_id)
        teacher_username = request.form.get('teacher_username', schedule['teacher_username'])
        teacher = db_get_user(teacher_username)

        program = request.form.get('program', '').strip()
        year_level = request.form.get('year_level', '').strip()
        section_letter = (
            request.form.get('section', '')
            or request.form.get('section_letter', '')
        ).strip()
        if program and year_level and section_letter:
            new_section = normalize_section_key(f"{program}|{year_level}|{section_letter}")
        else:
            new_section = normalize_section_key(
                request.form.get('section_key', schedule['section_key'])
            )

        new_start_time = request.form.get('start_time', schedule['start_time'])
        new_end_time = request.form.get('end_time', schedule['end_time'])
        start_mins = time_mins(new_start_time)
        end_mins = time_mins(new_end_time)
        if start_mins is None or end_mins is None or end_mins <= start_mins:
            flash('End time must be later than start time.', 'danger')
            return redirect(url_for('admin_schedules'))

        db_save_schedule(
            {
                'schedule_id': schedule_id,
                'section_key': new_section,
                'subject_id': subject_id,
                'subject_name': subject['name'] if subject else schedule['subject_name'],
                'course_code': subject.get('course_code', '') if subject else schedule['course_code'],
                'teacher_username': teacher_username,
                'teacher_name': teacher.get('full_name', teacher_username) if teacher else schedule['teacher_name'],
                'day_of_week': int(request.form.get('day_of_week', schedule['day_of_week'])),
                'start_time': new_start_time,
                'end_time': new_end_time,
                'grace_minutes': int(request.form.get('grace_minutes', schedule['grace_minutes'])),
                'created_by': schedule['created_by'],
            }
        )
        flash('Schedule updated.', 'success')
    except Exception as exc:
        flash(f'Error updating schedule: {exc}', 'danger')

    return redirect(url_for('admin_schedules'))


def admin_schedule_delete_impl(*, schedule_id, db_delete_schedule, flash, redirect, url_for):
    db_delete_schedule(schedule_id)
    flash('Schedule removed.', 'success')
    return redirect(url_for('admin_schedules'))


def api_schedules_today_impl(*, session_obj, get_todays_schedules, jsonify, dow_names):
    username = session_obj.get('username', '')
    schedules = get_todays_schedules(username)
    return jsonify({'schedules': schedules, 'dow_names': dow_names})


def api_schedules_search_impl(*, request, db_get_all_users, db_get_all_subjects, jsonify):
    query = request.args.get('q', '').strip().lower()

    users = db_get_all_users()
    teacher_results = []
    for username, user in users.items():
        if user.get('role') not in ('teacher', 'admin', 'super_admin'):
            continue
        name = user.get('full_name', username)
        if not query or query in name.lower() or query in username.lower():
            teacher_results.append(
                {'value': username, 'label': name, 'type': user.get('role', 'teacher')}
            )

    subjects = db_get_all_subjects()
    subject_results = []
    for subject_id, subject in subjects.items():
        label = subject.get('name', '')
        code = subject.get('course_code', '')
        if not query or query in label.lower() or query in code.lower():
            subject_results.append({'value': subject_id, 'code': code, 'label': label})

    return jsonify({'teachers': teacher_results[:20], 'subjects': subject_results[:20]})


def api_active_sessions_info_impl(
    *,
    get_active_sessions,
    session_obj,
    admin_roles,
    is_my_session,
    normalize_section_key,
    jsonify,
):
    active = get_active_sessions()
    current_role = session_obj.get('role', '')
    output = {}
    for session_id, session_data in active.items():
        if current_role not in admin_roles and not is_my_session(session_data):
            continue
        output[session_id] = {
            'sess_id': session_id,
            'schedule_id': session_data.get('schedule_id') or '',
            'subject_id': session_data.get('subject_id', ''),
            'section_key': normalize_section_key(session_data.get('section_key', '')),
            'teacher_username': session_data.get(
                'teacher_username', session_data.get('teacher', '')
            ),
            'teacher_name': session_data.get('teacher_name', ''),
            'is_active': not bool(session_data.get('ended_at')),
        }

    return jsonify(output)
