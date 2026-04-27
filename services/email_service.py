def get_email_config(get_db_fn):
    """Load SMTP config from DB. Returns dict with all keys."""
    defaults = {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'smtp_user': '',
        'smtp_password': '',
        'smtp_from': '',
        'enabled': '0',
    }
    try:
        with get_db_fn() as conn:
            rows = conn.execute('SELECT key, value FROM email_config').fetchall()
            cfg = dict(defaults)
            for row in rows:
                cfg[row['key']] = row['value']
            return cfg
    except Exception:
        return defaults


def save_email_config(cfg: dict, get_db_fn):
    """Upsert email config into DB."""
    with get_db_fn() as conn:
        for key, value in cfg.items():
            conn.execute(
                'INSERT INTO email_config (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (key, str(value)),
            )


def send_email_async(to_addrs: list, subject: str, html_body: str, cfg: dict):
    """Send an HTML email via SMTP in a background thread."""
    import threading as _th

    def _worker():
        try:
            import smtplib
            import ssl
            import socket
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            if cfg.get('enabled') != '1':
                return
            if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
                print('[EMAIL] SMTP credentials not configured - skipping.')
                return
            recipients = [a for a in to_addrs if a and '@' in a]
            if not recipients:
                return

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = cfg.get('smtp_from') or cfg['smtp_user']
            msg['To'] = ', '.join(recipients)
            msg.attach(MIMEText(html_body, 'html'))

            # ── HELPERS ──
            def _extract_email(s):
                import re
                if not s: return None
                match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', s)
                return match.group(0) if match else s

            host = cfg.get('smtp_host', '').lower().strip()
            
            # ── SENDGRID HTTP API BYPASS ──
            # Only trigger if host is explicitly SendGrid to avoid intercepting other services (like Brevo)
            # that might also use 'apikey' as a username but expect standard SMTP.
            if 'sendgrid.net' in host:
                import urllib.request
                import json
                
                url = "https://api.sendgrid.com/v3/mail/send"
                api_key = cfg['smtp_password'].strip()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                # SendGrid API REQUIRES a valid email in the 'from' field. 
                # If smtp_from is empty, we must NOT use 'apikey' as the email.
                sender_email = _extract_email(cfg.get('smtp_from')) or ''
                if not sender_email or '@' not in sender_email:
                    u_email = _extract_email(cfg.get('smtp_user'))
                    if u_email and '@' in u_email:
                        sender_email = u_email
                    else:
                        sender_email = "no-reply@davs-attendance.com"
                
                personalizations = [{"to": [{"email": r}]} for r in recipients]
                data = {
                    "personalizations": personalizations,
                    "from": {"email": sender_email},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}]
                }
                
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
                try:
                    urllib.request.urlopen(req, timeout=10)
                    print(f'[EMAIL] Sent "{subject}" to {recipients} via SendGrid API')
                except urllib.error.HTTPError as he:
                    err_body = he.read().decode('utf-8')
                    print(f'[EMAIL] SendGrid API Error {he.code}: {err_body}')
                    raise
                return

            # ── BREVO (SENDINBLUE) HTTP API BYPASS ──
            # Useful for Railway/Heroku where SMTP ports (587/465) are often blocked.
            if 'brevo.com' in host or 'sendinblue.com' in host:
                import urllib.request
                import json
                
                url = "https://api.brevo.com/v3/smtp/email"
                api_key = cfg['smtp_password'].strip()
                headers = {
                    "api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                sender_email = _extract_email(cfg.get('smtp_from')) or ''
                if not sender_email or '@' not in sender_email:
                    u_email = _extract_email(cfg.get('smtp_user'))
                    sender_email = u_email if (u_email and '@' in u_email) else "no-reply@brevo.com"
                
                data = {
                    "sender": {"email": sender_email},
                    "to": [{"email": r} for r in recipients],
                    "subject": subject,
                    "htmlContent": html_body
                }
                
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
                try:
                    urllib.request.urlopen(req, timeout=10)
                    print(f'[EMAIL] Sent "{subject}" to {recipients} via Brevo API')
                except urllib.error.HTTPError as he:
                    err_body = he.read().decode('utf-8')
                    print(f'[EMAIL] Brevo API Error {he.code}: {err_body}')
                    raise
                return

            # ── STANDARD SMTP ROUTE ──
            ctx = ssl.create_default_context()
            port = int(cfg.get('smtp_port', 587))
            timeout = 5

            try:
                addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                target_ip = addr_info[0][4][0]
            except:
                target_ip = host

            if port == 465:
                try:
                    srv = smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout)
                except:
                    srv = smtplib.SMTP_SSL(target_ip, port, context=ctx, timeout=timeout)
            else:
                try:
                    srv = smtplib.SMTP(host, port, timeout=timeout)
                except:
                    srv = smtplib.SMTP(target_ip, port, timeout=timeout)
                
                srv.ehlo()
                if srv.has_ext('STARTTLS'):
                    srv.starttls(context=ctx)
                    srv.ehlo()

            with srv:
                srv.login(cfg['smtp_user'], cfg['smtp_password'])
                srv.sendmail(msg['From'], recipients, msg.as_string())
            print(f'[EMAIL] Sent "{subject}" to {recipients}')
        except Exception as _e:
            print(f'[EMAIL] Failed to send "{subject}": {_e}')


    _th.Thread(target=_worker, daemon=True).start()
