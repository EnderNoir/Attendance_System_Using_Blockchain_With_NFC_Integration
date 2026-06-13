import sys
import os
import urllib.request
import json
import ssl
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.append(r'c:\Users\James NIcolo\Downloads\Attendance_System_Using_Blockchain_With_NFC_Integration')
from app import get_email_config

cfg = get_email_config()
print("Config loaded:", {k: v for k, v in cfg.items() if k != 'smtp_password'})

subject = "[DAVS] TEST SCRIPT"
html_body = "<h1>Test</h1>"
recipients = ["test@example.com"]  # Replace with a dummy

msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From'] = cfg.get('smtp_from') or cfg['smtp_user']
msg['To'] = ', '.join(recipients)
msg.attach(MIMEText(html_body, 'html'))

host = cfg.get('smtp_host', '').lower().strip()

# ── SENDGRID HTTP API BYPASS ──
if 'sendgrid.net' in host:
    print("Using SendGrid API...")
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {cfg['smtp_password'].strip()}",
        "Content-Type": "application/json"
    }
    sender_email = cfg.get('smtp_from') or "no-reply@davs.com"
    data = {
        "personalizations": [{"to": [{"email": r}]} for r in recipients],
        "from": {"email": sender_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    urllib.request.urlopen(req, timeout=10)
    print(f"Sent via SendGrid API to {recipients}")
    sys.exit(0)

# ── BREVO API BYPASS ──
if 'brevo.com' in host or 'sendinblue.com' in host:
    print("Using Brevo API...")
    url = "https://api.brevo.com/v3/smtp/email"
    headers = { "api-key": cfg['smtp_password'].strip(), "Content-Type": "application/json" }
    sender_email = cfg.get('smtp_from') or "no-reply@brevo.com"
    data = {
        "sender": {"email": sender_email},
        "to": [{"email": r} for r in recipients],
        "subject": subject,
        "htmlContent": html_body
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    urllib.request.urlopen(req, timeout=10)
    print(f"Sent via Brevo API to {recipients}")
    sys.exit(0)

print("Not using API. Falling back to SMTP logic.")
