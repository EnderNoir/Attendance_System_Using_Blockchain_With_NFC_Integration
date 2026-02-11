# Blockchain NFC Attendance System

A secure, decentralized attendance tracking system using blockchain, NFC technology, Ganache, and Truffle smart contracts.

## Features

✅ **Blockchain-based**: All attendance records stored immutably on the blockchain
✅ **NFC Technology**: Quick and easy check-in using NFC tags or cards
✅ **Smart Contracts**: Solidity-based contracts for automatic attendance tracking
✅ **Web Dashboard**: Real-time attendance monitoring and analytics
✅ **Python Backend**: Flask-based REST API for blockchain interaction
✅ **Transparent**: All transactions visible and verifiable
✅ **Scalable**: Handles multiple students and attendance records

## System Architecture

```
┌─────────────────────┐
│   Web Browser       │ (HTML/CSS/JavaScript)
├─────────────────────┤
│   Flask Backend     │ (Python)
│   - NFC Reader      │
│   - Web3 Integration│
├─────────────────────┤
│   Ganache Blockchain│ (Local Ethereum)
│   - Attendance      │
│     Smart Contract  │
└─────────────────────┘
```

## Prerequisites

Before you start, make sure you have installed:

- **Node.js** (v14+) and npm
- **Python** (v3.8+) and pip
- **Truffle** (`npm install -g truffle`)
- **Ganache CLI** (`npm install -g ganache`)

## Project Structure

```
blockchain-nfc-attendance/
├── contracts/              # Smart contracts
│   └── Attendance.sol      # Main attendance contract
├── migrations/             # Contract deployment scripts
│   └── 1_initial_migration.js
├── backend/                # Flask backend
│   ├── app.py              # Main Flask application
│   ├── nfc_reader.py       # NFC reader logic
│   ├── contract_abi.json   # Contract ABI
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Environment variables
├── frontend/               # Web interface
│   ├── templates/          # HTML templates
│   │   ├── index.html
│   │   └── dashboard.html
│   └── static/             # CSS and JavaScript
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── main.js
│           └── dashboard.js
├── package.json            # Node.js dependencies
├── truffle-config.js       # Truffle configuration
└── README.md               # This file
```

## Installation & Setup

### Step 1: Clone and Navigate to Project

```bash
cd blockchain-nfc-attendance
```

### Step 2: Install Node.js Dependencies

```bash
npm install
```

### Step 3: Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### Step 4: Start Ganache (Blockchain)

Open a new terminal and run:

```bash
ganache --deterministic --accounts 10 --host 0.0.0.0 --port 8545
```

**Note:** It's recommended to use `--deterministic` with a seed for consistent accounts.

Expected output:

```
ganache v7.8.0 (@ganache/cli: 0.0.1-alpha.0)
Ganache started, available at http://127.0.0.1:8545
```

### Step 5: Deploy Smart Contract

In a new terminal, run:

```bash
truffle migrate --network development
```

**Important:** Copy the deployed contract address from the output. You'll need it for the next step.

Example output:

```
Deploying 'Attendance'
   ----------------------
   > contract address:    0x123abc... ← Copy this
```

### Step 6: Configure Environment Variables

Edit `backend/.env` and update:

```env
WEB3_PROVIDER=http://127.0.0.1:8545
CONTRACT_ADDRESS=0x123abc...        # Paste the contract address from Step 5
PRIVATE_KEY=0xd41c057fd1cff8d3ebb689728db6d6cb0409945e  # Ganache default account
```

### Step 7: Start Flask Backend

In a new terminal:

```bash
cd backend
python app.py
```

Expected output:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### Step 8: Access the Web Interface

Open your browser and navigate to:

```
http://localhost:5000
```

## Usage

### Register a Student

1. Go to home page
2. Click "Register Student"
3. Fill in:
   - **Wallet Address**: Ethereum address (from Ganache accounts)
   - **Student ID**: e.g., `STU001`
   - **Student Name**: Full name
   - **NFC ID**: NFC tag identifier (e.g., `NFC123ABC`)

