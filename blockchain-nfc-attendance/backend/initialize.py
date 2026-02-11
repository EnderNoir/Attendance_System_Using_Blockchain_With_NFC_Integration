"""
Initialization script for setting up the attendance system
Run this after deploying the contract to set up admin accounts
"""

from web3 import Web3
import json
from dotenv import load_dotenv
import os

load_dotenv()

WEB3_PROVIDER = os.getenv('WEB3_PROVIDER', 'http://127.0.0.1:8545')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))

# Load contract ABI
with open('contract_abi.json', 'r') as abi_file:
    CONTRACT_ABI = json.load(abi_file)

def initialize_system():
    """Initialize the system with sample data"""
    
    if not web3.is_connected():
        print("❌ Not connected to blockchain!")
        return
    
    print("✓ Connected to blockchain")
    
    # Initialize contract
    contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    account = web3.eth.account.from_key(PRIVATE_KEY)
    
    # Sample students to register
    sample_students = [
        {
            'address': '0x8ba1f109551bD432803012645Ac136ddd64DBA72',
            'student_id': 'STU001',
            'name': 'John Doe',
            'nfc_id': 'NFC001'
        },
        {
            'address': '0xaAaAaAaaAaAaAaaAaAAAAAAAAaaaAaAaAaaAaaAa',
            'student_id': 'STU002',
            'name': 'Jane Smith',
            'nfc_id': 'NFC002'
        },
        {
            'address': '0xbBbBBBBbbBBBbbbBbbBbbbbBBBBBBBBBbBbbBBB',
            'student_id': 'STU003',
            'name': 'Bob Johnson',
            'nfc_id': 'NFC003'
        }
    ]
    
    print("\n📝 Registering sample students...")
    
    for student in sample_students:
        try:
            tx = contract.functions.registerStudent(
                student['address'],
                student['student_id'],
                student['name'],
                student['nfc_id']
            ).build_transaction({
                'from': account.address,
                'nonce': web3.eth.get_transaction_count(account.address),
                'gas': 300000,
                'gasPrice': web3.eth.gas_price,
            })
            
            signed_tx = web3.eth.account.sign_transaction(tx, account.key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            print(f"✓ Registered {student['name']} ({student['student_id']})")
            print(f"  NFCId: {student['nfc_id']}")
            print(f"  Tx: {tx_hash.hex()}\n")
            
        except Exception as e:
            print(f"✗ Error registering {student['name']}: {str(e)}\n")
    
    print("✓ System initialization complete!")
    print("\nYou can now:")
    print("1. Go to http://localhost:5000/dashboard")
    print("2. Use these NFC IDs to mark attendance: NFC001, NFC002, NFC003")
    print("3. View records in real-time")

if __name__ == '__main__':
    if not CONTRACT_ADDRESS or CONTRACT_ADDRESS == '0x0':
        print("❌ CONTRACT_ADDRESS not set in .env")
        print("Please deploy the contract first using: truffle migrate")
        exit(1)
    
    initialize_system()
