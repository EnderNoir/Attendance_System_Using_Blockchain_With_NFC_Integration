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

if 'sendgrid.net' in host or cfg.get('smtp_user') == 'apikey':
    print("Using SendGrid API...")
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {cfg['smtp_password'].strip()}",
        "Content-Type": "application/json"
    }
    html_body_extracted = msg.get_payload()[0].get_payload() if msg.is_multipart() else msg.get_payload()
    personalizations = [{"to": [{"email": r}]} for r in recipients]
    data = {
        "personalizations": personalizations,
        "from": {"email": msg['From']},
        "subject": msg['Subject'],
        "content": [{"type": "text/html", "value": html_body_extracted}]
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=10)
        print("Success:", response.status, response.read().decode())
    except Exception as e:
        print("Error in API:", str(e))
        if hasattr(e, 'read'):
            print("Response:", e.read().decode())
else:
    print("Not using SendGrid API.")
