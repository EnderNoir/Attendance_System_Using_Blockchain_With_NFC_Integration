"""
Optional utility module for advanced blockchain interactions
"""

from web3 import Web3
from eth_account import Account
import json

class BlockchainUtils:
    """Utility functions for blockchain operations"""
    
    @staticmethod
    def create_account():
        """Create a new Ethereum account"""
        account = Account.create()
        return {
            'address': account.address,
            'private_key': account.key.hex(),
            'public_key': account.key.public_key.to_checksum_address()
        }
    
    @staticmethod
    def validate_address(address):
        """Validate if address is a valid Ethereum address"""
        return Web3.is_address(address)
    
    @staticmethod
    def validate_private_key(private_key):
        """Validate if private key is valid"""
        try:
            Account.from_key(private_key)
            return True
        except:
            return False
    
    @staticmethod
    def get_checksum_address(address):
        """Convert address to checksum address"""
        return Web3.to_checksum_address(address)
    
    @staticmethod
    def calculate_gas_cost(gas_used, gas_price_in_gwei):
        """Calculate transaction cost in ETH"""
        gas_price_wei = Web3.to_wei(gas_price_in_gwei, 'gwei')
        cost_wei = gas_used * gas_price_wei
        cost_eth = Web3.from_wei(cost_wei, 'ether')
        return cost_eth

class NFCUtilities:
    """NFC-related utilities"""
    
    @staticmethod
    def generate_nfc_id(prefix='NFC'):
        """Generate a unique NFC ID"""
        import uuid
        uid = str(uuid.uuid4()).replace('-', '')[:8]
        return f"{prefix}{uid.upper()}"
    
    @staticmethod
    def validate_nfc_id(nfc_id):
        """Validate NFC ID format"""
        if not nfc_id or len(nfc_id) < 4:
            return False
        return True

class DataFormatter:
    """Format data for display and storage"""
    
    @staticmethod
    def format_timestamp(timestamp):
        """Convert Unix timestamp to readable format"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    @staticmethod
    def format_address(address, short=True):
        """Format Ethereum address"""
        if short:
            return f"{address[:6]}...{address[-4:]}"
        return address
    
    @staticmethod
    def format_transaction_hash(tx_hash, short=True):
        """Format transaction hash"""
        if short:
            return f"{tx_hash[:10]}...{tx_hash[-6:]}"
        return tx_hash
    
    @staticmethod
    def attendance_report(records):
        """Generate attendance report from records"""
        if not records:
            return {'total': 0, 'present': 0, 'absent': 0}
        
        total = len(records)
        present = sum(1 for r in records if r.get('is_present', False))
        absent = total - present
        
        return {
            'total': total,
            'present': present,
            'absent': absent,
            'percentage': round((present / total) * 100, 2) if total > 0 else 0
        }
