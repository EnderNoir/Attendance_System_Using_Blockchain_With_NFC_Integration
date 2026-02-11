# Quick Start Guide for Blockchain NFC Attendance System

## Windows Setup (PowerShell or CMD)

### 1. Prerequisites

- Node.js: https://nodejs.org (LTS version)
- Python: https://www.python.org (3.8+)
- Git: https://git-scm.com

### 2. Install Global Tools

```bash
npm install -g truffle
npm install -g ganache
```

### 3. Navigate to Project

```bash
cd "c:\Users\marclain\Documents\4th year\System\blockchain-nfc-attendance"
```

### 4. Install Dependencies

**Terminal 1 - Install Node Packages:**

```bash
npm install
```

**Terminal 1 - Install Python Packages:**

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 5. Start Services

**Terminal 1 - Start Ganache (Keep running):**

```bash
ganache --deterministic --accounts 10 --host 0.0.0.0 --port 8545
```

**Terminal 2 - Deploy Smart Contract:**

```bash
cd "c:\Users\marclain\Documents\4th year\System\blockchain-nfc-attendance"
truffle migrate --network development
```

⚠️ **IMPORTANT:** Copy the contract address from output!

**Terminal 3 - Configure .env:**

1. Open `backend\.env`
2. Paste the contract address:
   ```
   CONTRACT_ADDRESS=0x<paste_address_here>
   ```
3. Save the file

**Terminal 3 - Start Flask Backend:**

```bash
cd backend
python app.py
```

### 6. Access Web Interface

```
http://localhost:5000
```

## Quick Test

1. On home page → Click "Register Student"
2. Fill form:
   - Address: `0xd41c057fd1cff8d3ebb689728db6d6cb0409945e`
   - Student ID: `TEST001`
   - Name: `Test Student`
   - NFC ID: `NFC001`
3. Click Dashboard
4. Subject: `Math` → NFC: `NFC001` → Mark Present

## Troubleshooting

| Problem                       | Solution                                             |
| ----------------------------- | ---------------------------------------------------- |
| Port 8545 already in use      | Change port in Ganache: `ganache --port 8546`        |
| Module not found (Python)     | Run: `pip install -r requirements.txt`               |
| Contract not found (Solidity) | Run: `truffle migrate --network development --reset` |
| Connection refused            | Make sure Ganache is running on Terminal 1           |

## Ganache Default Accounts

The first 10 accounts (with --deterministic flag):

1. Address: `0xd41c057fd1cff8d3ebb689728db6d6cb0409945e`
   Key: `0xd41c057fd1cff8d3ebb689728db6d6cb0409945e` (for testing only!)

2-10: Check Ganache output terminal

## Next Steps

- Register multiple students
- Mark attendance for different subjects
- View dashboard analytics
- Export attendance records
- Integrate real NFC hardware

## File Locations

```
c:\Users\marclain\Documents\4th year\System\blockchain-nfc-attendance\
├── Smart Contract: contracts\Attendance.sol
├── Flask App: backend\app.py
├── Web UI: frontend\templates\index.html
├── Config: backend\.env
└── README: README.md
```

## Important Commands

```bash
# Compile contract
truffle compile

# Deploy contract
truffle migrate --network development

# Reset deployment
truffle migrate --network development --reset

# Start Flask
python app.py

# View Python environment
pip list

# Stop services
# Press Ctrl+C in each terminal
```

---

**Need Help?** Check README.md for detailed documentation
