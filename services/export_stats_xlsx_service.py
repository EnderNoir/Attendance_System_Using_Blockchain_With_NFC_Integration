from datetime import datetime
import re

from flask import Response


def export_stats_xlsx_impl(
    *,
    request_obj,
    session_obj,
    build_stats_export_dataset_fn,
    load_sessions_fn,
    db_get_all_students_fn,
    db_get_override_fn,
    normalize_section_key_fn,
    build_student_section_key_fn,
    fmt_time_fn,
    db_get_session_attendance_fn,
    get_db_fn,
    xl_helpers_fn,
    now=None,
):
    """Unified analytics export - GET or POST. Produces rich multi-sheet workbook."""
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

        if request_obj.method == 'POST':
            from urllib.parse import parse_qs

            body = request_obj.get_json() or {}
            qs = parse_qs(body.get('params', ''))

            def qp(k):
                return qs.get(k, [''])[0]

            period = qp('period') or 'all'
            f_section = qp('section_key') or qp('section')
            f_year_lvl = qp('year_level')
            f_subject = qp('subject')
            f_instr = qp('instructor')
            f_class_type = qp('class_type').strip().lower()
            f_month = qp('month')
            f_year_num = qp('year_num')
            f_program = qp('program')
            f_sec_ltr = qp('section_letter')
            f_tod = qp('time_of_day')
            f_semester = qp('semester')
            f_enrollment = qp('enrollment_type')
        else:
            qp = lambda _k: ''
            period = request_obj.args.get('period', 'all')
            f_section = request_obj.args.get('section_key', request_obj.args.get('section', '')).strip()
            f_year_lvl = request_obj.args.get('year_level', '').strip()
            f_subject = request_obj.args.get('subject', '').strip()
            f_instr = request_obj.args.get('instructor', '').strip()
            f_class_type = request_obj.args.get('class_type', '').strip().lower()
            f_month = request_obj.args.get('month', '').strip()
            f_year_num = request_obj.args.get('year_num', '').strip()
            f_program = request_obj.args.get('program', '').strip()
            f_sec_ltr = request_obj.args.get('section_letter', '').strip()
            f_tod = request_obj.args.get('time_of_day', '').strip()
            f_semester = request_obj.args.get('semester', '').strip()
            f_enrollment = request_obj.args.get('enrollment_type', '').strip()

        role = session_obj.get('role')
        username = session_obj.get('username')
        if now is None:
            now = datetime.now()
        if not f_year_num:
            f_year_num = (
                qp('year') if request_obj.method == 'POST' else request_obj.args.get('year', '').strip()
            ) if period in ('month', 'year') else ''

        ds = build_stats_export_dataset_fn(
            period=period,
            f_section=f_section,
            f_year_lvl=f_year_lvl,
            f_subject=f_subject,
            f_instr=f_instr,
            f_class_type=f_class_type,
            f_month=f_month,
            f_year_num=f_year_num,
            f_program=f_program,
            f_sec_ltr=f_sec_ltr,
            f_tod=f_tod,
            f_semester=f_semester,
            f_enrollment=f_enrollment,
            role=role,
            username=username,
            now=now,
            load_sessions_fn=load_sessions_fn,
            db_get_all_students_fn=db_get_all_students_fn,
            db_get_override_fn=db_get_override_fn,
            normalize_section_key_fn=normalize_section_key_fn,
            build_student_section_key_fn=build_student_section_key_fn,
            fmt_time_fn=fmt_time_fn,
            db_get_session_attendance_fn=db_get_session_attendance_fn,
            get_db_fn=get_db_fn,
        )
        period_label = ds['period_label']
        filter_label = ds['filter_label']
        donut = ds['donut']
        trend = ds['trend']
        subj_d = ds['subj_d']
        sess_rows = ds['sess_rows']
        detail_rows = ds['detail_rows']
        by_section = ds['by_section']

        total_all = sum(donut.values())
        H = xl_helpers_fn()
        C = H['C']
        wb = Workbook()

        # Sheet 1: Summary
        ws1 = wb.active
        ws1.title = 'Summary'
        n_cols = 12
        subtitles = [
            'Cavite State University - Decentralized Attendance Verification System',
            f'Period: {period_label}  |  Filters: {filter_label}',
            f'Generated: {now.strftime("%B %d, %Y  %I:%M %p")}  |  Role: {role.upper()}',
        ]
        first_row = H['title_block'](ws1, 'DAVS - Attendance Analytics Report', subtitles, n_cols)
        first_row = H['stat_block'](ws1, first_row, donut, n_cols)
        hdrs = [
            'Subject',
            'Class Type',
            'Session Date & Time',
            'Section',
            'Instructor',
            'Time Slot',
            'Enrolled',
            'Present',
            'Late',
            'Absent',
            'Excused',
            'Rate %',
        ]
        wids = [30, 12, 22, 24, 22, 16, 10, 10, 9, 9, 10, 10]
        H['make_header_row'](ws1, first_row, hdrs, wids)
        first_row += 1
        for ri, row in enumerate(sess_rows, first_row):
            vals = list(row)
            vals[11] = f"{vals[11]}%"
            col_fmt = {8: ('num',), 9: ('num',), 10: ('num',), 11: ('num',)}
            H['data_row'](ws1, ri, vals, alt=(ri % 2 == 0), col_formats=col_fmt)
        last_data = first_row + len(sess_rows) - 1
        tr = last_data + 1
        H['totals_row'](
            ws1,
            tr,
            [
                'TOTAL',
                '',
                '',
                '',
                '',
                f'=SUM(F{first_row}:F{last_data})',
                f'=SUM(G{first_row}:G{last_data})',
                f'=SUM(H{first_row}:H{last_data})',
                f'=SUM(I{first_row}:I{last_data})',
                f'=SUM(J{first_row}:J{last_data})',
                f'=IFERROR(TEXT((G{tr}+H{tr})/F{tr},"0.0%"),"-")',
            ],
            n_cols,
        )
        ws1.cell(row=tr + 2, column=1, value=f'Generated by DAVS on {now.strftime("%B %d, %Y %I:%M %p")}').font = XFont(
            name='Calibri', size=9, italic=True, color='94A3B8'
        )
        ws1.freeze_panes = ws1.cell(row=first_row, column=1)

        # Sheet 2: Student Detail
        ws2 = wb.create_sheet('Student Detail')
        n2 = 16
        subtitles2 = [
            'Cavite State University - DAVS',
            f'Period: {period_label}  |  Filters: {filter_label}',
            'Each row represents one student in one session including full blockchain proof.',
        ]
        dr = H['title_block'](ws2, 'Student Attendance Detail', subtitles2, n2)
        det_hdrs = [
            'Student Name',
            'Student ID',
            'NFC Card UID',
            'Program',
            'Year',
            'Sec',
            'Enrollment Type',
            'Subject',
            'Class Type',
            'Session Date',
            'Time Slot',
            'Instructor',
            'Status',
            'TX Hash',
            'Block #',
            'Excuse Reason',
            'Document',
        ]
        det_wids = [24, 14, 14, 24, 10, 6, 15, 28, 12, 20, 16, 22, 10, 52, 10, 26, 20]
        H['make_header_row'](ws2, dr, det_hdrs, det_wids)
        dr += 1
        for ri, row in enumerate(detail_rows, dr):
            col_fmt = {13: ('status',), 14: ('tx',), 15: ('num',)}
            H['data_row'](ws2, ri, row, alt=(ri % 2 == 0), col_formats=col_fmt)
        ws2.freeze_panes = ws2.cell(row=dr, column=1)

        # Sheet 3: By Date
        ws3 = wb.create_sheet('By Date')
        n3 = 5
        subtitles3 = [f'Period: {period_label}  |  Attendance counts per session date']
        tr3 = H['title_block'](ws3, 'Attendance Trend by Date', subtitles3, n3)
        H['make_header_row'](ws3, tr3, ['Date', 'Present', 'Late', 'Absent', 'Excused'], [18, 12, 12, 12, 12])
        tr3 += 1
        for ri, (date, td) in enumerate(sorted(trend.items()), tr3):
            col_fmt = {2: ('num',), 3: ('num',), 4: ('num',), 5: ('num',)}
            H['data_row'](
                ws3,
                ri,
                [date, td['present'], td['late'], td['absent'], td['excused']],
                alt=(ri % 2 == 0),
                col_formats=col_fmt,
            )
        last_tr3 = tr3 + len(trend) - 1
        if trend:
            bar3 = BarChart()
            bar3.type = 'col'
            bar3.grouping = 'stacked'
            bar3.overlap = 100
            bar3.title = 'Daily Attendance Trend'
            bar3.style = 10
            bar3.width = 22
            bar3.height = 14
            bar3.y_axis.title = 'Count'
            bar3.legend.position = 'b'
            cats3 = Reference(ws3, min_col=1, min_row=tr3, max_row=last_tr3)
            data3 = Reference(ws3, min_col=2, min_row=tr3 - 1, max_row=last_tr3, max_col=5)
            bar3.add_data(data3, titles_from_data=True)
            bar3.set_categories(cats3)
            colors3 = [C['present'], C['late'], C['absent'], C['excused']]
            for i, clr in enumerate(colors3):
                if i < len(bar3.series):
                    bar3.series[i].graphicalProperties.solidFill = clr
                    bar3.series[i].graphicalProperties.line.solidFill = clr
            ws3.add_chart(bar3, f'G{tr3}')

        # Sheet 4: By Subject
        ws4 = wb.create_sheet('By Subject')
        n4 = 7
        subtitles4 = [f'Period: {period_label}  |  Aggregate attendance per subject']
        ts4 = H['title_block'](ws4, 'Attendance by Subject', subtitles4, n4)
        H['make_header_row'](
            ws4,
            ts4,
            ['Subject', 'Code', 'Present', 'Late', 'Absent', 'Excused', 'Rate %'],
            [36, 12, 12, 12, 12, 12, 12],
        )
        ts4 += 1
        for ri, (sn, sd) in enumerate(sorted(subj_d.items()), ts4):
            total2 = sd['present'] + sd['late'] + sd['absent'] + sd['excused']
            rate2 = f"{round((sd['present'] + sd['late']) / total2 * 100, 1)}%" if total2 else '-'
            col_fmt4 = {3: ('num',), 4: ('num',), 5: ('num',), 6: ('num',)}
            H['data_row'](
                ws4,
                ri,
                [sn, sd['code'], sd['present'], sd['late'], sd['absent'], sd['excused'], rate2],
                alt=(ri % 2 == 0),
                col_formats=col_fmt4,
            )
        last_ts4 = ts4 + len(subj_d) - 1
        if subj_d:
            bar4 = BarChart()
            bar4.type = 'bar'
            bar4.grouping = 'stacked'
            bar4.overlap = 100
            bar4.title = 'Attendance by Subject'
            bar4.style = 10
            bar4.width = 22
            bar4.height = 14
            bar4.x_axis.title = 'Count'
            bar4.legend.position = 'b'
            cats4 = Reference(ws4, min_col=1, min_row=ts4, max_row=last_ts4)
            data4 = Reference(ws4, min_col=3, min_row=ts4 - 1, max_row=last_ts4, max_col=6)
            bar4.add_data(data4, titles_from_data=True)
            bar4.set_categories(cats4)
            colors4 = [C['present'], C['late'], C['absent'], C['excused']]
            for i, clr in enumerate(colors4):
                if i < len(bar4.series):
                    bar4.series[i].graphicalProperties.solidFill = clr
            ws4.add_chart(bar4, f'I{ts4}')

        # Sheet 5: By Section
        ws5 = wb.create_sheet('By Section')
        n5 = 7
        subtitles5 = [f'Period: {period_label}  |  Aggregate attendance per section']
        ts5 = H['title_block'](ws5, 'Attendance by Section', subtitles5, n5)
        H['make_header_row'](
            ws5,
            ts5,
            ['Section', 'Enrolled', 'Present', 'Late', 'Absent', 'Excused', 'Rate %'],
            [32, 10, 12, 12, 12, 12, 12],
        )
        ts5 += 1
        for ri, (sec_k, sc) in enumerate(sorted(by_section.items()), ts5):
            rate5 = f"{round((sc['present'] + sc['late']) / sc['enrolled'] * 100, 1)}%" if sc['enrolled'] else '-'
            col_fmt5 = {2: ('num',), 3: ('num',), 4: ('num',), 5: ('num',), 6: ('num',)}
            H['data_row'](
                ws5,
                ri,
                [
                    sec_k.replace('|', ' · '),
                    sc['enrolled'],
                    sc['present'],
                    sc['late'],
                    sc['absent'],
                    sc['excused'],
                    rate5,
                ],
                alt=(ri % 2 == 0),
                col_formats=col_fmt5,
            )
        last_ts5 = ts5 + len(by_section) - 1
        if by_section:
            bar5 = BarChart()
            bar5.type = 'bar'
            bar5.grouping = 'stacked'
            bar5.overlap = 100
            bar5.title = 'Attendance by Section'
            bar5.style = 10
            bar5.width = 22
            bar5.height = 14
            bar5.x_axis.title = 'Count'
            bar5.legend.position = 'b'
            cats5 = Reference(ws5, min_col=1, min_row=ts5, max_row=last_ts5)
            data5 = Reference(ws5, min_col=3, min_row=ts5 - 1, max_row=last_ts5, max_col=6)
            bar5.add_data(data5, titles_from_data=True)
            bar5.set_categories(cats5)
            colors5 = [C['present'], C['late'], C['absent'], C['excused']]
            for i, clr in enumerate(colors5):
                if i < len(bar5.series):
                    bar5.series[i].graphicalProperties.solidFill = clr
                    bar5.series[i].graphicalProperties.line.solidFill = clr
            ws5.add_chart(bar5, f'I{ts5}')

        # Sheet 6: By Class Type
        ws6 = wb.create_sheet('By Class Type')
        n6 = 7
        subtitles6 = [f'Period: {period_label}  |  Aggregate attendance per class type']
        ts6 = H['title_block'](ws6, 'Attendance by Class Type', subtitles6, n6)
        H['make_header_row'](
            ws6,
            ts6,
            ['Class Type', 'Present', 'Late', 'Absent', 'Excused', 'Total', 'Rate %'],
            [22, 12, 12, 12, 12, 12, 12],
        )
        ts6 += 1
        by_class_type = ds.get('by_class_type', {})

        for ri, (ctype, cnts) in enumerate(sorted(by_class_type.items()), ts6):
            total6 = cnts['present'] + cnts['late'] + cnts['absent'] + cnts['excused']
            rate6 = f"{round((cnts['present'] + cnts['late']) / total6 * 100, 1)}%" if total6 else '-'
            col_fmt6 = {2: ('num',), 3: ('num',), 4: ('num',), 5: ('num',), 6: ('num',)}
            H['data_row'](
                ws6,
                ri,
                [ctype, cnts['present'], cnts['late'], cnts['absent'], cnts['excused'], total6, rate6],
                alt=(ri % 2 == 0),
                col_formats=col_fmt6,
            )
        last_ts6 = ts6 + len(by_class_type) - 1
        if by_class_type:
            bar6 = BarChart()
            bar6.type = 'bar'
            bar6.grouping = 'stacked'
            bar6.overlap = 100
            bar6.title = 'Attendance by Class Type'
            bar6.style = 10
            bar6.width = 18
            bar6.height = max(9, len(by_class_type) * 1.8)
            bar6.x_axis.title = 'Count'
            bar6.legend.position = 'b'
            cats6 = Reference(ws6, min_col=1, min_row=ts6, max_row=last_ts6)
            data6 = Reference(ws6, min_col=2, min_row=ts6 - 1, max_row=last_ts6, max_col=5)
            bar6.add_data(data6, titles_from_data=True)
            bar6.set_categories(cats6)
            colors6 = [C['present'], C['late'], C['absent'], C['excused']]
            for i, clr in enumerate(colors6):
                if i < len(bar6.series):
                    bar6.series[i].graphicalProperties.solidFill = clr
                    bar6.series[i].graphicalProperties.line.solidFill = clr
            ws6.add_chart(bar6, f'I{ts6}')

        # Sheet 7: Charts Dashboard
        wc = wb.create_sheet('Charts')
        wc.sheet_view.showGridLines = False

        n_chart_cols = 20
        wc.merge_cells(f'A1:{chr(64 + n_chart_cols)}1')
        wc['A1'] = 'DAVS - Attendance Analytics Charts'
        wc['A1'].font = XFont(name='Calibri', bold=True, size=16, color=C['gold'])
        wc['A1'].fill = XFill('solid', fgColor=C['bg'])
        wc['A1'].alignment = XAlign(horizontal='center', vertical='center')
        wc.row_dimensions[1].height = 36
        for col in range(2, n_chart_cols + 1):
            wc.cell(row=1, column=col).fill = XFill('solid', fgColor=C['bg'])

        wc.merge_cells(f'A2:{chr(64 + n_chart_cols)}2')
        wc['A2'] = f'Period: {period_label}  |  Filters: {filter_label}  |  Generated: {now.strftime("%B %d, %Y")} '
        wc['A2'].font = XFont(name='Calibri', size=9, italic=True, color='94A3B8')
        wc['A2'].fill = XFill('solid', fgColor=C['bg'])
        wc['A2'].alignment = XAlign(horizontal='center', vertical='center')
        for col in range(2, n_chart_cols + 1):
            wc.cell(row=2, column=col).fill = XFill('solid', fgColor=C['bg'])

        pie_labels = ['Present', 'Late', 'Absent', 'Excused']
        pie_vals = [donut[k] for k in pie_labels]
        for ri_p, (lbl, val) in enumerate(zip(pie_labels, pie_vals), 4):
            wc.cell(row=ri_p, column=30, value=lbl)
            wc.cell(row=ri_p, column=31, value=val)

        pie_c = PieChart()
        pie_c.title = f'Overall Attendance Status - {period_label}'
        pie_c.style = 10
        pie_c.width = 16
        pie_c.height = 14
        pie_c.add_data(Reference(wc, min_col=31, min_row=4, max_row=7))
        pie_c.set_categories(Reference(wc, min_col=30, min_row=4, max_row=7))
        wc.add_chart(pie_c, 'B4')

        subj_data_row = 10
        if subj_d:
            wc.cell(row=subj_data_row - 1, column=33, value='Subject')
            wc.cell(row=subj_data_row - 1, column=34, value='Present')
            wc.cell(row=subj_data_row - 1, column=35, value='Late')
            wc.cell(row=subj_data_row - 1, column=36, value='Absent')
            wc.cell(row=subj_data_row - 1, column=37, value='Excused')
            for ri_s, (sn, sd) in enumerate(sorted(subj_d.items()), subj_data_row):
                wc.cell(row=ri_s, column=33, value=sn[:30])
                wc.cell(row=ri_s, column=34, value=sd['present'])
                wc.cell(row=ri_s, column=35, value=sd['late'])
                wc.cell(row=ri_s, column=36, value=sd['absent'])
                wc.cell(row=ri_s, column=37, value=sd['excused'])
            n_subj = len(subj_d)
            subj_last = subj_data_row + n_subj - 1
            bar_s = BarChart()
            bar_s.type = 'bar'
            bar_s.grouping = 'stacked'
            bar_s.overlap = 100
            bar_s.title = 'Attendance by Subject'
            bar_s.style = 10
            bar_s.width = 20
            bar_s.height = max(10, n_subj * 1.2)
            bar_s.legend.position = 'b'
            bar_s.add_data(
                Reference(wc, min_col=34, min_row=subj_data_row - 1, max_row=subj_last, max_col=37),
                titles_from_data=True,
            )
            bar_s.set_categories(Reference(wc, min_col=33, min_row=subj_data_row, max_row=subj_last))
            for i, clr in enumerate([C['present'], C['late'], C['absent'], C['excused']]):
                if i < len(bar_s.series):
                    bar_s.series[i].graphicalProperties.solidFill = clr
                    bar_s.series[i].graphicalProperties.line.solidFill = clr
            wc.add_chart(bar_s, 'B36')

        sec_data_row = 10
        if by_section:
            wc.cell(row=sec_data_row - 1, column=38, value='Section')
            wc.cell(row=sec_data_row - 1, column=39, value='Present')
            wc.cell(row=sec_data_row - 1, column=40, value='Late')
            wc.cell(row=sec_data_row - 1, column=41, value='Absent')
            wc.cell(row=sec_data_row - 1, column=42, value='Excused')
            for ri_sc, (sec_k, sc) in enumerate(sorted(by_section.items()), sec_data_row):
                wc.cell(row=ri_sc, column=38, value=sec_k.replace('|', ' · ')[:30])
                wc.cell(row=ri_sc, column=39, value=sc['present'])
                wc.cell(row=ri_sc, column=40, value=sc['late'])
                wc.cell(row=ri_sc, column=41, value=sc['absent'])
                wc.cell(row=ri_sc, column=42, value=sc['excused'])
            n_sec = len(by_section)
            sec_last = sec_data_row + n_sec - 1
            bar_sc = BarChart()
            bar_sc.type = 'bar'
            bar_sc.grouping = 'stacked'
            bar_sc.overlap = 100
            bar_sc.title = 'Attendance by Section'
            bar_sc.style = 10
            bar_sc.width = 20
            bar_sc.height = max(10, n_sec * 1.4)
            bar_sc.legend.position = 'b'
            bar_sc.add_data(
                Reference(wc, min_col=39, min_row=sec_data_row - 1, max_row=sec_last, max_col=42),
                titles_from_data=True,
            )
            bar_sc.set_categories(Reference(wc, min_col=38, min_row=sec_data_row, max_row=sec_last))
            for i, clr in enumerate([C['present'], C['late'], C['absent'], C['excused']]):
                if i < len(bar_sc.series):
                    bar_sc.series[i].graphicalProperties.solidFill = clr
                    bar_sc.series[i].graphicalProperties.line.solidFill = clr
            wc.add_chart(bar_sc, 'N4')

        class_type_data_row = 10
        if by_class_type:
            wc.cell(row=class_type_data_row - 1, column=43, value='Class Type')
            wc.cell(row=class_type_data_row - 1, column=44, value='Present')
            wc.cell(row=class_type_data_row - 1, column=45, value='Late')
            wc.cell(row=class_type_data_row - 1, column=46, value='Absent')
            wc.cell(row=class_type_data_row - 1, column=47, value='Excused')
            for ri_ct, (ctype, cnts) in enumerate(sorted(by_class_type.items()), class_type_data_row):
                wc.cell(row=ri_ct, column=43, value=ctype)
                wc.cell(row=ri_ct, column=44, value=cnts['present'])
                wc.cell(row=ri_ct, column=45, value=cnts['late'])
                wc.cell(row=ri_ct, column=46, value=cnts['absent'])
                wc.cell(row=ri_ct, column=47, value=cnts['excused'])
            n_ct = len(by_class_type)
            ct_last = class_type_data_row + n_ct - 1
            bar_ct = BarChart()
            bar_ct.type = 'bar'
            bar_ct.grouping = 'stacked'
            bar_ct.overlap = 100
            bar_ct.title = 'Attendance by Class Type'
            bar_ct.style = 10
            bar_ct.width = 20
            bar_ct.height = max(9, n_ct * 2)
            bar_ct.legend.position = 'b'
            bar_ct.add_data(
                Reference(wc, min_col=44, min_row=class_type_data_row - 1, max_row=ct_last, max_col=47),
                titles_from_data=True,
            )
            bar_ct.set_categories(Reference(wc, min_col=43, min_row=class_type_data_row, max_row=ct_last))
            for i, clr in enumerate([C['present'], C['late'], C['absent'], C['excused']]):
                if i < len(bar_ct.series):
                    bar_ct.series[i].graphicalProperties.solidFill = clr
                    bar_ct.series[i].graphicalProperties.line.solidFill = clr
            wc.add_chart(bar_ct, 'N36')

        parts = ['DAVS_Attendance_Report', period_label.replace(' ', '_').replace(',', '')]
        if f_program:
            parts.append(f_program.replace('BS ', 'BS').replace(' ', '_'))
        if f_year_lvl:
            parts.append(f_year_lvl.replace(' ', '_'))
        if f_sec_ltr:
            parts.append(f'Section_{f_sec_ltr}')
        if f_subject:
            parts.append(re.sub(r'[^A-Za-z0-9]', '_', f_subject)[:20])
        if f_instr:
            parts.append(f_instr.split()[0])
        if f_semester:
            parts.append(f_semester.replace(' ', '_'))
        fname = request_obj.args.get('filename') or ('_'.join(parts) + f'_{now.strftime("%Y-%m-%d")}.xlsx')
        fname = re.sub(r'_+', '_', fname)
        fname = fname.replace('\u2014', '-').replace('\u2013', '-')
        fname = fname.encode('ascii', 'ignore').decode('ascii')
        fname = re.sub(r'[^\w\-.]', '_', fname)
        fname = re.sub(r'_+', '_', fname).strip('_')
        if not fname.endswith('.xlsx'):
            fname += '.xlsx'
        output = _io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{fname}"'},
        )
    except Exception:
        import traceback

        return Response(f'Export error: {traceback.format_exc()}', status=500, mimetype='text/plain')
