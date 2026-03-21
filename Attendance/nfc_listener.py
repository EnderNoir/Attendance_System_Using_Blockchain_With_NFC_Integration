"""
nfc_listener.py
===============
DAVS — NFC Card Reader

Launched automatically by app.py in the background.
You do NOT need to run this manually.

When running in background (no terminal):
  All output is written to nfc_listener.log in the same folder.
  Check that file if you need to debug card taps.

When running manually (python nfc_listener.py):
  Output goes to both terminal and nfc_listener.log.
"""

import sys
import time
import secrets
import subprocess
import importlib
import importlib.util
import threading
import os

FLASK_URL        = "http://127.0.0.1:5000"
DEBOUNCE_SECONDS = 2.0
LOG_FILE         = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "nfc_listener.log")

# Detect if we are running with a visible terminal or hidden in background
HAS_TERMINAL = sys.stdout.isatty()


# ── Logging — writes to file always, terminal only if visible ─────────────────

_log_lock = threading.Lock()

def log(msg: str):
    ts  = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    with _log_lock:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass
    if HAS_TERMINAL:
        print(msg)


# ── Auto-install dependencies ─────────────────────────────────────────────────

def _ensure(package: str, import_name: str = None):
    name = import_name or package
    try:
        already = importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ValueError):
        already = False
    if not already:
        log(f"  Installing {package}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log(f"  {package} installed.")
        except Exception as e:
            log(f"  Could not install {package}: {e}")

_ensure("requests")
_ensure("pyscard", "smartcard")

import requests  # noqa: E402


# ── Windows Smart Card service ────────────────────────────────────────────────

def _service_running() -> bool:
    try:
        r = subprocess.run(["sc", "query", "SCardSvr"],
                           capture_output=True, text=True, timeout=5)
        return "RUNNING" in r.stdout.upper()
    except Exception:
        return False

def _ensure_windows_service() -> bool:
    if sys.platform != "win32":
        return True
    if _service_running():
        return True
    try:
        subprocess.run(["sc", "start", "SCardSvr"],
                       capture_output=True, text=True, timeout=10)
        time.sleep(2)
        if _service_running():
            log("  Smart Card service started.")
            return True
    except Exception:
        pass
    log("  ERROR: Smart Card service is not running.")
    log("  Run in Admin CMD:  sc start SCardSvr")
    log("                     sc config SCardSvr start= auto")
    return False


# ── Flask communication ───────────────────────────────────────────────────────

def send_tap(uid: str):
    uid = uid.strip().upper()
    try:
        resp   = requests.post(f"{FLASK_URL}/mark_pico",
                               json={"nfc_id": uid}, timeout=5)
        data   = resp.json()
        status = data.get("status", "")

        if status == "ok":
            late_tag = " [LATE]" if data.get("is_late") else ""
            log(f"  PRESENT{late_tag}: {data.get('name', uid)}"
                f"  |  {data.get('subject', '')}  |  {data.get('time', '')}")

        elif status == "already_marked":
            log(f"  ALREADY MARKED: {data.get('message', '')}")

        elif status == "registration":
            log(f"  REGISTRATION: UID {uid} sent to register form.")

        elif status == "no_session":
            log(f"  NO SESSION for UID: {uid}")
            stu = data.get("debug_student")
            if stu:
                log(f"  Student: {stu.get('name')} | "
                    f"{stu.get('course')} {stu.get('year_level')} "
                    f"Sec {stu.get('section')}")
            if not data.get("debug_active_sessions"):
                log("  No active sessions. Teacher must start a session first.")
        else:
            log(f"  RESPONSE: {data}")

    except requests.exceptions.ConnectionError:
        log("  Flask not reachable.")
    except Exception as e:
        log(f"  Error: {e}")


# ── UID helper ────────────────────────────────────────────────────────────────

def _uid_from_bytes(b) -> str:
    return ''.join(f'{x:02X}' for x in b)

GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]


# ── CardObserver — event-driven, fires regardless of window focus ─────────────

class NFCObserver:
    def __init__(self):
        self._last_uid  = None
        self._last_time = 0.0
        self._lock      = threading.Lock()

    def update(self, observable, actions):
        added, removed = actions

        for card in added:
            try:
                conn = card.createConnection()
                conn.connect()
                resp, sw1, sw2 = conn.transmit(GET_UID)
                uid = (_uid_from_bytes(resp) if sw1 == 0x90 and resp
                       else _uid_from_bytes(conn.getATR()[-4:]))
                conn.disconnect()

                now = time.time()
                with self._lock:
                    if (uid == self._last_uid and
                            now - self._last_time < DEBOUNCE_SECONDS):
                        continue
                    self._last_uid  = uid
                    self._last_time = now

                log(f"  CARD TAPPED: {uid}")
                threading.Thread(target=send_tap, args=(uid,),
                                 daemon=True).start()

            except Exception as e:
                err = str(e).lower()
                if not any(k in err for k in ("no card", "removed",
                                               "absent", "reset")):
                    log(f"  Card read error: {e}")

        if removed:
            with self._lock:
                self._last_uid = None


# ── PC/SC reader ──────────────────────────────────────────────────────────────

def run_reader() -> bool:
    try:
        from smartcard.System         import readers
        from smartcard.CardMonitoring import CardMonitor
        from smartcard.Exceptions     import EstablishContextException
    except ImportError:
        log("  pyscard import failed. Run: pip install pyscard")
        return False

    if not _ensure_windows_service():
        return False

    try:
        available = readers()
    except EstablishContextException:
        log("  Smart Card service not reachable.")
        return False
    except Exception as e:
        log(f"  Reader error: {e}")
        return False

    if not available:
        log("  No USB NFC reader detected. Plug in reader and restart.")
        return False

    log(f"  Reader: {available[0]}")
    log("  NFC listener ACTIVE — tap cards from any window.")

    observer = NFCObserver()
    monitor  = CardMonitor()
    monitor.addObserver(observer)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("  Stopped.")
    finally:
        try:
            monitor.deleteObserver(observer)
        except Exception:
            pass

    return True


# ── Keyboard simulator fallback ───────────────────────────────────────────────

def run_simulator():
    log("  No USB reader — keyboard simulator active.")
    if not HAS_TERMINAL:
        # Running hidden with no terminal — simulator makes no sense
        # Just keep alive so the process doesn't exit
        log("  Running headless. Waiting for reader to be connected...")
        while True:
            time.sleep(5)
            # Retry reader detection every 5 seconds
            try:
                from smartcard.System import readers
                if readers():
                    log("  Reader detected! Restarting listener...")
                    run_reader()
                    return
            except Exception:
                pass
        return

    # Has terminal — run interactive simulator
    print()
    print("  Type a UID + Enter     →  simulate tap")
    print("  Press Enter (blank)    →  random UID")
    print("  Type 'exit'            →  quit")
    print()
    while True:
        try:
            raw = input("Tap (UID): ").strip().upper()
            if raw == "EXIT":
                print("  Bye.")
                break
            if not raw:
                raw = secrets.token_hex(4).upper()
                print(f"  Generated: {raw}")
            send_tap(raw)
        except (KeyboardInterrupt, EOFError):
            print("\n  Bye.")
            break


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log("=" * 50)
    log("  DAVS NFC Listener starting")
    log(f"  Flask: {FLASK_URL}")
    log("=" * 50)

    if not run_reader():
        run_simulator()


if __name__ == "__main__":
    main()
    