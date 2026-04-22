def _format_sem(sec_key, raw_sem):
    parts = str(sec_key or '').split('|')
    year = parts[1].strip() if len(parts) >= 2 else ''
    s_map = {'First': '1st Sem', 'Second': '2nd Sem', 'Summer': 'Summer'}
    sem = s_map.get(str(raw_sem or '').strip(), str(raw_sem or '').strip())
    if not sem: sem = '1st Sem'
    if year: return f"{year} {sem}".strip()
    return sem

def student_sessions_api_impl(
    *,
    nfc_id,
    get_db,
    excuse_pk_column,
    url_for,
    get_all_students,
    build_student_section_key,
    row_to_dict,
    normalize_section_key,
    jsonify,
):
    with get_db() as conn:
        log_rows = conn.execute(
            "SELECT al.nfc_id, al.status, al.tx_hash, al.block_number, "
            "al.tap_time, al.excuse_note, al.excuse_request_id, "
            "s.sess_id, s.subject_name, s.course_code, s.section_key, "
            "s.teacher_name, s.class_type, s.time_slot, s.started_at, s.semester "
            "FROM attendance_logs al "
            "JOIN sessions s ON al.sess_id = s.sess_id "
            "WHERE al.nfc_id = ? "
            "ORDER BY s.started_at DESC",
            (nfc_id,)
        ).fetchall()

    result = []
    seen_sessions = set()
    for row in log_rows:
        seen_sessions.add(row['sess_id'])
        attachment_url = ''
        if (row['status'] or '').lower() == 'excused':
            resolved_excuse_id = row['excuse_request_id'] if 'excuse_request_id' in row.keys() else None
            if not resolved_excuse_id:
                try:
                    with get_db() as conn:
                        pk_col = excuse_pk_column(conn)
                        ex_row = conn.execute(
                            f"SELECT {pk_col} AS id "
                            "FROM excuse_requests "
                            "WHERE sess_id=? AND nfc_id=? AND status='approved' "
                            "ORDER BY COALESCE(created_at, submitted_at, '') DESC LIMIT 1",
                            (row['sess_id'], row['nfc_id'])
                        ).fetchone()
                    if ex_row:
                        resolved_excuse_id = ex_row['id']
                except Exception:
                    resolved_excuse_id = None
            if resolved_excuse_id:
                attachment_url = url_for('admin_excuse_attachment', excuse_id=resolved_excuse_id)

        result.append({
            'subject_name': row['subject_name'] or '',
            'course_code': row['course_code'] or '',
            'teacher_name': row['teacher_name'] or '',
            'class_type': (row['class_type'] or 'lecture').lower(),
            'section_key': row['section_key'] or '',
            'time_slot': row['time_slot'] or '',
            'date': (row['started_at'] or '')[:10],
            'started_at': row['started_at'] or '',
            'status': (row['status'] or 'absent').lower(),
            'tap_time': row['tap_time'] or '',
            'tx_hash': row['tx_hash'] or '',
            'block': str(row['block_number']) if row['block_number'] else '',
            'excuse_note': row['excuse_note'] or '',
            'attachment_url': attachment_url,
            'semester': _format_sem(row['section_key'], row['semester']),
        })

    if not result:
        all_students = get_all_students()
        student = next((x for x in all_students if x['nfcId'] == nfc_id), None)
        student_section = build_student_section_key(student) if student else ''

        with get_db() as conn:
            sess_rows = conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY started_at DESC"
            ).fetchall()

        for row in sess_rows:
            sess = row_to_dict(row)
            section_key = normalize_section_key(sess.get('section_key', ''))
            if student_section and section_key != student_section:
                continue
            if sess.get('sess_id') in seen_sessions:
                continue

            if nfc_id in sess.get('excused', []):
                status = 'excused'
            elif nfc_id in sess.get('late', []):
                status = 'late'
            elif nfc_id in sess.get('present', []):
                status = 'present'
            elif student_section == section_key:
                status = 'absent'
            else:
                continue

            tx_info = sess.get('tx_hashes', {}).get(nfc_id, {})
            result.append({
                'subject_name': sess.get('subject_name', ''),
                'course_code': sess.get('course_code', ''),
                'teacher_name': sess.get('teacher_name', ''),
                'class_type': str(sess.get('class_type', 'lecture')).strip().lower(),
                'section_key': sess.get('section_key', ''),
                'time_slot': sess.get('time_slot', ''),
                'date': (sess.get('started_at', '') or '')[:10],
                'started_at': sess.get('started_at', ''),
                'status': status,
                'tap_time': '',
                'tx_hash': tx_info.get('tx_hash', ''),
                'block': str(tx_info.get('block', '')),
                'excuse_note': '',
                'attachment_url': '',
                'semester': _format_sem(sess.get('section_key'), sess.get('semester')),
            })

    result.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(result)
