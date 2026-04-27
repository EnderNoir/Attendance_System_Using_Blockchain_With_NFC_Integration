from typing import Callable, Optional
from datetime import datetime

def _fmt_time(t_str):
    """Format time string (e.g. '07:30:00' or '2024-04-26 07:30:00') to '7:00am'."""
    if not t_str or t_str == '—': return '—'
    try:
        t_str = str(t_str)
        if ' ' in t_str:
            # Handle full ISO format
            dt = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
        elif ':' in t_str:
            # Handle HH:MM:SS or HH:MM
            parts = t_str.split(':')
            if len(parts) == 3:
                dt = datetime.strptime(t_str, '%H:%M:%S')
            else:
                dt = datetime.strptime(t_str, '%H:%M')
        else:
            return t_str
        # Format as 7:00am (lowercase, no leading zero on hour)
        return dt.strftime('%I:%M%p').lower().lstrip('0')
    except:
        return str(t_str)

def _fmt_date(d_str):
    """Format date string '2024-04-26 07:30:00' to 'April 26 2024'."""
    if not d_str or d_str == '—': return '—'
    try:
        if ' ' in str(d_str):
            dt = datetime.strptime(str(d_str).split(' ')[0], '%Y-%m-%d')
        else:
            dt = datetime.strptime(str(d_str), '%Y-%m-%d')
        return dt.strftime('%B %d %Y')
    except:
        return str(d_str)

def _fmt_dt(dt_str):
    """Format to 'April 26 2024, 7:00am'."""
    if not dt_str or dt_str == '—': return '—'
    return f"{_fmt_date(dt_str)}, {_fmt_time(dt_str)}"

def _fmt_slot(slot):
    """Format '07:00 - 09:00' or '07:00 to 09:00' to '7:00am to 9:00am'."""
    if not slot: return '—'
    slot_str = str(slot)
    
    # Try different delimiters
    delimiter = None
    if ' - ' in slot_str:
        delimiter = ' - '
    elif ' to ' in slot_str:
        delimiter = ' to '
    
    if not delimiter: return slot_str
    
    try:
        parts = slot_str.split(delimiter)
        if len(parts) == 2:
            return f"{_fmt_time(parts[0].strip())} to {_fmt_time(parts[1].strip())}"
        return slot_str
    except:
        return slot_str


