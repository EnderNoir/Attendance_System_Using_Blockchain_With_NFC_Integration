from datetime import datetime
import io
import traceback
import json

from flask import Response, flash, redirect, request, url_for


def _parse_dt(value):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None

def _format_sem(sec_key, raw_sem):
    parts = str(sec_key or '').split('|')
    year = parts[1].strip() if len(parts) >= 2 else ''
    s_map = {'First': '1st Sem', 'Second': '2nd Sem', 'Summer': 'Summer'}
    sem = s_map.get(str(raw_sem or '').strip(), str(raw_sem or '').strip())
    if not sem: sem = '1st Sem'
    if year: return f"{year} {sem}".strip()
    return sem


def _fmt_date_dash(value):
    dt = _parse_dt(value)
    if not dt:
        return '—'
    return dt.strftime('%B-%d-%Y')


def _fmt_date_colon(value):
    dt = _parse_dt(value)
    if not dt:
        return '—'
    return dt.strftime('%B:%d:%Y')


def _fmt_time_hms_ampm(value):
    dt = _parse_dt(value)
    if not dt:
        return '—'
    return dt.strftime('%I:%M %p').lstrip('0')


def _normalize_time_token(value, with_seconds=False):
    if value is None:
        return '—'
    raw = str(value).strip()
    if not raw:
        return '—'
    if 'AM' in raw.upper() or 'PM' in raw.upper():
        # Remove seconds and leading zeros if present
        import re
        raw = re.sub(r'^0+', '', raw)
        raw = re.sub(r':00\s+(AM|PM)', r' \1', raw, flags=re.I)
        return raw.upper()
    m = None
    try:
        import re
        m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', raw)
    except Exception:
        m = None
    if not m:
        return raw
    h = int(m.group(1))
    mm = m.group(2)
    ss = m.group(3)
    period = 'PM' if h >= 12 else 'AM'
    hh = 12 if h % 12 == 0 else (h % 12)
    if with_seconds and ss:
        return f"{hh}:{mm}:{ss} {period}"
    return f"{hh}:{mm} {period}"


def _normalize_time_slot(value):
    if not value:
        return '—'
    raw = str(value).strip()
    if not raw:
        return '—'
    if 'AM' in raw.upper() or 'PM' in raw.upper():
        return raw.upper()
    if '–' in raw:
        parts = [p.strip() for p in raw.split('–', 1)]
    elif '-' in raw:
        parts = [p.strip() for p in raw.split('-', 1)]
    else:
        parts = [raw]
    if len(parts) == 2:
        return f"{_normalize_time_token(parts[0])} - {_normalize_time_token(parts[1])}"
    return _normalize_time_token(parts[0])


