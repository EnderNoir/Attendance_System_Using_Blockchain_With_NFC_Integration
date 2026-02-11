from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from web3 import Web3
from datetime import datetime
import json
import os
import secrets
import time
from collections import deque

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# --- 1. Connect to Ganache ---
ganache_url = "http://127.0.0.1:8545"  # or 7545 – adjust to your Ganache port
web3 = Web3(Web3.HTTPProvider(ganache_url))
if not web3.is_connected():
    raise Exception("❌ Cannot connect to Ganache. Make sure it's running on " + ganache_url)
print("✅ Connected to Ganache")

# --- 2. Load contract ABI from Truffle build artifact ---
contract_json_path = os.path.join(os.path.dirname(__file__), 'build', 'contracts', 'Attendance.json')
try:
    with open(contract_json_path) as f:
        contract_json = json.load(f)
        abi = contract_json['abi']
    print("✅ Contract ABI loaded")
except FileNotFoundError:
    raise Exception("❌ Attendance.json not found. Run 'truffle compile' first.")

# --- 3. Contract address (from truffle migrate) ---
contract_address = "0x40df75DEB8090260640a7B0AeFcbF36B2d63F1d3"   # <-- YOUR CONTRACT ADDRESS

# --- 4. Create contract instance ---
contract = web3.eth.contract(address=contract_address, abi=abi)
print(f"✅ Contract instance created at {contract_address}")

# --- 5. Admin account (first Ganache account) ---
admin_account = web3.eth.accounts[0]
print(f"✅ Admin account: {admin_account}")

# ============= STUDENT TRACKING (for toasts) =============
student_name_map = {}

def load_student_names():
    """Load all registered students from blockchain events."""
    try:
        latest = web3.eth.block_number
        event_filter = contract.events.StudentRegistered.create_filter(
            fromBlock=0,
            toBlock=latest
        )
        entries = event_filter.get_all_entries()
        for e in entries:
            args = e['args']
            student_name_map[args['nfcId']] = args['name']
        print(f"✅ Loaded {len(student_name_map)} students.")
    except Exception as e:
        print(f"⚠️ Could not load students: {e}")

load_student_names()

# --- Recent attendance (last 20 taps) ---
recent_attendance = deque(maxlen=20)

# ============= ROUTES =============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nfc_id = request.form['nfc_id']
        name = request.form['name']

        # Generate a unique Ethereum address for the student
        private_key = "0x" + secrets.token_hex(32)
        account = web3.eth.account.from_key(private_key)
        student_address = account.address

        try:
            # Send transaction from admin account
            tx_hash = contract.functions.registerStudent(
                student_address, nfc_id, name
            ).transact({'from': admin_account})
            web3.eth.wait_for_transaction_receipt(tx_hash)

            # Add to name map immediately (so toasts work right away)
            student_name_map[nfc_id] = name

            flash(f'✅ Student {name} registered with address {student_address}')
        except Exception as e:
            if 'already used' in str(e) or 'NFC ID already registered' in str(e):
                flash(f'❌ This NFC ID is already registered.')
            else:
                flash(f'❌ Registration failed: {str(e)}')
        
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/mark', methods=['POST'])
def mark():
    """Called by NFC listener when a card is tapped."""
    nfc_id = request.form['nfc_id']
    try:
        tx_hash = contract.functions.markAttendance(nfc_id).transact({'from': admin_account})
        web3.eth.wait_for_transaction_receipt(tx_hash)

        # Get student name (fallback to "Unknown")
        name = student_name_map.get(nfc_id, "Unknown")
        
        # Store for toast notifications
        recent_attendance.append({
            'nfc_id': nfc_id,
            'name': name,
            'timestamp': time.time()
        })

        flash(f'✅ Attendance marked for {name}')
    except Exception as e:
        flash(f'❌ Error: {str(e)}')
    return redirect(url_for('index'))

@app.route('/api/attendance/recent')
def recent_attendance_api():
    """API endpoint for toast polling."""
    since = request.args.get('since', type=float, default=0)
    events = [e for e in recent_attendance if e['timestamp'] > since]
    return jsonify(events)

@app.route('/view/<nfc_id>')
def view_attendance(nfc_id):
    """View attendance history for a given NFC ID."""
    try:
        timestamps, present = contract.functions.getAttendance(nfc_id).call()
        records = []
        for ts, p in zip(timestamps, present):
            dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            records.append((dt, p))
    except Exception as e:
        flash(f'❌ Could not fetch attendance: {str(e)}')
        records = []
    return render_template('attendance.html', nfc_id=nfc_id, records=records)

@app.route('/dashboard')
def dashboard():
    """Display all registered students with search."""
    try:
        latest_block = web3.eth.block_number
        event_filter = contract.events.StudentRegistered.create_filter(
            from_block=0,
            to_block=latest_block
        )
        entries = event_filter.get_all_entries()
    except Exception as e:
        flash(f'❌ Could not load student list: {str(e)}')
        entries = []
    
    students = []
    for entry in entries:
        args = entry['args']
        students.append({
            'name': args['name'],
            'nfcId': args['nfcId'],
            'address': args['studentAddr'],
            'tx_hash': entry['transactionHash'].hex()
        })
    
    # Remove duplicates (shouldn't happen, but safe)
    unique_students = {s['nfcId']: s for s in students}.values()
    return render_template('dashboard.html', students=list(unique_students))

# ============= NFC REGISTRATION HELPERS (file‑based) =============
FLAG_FILE = "registration_mode.flag"
UID_FILE = "scanned_uid.txt"

@app.route('/request_registration_scan', methods=['POST'])
def request_registration_scan():
    """Tell the NFC listener that the next scan is for registration."""
    try:
        if os.path.exists(UID_FILE):
            os.remove(UID_FILE)
        with open(FLAG_FILE, 'w') as f:
            f.write('waiting')
        return jsonify({'status': 'ready'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_scanned_uid', methods=['GET'])
def get_scanned_uid():
    """Retrieve the UID captured by the NFC listener."""
    if os.path.exists(UID_FILE):
        with open(UID_FILE, 'r') as f:
            uid = f.read().strip()
        os.remove(UID_FILE)   # consume it
        return jsonify({'uid': uid})
    return jsonify({'uid': None})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)