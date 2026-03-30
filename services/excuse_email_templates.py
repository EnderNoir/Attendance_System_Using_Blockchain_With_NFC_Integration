def send_excuse_received_email(email, student_name, subject_name, reason_type, excuse_id, reason_labels, send_email_fn):
    if not email or '@' not in email:
        return
    reason_label = reason_labels.get(reason_type, (reason_type or '').title())
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.1);">
      <tr><td style="background:#1E4A1A;padding:20px 28px;">
        <div style="font-size:18px;font-weight:700;color:#F5C518;">DAVS</div>
        <div style="font-size:11px;color:#94a3b8;">Decentralized Attendance Verification System</div>
      </td></tr>
      <tr><td style="padding:24px 28px;">
        <p style="font-size:15px;color:#1E4A1A;font-weight:700;">Excuse Request Received</p>
        <p style="font-size:13px;color:#444;">Dear <strong>{student_name}</strong>,</p>
        <p style="font-size:13px;color:#444;">
          Your excuse request for <strong>{subject_name}</strong> has been received and is
          <strong>pending review</strong> by the administrator.
        </p>
        <table style="border:1px solid #eee;border-radius:8px;width:100%;">
          <tr><td style="padding:8px 12px;font-size:12px;color:#666;width:130px;">Reason</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;">{reason_label}</td></tr>
          <tr><td style="padding:8px 12px;font-size:12px;color:#666;">Request #</td>
              <td style="padding:8px 12px;font-size:12px;font-family:monospace;color:#333;">#{excuse_id}</td></tr>
        </table>
        <p style="font-size:11px;color:#94a3b8;margin-top:20px;">
          You will receive another email when your request is reviewed.<br>Please do not reply to this email.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>'''
    send_email_fn([email], f'[DAVS] Excuse Request Received - {subject_name}', html)


def send_excuse_resolved_email(email, student_name, reason_type, resolution, reason_labels, send_email_fn):
    if not email or '@' not in email:
        return
    reason_label = reason_labels.get(reason_type, (reason_type or '').title())
    color = '#2D6A27' if resolution == 'approved' else '#C0392B'
    badge = 'APPROVED ✓' if resolution == 'approved' else 'REJECTED ✕'
    message = (
        'Your excuse has been <strong>approved</strong> and your attendance has been '
        'updated to <strong>Excused</strong>.'
        if resolution == 'approved'
        else 'Your excuse request has been <strong>rejected</strong>. '
             'Please contact your instructor or administrator for more details.'
    )
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.1);">
      <tr><td style="background:#1E4A1A;padding:20px 28px;">
        <div style="font-size:18px;font-weight:700;color:#F5C518;">DAVS</div>
        <div style="font-size:11px;color:#94a3b8;">Decentralized Attendance Verification System</div>
      </td></tr>
      <tr><td style="padding:24px 28px;">
        <div style="font-size:22px;font-weight:700;color:{color};margin-bottom:12px;">{badge}</div>
        <p style="font-size:13px;color:#444;">Dear <strong>{student_name}</strong>,</p>
        <p style="font-size:13px;color:#444;">{message}</p>
        <table style="border:1px solid #eee;border-radius:8px;width:100%;">
          <tr><td style="padding:8px 12px;font-size:12px;color:#666;width:130px;">Reason Filed</td>
              <td style="padding:8px 12px;font-size:12px;color:#333;">{reason_label}</td></tr>
          <tr><td style="padding:8px 12px;font-size:12px;color:#666;">Decision</td>
              <td style="padding:8px 12px;font-size:12px;font-weight:700;color:{color};">{resolution.title()}</td></tr>
        </table>
        <p style="font-size:11px;color:#94a3b8;margin-top:20px;">Please do not reply to this email.</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>'''
    send_email_fn([email], f'[DAVS] Excuse Request {resolution.title()} - {reason_label}', html)
