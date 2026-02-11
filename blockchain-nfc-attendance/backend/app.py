from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from web3 import Web3
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from nfc_reader import NFCReader

load_dotenv()

app = Flask(__name__)
CORS(app)

# Web3 Setup
WEB3_PROVIDER = os.getenv('WEB3_PROVIDER', 'http://127.0.0.1:8545')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '0x0')
PRIVATE_KEY = os.getenv('PRIVATE_KEY', '')

web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))

# Load contract ABI
with open('contract_abi.json', 'r') as abi_file:
    CONTRACT_ABI = json.load(abi_file)

# Initialize contract
contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

# NFC Reader instance
nfc_reader = NFCReader()

class AttendanceSystem:
    def __init__(self):
        self.web3 = web3
        self.contract = contract
        self.account = None
        self.nfc_reader = nfc_reader
        
    def set_account(self, private_key):
        """Set the account for transactions"""
        self.account = self.web3.eth.account.from_key(private_key)
        
    def register_student(self, student_address, student_id, name, nfc_id):
        """Register a new student on the blockchain"""
        try:
            tx = self.contract.functions.registerStudent(
                student_address,
                student_id,
                name,
                nfc_id
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 300000,
                'gasPrice': self.web3.eth.gas_price,
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'success': True,
                'transaction_hash': tx_hash.hex(),
                'message': f'Student {name} registered successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def mark_attendance(self, nfc_id, subject):
        """Mark attendance using NFC ID"""
        try:
            tx = self.contract.functions.markAttendance(
                nfc_id,
                subject
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.web3.eth.gas_price,
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'success': True,
                'transaction_hash': tx_hash.hex(),
                'message': 'Attendance marked successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_attendance_count(self, student_id):
        """Get attendance count for a student"""
        try:
            count = self.contract.functions.getStudentAttendanceCount(student_id).call()
            return {
                'success': True,
                'attendance_count': count
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_student_info(self, student_address):
        """Get student information"""
        try:
            student = self.contract.functions.getStudent(student_address).call()
            return {
                'success': True,
                'student_id': student[0],
                'name': student[1],
                'nfc_id': student[2],
                'is_active': student[3]
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_all_attendance_records(self):
        """Retrieve all attendance records"""
        try:
            count = self.contract.functions.getAttendanceRecordsCount().call()
            records = []
            for i in range(count):
                record = self.contract.functions.getAttendanceRecord(i).call()
                records.append({
                    'student_id': record[0],
                    'timestamp': record[1],
                    'subject': record[2],
                    'is_present': record[3],
                    'datetime': datetime.fromtimestamp(record[1]).strftime('%Y-%m-%d %H:%M:%S')
                })
            return {
                'success': True,
                'records': records
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }

# Initialize attendance system
attendance_system = AttendanceSystem()

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/register-student', methods=['POST'])
def register_student():
    """Register a new student"""
    data = request.json
    attendance_system.set_account(PRIVATE_KEY)
    result = attendance_system.register_student(
        data['student_address'],
        data['student_id'],
        data['name'],
        data['nfc_id']
    )
    return jsonify(result)

@app.route('/api/mark-attendance', methods=['POST'])
def mark_attendance():
    """Mark attendance via NFC"""
    data = request.json
    attendance_system.set_account(PRIVATE_KEY)
    result = attendance_system.mark_attendance(
        data['nfc_id'],
        data['subject']
    )
    return jsonify(result)

@app.route('/api/attendance-count/<student_id>', methods=['GET'])
def attendance_count(student_id):
    """Get attendance count for a student"""
    result = attendance_system.get_attendance_count(student_id)
    return jsonify(result)

@app.route('/api/student-info/<student_address>', methods=['GET'])
def student_info(student_address):
    """Get student information"""
    result = attendance_system.get_student_info(student_address)
    return jsonify(result)

@app.route('/api/all-records', methods=['GET'])
def all_records():
    """Get all attendance records"""
    result = attendance_system.get_all_attendance_records()
    return jsonify(result)

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    try:
        is_connected = web3.is_connected()
        return jsonify({
            'status': 'healthy' if is_connected else 'unhealthy',
            'web3_connected': is_connected,
            'contract_address': CONTRACT_ADDRESS
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
