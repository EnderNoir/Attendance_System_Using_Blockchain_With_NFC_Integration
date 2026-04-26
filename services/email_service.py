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


def send_email_async(to_addrs: list, subject: str, html_body: str, get_email_config_fn):
    """Send an HTML email via SMTP in a background thread."""
    import threading as _th

    def _worker():
        try:
            import smtplib
            import ssl
            import socket
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            cfg = get_email_config_fn()
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

            ctx = ssl.create_default_context()
            port = int(cfg.get('smtp_port', 587))
            host = cfg.get('smtp_host', 'smtp.gmail.com')
            timeout = 25

            # Force IPv4 resolution
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
