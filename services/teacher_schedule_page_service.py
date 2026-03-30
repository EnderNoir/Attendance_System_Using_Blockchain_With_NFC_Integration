def teacher_schedule_page_impl(*, username, db_get_schedules_for_teacher, db_get_all_subjects, render_template, dow_names):
    """Render teacher schedule page with subject metadata and day names."""
    schedules = db_get_schedules_for_teacher(username)
    subjects = db_get_all_subjects()
    return render_template(
        'teacher_schedule.html',
        schedules=schedules,
        subjects=subjects,
        dow_list=dow_names,
    )