def export_student_sessions_impl(
    nfc_id,
    *,
    get_all_students_fn,
    get_db_fn,
    xl_helpers_fn,
    viewer_role,
):
    """Export one student's full attendance history with blockchain proof."""
    try:
        _ox = __import__('openpyxl')
        _ox_chart = __import__('openpyxl.chart', fromlist=['BarChart', 'PieChart', 'Reference'])
        _ox_styles = __import__('openpyxl.styles', fromlist=['Font', 'PatternFill', 'Alignment'])
        Workbook = _ox.Workbook
        BarChart = _ox_chart.BarChart
        PieChart = _ox_chart.PieChart
        Reference = _ox_chart.Reference
        XFont = _ox_styles.Font
        XFill = _ox_styles.PatternFill
        XAlign = _ox_styles.Alignment

        f_status = request.args.get('status', '').strip()
        f_subject = request.args.get('subject', '').strip()
        f_instructor = request.args.get('instructor', '').strip()
        f_year = request.args.get('year', '').strip()
        f_section = request.args.get('section', '').strip()
        f_class_type = request.args.get('class_type', '').strip().lower()
        f_semester = request.args.get('semester', '').strip()
        stud_name = request.args.get('name', 'Student').strip()
        now = datetime.now()

        all_students = get_all_students_fn()
        student = next((x for x in all_students if x['nfcId'] == nfc_id), None)

        with get_db_fn() as conn:
            log_rows = conn.execute(
                "SELECT al.*, s.subject_name, s.course_code, s.section_key, s.semester, "
                "s.teacher_name, s.class_type, s.time_slot, s.started_at, s.ended_at, "
                "st.year_level, st.section "
                "FROM attendance_logs al "
                "JOIN sessions s ON al.sess_id = s.sess_id "
                "LEFT JOIN students st ON al.nfc_id = st.nfc_id "
                "WHERE al.nfc_id=? ORDER BY s.started_at DESC",
                (nfc_id,),
            ).fetchall()
            exc_rows = conn.execute(
                "SELECT sess_id, reason_type, reason_detail, attachment_file "
                "FROM excuse_requests "
                "WHERE nfc_id=? AND status='approved'",
                (nfc_id,),
            ).fetchall()

        exc_map = {}
        for ex in exc_rows:
            exc_map[ex['sess_id']] = {
                'reason_type': ex['reason_type'] or '',
                'reason_detail': ex['reason_detail'] or '',
                'attachment_file': ex['attachment_file'] or '',
            }

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

        rows = []
        status_counts = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
        for lg in log_rows:
            status = lg['status'].capitalize()
            if f_status and status.lower() != f_status.lower():
                continue
            if f_subject and lg['subject_name'] != f_subject:
                continue
            if f_instructor and lg['teacher_name'] != f_instructor:
                continue
            if f_year and str(lg.get('year_level') or '') != f_year:
                continue
            if f_section and str(lg.get('section') or '') != f_section:
                continue

            class_type = str(lg['class_type'] or 'lecture').strip().lower()
            if f_class_type in ('lecture', 'laboratory', 'school_event') and class_type != f_class_type:
                continue
            
            # Semester filtering
            lg_sem = _format_sem(lg['section_key'], lg.get('semester'))
            if f_semester and lg_sem != f_semester:
                continue

            status_counts[status] = status_counts.get(status, 0) + 1
            ex = exc_map.get(lg['sess_id'], {})
            reason = ''
            if ex.get('reason_type'):
                reason = reason_labels.get(ex['reason_type'], ex['reason_type'])
                if ex.get('reason_detail'):
                    reason += f" ({ex['reason_detail']})"
            elif lg['excuse_note']:
                reason = lg['excuse_note']

            rows.append(
                {
                    'subject': lg['subject_name'],
                    'code': lg['course_code'] or '',
                    'class_type': class_type.capitalize(),
                    'teacher': lg['teacher_name'] or '',
                    'date_dash': _fmt_date_dash(lg['started_at'] or ''),
                    'date_colon': _fmt_date_colon(lg['started_at'] or ''),
                    'tap_time': '-' if status.lower() in ('absent', 'excused') else (_fmt_time_hms_ampm(lg['tap_time'] or '') if lg.get('tap_time') else '-'),
                    'time_slot': _normalize_time_slot(lg['time_slot'] or ''),
                    'status': status,
                    'enrollment_status': student.get('enrollment_status', 'Regular') if student else 'Regular',
                    'tx_hash': lg['tx_hash'] or '—',
                    'block': str(lg['block_number']) if lg['block_number'] else '—',
                    'excuse': reason or '—',
                    'document': ex.get('attachment_file') or '—',
                }
            )

        H = xl_helpers_fn()
        C = H['C']
        wb = Workbook()
        ws = wb.active
        ws.title = 'Attendance Log'
        prog = student.get('course', '') if student else ''
        yr = student.get('year_level', '') if student else ''
        sec = student.get('section', '') if student else ''
        sid_ = student.get('student_id', '') if student else ''
        is_admin_view = viewer_role in ('admin', 'super_admin')
        if is_admin_view:
            headers = [
                '#',
                'Course Code',
                'Subject Name',
                'Class Type',
                'Instructor Name',
                'Date',
                'Tapped Time',
                'Time Slot',
                'Transaction Number (TX)',
                'Block Number',
                'Status',
                'Enrollment Type',
                'Excused Reason',
                'Document',
            ]
            widths = [4, 12, 28, 12, 24, 16, 16, 20, 56, 12, 12, 16, 28, 22]
        else:
            headers = [
                '#',
                'Course Code',
                'Subject Name',
                'Class Type',
                'Date',
                'Tapped Time',
                'Time Slot',
                'Status',
                'Enrollment Type',
                'Excused Reason',
                'Document',
                'Transaction Number (TX)',
                'Block Number',
            ]
            widths = [4, 12, 30, 12, 16, 16, 20, 12, 16, 30, 22, 56, 12]
        subtitles = [
            'Cavite State University — DAVS Attendance Record',
            f'Student: {stud_name}  |  ID: {sid_}  |  NFC: {nfc_id}',
            f'Program: {prog}  |  Year: {yr}  |  Section: {sec}',
            f'Semester Filter: {f_semester}' if f_semester else '',
            f'Exported: {now.strftime("%B %d, %Y %I:%M %p")}',
        ]
        subtitles = [s for s in subtitles if s]
        first_data = H['title_block'](ws, f'Student Attendance Report — {stud_name}', subtitles, len(headers))
        first_data = H['stat_block'](ws, first_data, status_counts, len(headers))
        H['make_header_row'](ws, first_data, headers, widths)
        first_data += 1
        col_fmt = {}
        if is_admin_view:
            col_fmt = {9: ('tx',), 10: ('num',), 11: ('status',)}
        else:
            col_fmt = {10: ('tx',), 11: ('num',)}
        for ri, row in enumerate(rows, first_data):
            if is_admin_view:
                vals = [
                    ri - first_data + 1,
                    row['code'],
                    row['subject'],
                    row['class_type'],
                    row['teacher'],
                    row['date_dash'],
                    row['tap_time'],
                    row['time_slot'],
                    row['tx_hash'],
                    row['block'],
                    row['status'],
                    row['enrollment_status'],
                    row['excuse'],
                    row['document'],
                ]
            else:
                vals = [
                    ri - first_data + 1,
                    row['code'],
                    row['subject'],
                    row['class_type'],
                    row['date_colon'],
                    row['tap_time'],
                    row['time_slot'],
                    row['status'],
                    row['enrollment_status'],
                    row['excuse'],
                    row['document'],
                    row['tx_hash'],
                    row['block'],
                ]
            H['data_row'](
                ws,
                ri,
                vals,
                alt=(ri % 2 == 0),
                col_formats=col_fmt,
            )
        last_data = first_data + len(rows) - 1
        if is_admin_view:
            total_vals = [
                'TOTAL',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                f"{status_counts['Present']}P / {status_counts['Late']}L / {status_counts['Absent']}A / {status_counts['Excused']}E",
                '',
                '',
            ]
        else:
            total_vals = [
                'TOTAL',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
            ]
        H['totals_row'](ws, last_data + 1, total_vals, len(headers))
        ws.cell(
            row=last_data + 3,
            column=1,
            value=f'Generated by DAVS on {now.strftime("%B %d, %Y %I:%M %p")}',
        ).font = __import__('openpyxl').styles.Font(name='Calibri', size=9, italic=True, color='94A3B8')

        wc = wb.create_sheet('Charts')
        wc.sheet_view.showGridLines = False
        wc.merge_cells('A1:N1')
        wc['A1'] = f'Attendance Summary — {stud_name}'
        wc['A1'].font = XFont(name='Calibri', bold=True, size=14, color=C['gold'])
        wc['A1'].fill = XFill('solid', fgColor=C['bg'])
        wc['A1'].alignment = XAlign(horizontal='center', vertical='center')
        wc.row_dimensions[1].height = 32
        for col in range(2, 15):
            wc.cell(row=1, column=col).fill = XFill('solid', fgColor=C['bg'])
        wc.cell(row=3, column=1, value='Status').font = XFont(bold=True, size=9)
        wc.cell(row=3, column=2, value='Count').font = XFont(bold=True, size=9)
        status_order = ['Present', 'Late', 'Absent', 'Excused']
        for ri, st in enumerate(status_order, 4):
            wc.cell(row=ri, column=1, value=st)
            wc.cell(row=ri, column=2, value=status_counts.get(st, 0))
        pie = PieChart()
        pie.title = 'Attendance Status Breakdown'
        pie.style = 10
        pie.width = 14
        pie.height = 10
        pie.add_data(Reference(wc, min_col=2, min_row=4, max_row=7))
        pie.set_categories(Reference(wc, min_col=1, min_row=4, max_row=7))
        wc.add_chart(pie, 'D3')
        subj_counts = {}
        for r in rows:
            subj_counts[r['subject']] = subj_counts.get(r['subject'], 0) + 1
        wc.cell(row=3, column=9, value='Subject').font = XFont(bold=True, size=9)
        wc.cell(row=3, column=10, value='Count').font = XFont(bold=True, size=9)
        for ri2, (sn, cnt) in enumerate(sorted(subj_counts.items()), 4):
            wc.cell(row=ri2, column=9, value=sn[:30])
            wc.cell(row=ri2, column=10, value=cnt)
        if subj_counts:
            bar = BarChart()
            bar.type = 'bar'
            bar.grouping = 'clustered'
            bar.title = 'Sessions by Subject'
            bar.style = 10
            bar.width = 18
            bar.height = 10
            bar.y_axis.title = 'Count'
            cats2 = Reference(wc, min_col=9, min_row=4, max_row=3 + len(subj_counts))
            data2 = Reference(wc, min_col=10, min_row=3, max_row=3 + len(subj_counts))
            bar.add_data(data2, titles_from_data=True)
            bar.set_categories(cats2)
            if bar.series:
                bar.series[0].graphicalProperties.solidFill = C['accent']
            wc.add_chart(bar, 'D21')

        name_slug = stud_name.replace(' ', '_')
        fname = request.args.get('filename') or f"{name_slug}_Attendance_Record_{now.strftime('%Y-%m-%d')}.xlsx"
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment;filename="{fname}"'},
        )
    except Exception:
        return Response(f'Export error: {traceback.format_exc()}', status=500, mimetype='text/plain')