def send_student_attendance_receipt(
    student_name,
    student_email,
    student_id,
    subject_name,
    section_key,
    teacher_name,
    tap_time,
    status,
    tx_hash,
    block_num,
    sess_id=None,
    nfc_id=None,
    send_email_fn: Optional[Callable] = None,
    url_for_fn: Optional[Callable] = None,
    semester=None,
    time_slot=None,
):
    """Send attendance receipt email to student."""
    if not student_email or '@' not in student_email or send_email_fn is None:
        return
    status_colors = {
        'present': ('#2D6A27', '#E8F5E9', '✓ Present'),
        'late': ('#D4A017', '#FFF8E1', '⏱ Late'),
        'absent': ('#C0392B', '#FFEBEE', '✕ Absent'),
        'excused': ('#2980B9', '#E3F2FD', '◎ Excused'),
    }
    clr, bg, label = status_colors.get(status, ('#333333', '#F5F5F5', status.capitalize()))
    
    # Section + Semester formatting
    section_display = (section_key.replace('|', ' · ') if section_key else '—')
    if semester:
        section_display += f" · {semester}"
        
    tx_row = ''
    excuse_section = ''

    if status == 'absent' and sess_id and nfc_id and url_for_fn is not None:
        try:
            excuse_link = url_for_fn('excuse_submit', sess_id=sess_id, nfc_id=nfc_id, _external=True)
            excuse_section = f'''
            <tr>
              <td colspan="2" style="padding:16px 32px;text-align:center;border-top:1px solid #eee;">
                <div style="font-size:13px;color:#666;margin-bottom:10px;">If this absence is valid, please submit an excuse request below:</div>
                <a href="{excuse_link}" style="display:inline-block;background:#3b82f6;color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;font-weight:bold;font-size:14px;">Submit Excuse Form</a>
              </td>
            </tr>
            '''
        except Exception:
            excuse_section = ''

    if tx_hash:
        tx_row = f'''
        <tr>
          <td style="padding:8px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee;">
            Blockchain TX
          </td>
          <td style="padding:8px 12px;font-size:11px;font-family:monospace;
                     color:#2D6A27;border-bottom:1px solid #eee;word-break:break-all;">
            {tx_hash}
            <div style="margin-top:4px;">
              <a href="https://sepolia.etherscan.io/tx/{tx_hash}" style="color:#2D6A27;text-decoration:none;font-weight:bold;font-size:10px;" target="_blank">
                View on Blockchain Explorer
              </a>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 12px;font-size:12px;color:#666;">Block #</td>
          <td style="padding:8px 12px;font-size:12px;font-family:monospace;color:#333;">
            {block_num}
          </td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="560" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.1);">
      <!-- Header -->
      <tr>
        <td style="background:#1E4A1A;padding:24px 32px;">
          <div style="font-size:20px;font-weight:700;color:#F5C518;
                      letter-spacing:1px;">DAVS</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:2px;">
            Decentralized Attendance Verification System
          </div>
          <div style="font-size:11px;color:#94a3b8;">
            Cavite State University - Silang Campus
          </div>
        </td>
      </tr>
      <!-- Status banner -->
      <tr>
        <td style="background:{bg};padding:20px 32px;
                   border-left:4px solid {clr};">
          <div style="font-size:28px;font-weight:700;color:{clr};">
            {label}
          </div>
          <div style="font-size:13px;color:#555;margin-top:4px;">
            Your attendance has been recorded for today's class.
          </div>
        </td>
      </tr>
      <!-- Details table -->
      <tr>
        <td style="padding:24px 32px 8px;">
          <div style="font-size:13px;font-weight:700;color:#1E4A1A;
                      text-transform:uppercase;letter-spacing:1px;
                      margin-bottom:12px;">Attendance Details</div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #eee;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;width:140px;">Student</td>
              <td style="padding:8px 12px;font-size:12px;font-weight:600;
                         color:#333;border-bottom:1px solid #eee;">
                {student_name}
                {f'<span style="color:#999;font-size:11px;"> - ID: {student_id}</span>'
                 if student_id else ''}
              </td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Subject</td>
              <td style="padding:8px 12px;font-size:12px;font-weight:600;
                         color:#333;border-bottom:1px solid #eee;">
                {subject_name}
              </td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Section</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{section_display}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Instructor</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{teacher_name}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Date</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{_fmt_date(tap_time)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Tapped Time</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                          border-bottom:1px solid #eee;">{"-" if status.lower() in ("absent", "excused") else _fmt_time(tap_time)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Time Slot</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{_fmt_slot(time_slot)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Status</td>
              <td style="padding:8px 12px;">
                <span style="background:{bg};color:{clr};font-weight:700;
                             font-size:12px;padding:3px 10px;border-radius:20px;
                             border:1px solid {clr};">{label}</span>
              </td>
            </tr>
            {tx_row}
          </table>
        </td>
      </tr>
      {excuse_section}
      <!-- Footer -->
      <tr>
        <td style="padding:20px 32px 28px;">
          <div style="font-size:11px;color:#94a3b8;line-height:1.6;">
            This is an automated attendance receipt from the DAVS system.<br>
            {"The TX hash above is your tamper-proof blockchain proof of attendance.<br>" if tx_hash else ""}
            Please do not reply to this email.
          </div>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>'''
    send_email_fn(
        [student_email],
        f'[DAVS] Attendance Receipt - {subject_name} ({label})',
        html,
    )


