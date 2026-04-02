def xl_helpers():
    """Return a dict of reusable Excel style helpers."""
    _ox_styles = __import__('openpyxl.styles', fromlist=['Alignment', 'Border', 'Font', 'PatternFill', 'Side'])
    _ox_utils = __import__('openpyxl.utils', fromlist=['get_column_letter'])
    _ox_chart = __import__('openpyxl.chart', fromlist=['BarChart', 'PieChart', 'Reference'])
    _ox_chart_series = __import__('openpyxl.chart.series', fromlist=['SeriesLabel'])
    Alignment = _ox_styles.Alignment
    Border = _ox_styles.Border
    Font = _ox_styles.Font
    PatternFill = _ox_styles.PatternFill
    Side = _ox_styles.Side
    get_column_letter = _ox_utils.get_column_letter
    BarChart = _ox_chart.BarChart
    PieChart = _ox_chart.PieChart
    Reference = _ox_chart.Reference
    SeriesLabel = _ox_chart_series.SeriesLabel

    C = {
        'bg': '1E4A1A', 'header': '1E4A1A', 'accent': '2D6A27',
        'gold': 'F5C518', 'surface': 'FFFFFF', 'border': 'D4DDD4',
        'present': '2D6A27', 'late': 'D4A017', 'absent': 'C0392B', 'excused': '2980B9',
        'present_bg': 'E8F5E9', 'late_bg': 'FFF8E1', 'absent_bg': 'FFEBEE', 'excused_bg': 'E3F2FD',
        'white': 'FFFFFF', 'row_alt': 'F0F2F0', 'row_def': 'FFFFFF',
        'muted': '5A6B5A', 'sub_hdr': '2D6A27',
    }

    def fill(h):
        return PatternFill('solid', fgColor=h)

    def thin_border():
        s = Side(style='thin', color='CBD5E1')
        return Border(left=s, right=s, top=s, bottom=s)

    def ctr(wrap=True):
        return Alignment(horizontal='center', vertical='center', wrap_text=wrap)

    def lft():
        return Alignment(horizontal='left', vertical='center', wrap_text=True)

    def rgt():
        return Alignment(horizontal='right', vertical='center', wrap_text=True)

    def header_font(size=10):
        return Font(name='Calibri', bold=True, color='FFFFFF', size=size)

    def normal_font(size=10, color='111111', bold=False):
        return Font(name='Calibri', size=size, color=color, bold=bold)

    def title_font(size=16, color=None):
        return Font(name='Calibri', bold=True, size=size, color=color or C['accent'])

    def make_header_row(ws, row_num, headers, widths, bg=None):
        bg = bg or C['header']
        for ci, (h, w) in enumerate(zip(headers, widths), 1):
            ws.column_dimensions[get_column_letter(ci)].width = w
            c = ws.cell(row=row_num, column=ci, value=h)
            c.font = header_font()
            c.fill = fill(bg)
            c.alignment = ctr()
            c.border = thin_border()
        ws.row_dimensions[row_num].height = 22

    def data_row(ws, row_num, values, alt=False, col_formats=None):
        rf = fill(C['row_alt'] if alt else C['row_def'])
        for ci, val in enumerate(values, 1):
            c = ws.cell(row=row_num, column=ci, value=val)
            c.border = thin_border()
            cf = (col_formats or {}).get(ci)
            if cf and cf[0] == 'status':
                status = val
                status_colors = {
                    'Present': C['present'],
                    'Late': C['late'],
                    'Absent': C['absent'],
                    'Excused': C['excused'],
                }
                fg = status_colors.get(status, '111111')
                c.font = Font(name='Calibri', size=10, bold=True, color=fg)
                c.fill = rf
                c.alignment = ctr()
            elif cf and cf[0] == 'tx':
                c.font = Font(name='Courier New', size=8, color=C['muted'])
                c.fill = rf
                c.alignment = lft()
            elif cf and cf[0] == 'num':
                c.font = normal_font()
                c.fill = rf
                c.alignment = ctr()
            else:
                c.font = normal_font()
                c.fill = rf
                c.alignment = lft() if ci <= 3 else ctr()
        ws.row_dimensions[row_num].height = 17

    def title_block(ws, title, subtitle_lines, n_cols):
        ws.sheet_view.showGridLines = False
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
        c = ws.cell(row=1, column=1, value=title)
        c.font = title_font(16, C['gold'])
        c.fill = fill(C['bg'])
        c.alignment = ctr()
        ws.row_dimensions[1].height = 36
        for col in range(2, n_cols + 1):
            ws.cell(row=1, column=col).fill = fill(C['bg'])
        for i, sub in enumerate(subtitle_lines, 2):
            ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=n_cols)
            c = ws.cell(row=i, column=1, value=sub)
            c.font = Font(name='Calibri', size=9, color='94A3B8', italic=True)
            c.fill = fill(C['bg'])
            c.alignment = ctr()
            ws.row_dimensions[i].height = 16
            for col in range(2, n_cols + 1):
                ws.cell(row=i, column=col).fill = fill(C['bg'])
        next_row = len(subtitle_lines) + 2
        for col in range(1, n_cols + 1):
            ws.cell(row=next_row, column=col).fill = fill('F8FAFC')
        ws.row_dimensions[next_row].height = 7
        return next_row + 1

    def stat_block(ws, start_row, donut_data, n_cols=8):
        total = sum(donut_data.values())
        boxes = [
            ('✓  PRESENT', donut_data.get('present', donut_data.get('Present', 0)), C['present'], C['present_bg']),
            ('⏱  LATE', donut_data.get('late', donut_data.get('Late', 0)), C['late'], C['late_bg']),
            ('✕  ABSENT', donut_data.get('absent', donut_data.get('Absent', 0)), C['absent'], C['absent_bg']),
            ('◎  EXCUSED', donut_data.get('excused', donut_data.get('Excused', 0)), C['excused'], C['excused_bg']),
        ]
        cols_per = max(1, n_cols // 4)
        for bi, (label, val, fg, bg2) in enumerate(boxes):
            sc = bi * cols_per + 1
            ec = sc + cols_per - 1
            pct = f"{round(val / total * 100, 1)}%" if total else '0%'
            for row_offset, (text, sz, bold, height) in enumerate([
                (label, 9, True, 18),
                (val, 26, True, 40),
                (pct, 9, False, 18),
            ]):
                r = start_row + row_offset
                ws.merge_cells(start_row=r, start_column=sc, end_row=r, end_column=ec)
                c = ws.cell(row=r, column=sc, value=text)
                c.font = Font(name='Calibri', size=sz, bold=bold, color=fg)
                c.fill = fill(bg2)
                c.alignment = ctr()
                ws.row_dimensions[r].height = height
                for col in range(sc + 1, ec + 1):
                    ws.cell(row=r, column=col).fill = fill(bg2)
        spacer_row = start_row + 3
        for col in range(1, n_cols + 1):
            ws.cell(row=spacer_row, column=col).fill = fill('F8FAFC')
        ws.row_dimensions[spacer_row].height = 8
        return spacer_row + 1

    def totals_row(ws, row_num, values, n_cols):
        for ci, val in enumerate(values, 1):
            c = ws.cell(row=row_num, column=ci, value=val)
            c.font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
            c.fill = fill(C['sub_hdr'])
            c.border = thin_border()
            c.alignment = lft() if ci == 1 else ctr()
        ws.row_dimensions[row_num].height = 20

    def add_bar_chart(
        wb,
        ws_name,
        data_ws_name,
        title,
        first_data_row,
        last_data_row,
        n_series,
        cat_col,
        series_cols_start,
        series_titles,
        series_colors,
        chart_anchor,
        width=18,
        height=12,
    ):
        chart_ws = wb[ws_name]
        data_ws = wb[data_ws_name]
        chart = BarChart()
        chart.type = 'col'
        chart.grouping = 'stacked'
        chart.overlap = 100
        chart.title = title
        chart.style = 10
        chart.y_axis.title = 'Count'
        chart.x_axis.title = ''
        chart.width = width
        chart.height = height
        chart.legend.position = 'b'
        cats = Reference(data_ws, min_col=cat_col, min_row=first_data_row, max_row=last_data_row)
        for i in range(n_series):
            col = series_cols_start + i
            data_ref = Reference(data_ws, min_col=col, min_row=first_data_row - 1, max_row=last_data_row)
            chart.series.append(data_ref)
        chart.set_categories(cats)
        for i, (title_s, color) in enumerate(zip(series_titles, series_colors)):
            if i < len(chart.series):
                chart.series[i].title = SeriesLabel(v=title_s)
                chart.series[i].graphicalProperties.solidFill = color
                chart.series[i].graphicalProperties.line.solidFill = color
        chart_ws.add_chart(chart, chart_anchor)

    def add_pie_chart(
        wb,
        ws_name,
        data_ws_name,
        title,
        first_data_row,
        last_data_row,
        label_col,
        val_col,
        series_colors,
        chart_anchor,
        width=12,
        height=10,
    ):
        chart_ws = wb[ws_name]
        data_ws = wb[data_ws_name]
        chart = PieChart()
        chart.title = title
        chart.style = 10
        chart.width = width
        chart.height = height
        labels = Reference(data_ws, min_col=label_col, min_row=first_data_row, max_row=last_data_row)
        data = Reference(data_ws, min_col=val_col, min_row=first_data_row, max_row=last_data_row)
        chart.add_data(data)
        chart.set_categories(labels)
        chart_ws.add_chart(chart, chart_anchor)

    return dict(
        C=C,
        fill=fill,
        thin_border=thin_border,
        ctr=ctr,
        lft=lft,
        rgt=rgt,
        header_font=header_font,
        normal_font=normal_font,
        title_font=title_font,
        make_header_row=make_header_row,
        data_row=data_row,
        title_block=title_block,
        stat_block=stat_block,
        totals_row=totals_row,
        add_bar_chart=add_bar_chart,
        add_pie_chart=add_pie_chart,
    )