def export_session_attendance_impl(
    sess_id,
    *,
    load_session_fn,
    is_my_session_fn,
    get_all_students_fn,
    normalize_section_key_fn,
    build_student_section_key_fn,
    db_get_session_attendance_fn,
    get_db_fn,
    xl_helpers_fn,
):
    """Export one classroom session — attendance list with blockchain proof + charts."""
    try:
        _ox = __import__('openpyxl')
        _ox_chart = __import__('openpyxl.chart', fromlist=['BarChart', 'PieChart', 'Reference'])
        _ox_styles = __import__('openpyxl.styles', fromlist=['Font', 'PatternFill', 'Alignment'])
        Workbook = _ox.Workbook
        BarChart = _ox_chart.BarChart
        PieChart = _ox_chart.PieChart
        Reference = _ox_chart.Reference
        XFont = _ox_styles.Font
        XFill = _ox_styles.PatternFill
        XAlign = _ox_styles.Alignment
        import io as _io

        sess = load_session_fn(sess_id)
        if not sess:
            flash('Session not found.')
            return redirect(url_for('admin_sessions'))
        if not is_my_session_fn(sess):
            flash('Access denied.')
            return redirect(url_for('teacher_sessions'))

        now = datetime.now()
        section_key = normalize_section_key_fn(sess.get('section_key', ''))
        class_type_norm = str(sess.get('class_type', 'lecture') or 'lecture').strip().lower()
        is_school_event = class_type_norm == 'school_event'

        related_ids = [sess_id]
        section_keys = {section_key} if section_key else set()
        teacher_names = [str(sess.get('teacher_name', '') or '').strip()]

        if is_school_event:
            sched_id = str(sess.get('schedule_id', '') or '').strip()
            event_id = ''
            if sched_id.startswith('event:'):
                parts = sched_id.split(':', 3)
                if len(parts) == 4:
                    event_id = parts[1]
            if event_id:
                with get_db_fn() as _conn:
                    rel_rows = _conn.execute(
                        "SELECT sess_id, section_key, teacher_name FROM sessions "
                        "WHERE class_type='school_event' AND schedule_id LIKE ?",
                        (f"event:{event_id}:%",),
                    ).fetchall()
                if rel_rows:
                    related_ids = [r['sess_id'] for r in rel_rows if r.get('sess_id')]
                    if not related_ids:
                        related_ids = [sess_id]
                    for r in rel_rows:
                        sk = normalize_section_key_fn(r.get('section_key', ''))
                        if sk:
                            section_keys.add(sk)
                        tn = str(r.get('teacher_name', '') or '').strip()
                        if tn:
                            teacher_names.append(tn)
                with get_db_fn() as _conn:
                    ev_row = _conn.execute(
                        "SELECT teacher_usernames_json, section_keys_json FROM event_schedules WHERE event_id=? LIMIT 1",
                        (event_id,),
                    ).fetchone()
                if ev_row:
                    try:
                        for sk in json.loads(ev_row['section_keys_json'] or '[]'):
                            skn = normalize_section_key_fn(sk)
                            if skn:
                                section_keys.add(skn)
                    except Exception:
                        pass
        all_students = get_all_students_fn()
        if is_school_event:
            enrolled = sorted(
                [s for s in all_students if build_student_section_key_fn(s) in section_keys],
                key=lambda x: x['name'],
            )
        else:
            enrolled = sorted(
                [s for s in all_students if build_student_section_key_fn(s) == section_key],
                key=lambda x: x['name'],
            )
        present_ids = set(sess.get('present', []))
        late_ids = set(sess.get('late', []))
        excused_ids = set(sess.get('excused', []))
        att_logs = {}
        for rid in (related_ids if is_school_event else [sess_id]):
            for lg in db_get_session_attendance_fn(rid):
                att_logs[lg['nfc_id']] = lg

        if is_school_event:
            present_ids = {nid for nid, lg in att_logs.items() if str(lg.get('status', '')).strip().lower() in ('present', 'late')}
            late_ids = set()
            excused_ids = set()

        tapped_nfc_ids = present_ids | late_ids | excused_ids
        existing_nfc_ids = {s['nfcId'] for s in enrolled}
        for s in all_students:
            if s['nfcId'] in tapped_nfc_ids and s['nfcId'] not in existing_nfc_ids:
                enrolled.append(s)
                existing_nfc_ids.add(s['nfcId'])

        excuse_details = {}
        with get_db_fn() as _conn:
            if is_school_event and related_ids:
                ph = ','.join(['?'] * len(related_ids))
                excuses = _conn.execute(
                    "SELECT nfc_id, reason_type, reason_detail, attachment_file FROM excuse_requests "
                    "WHERE sess_id IN (" + ph + ") AND status='approved'",
                    tuple(related_ids),
                ).fetchall()
            else:
                excuses = _conn.execute(
                    "SELECT nfc_id, reason_type, reason_detail, attachment_file FROM excuse_requests WHERE sess_id=? AND status='approved'",
                    (sess_id,),
                ).fetchall()
            for exc in excuses:
                excuse_details[exc['nfc_id']] = {
                    'reason': exc['reason_type'],
                    'reason_detail': exc['reason_detail'],
                    'attachment_file': exc['attachment_file'],
                }

            # Get session blockchain transaction
            sess_tx_row = _conn.execute(
                "SELECT session_tx_hash, session_block_number FROM sessions WHERE sess_id=?", 
                (sess_id,)
            ).fetchone()
            session_tx_hash = sess_tx_row['session_tx_hash'] if sess_tx_row else ''
            session_block_number = sess_tx_row['session_block_number'] if sess_tx_row and sess_tx_row['session_block_number'] else 0

        counts = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
        rows = []
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
        for st in enrolled:
            nid = st['nfcId']
            if nid in excused_ids:
                status = 'Excused'
            elif nid in late_ids:
                status = 'Late'
            elif nid in present_ids:
                status = 'Present'
            else:
                status = 'Absent'
            if is_school_event and status == 'Late':
                status = 'Present'
            counts[status] += 1
            lg = att_logs.get(nid, {})
            excuse_info = excuse_details.get(nid, {})
            excuse_reason = ''
            if excuse_info.get('reason'):
                excuse_reason = reason_labels.get(excuse_info['reason'], excuse_info['reason'])
                if excuse_info.get('reason_detail'):
                    excuse_reason += f" ({excuse_info['reason_detail']})"
            rows.append(
                {
                    'name': st['name'],
                    'student_id': st.get('student_id', '—'),
                    'section_origin': '-'.join([
                        str(st.get('course', '') or '').strip(),
                        str(st.get('year_level', '') or '').strip(),
                        str(st.get('section', '') or '').strip(),
                    ]).strip('-') or '—',
                    'year': st.get('year_level', ''),
                    'status': status,
                    'enrollment_status': st.get('enrollment_status', 'Regular'),
                    'tap_date': '-' if status.lower() in ('absent', 'excused') else _fmt_date_dash(lg.get('tap_time', '') or ''),
                    'tap_time': '-' if status.lower() in ('absent', 'excused') else _fmt_time_hms_ampm(lg.get('tap_time', '') or ''),
                    'tx_hash': lg.get('tx_hash', '') or '—',
                    'block': str(lg.get('block_number', '')) if lg.get('block_number') else '—',
                    'excuse_reason': excuse_reason or '—',
                    'excuse_document': excuse_info.get('attachment_file', '') or '—',
                }
            )

        H = xl_helpers_fn()
        C = H['C']
        wb = Workbook()
        ws = wb.active
        ws.title = 'Attendance'
        subj = sess.get('subject_name', '')
        code = sess.get('course_code', '')
        sec = section_key.replace('|', ' · ')
        instr = sess.get('teacher_name', '')
        slot = sess.get('time_slot', '—')
        if class_type_norm == 'school_event':
            class_type_label = 'School Event'
        elif class_type_norm == 'laboratory':
            class_type_label = 'Laboratory'
        else:
            class_type_label = 'Lecture'
        started = sess.get('started_at', '—')
        ended = sess.get('ended_at', 'Still running')
        teacher_scope = ', '.join(sorted({t for t in teacher_names if t})) or instr or '—'
        section_scope = ' · '.join(sorted(section_keys)).replace('|', ' / ') if section_keys else sec
        n_cols = 12
        subtitles = [
            'Cavite State University — DAVS Session Attendance Report',
            f'Subject: {subj}  {"["+code+"]" if code else ""}',
            (f'Event Scope: {section_scope}' if is_school_event else f'Section: {sec}  |  Instructor: {instr}'),
            (f'Teacher(s) Involved: {teacher_scope}' if is_school_event else ''),
            f'Time Slot: {slot}  |  Class Type: {class_type_label}  |  Started: {started}  |  Ended: {ended}',
            f"Session TX: {session_tx_hash}{'' if not session_tx_hash else ' (Sepolia)'}  |  Block: {session_block_number}" if session_tx_hash else '',
            f'Exported: {now.strftime("%B %d, %Y %I:%M %p")}',
        ]
        subtitles = [s for s in subtitles if s]
        first_data = H['title_block'](ws, 'Session Attendance Report', subtitles, n_cols)
        first_data = H['stat_block'](ws, first_data, counts, n_cols)
        headers = [
            '#',
            'Student Name',
            'Student ID',
            'Program-Year-Section',
            'Class Type',
            'Status',
            'Enrollment Type',
            'Date',
            'Time',
            'Excuse Reason',
            'Document',
        ]
        widths = [4, 24, 14, 24, 12, 12, 16, 16, 14, 30, 24]
        H['make_header_row'](ws, first_data, headers, widths)
        first_data += 1
        col_fmt = {6: ('status',), 9: ('tx',), 10: ('num',)}
        for ri, row in enumerate(rows, first_data):
            H['data_row'](
                ws,
                ri,
                [
                    ri - first_data + 1,
                    row['name'],
                    row['student_id'],
                    row['section_origin'],
                    class_type_label,
                    row['status'],
                    row['enrollment_status'],
                    row['tap_date'],
                    row['tap_time'],
                    row['excuse_reason'],
                    row['excuse_document'],
                ],
                alt=(ri % 2 == 0),
                col_formats=col_fmt,
            )
        last_data = first_data + len(rows) - 1
        total_row_vals = [
            'TOTAL',
            f'{len(enrolled)} enrolled',
            '',
            f"{counts['Present']}P/{counts['Late']}L/{counts['Absent']}A/{counts['Excused']}E",
            '',
            '',
            '',
            '',
            '',
            '',
            '',
        ]
        H['totals_row'](ws, last_data + 1, total_row_vals, len(headers))
        ws.cell(
            row=last_data + 3,
            column=1,
            value=f'Generated by DAVS on {now.strftime("%B %d, %Y %I:%M %p")}',
        ).font = XFont(name='Calibri', size=9, italic=True, color='94A3B8')

        wc = wb.create_sheet('Charts')
        wc.sheet_view.showGridLines = False
        wc.merge_cells('A1:N1')
        wc['A1'] = f'Attendance Charts — {subj} {"["+code+"]" if code else ""}'
        wc['A1'].font = XFont(name='Calibri', bold=True, size=14, color=C['gold'])
        wc['A1'].fill = XFill('solid', fgColor=C['bg'])
        wc['A1'].alignment = XAlign(horizontal='center', vertical='center')
        wc.row_dimensions[1].height = 32
        for col in range(2, 15):
            wc.cell(row=1, column=col).fill = XFill('solid', fgColor=C['bg'])
        status_order = ['Present', 'Late', 'Absent', 'Excused']
        wc.cell(row=3, column=1, value='Status').font = XFont(bold=True, size=9, color=C['muted'])
        wc.cell(row=3, column=2, value='Count').font = XFont(bold=True, size=9, color=C['muted'])
        for ri, st in enumerate(status_order, 4):
            wc.cell(row=ri, column=1, value=st)
            wc.cell(row=ri, column=2, value=counts[st])
        pie = PieChart()
        pie.title = 'Attendance Status Breakdown'
        pie.style = 10
        pie.width = 14
        pie.height = 12
        pie.add_data(Reference(wc, min_col=2, min_row=4, max_row=7))
        pie.set_categories(Reference(wc, min_col=1, min_row=4, max_row=7))
        wc.add_chart(pie, 'D3')
        prog_counts = {}
        for r in rows:
            key = f"{r['year']}"
            prog_counts[key] = prog_counts.get(key, {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0})
            prog_counts[key][r['status']] += 1
        if len(prog_counts) > 1:
            r3c = 9
            wc.cell(row=3, column=r3c, value='Year Level').font = XFont(bold=True, size=9, color=C['muted'])
            wc.cell(row=3, column=r3c + 1, value='Present').font = XFont(bold=True, size=9, color=C['muted'])
            wc.cell(row=3, column=r3c + 2, value='Late').font = XFont(bold=True, size=9, color=C['muted'])
            wc.cell(row=3, column=r3c + 3, value='Absent').font = XFont(bold=True, size=9, color=C['muted'])
            for ri3, (yr_k, yc) in enumerate(sorted(prog_counts.items()), 4):
                wc.cell(row=ri3, column=r3c, value=yr_k)
                wc.cell(row=ri3, column=r3c + 1, value=yc['Present'])
                wc.cell(row=ri3, column=r3c + 2, value=yc['Late'])
                wc.cell(row=ri3, column=r3c + 3, value=yc['Absent'])
            bar = BarChart()
            bar.type = 'col'
            bar.grouping = 'stacked'
            bar.overlap = 100
            bar.title = 'Attendance by Year Level'
            bar.style = 10
            bar.width = 16
            bar.height = 12
            n_yl = len(prog_counts)
            bar.add_data(Reference(wc, min_col=r3c + 1, min_row=3, max_row=3 + n_yl), titles_from_data=True)
            bar.set_categories(Reference(wc, min_col=r3c, min_row=4, max_row=3 + n_yl))
            for i, clr in enumerate([C['present'], C['late'], C['absent']]):
                if i < len(bar.series):
                    bar.series[i].graphicalProperties.solidFill = clr
            wc.add_chart(bar, 'D21')

        sec_last = section_key.split('|')[-1] if section_key else 'Sec'
        date_str = (started or '')[:10]
        code_part = f'_{code}' if code else ''
        fname = request.args.get('filename') or f"Session_Attendance{code_part}_{sec_last}_{date_str}.xlsx"
        output = _io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment;filename="{fname}"'},
        )
    except Exception:
        return Response(f'Export error: {traceback.format_exc()}', status=500, mimetype='text/plain')
