# Blockchain Attendance Recording Feature - Implementation Guide

## Overview
This document outlines the blockchain attendance recording feature that records complete session attendance data to the Sepolia blockchain with one transaction per session.

## Completed Implementations

### 1. ✅ Smart Contract Updates (Attendance.sol)
- Added `SessionRecord` struct to store complete session data
- Added `sessionRecords` mapping to store sessions by ID
- Added `recordSession()` function to record entire session with all student statuses
- Added `getSession()` to retrieve session records
- Added `getAllSessionIds()` and `getSessionCount()` functions
- New event: `SessionRecorded` emitted when session is recorded on-chain

**Key Contract Functions:**
```solidity
function recordSession(
    string _sessionId,
    string _subjectName, 
    string _teacherName,
    uint256 _startTime,
    uint256 _endTime,
    string[] _studentNfcIds,
    uint8[] _studentStatuses
)
```

### 2. ✅ Database Schema (app.py)
Added two new columns to `sessions` table:
- `session_tx_hash` (TEXT): Stores the transaction hash when session is recorded
- `session_block_number` (INTEGER): Stores the block number where session was recorded

### 3. ✅ Blockchain Integration (app.py)
Added `record_session_on_chain()` function that:
- Converts status labels to blockchain status codes
- Calls the smart contract's `recordSession()` method
- Waits for transaction receipt
- Returns transaction hash and block number

### 4. ✅ Session Finalization Enhancement
Modified `_prepare_session_blockchain_data()` to:
- Collect all student records for a session
- Convert timestamps to Unix format
- Call `record_session_on_chain()` when session ends
- Store transaction hash in database
- Log full session blockchain data

### 5. ✅ Email System Integration
Updated `send_teacher_session_summary()` to:
- Accept `session_tx_hash` and `session_block_number` parameters
- Display session blockchain record with link to Sepolia explorer
- Show transaction hash and block number in email

## Manual Next Steps Required

### Step 1: Deploy Updated Smart Contract
```bash
npx hardhat run scripts/deploy.js --network sepolia
```
This will:
- Deploy the updated Attendance contract with new session recording features
- Update `attendance-contract.json` with new contract address
- Ensure the system uses the latest contract ABI

### Step 2: Access Points for Transaction Hash Display

#### A. Attendance Records Page (`/attendance_report`)
**File:** `templates/attendance_report.html`
**Required Changes:**
```html
<!-- Add column to attendance table -->
<th>Blockchain TX</th>
<td>
  <a href="https://sepolia.etherscan.io/tx/{tx_hash}" 
     target="_blank" 
     style="color:#2D6A27;text-decoration:none;">
    {tx_hash[:16]}...
  </a>
</td>
```

#### B. Classroom Sessions Page (`/session_live`)
**File:** `templates/session_live.html`  
**Required Changes:**
- Add section showing session transaction hash
- Display link to blockchain explorer
- Show verification status

**Example HTML:**
```html
<div id="sessionBlockchainInfo" style="display:none;">
  <div style="background:#E8F5E9;padding:16px;border-radius:8px;margin-top:16px;">
    <h4 style="color:#2D6A27;margin-top:0;">Blockchain Record</h4>
    <div>
      <strong>Transaction Hash:</strong><br/>
      <code id="sessionTxHash"></code>
    </div>
    <div style="margin-top:8px;">
      <a id="explorerLink" href="#" target="_blank" style="color:#2D6A27;">
        View on Blockchain Explorer
      </a>
    </div>
  </div>
</div>
```

**JavaScript to populate:**
```javascript
fetch(`/api/session/${sessionId}`)
  .then(r => r.json())
  .then(data => {
    if (data.session_tx_hash) {
      document.getElementById('sessionTxHash').textContent = data.session_tx_hash;
      document.getElementById('explorerLink').href = 
        `https://sepolia.etherscan.io/tx/${data.session_tx_hash}`;
      document.getElementById('sessionBlockchainInfo').style.display = 'block';
    }
  });
```

#### C. Excel Exports
**Files to Update:**
- `services/export_attendance_routes.py`
- `services/export_stats_xlsx_service.py`

**Changes:**
Add columns to exports:
- Session Transaction Hash
- Session Block Number

```python
# In export function
worksheet.write(row, col, session_tx_hash, style)
worksheet.write(row, col+1, session_block_number, style)
```

### Step 3: Create Blockchain Verification Endpoint

**Add to app.py:**
```python
@app.route('/api/blockchain/verify/<tx_hash>')
@admin_or_teacher_required
def verify_transaction(tx_hash):
    """Verify a transaction on the blockchain and return session data."""
    try:
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        if not receipt:
            return {'verified': False, 'error': 'Transaction not found'}, 404
        
        # Decode transaction data if needed
        return {
            'verified': True,
            'tx_hash': receipt['transactionHash'].hex(),
            'block_number': receipt['blockNumber'],
            'block_timestamp': web3.eth.get_block(receipt['blockNumber'])['timestamp'],
            'gas_used': receipt['gasUsed'],
            'status': receipt['status'],  # 1 = success
            'explorer_url': f'https://sepolia.etherscan.io/tx/{tx_hash}'
        }
    except Exception as e:
        return {'verified': False, 'error': str(e)}, 500
```

### Step 4: Display Session TX Hash in API Endpoints

**Update endpoints to return session_tx_hash:**
- `/api/session/<sess_id>`
- `/api/attendance/records`
- Any endpoint that returns session data

**Example:**
```python
with get_db() as conn:
    sess = conn.execute(
        "SELECT ... session_tx_hash, session_block_number FROM sessions WHERE sess_id=?",
        (sess_id,)
    ).fetchone()
```

## Data Flow

1. **Session Starts:** Teacher creates live attendance session
2. **Students Check In:** NFC taps recorded to database and blockchain (individual records)
3. **Session Ends:** `_finalize_session()` called
4. **Blockchain Recording:** `_prepare_session_blockchain_data()` runs:
   - Collects all student records
   - Calls `record_session_on_chain()` 
   - Stores transaction hash in database
5. **Emails Sent:** Teacher receives summary with:
   - Individual student TX hashes
   - Session TX hash with Sepolia link
6. **Display:** Transaction hashes visible in:
   - Attendance records page
   - Session details
   - Excel exports
   - Blockchain explorer (publicly searchable)

## Sepolia Blockchain Explorer

View recorded sessions at: `https://sepolia.etherscan.io/`

Example search:
- TX Hash: Copy from email or UI
- Contract: `0x...` (contract address from attendance-contract.json)

## Testing

1. Deploy new contract
2. Restart Flask app
3. Create a live session with test students
4. End session - watch for blockchain transaction
5. Check email for transaction hash
6. Click link in email to verify on Sepolia explorer
7. Verify transaction contains session data

## Immutability & Security

- All session attendance records immutable once recorded
- Timestamp prevents tampering with session times
- Teacher name and subject locked in transaction
- Individual student statuses cannot be modified
- All data publicly verifiable on Sepolia blockchain

## Next Phase: Full Integration

For complete implementation:
1. Update all HTML templates to display TX hashes
2. Add TX hash columns to Excel exports
3. Create transaction search/verification page
4. Add blockchain status indicators to UI
5. Implement automated verification checks
