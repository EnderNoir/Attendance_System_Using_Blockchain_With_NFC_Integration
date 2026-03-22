import nfc
import requests
import time
import os
import threading

FLASK_URL = "http://localhost:5000"
FLAG_FILE = "registration_mode.flag"
UID_FILE = "scanned_uid.txt"

def on_connect(tag):
    """Called when an NFC tag is touched on a real reader."""
    uid = tag.identifier.hex().upper()
    print(f"\n📱 Tag detected: {uid}")

    # Check if we are waiting for a registration scan
    if os.path.exists(FLAG_FILE):
        with open(FLAG_FILE, 'r') as f:
            mode = f.read().strip()
        if mode == 'waiting':
            # Store the UID and turn off registration mode
            with open(UID_FILE, 'w') as f:
                f.write(uid)
            os.remove(FLAG_FILE)
            print("✅ UID captured for registration.")
            return True

    # Normal attendance
    try:
        requests.post(f"{FLASK_URL}/mark", data={'nfc_id': uid}, timeout=3)
        print("✅ Attendance marked.")
    except Exception as e:
        print(f"❌ Failed to send: {e}")
    return True

def simulator():
    """Simulator – mimics a reader using console input."""
    print("\n=== NFC SIMULATOR ===")
    print("Type a UID (or press Enter for random) and press Enter.")
    print("Type 'exit' to quit.\n")
    while True:
        uid = input("Tap (simulated): ").strip()
        if uid.lower() == 'exit':
            break
        if not uid:
            uid = ''.join(f"{b:02X}" for b in bytes.fromhex('04') + os.urandom(3))
            print(f"Generated UID: {uid}")

        # Same logic as on_connect, but using the same files
        if os.path.exists(FLAG_FILE):
            with open(FLAG_FILE, 'r') as f:
                mode = f.read().strip()
            if mode == 'waiting':
                with open(UID_FILE, 'w') as f:
                    f.write(uid)
                os.remove(FLAG_FILE)
                print("✅ UID captured for registration.")
                continue

        # Normal attendance
        try:
            requests.post(f"{FLASK_URL}/mark", data={'nfc_id': uid}, timeout=2)
            print("✅ Attendance marked (simulated).")
        except Exception as e:
            print(f"❌ Could not reach Flask: {e}")

def try_real_reader():
    """Attempt to connect to a physical NFC reader."""
    try:
        # Try to open the default USB reader
        clf = nfc.ContactlessFrontend('usb')
        print(f"✅ Connected to NFC reader.")
        return clf
    except IOError as e:
        print(f"⚠️  No NFC reader found: {e}")
        return None
    except Exception as e:
        print(f"⚠️  Unexpected error: {e}")
        return None

def nfc_listener():
    """Try real reader; fall back to simulator."""
    # Clean up any stale flag files on startup
    for f in [FLAG_FILE, UID_FILE]:
        if os.path.exists(f):
            os.remove(f)

    clf = try_real_reader()
    if clf is None:
        print("Starting simulator...")
        simulator()
        return

    # Real reader mode
    try:
        while clf.connect(rdwr={'on-connect': on_connect}):
            pass
    except KeyboardInterrupt:
        print("\n👋 Shutting down NFC listener.")
    finally:
        clf.close()

if __name__ == '__main__':
    nfc_listener()