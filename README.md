# Quick Start Guide - Attendance System

## Installation Prerequisites

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

## One-Command System Startup

### Option 1: Windows (Easiest)

Double-click:

```
START_SYSTEM.bat
```

### Option 2: Any OS (Recommended)

```bash
python run_system.py
```

### Option 3: PowerShell

```powershell
.\RUN_SYSTEM.ps1
```

---

## What Happens When You Run a Startup Script

1. **Hardhat** starts blockchain node (port 8545)
2. **Smart Contract** deploys to local blockchain (30 seconds)
3. **Flask** starts web server (port 5000)
4. **NFC Listener** starts in simulator mode

Once you see: ✅ **SYSTEM STARTED SUCCESSFULLY!**

Open your browser: **http://localhost:5000**

---

## System Check

Before starting, verify everything is installed:

```bash
python diagnose.py
```

This will check:

- ✓ Python packages (Flask, Web3)
- ✓ Node.js and npm
- ✓ Hardhat smart contract setup
- ✓ All HTML templates and CSS/JS files
- ✓ Port availability (5000, 8545)

---

## Using the System

### Register a Student

1. Click "Register Student" on home page
2. Click "Scan NFC ID"
3. In NFC Listener terminal: type a UID (e.g., `E4A91234`) and press Enter
4. Student registered! Blockchain hash will be displayed

### Mark Attendance

1. Click "Mark Attendance" on home page
2. In NFC Listener terminal: type the student UID to mark attendance
3. Toast notification appears (checks every 3 seconds)
4. Dashboard updates automatically

### View Dashboard

1. Click "Dashboard" to see all registered students
2. Use search to filter by name or NFC ID
3. Click student name to view full attendance history

---

## Troubleshooting

| Issue                      | Solution                                                   |
| -------------------------- | ---------------------------------------------------------- |
| "Port 5000 already in use" | Change port in app.py or kill other Flask process          |
| "npm not found"            | Install Node.js from nodejs.org                            |
| "Flask not found"          | Run: `pip install -r requirements.txt`                     |
| "Module not found" errors  | Run: `python diagnose.py` to check all dependencies        |
| NFC Listener won't start   | Check terminal isn't closed; use NFC tab to test           |
| Contract deploy fails      | Wait longer for Hardhat (30+ seconds) before Flask starts  |
| Hardhat already running    | Kill existing `node` process before running startup script |

---

## File Structure

```
.
├── app.py                          # Flask backend (port 5000)
├── nfc_listener.py                 # NFC simulator/reader process
├── run_system.py                   # Python startup (RECOMMENDED)
├── START_SYSTEM.bat                # Windows startup
├── RUN_SYSTEM.ps1                  # PowerShell startup
├── diagnose.py                     # System diagnostics
├── requirements.txt                # Python dependencies
├── hardhat.config.js               # Blockchain config
├── contracts/
│   └── Attendance.sol              # Smart contract
├── scripts/
│   └── deploy.js                   # Contract deployment
├── templates/
│   ├── base.html                   # Master layout
│   ├── index.html                  # Home page
│   ├── register.html               # Registration page
│   ├── dashboard.html              # Student list
│   └── attendance.html             # History view
└── static/
    ├── css/
    │   ├── style.css               # Core styles
    │   ├── pages.css               # Component styles
    │   └── pages-extra.css         # Utilities
    └── js/
        ├── toast-polling.js        # Real-time notifications
        ├── register.js             # NFC scanning
        └── dashboard.js            # Table filtering
```

---

## API Reference

### Flask Endpoints

| Endpoint                 | Method | Purpose                   |
| ------------------------ | ------ | ------------------------- |
| `/`                      | GET    | Home page                 |
| `/register`              | GET    | Registration page         |
| `/dashboard`             | GET    | Student list              |
| `/attendance/<nfc_id>`   | GET    | Attendance history        |
| `/register/scan`         | POST   | Initiate NFC scan         |
| `/get_scanned_uid`       | GET    | Poll for scanned UID      |
| `/mark_attendance`       | POST   | Record attendance         |
| `/api/attendance/recent` | GET    | Recent events (for toast) |

### Blockchain

- **Network**: Hardhat Local (localhost:8545)
- **Contract**: Attendance.sol at deployed address
- **Functions**: `registerStudent()`, `markAttendance()`, `getAttendance()`

---

## Next Steps

1. Run system startup ✓
2. Open http://localhost:5000
3. Register first student ✓
4. Test NFC scanning ✓
5. View dashboard ✓
6. Check attendance records ✓

**That's it! Your attendance system is ready to use.**

---

_For more detailed information, see `STARTUP_GUIDE.md` and `PROJECT_STRUCTURE.md`_
