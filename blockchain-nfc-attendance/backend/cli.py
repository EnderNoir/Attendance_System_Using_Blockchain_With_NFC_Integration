"""
CLI Tool for managing blockchain NFC attendance system
Usage: python cli.py [command] [arguments]
"""

import sys
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import os

load_dotenv()

WEB3_PROVIDER = os.getenv('WEB3_PROVIDER', 'http://127.0.0.1:8545')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))

# Load contract ABI
try:
    with open('contract_abi.json', 'r') as abi_file:
        CONTRACT_ABI = json.load(abi_file)
    contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
except:
    contract = None

class CLI:
    """Command Line Interface for Attendance System"""
    
    @staticmethod
    def check_blockchain():
        """Check blockchain connection"""
        if web3.is_connected():
            print("✓ Connected to blockchain")
            print(f"  Provider: {WEB3_PROVIDER}")
            try:
                block = web3.eth.get_block('latest')
                print(f"  Latest block: {block.number}")
                print(f"  Gas price: {web3.from_wei(web3.eth.gas_price, 'gwei')} gwei")
            except:
                pass
        else:
            print("✗ Not connected to blockchain")
            return False
        return True
    
    @staticmethod
    def check_contract():
        """Check contract deployment"""
        if not CONTRACT_ADDRESS or CONTRACT_ADDRESS == '0x0':
            print("✗ Contract address not set in .env")
            return False
        
        try:
            # Check if contract has code
            code = web3.eth.get_code(CONTRACT_ADDRESS)
            if code == b'':
                print("✗ No contract found at address")
                return False
            
            print("✓ Contract deployed")
            print(f"  Address: {CONTRACT_ADDRESS}")
            
            # Try to get admin
            admin = contract.functions.admin().call()
            print(f"  Admin: {admin}")
            
        except Exception as e:
            print(f"✗ Error checking contract: {e}")
            return False
        
        return True
    
    @staticmethod
    def list_records(limit=10):
        """List attendance records"""
        try:
            count = contract.functions.getAttendanceRecordsCount().call()
            print(f"Total records: {count}\n")
            
            start = max(0, count - limit)
            for i in range(start, count):
                record = contract.functions.getAttendanceRecord(i).call()
                student_id, timestamp, subject, is_present = record
                status = "✓ Present" if is_present else "✗ Absent"
                print(f"[{i}] {student_id} - {subject} - {status}")
        
        except Exception as e:
            print(f"✗ Error: {e}")
    
    @staticmethod
    def get_student_attendance(student_id):
        """Get attendance count for a student"""
        try:
            count = contract.functions.getStudentAttendanceCount(student_id).call()
            print(f"Student {student_id}: {count} present")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    @staticmethod
    def help():
        """Show help information"""
        print("""
╔════════════════════════════════════════════════════════════════╗
║        Blockchain NFC Attendance System - CLI Tool             ║
╚════════════════════════════════════════════════════════════════╝

Commands:
  status              - Check blockchain and contract status
  records [limit]     - List attendance records (default: 10)
  attendance [sid]    - Get attendance count for student
  create-account      - Create a new Ethereum account
  help                - Show this help message

Examples:
  python cli.py status
  python cli.py records 20
  python cli.py attendance STU001
  python cli.py create-account

Configuration:
  Update backend\.env with:
  - WEB3_PROVIDER: Blockchain RPC URL
  - CONTRACT_ADDRESS: Deployed contract address
  - PRIVATE_KEY: Private key for transactions

        """)
    
    @staticmethod
    def create_account():
        """Create new account"""
        from eth_account import Account
        account = Account.create()
        print("\n✓ New account created (SAVE THIS SAFELY!):")
        print(f"  Address:     {account.address}")
        print(f"  Private Key: {account.key.hex()}")
        print("\n⚠️  NEVER share your private key!\n")

def main():
    """Main CLI handler"""
    if len(sys.argv) < 2:
        CLI.help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        print("\n📋 System Status\n")
        if CLI.check_blockchain():
            print()
            CLI.check_contract()
        print()
    
    elif command == 'records':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(f"\n📊 Latest {limit} Attendance Records\n")
        CLI.list_records(limit)
        print()
    
    elif command == 'attendance':
        if len(sys.argv) < 3:
            print("Usage: python cli.py attendance [student_id]")
            return
        CLI.get_student_attendance(sys.argv[2])
        print()
    
    elif command == 'create-account':
        CLI.create_account()
    
    elif command == 'help' or command == '-h' or command == '--help':
        CLI.help()
    
    else:
        print(f"✗ Unknown command: {command}")
        print("Use 'python cli.py help' for available commands")

if __name__ == '__main__':
    main()