def send_teacher_session_summary(
    teacher_email,
    teacher_name,
    subject_name,
    section_key,
    time_slot,
    started_at,
    ended_at,
    present_count,
    late_count,
    absent_count,
    excused_count,
    student_rows,
    session_tx_hash=None,
    session_block_number=None,
    send_email_fn: Optional[Callable] = None,
    course_code=None,
    semester=None,
):
    """Send session summary email to teacher when session ends."""
    if not teacher_email or '@' not in teacher_email or send_email_fn is None:
        return
    total = present_count + late_count + absent_count + excused_count
    rate = round((present_count + late_count) / total * 100, 1) if total else 0
    
    # Section + Semester formatting
    section_disp = section_key.replace('|', ' · ') if section_key else '—'
    if semester:
        section_disp += f" · {semester}"
        
    status_colors = {
        'present': ('#2D6A27', '#E8F5E9', '✓ Present'),
        'late': ('#D4A017', '#FFF8E1', '⏱ Late'),
        'absent': ('#C0392B', '#FFEBEE', '✕ Absent'),
        'excused': ('#2980B9', '#E3F2FD', '◎ Excused'),
    }
    
    # Subject display with course code
    subject_display = subject_name
    if course_code:
        subject_display += f" [{course_code}]"
        
    rows_html = ''
    for i, st in enumerate(student_rows):
        clr, bg, lbl = status_colors.get(
            st.get('status', 'absent'),
            ('#333', '#f5f5f5', st.get('status', '—').capitalize()),
        )
        bg_row = '#F9FBF9' if i % 2 == 0 else '#FFFFFF'
        rows_html += f'''<tr style="background:{bg_row};">
          <td style="padding:7px 10px;font-size:12px;border-bottom:1px solid #eee;">
            {st.get("name", "—")}
            <div style="font-size:10px;color:#999;">{st.get("student_id", "")}</div>
          </td>
          <td style="padding:7px 10px;font-size:11px;color:#666;
                     border-bottom:1px solid #eee;white-space:nowrap;">
             {"-" if st.get("status", "absent").lower() in ("absent", "excused") else _fmt_time(st.get("tap_time", "-"))}
          </td>
          <td style="padding:7px 10px;border-bottom:1px solid #eee;">
            <span style="background:{bg};color:{clr};font-weight:700;
                         font-size:11px;padding:2px 8px;border-radius:20px;
                         border:1px solid {clr};">{lbl}</span>
          </td>
        </tr>'''
    
    # Add session blockchain info if available
    session_blockchain_info = ''
    if session_tx_hash:
        session_blockchain_info = f'''
      <!-- Session Blockchain Info -->
      <tr>
        <td style="background:#E8F5E9;padding:16px 32px;border-top:1px solid #ddd;">
          <div style="font-size:13px;font-weight:700;color:#2D6A27;margin-bottom:12px;">
            📋 Session Blockchain Record
          </div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:12px;color:#666;width:120px;">Transaction Hash:</td>
              <td style="padding:6px 0;font-size:11px;font-family:monospace;color:#2D6A27;word-break:break-all;">
                {session_tx_hash}
              </td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:12px;color:#666;">Block Number:</td>
              <td style="padding:6px 0;font-size:12px;font-family:monospace;color:#333;">
                {session_block_number}
              </td>
            </tr>
            <tr>
              <td colspan="2" style="padding:8px 0;font-size:11px;color:#999;border-top:1px solid #ccc;margin-top:8px;padding-top:8px;">
                ✓ This entire session's attendance record has been permanently recorded on the Sepolia blockchain.<br/>
                <a href="https://sepolia.etherscan.io/tx/{session_tx_hash}" style="color:#2D6A27;text-decoration:none;font-weight:bold;" target="_blank">
                  View on Blockchain Explorer
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>'''
    
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="640" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.1);">
      <!-- Header -->
      <tr>
        <td style="background:#1E4A1A;padding:24px 32px;">
          <div style="font-size:20px;font-weight:700;color:#F5C518;">DAVS</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:2px;">
            Session Summary Report - {subject_name}
          </div>
        </td>
      </tr>
      <!-- Summary stats -->
      <tr>
        <td style="padding:20px 32px 8px;">
          <div style="font-size:13px;font-weight:700;color:#1E4A1A;
                      text-transform:uppercase;letter-spacing:1px;
                      margin-bottom:12px;">Session Overview</div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #eee;border-radius:8px;
                        overflow:hidden;margin-bottom:16px;">
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;width:140px;">Subject</td>
              <td style="padding:8px 12px;font-size:12px;font-weight:600;
                         color:#333;border-bottom:1px solid #eee;">{subject_display}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Section</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{section_disp}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Time Slot</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{_fmt_slot(time_slot)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Started</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{_fmt_dt(started_at)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px;font-size:12px;color:#666;
                         border-bottom:1px solid #eee;">Ended</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;
                         border-bottom:1px solid #eee;">{_fmt_dt(ended_at)}</td>
            </tr>
          </table>
          <!-- Stat boxes -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
            <tr>
              <td width="25%" style="padding:4px;">
                <div style="background:#E8F5E9;border:1px solid #2D6A27;border-radius:8px;
                            padding:12px;text-align:center;">
                  <div style="font-size:28px;font-weight:700;color:#2D6A27;">{present_count}</div>
                  <div style="font-size:11px;color:#2D6A27;font-weight:600;">Present</div>
                </div>
              </td>
              <td width="25%" style="padding:4px;">
                <div style="background:#FFF8E1;border:1px solid #D4A017;border-radius:8px;
                            padding:12px;text-align:center;">
                  <div style="font-size:28px;font-weight:700;color:#D4A017;">{late_count}</div>
                  <div style="font-size:11px;color:#D4A017;font-weight:600;">Late</div>
                </div>
              </td>
              <td width="25%" style="padding:4px;">
                <div style="background:#FFEBEE;border:1px solid #C0392B;border-radius:8px;
                            padding:12px;text-align:center;">
                  <div style="font-size:28px;font-weight:700;color:#C0392B;">{absent_count}</div>
                  <div style="font-size:11px;color:#C0392B;font-weight:600;">Absent</div>
                </div>
              </td>
              <td width="25%" style="padding:4px;">
                <div style="background:#E3F2FD;border:1px solid #2980B9;border-radius:8px;
                            padding:12px;text-align:center;">
                  <div style="font-size:28px;font-weight:700;color:#2980B9;">{excused_count}</div>
                  <div style="font-size:11px;color:#2980B9;font-weight:600;">Excused</div>
                </div>
              </td>
            </tr>
          </table>
          <div style="font-size:12px;color:#555;margin-bottom:20px;">
            Attendance rate: <strong style="color:#1E4A1A;">{rate}%</strong>
            &nbsp;-&nbsp; {total} students enrolled
          </div>
          <!-- Student list -->
          <div style="font-size:13px;font-weight:700;color:#1E4A1A;
                      text-transform:uppercase;letter-spacing:1px;
                      margin-bottom:10px;">Student Attendance List</div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #eee;border-radius:8px;overflow:hidden;">
            <thead>
              <tr style="background:#1E4A1A;">
                <th style="padding:9px 10px;font-size:11px;color:#fff;
                           text-align:left;font-weight:600;">Student</th>
                <th style="padding:9px 10px;font-size:11px;color:#fff;
                           text-align:left;font-weight:600;">Tap Time</th>
                <th style="padding:9px 10px;font-size:11px;color:#fff;
                           text-align:left;font-weight:600;">Status</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </td>
      </tr>
      {session_blockchain_info}
      <!-- Footer -->
      <tr>
        <td style="padding:16px 32px 28px;">
          <div style="font-size:11px;color:#94a3b8;line-height:1.6;">
            This is an automated session summary from the DAVS system.<br>
            All TX hashes are immutable blockchain records verifiable on the Sepolia testnet.<br>
            Please do not reply to this email.
          </div>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>'''
    send_email_fn(
        [teacher_email],
        f'[DAVS] Session Summary - {subject_name} · {section_disp}',
        html,
    )
