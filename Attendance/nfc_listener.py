"""
nfc_listener.py
Runs on your PC in Terminal 4.
No NFC hardware? It auto-starts the simulator.
Type a student UID and press Enter to simulate a card tap.
All taps go through /mark_pico on the Flask server.
"""

import requests
import secrets
import time

FLASK_URL = "http://127.0.0.1:5000"

def send_tap(uid):
    """Send a single NFC tap to the Flask server via /mark_pico."""
    try:
        resp = requests.post(
            f"{FLASK_URL}/mark_pico",
            json={"nfc_id": uid},
            timeout=5
        )
        data = resp.json()
        status = data.get("status")

        if status == "ok":
            print(f"  ✅ Present: {data.get('name')}  [{data.get('subject', '')}]  {data.get('time', '')}")
        elif status == "already_marked":
            print(f"  ⚠️  {data.get('message')}")
        elif status == "registration":
            print(f"  📋 Registration mode — UID {uid} sent to registration form.")
        elif status == "no_session":
            print(f"  ❌ No active session for this student's section.")
            if data.get("debug_student"):
                s = data["debug_student"]
                print(f"     Student: {s.get('name')}  |  {s.get('course')} {s.get('year_level')} Sec {s.get('section')}")
            if data.get("debug_active_sessions") is not None:
                sessions = data["debug_active_sessions"]
                if sessions:
                    print(f"     Active session IDs: {sessions}")
                else:
                    print(f"     ⚠️  No active sessions found. Make sure the teacher clicked 'Start Session' first.")
        else:
            print(f"  ℹ️  Response: {data}")

    except requests.exceptions.ConnectionError:
        print("  ❌ Cannot connect to Flask. Make sure Terminal 3 (python app.py) is running.")
    except Exception as e:
        print(f"  ❌ Error: {e}")


def run_simulator():
    print()
    print("=" * 50)
    print("  NFC SIMULATOR — DAVS")
    print("=" * 50)
    print("  Type a student UID + Enter  →  simulate card tap")
    print("  Press Enter (blank)         →  random UID")
    print("  Type 'exit'                 →  quit")
    print("=" * 50)
    print()

    while True:
        try:
            uid = input("Tap (simulated): ").strip().upper()

            if uid == "EXIT":
                print("👋 Simulator stopped.")
                break

            if uid == "":
                uid = secrets.token_hex(4).upper()
                print(f"  Generated UID: {uid}")

            send_tap(uid)

        except KeyboardInterrupt:
            print("\n👋 Simulator stopped.")
            break


def try_real_reader():
    """Try to connect to a real USB NFC reader. Returns False if not found."""
    try:
        import nfc

        def on_connect(tag):
            uid = tag.identifier.hex().upper()
            print(f"\n📱 Card detected: {uid}")
            send_tap(uid)
            return True

        clf = nfc.ContactlessFrontend('usb')
        print("✅ NFC reader found. Waiting for card tap...")
        while True:
            clf.connect(rdwr={'on-connect': on_connect})
            time.sleep(0.5)
    except Exception:
        return False
    return True


if __name__ == "__main__":
    if not try_real_reader():
        print("⚠️  No NFC reader found. Starting simulator...")
        run_simulator()