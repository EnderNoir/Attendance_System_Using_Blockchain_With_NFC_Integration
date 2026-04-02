from typing import Optional, Callable


def _valid_email(addr: str) -> bool:
    return bool(addr and '@' in addr)


def send_student_welcome_email(
    *,
    student_name: str,
    student_email: str,
    nfc_id: str,
    student_id: str = '',
    course: str = '',
    year_level: str = '',
    section: str = '',
    send_email_fn: Optional[Callable] = None,
):
    """Send a welcome email after student registration."""
    if send_email_fn is None or not _valid_email(student_email):
        return

    details = []
    if student_id:
        details.append(f"<tr><td style='padding:6px 10px;color:#475569;'>Student ID</td><td style='padding:6px 10px;font-weight:600;color:#0f172a;'>{student_id}</td></tr>")
    if nfc_id:
        details.append(f"<tr><td style='padding:6px 10px;color:#475569;'>NFC ID</td><td style='padding:6px 10px;font-weight:600;color:#0f172a;'>{nfc_id}</td></tr>")
    if course:
        details.append(f"<tr><td style='padding:6px 10px;color:#475569;'>Course</td><td style='padding:6px 10px;font-weight:600;color:#0f172a;'>{course}</td></tr>")
    if year_level:
        details.append(f"<tr><td style='padding:6px 10px;color:#475569;'>Year Level</td><td style='padding:6px 10px;font-weight:600;color:#0f172a;'>{year_level}</td></tr>")
    if section:
        details.append(f"<tr><td style='padding:6px 10px;color:#475569;'>Section</td><td style='padding:6px 10px;font-weight:600;color:#0f172a;'>{section}</td></tr>")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:22px;border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;">
      <h2 style="margin:0 0 10px;color:#1e4a1a;">Welcome to DAVS</h2>
      <p style="margin:0 0 12px;color:#334155;">Hello {student_name or 'Student'},</p>
      <p style="margin:0 0 14px;color:#334155;">Congratulations. Your student account has been created in the Decentralized Attendance Verification System (DAVS).</p>
      <table style="width:100%;border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">{''.join(details)}</table>
      <p style="margin:14px 0 0;color:#475569;font-size:13px;">You are now officially part of DAVS. Welcome and best of luck this term.</p>
      <p style="margin:14px 0 0;color:#94a3b8;font-size:11px;">Cavite State University - DAVS System (Automated Message)</p>
    </div>
    """
    send_email_fn([student_email], '[DAVS] Welcome - Student Account Created', html)


def send_staff_welcome_email(
    *,
    full_name: str,
    email: str,
    username: str,
    role: str,
    initial_password: str = '',
    login_url: str = '',
    send_email_fn: Optional[Callable] = None,
):
    """Send a welcome email after teacher/admin account creation."""
    if send_email_fn is None or not _valid_email(email):
        return

    role_label = (role or 'teacher').replace('_', ' ').title()
    login_line = f"<p style='margin:12px 0 0;color:#334155;'>Login: <a href='{login_url}' style='color:#1e4a1a;font-weight:700;'>{login_url}</a></p>" if login_url else ''

    pw_block = ''
    if initial_password:
        pw_block = f"""
        <p style='margin:10px 0 6px;color:#475569;'>Initial Password</p>
        <p style='margin:0;font-weight:700;color:#0f172a;letter-spacing:.5px;'>{initial_password}</p>
        <p style='margin:10px 0 0;color:#b45309;font-size:13px;font-weight:700;'>For security, please change this password immediately after your first login.</p>
        """

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:22px;border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;">
      <h2 style="margin:0 0 10px;color:#1e4a1a;">Welcome to DAVS</h2>
      <p style="margin:0 0 12px;color:#334155;">Hello {full_name or username},</p>
      <p style="margin:0 0 14px;color:#334155;">Congratulations. Your {role_label} account has been created successfully. We are happy to have you as part of DAVS.</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;">
        <p style="margin:0 0 6px;color:#475569;">Username</p>
        <p style="margin:0;font-weight:700;color:#0f172a;">{username}</p>
        <p style="margin:10px 0 6px;color:#475569;">Role</p>
        <p style="margin:0;font-weight:700;color:#0f172a;">{role_label}</p>
                {pw_block}
      </div>
      {login_line}
            <div style="margin-top:14px;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
                <p style="margin:0;color:#475569;font-size:12px;line-height:1.5;">
                    Privacy and lawful use notice: DAVS account and attendance data are collected and processed only for legitimate academic attendance monitoring,
                    verification, and school administrative purposes. Any unauthorized or illegal use of this information is strictly prohibited.
                </p>
            </div>
            <p style="margin:14px 0 0;color:#94a3b8;font-size:11px;">Cavite State University - DAVS System (Automated Message)</p>
    </div>
    """
    send_email_fn([email], f'[DAVS] Welcome - {role_label} Account Created', html)


def send_password_changed_success_email(
        *,
        full_name: str,
        email: str,
        username: str,
        role: str,
        send_email_fn: Optional[Callable] = None,
):
        """Send email confirmation after password is changed successfully."""
        if send_email_fn is None or not _valid_email(email):
                return

        role_label = (role or 'user').replace('_', ' ').title()
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:22px;border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;">
            <h2 style="margin:0 0 10px;color:#1e4a1a;">Password Updated Successfully</h2>
            <p style="margin:0 0 12px;color:#334155;">Hello {full_name or username},</p>
            <p style="margin:0 0 14px;color:#334155;">Congratulations. Your DAVS password was changed successfully for your {role_label} account.</p>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;">
                <p style="margin:0 0 6px;color:#475569;">Username</p>
                <p style="margin:0;font-weight:700;color:#0f172a;">{username}</p>
            </div>
            <p style="margin:12px 0 0;color:#b91c1c;font-size:13px;font-weight:700;">If you did not perform this action, please report immediately to your DAVS administrator.</p>
            <div style="margin-top:14px;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
                <p style="margin:0;color:#475569;font-size:12px;line-height:1.5;">
                    Privacy and lawful use notice: DAVS account and attendance data are collected and processed only for legitimate academic attendance monitoring,
                    verification, and school administrative purposes. Any unauthorized or illegal use of this information is strictly prohibited.
                </p>
            </div>
            <p style="margin:14px 0 0;color:#94a3b8;font-size:11px;">Cavite State University - DAVS System (Automated Message)</p>
        </div>
        """
        send_email_fn([email], '[DAVS] Password Changed Successfully', html)
