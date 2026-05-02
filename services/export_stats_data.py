from datetime import datetime
import calendar as _cal


def build_stats_export_dataset(
    *,
    period,
    f_section,
    f_year_lvl,
    f_subject,
    f_instr,
    f_class_type,
    f_month,
    f_year_num,
    f_program,
    f_sec_ltr,
    f_tod,
    f_semester=None,
    role,
    username,
    now,
    load_sessions_fn,
    db_get_all_students_fn,
    db_get_override_fn,
    normalize_section_key_fn,
    build_student_section_key_fn,
    fmt_time_fn,
    db_get_session_attendance_fn,
    get_db_fn,
):
    if period == 'today':
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        period_label = now.strftime('Today - %B %d, %Y')
    elif period == 'month':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        mo = int(f_month) if f_month and f_month.isdigit() else now.month
        start_dt = datetime(yr, mo, 1)
        end_dt = datetime(yr, mo, _cal.monthrange(yr, mo)[1], 23, 59, 59)
        period_label = start_dt.strftime('%B %Y')
    elif period == 'year':
        yr = int(f_year_num) if f_year_num and f_year_num.isdigit() else now.year
        start_dt = datetime(yr, 1, 1)
        end_dt = datetime(yr, 12, 31, 23, 59, 59)
        period_label = str(yr)
    else:
        start_dt = datetime(2000, 1, 1)
        end_dt = None
        period_label = 'All Time'

    all_sess = load_sessions_fn()
    all_stud = db_get_all_students_fn()
    for _st in all_stud:
        _ov = db_get_override_fn(_st['nfcId'])
        if _ov.get('course'):
            _st['course'] = _ov['course']
        if _ov.get('year_level'):
            _st['year_level'] = _ov['year_level']
        if _ov.get('section'):
            _st['section'] = _ov['section'].upper()
        if _ov.get('full_name'):
            _st['name'] = _ov['full_name']
        if _ov.get('student_id'):
            _st['student_id'] = _ov['student_id']
        _st['section'] = (_st.get('section') or '').strip().upper()

    filtered = {}
    f_section_norm = normalize_section_key_fn(f_section) if f_section else ''
    for sid, s in all_sess.items():
        if not s.get('started_at'):
            continue
        try:
            sess_dt = datetime.strptime(s['started_at'], '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue
        if sess_dt < start_dt:
            continue
        if end_dt and sess_dt > end_dt:
            continue
        if role == 'teacher' and s.get('teacher') != username:
            continue
        sk = s.get('section_key', '')
        sk_parts = sk.split('|')
        if f_section_norm and normalize_section_key_fn(sk) != f_section_norm:
            continue
        if f_program and (len(sk_parts) < 1 or sk_parts[0] != f_program):
            continue
        if f_year_lvl and (len(sk_parts) < 2 or sk_parts[1] != f_year_lvl):
            continue
        if f_sec_ltr and (len(sk_parts) < 3 or sk_parts[2] != f_sec_ltr):
            continue
        if f_subject and s.get('subject_name', '') != f_subject:
            continue
        if f_instr and s.get('teacher_name', '') != f_instr:
            continue
        class_type_norm = str(s.get('class_type', 'lecture')).strip().lower()
        if f_class_type in ('lecture', 'laboratory', 'school_event') and class_type_norm != f_class_type:
            continue
        if f_tod:
            if ':' in f_tod:
                if s.get('time_slot', '') != f_tod:
                    continue
            else:
                try:
                    h = sess_dt.hour
                    if f_tod == 'morning' and h >= 12:
                        continue
                    if f_tod == 'afternoon' and h < 12:
                        continue
                except Exception:
                    pass
        if f_semester and (s.get('semester') or '').lower() != f_semester.lower():
            continue
        filtered[sid] = s

    af = []
    if f_program:
        af.append('Program: ' + f_program)
    if f_year_lvl:
        af.append('Year: ' + f_year_lvl)
    if f_sec_ltr:
        af.append('Section: ' + f_sec_ltr)
    if f_section:
        af.append('Section: ' + f_section.replace('|', ' · '))
    if f_subject:
        af.append('Subject: ' + f_subject)
    if f_instr:
        af.append('Instructor: ' + f_instr)
    if f_class_type in ('lecture', 'laboratory', 'school_event'):
        af.append('Class Type: ' + ('School Event' if f_class_type == 'school_event' else f_class_type.capitalize()))
    if f_tod:
        af.append('Time: ' + f_tod)
    if f_semester:
        af.append('Semester: ' + f_semester)
    filter_label = ' | '.join(af) if af else 'All data'

    donut = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
    trend = {}
    subj_d = {}
    sess_rows = []
    detail_rows = []
    by_section = {}
    by_class_type = {}
    reason_labels = {
        'sickness': 'Sickness / Illness',
        'lbm': 'LBM',
        'emergency': 'Family Emergency',
        'bereavement': 'Bereavement',
        'medical': 'Medical Appointment',
        'accident': 'Accident / Injury',
        'official': 'Official School Business',
        'weather': 'Extreme Weather / Calamity',
        'transport': 'Transportation Problem',
        'others': 'Others',
    }

    for sid, s in sorted(filtered.items(), key=lambda x: x[1].get('started_at', '')):
        class_type_norm = str(s.get('class_type', 'lecture')).strip().lower()
        if class_type_norm not in ('lecture', 'laboratory', 'school_event'):
            class_type_norm = 'lecture'
        sk = normalize_section_key_fn(s.get('section_key', ''))
        enrolled_official = [st for st in all_stud if build_student_section_key_fn(st) == sk]
        
        att_logs = {lg['nfc_id']: lg for lg in db_get_session_attendance_fn(sid)}
        
        # Combined student set: official enrolled + any irregular student who tapped
        all_session_stud_ids = {st['nfcId'] for st in enrolled_official} | set(att_logs.keys())
        
        # Smart Absent Logic: Only count official students as "Absent" if they were already registered when the session started.
        # This prevents new students from appearing absent in history.
        official_ids_for_absent = {
            st['nfcId'] for st in enrolled_official 
            if (st.get('created_at') or '9999') <= s.get('started_at', '')
        }
        
        pre = set(s.get('present', []))
        late = set(s.get('late', []))
        exc = set(s.get('excused', []))
        
        # Recalculate counts to include irregular students
        # Absent = (Eligible Official IDs + Irregular Taps) - (Present + Late + Excused)
        # Actually, Irregular Taps are never absent by definition.
        # So Absent = Eligible Official IDs - (Present + Late + Excused)
        abs_ = official_ids_for_absent - pre - late - exc
        
        # All IDs involved in this specific session (for total enrollment stat)
        session_total_ids = official_ids_for_absent | set(att_logs.keys())
        
        cnt = {
            'enrolled': len(session_total_ids),
            'present': len(pre - late),
            'late': len(late),
            'absent': len(abs_),
            'excused': len(exc),
        }
        for k in ('present', 'late', 'absent', 'excused'):
            donut[k.capitalize()] += cnt[k]
        code = s.get('course_code', '')
        subj_lbl = f"[{code}] {s.get('subject_name', '')}" if code else s.get('subject_name', '')
        rate = round((cnt['present'] + cnt['late']) / cnt['enrolled'] * 100, 1) if cnt['enrolled'] else 0
        date_key = s['started_at'][:10]
        if date_key not in trend:
            trend[date_key] = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0}
        for k in ('present', 'late', 'absent', 'excused'):
            trend[date_key][k] += cnt[k]
        sn = s.get('subject_name', 'Unknown')
        if sn not in subj_d:
            subj_d[sn] = {'code': code, 'present': 0, 'late': 0, 'absent': 0, 'excused': 0}
        for k in ('present', 'late', 'absent', 'excused'):
            subj_d[sn][k] += cnt[k]
        if sk not in by_section:
            by_section[sk] = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'enrolled': 0}
        for k in ('present', 'late', 'absent', 'excused', 'enrolled'):
            by_section[sk][k] += cnt[k]
        
        ct_key = class_type_norm.title()
        if ct_key not in by_class_type:
            by_class_type[ct_key] = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0}
        for k in ('present', 'late', 'absent', 'excused'):
            by_class_type[ct_key][k] += cnt[k]

        sess_rows.append(
            [
                subj_lbl,
                class_type_norm.capitalize(),
                fmt_time_fn(s['started_at']),
                sk.replace('|', ' · '),
                s.get('teacher_name', ''),
                s.get('time_slot', ''),
                cnt['enrolled'],
                cnt['present'],
                cnt['late'],
                cnt['absent'],
                cnt['excused'],
                rate,
            ]
        )
        excuse_details = {}
        with get_db_fn() as _conn:
            excuses = _conn.execute(
                "SELECT nfc_id, reason_type, reason_detail, attachment_file FROM excuse_requests WHERE sess_id=? AND status='approved'",
                (sid,),
            ).fetchall()
            for exc_row in excuses:
                excuse_details[exc_row['nfc_id']] = {
                    'reason': exc_row['reason_type'],
                    'reason_detail': exc_row['reason_detail'],
                    'attachment_file': exc_row['attachment_file'],
                }

        # Map all students for quick lookup
        stud_db_map = {st['nfcId']: st for st in all_stud}
        
        for nid in sorted(all_session_stud_ids):
            st = stud_db_map.get(nid)
            lg = att_logs.get(nid, {})
            
            # If student not in DB (rare), use log data
            st_name = st['name'] if st else lg.get('student_name', 'Unknown')
            st_id = st.get('student_id', '') if st else lg.get('student_id', '')
            st_course = st.get('course', '') if st else ''
            st_year = st.get('year_level', '') if st else ''
            st_sec = st.get('section', '') if st else ''
            st_enrollment = st.get('enrollment_status', 'Regular') if st else 'Irregular'
            
            if nid in exc:
                status = 'Excused'
            elif nid in late:
                status = 'Late'
            elif nid in pre:
                status = 'Present'
            else:
                status = 'Absent'
            
            excuse_info = excuse_details.get(nid, {})
            excuse_reason = ''
            if excuse_info.get('reason'):
                excuse_reason = reason_labels.get(excuse_info['reason'], excuse_info['reason'])
                if excuse_info.get('reason_detail'):
                    excuse_reason += f" ({excuse_info['reason_detail']})"
            
            detail_rows.append(
                [
                    st_name,
                    st_id,
                    nid,
                    st_course,
                    st_year,
                    st_sec,
                    st_enrollment,
                    subj_lbl,
                    class_type_norm.capitalize(),
                    fmt_time_fn(s['started_at']),
                    s.get('time_slot', ''),
                    s.get('teacher_name', ''),
                    status,
                    lg.get('tx_hash', ''),
                    lg.get('block_number', ''),
                    excuse_reason,
                    'Yes' if excuse_info.get('attachment_file') else '',
                ]
            )

    return {
        'period_label': period_label,
        'filter_label': filter_label,
        'donut': donut,
        'trend': trend,
        'subj_d': subj_d,
        'sess_rows': sess_rows,
        'detail_rows': detail_rows,
        'by_section': by_section,
        'by_class_type': by_class_type,
    }