### Mark Attendance

1. Go to Dashboard
2. Enter subject name
3. Tap NFC tag (or enter NFC ID manually for testing)
4. Click "Mark Present"

### View Records

- All attendance records are displayed in real-time
- Statistics show total records, today's attendance, and active students
- Search specific student by ID
- Export records as CSV

## Testing Without NFC Hardware

For testing without physical NFC hardware:

1. Manually enter NFC IDs in the dashboard input field
2. The system will mark attendance for that NFC ID
3. Use different IDs for different students

## API Endpoints

| Method | Endpoint                              | Description                     |
| ------ | ------------------------------------- | ------------------------------- |
| POST   | `/api/register-student`               | Register a new student          |
| POST   | `/api/mark-attendance`                | Mark attendance via NFC         |
| GET    | `/api/attendance-count/<student_id>`  | Get attendance count            |
| GET    | `/api/student-info/<student_address>` | Get student information         |
| GET    | `/api/all-records`                    | Retrieve all attendance records |
| GET    | `/api/health`                         | System health check             |

## Smart Contract Functions

### Admin Functions

- `registerStudent(address, studentId, name, nfcId)` - Register a new student
- `markAbsence(studentId, subject)` - Mark absence for a student
- `deactivateStudent(address)` - Deactivate a student account

### Public Functions

- `markAttendance(nfcId, subject)` - Mark attendance using NFC ID
- `getStudent(address)` - Get student information
- `getStudentAttendanceCount(studentId)` - Get attendance count
- `getAttendanceRecord(index)` - Get specific record
- `getAttendanceRecordsCount()` - Get total records

## Troubleshooting

### Issue: Connection to Ganache refused

**Solution:**

```bash
# Check if Ganache is running
# If not, start it with:
ganache --deterministic --accounts 10 --host 0.0.0.0 --port 8545
```

### Issue: Contract address not found

**Solution:**

- Redeploy the contract: `truffle migrate --network development --reset`
- Update the contract address in `backend/.env`

### Issue: Transaction failing with "Only admin can call this function"

**Solution:**

- Make sure you're using the first Ganache account (the admin)
- Check that `PRIVATE_KEY` in `.env` matches the first account in Ganache

### Issue: NFC reader not detecting tags

**Solution:**

- For testing, manually enter NFC IDs in the input field
- Install proper drivers for your NFC reader if using hardware
- Check NFC reader connection and permissions

## Running Tests

```bash
truffle test
```

## Deploying to Testnet

### Using Ropsten Testnet

1. Get Ropsten ETH from a faucet
2. Update `truffle-config.js` with Ropsten RPC URL
3. Deploy: `truffle migrate --network ropsten`

## Gas Estimates

- Student Registration: ~100,000 gas
- Mark Attendance: ~80,000 gas
- Get Records: 0 gas (view function)

## Security Considerations

⚠️ **Important:**

- Never share your private keys
- Use a secure wallet for production
- Keep contract address confidential
- Validate all NFC inputs
- Use HTTPS in production

## Future Enhancements

- [ ] Multi-admin support
- [ ] Facial recognition integration
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Attendance reward system
- [ ] Integration with student management systems
- [ ] QR code alternative to NFC
- [ ] Automated alerts for absences

## License

MIT License - Feel free to use for educational and commercial purposes

## Support

For issues or questions:

1. Check the Troubleshooting section
2. Review smart contract logs in Ganache
3. Check browser console for frontend errors
4. Review Flask logs in terminal

## Contributors

- Your Name
- Contributors welcome! Please submit issues and pull requests

## Disclaimer

This is an educational project. For production use:

- Conduct security audit
- Use production-grade blockchain
- Implement proper authentication
- Add rate limiting
- Implement data encryption

---

**Built with:** Solidity, Truffle, Ganache, Flask, Python, JavaScript, Web3.js
