import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()
rpc_url = os.getenv('SEPOLIA_RPC_URL')
w3 = Web3(Web3.HTTPProvider(rpc_url))

tx_hash = '0x2de1e59131a70ab5ceaeb0661ae21ebb0f1072d22bc0269782ebe44fb4eb9a88'
try:
    tx = w3.eth.get_transaction(tx_hash)
    print("Transaction found!")
    print("Block number:", tx.get('blockNumber'))
    print("From:", tx.get('from'))
    print("To:", tx.get('to'))
except Exception as e:
    print("Error fetching transaction:", e)
