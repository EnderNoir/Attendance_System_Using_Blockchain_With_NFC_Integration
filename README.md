## Overview

An innovative attendance tracking system that combines **blockchain technology** with **NFC (Near Field Communication)** for secure, transparent, and tamper-proof attendance management. This system leverages the immutability of blockchain to create an unforgeable attendance record while using NFC cards for seamless, contactless check-in/check-out operations.

## Features

✨ **Key Capabilities:**

- 🔐 **Blockchain-Based Records**: Immutable attendance logs stored on blockchain
- 📱 **NFC Integration**: Contactless attendance marking using NFC cards
- 🔒 **Security**: Cryptographic verification and tamper-proof records
- 📊 **Real-time Tracking**: Instant attendance updates and status monitoring
- 🎓 **Educational/Enterprise Ready**: Suitable for schools, universities, and organizations
- 📈 **Analytics Dashboard**: Visual reports and attendance analytics
- ⚡ **Smart Contracts**: Ethereum-based smart contracts for attendance validation

## Technology Stack

| Technology | Purpose | Percentage |
|-----------|---------|-----------|
| **HTML** | Frontend Structure | 53.6% |
| **CSS** | Styling & UI Design | 19.8% |
| **Python** | Backend Logic & Processing | 13.1% |
| **JavaScript** | Frontend Interactivity | 10.4% |
| **Solidity** | Smart Contracts (Blockchain) | 3.1% |

### Prerequisites

- Python 3.8+
- Node.js & npm
- PostgreSQL 14+
- Ethereum wallet (MetaMask or similar)
- NFC Reader/Writer compatible hardware
- Web browser (Chrome, Firefox, Safari, Edge)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/EnderNoir/Attendance_System_Using_Blockchain_With_NFC_Integration.git
cd Attendance_System_Using_Blockchain_With_NFC_Integration
```

### 2. Backend Setup (Python)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Required for PostgreSQL driver
pip install psycopg2-binary
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/davs
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID
BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID
ADMIN_PRIVATE_KEY=0xYOUR_WALLET_PRIVATE_KEY
```

### 3. Smart Contracts (Solidity)

```bash
# Install project dependencies
npm install

# Compile contract
npx hardhat compile

# Deploy to Sepolia and generate attendance-contract.json
npx hardhat run scripts/deploy.js --network sepolia
```

### 4. Start the App

```bash
python app.py
```

## Usage

### Marking Attendance

1. **NFC Card Registration**: Register user NFC cards in the system
2. **Check-in**: Tap NFC card on the reader to check in
3. **Blockchain Recording**: Attendance is automatically recorded on blockchain
4. **Verification**: View attendance records with blockchain verification

### Admin Dashboard

- View real-time attendance status
- Generate attendance reports
- Manage NFC card assignments
- View blockchain transaction history

## Architecture

```
NFC Reader → Python Backend → Smart Contract → Blockchain
                ↓
           Web Dashboard (HTML/CSS/JS)
```

## How It Works

1. **NFC Scanning**: User taps NFC card on the reader
2. **Backend Processing**: Python backend validates the card and user
3. **Smart Contract Execution**: Attendance data is submitted to Ethereum smart contract
4. **Blockchain Recording**: Transaction is mined and permanently recorded
5. **Dashboard Update**: Frontend displays updated attendance status

## Security Features

- ✅ Blockchain immutability prevents record tampering
- ✅ Cryptographic hashing of attendance data
- ✅ NFC authentication prevents spoofing
- ✅ Smart contract auditing
- ✅ Role-based access control

## Configuration

Configure the environment variables in `.env`:

```python
# PostgreSQL
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/davs"

# Ethereum Sepolia
SEPOLIA_RPC_URL = "https://sepolia.infura.io/v3/..."
BLOCKCHAIN_RPC_URL = "https://sepolia.infura.io/v3/..."
ADMIN_PRIVATE_KEY = "0x..."

# NFC Reader settings
NFC_PORT = "/dev/ttyUSB0"
NFC_BAUDRATE = 9600

# System settings
INSTITUTION_NAME = "Your Institution"
BLOCKCHAIN_NETWORK = "sepolia"
```

## API Endpoints

### Check-in Endpoint
```
POST /api/attendance/checkin
Content-Type: application/json

{
  "nfc_id": "card_identifier",
  "user_id": "user_123"
}
```

### Get Attendance Records
```
GET /api/attendance/records?user_id=user_123&date=2026-03-05
```

### View Blockchain Transaction
```
GET /api/blockchain/transaction/:tx_hash
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact & Support

- **Author**: EnderNoir
- **Repository**: [GitHub Repository](https://github.com/EnderNoir/Attendance_System_Using_Blockchain_With_NFC_Integration)
- **Issues**: Please report bugs and feature requests via GitHub Issues

## Acknowledgments

- Ethereum & Solidity community
- NFC technology providers
- Open-source libraries and frameworks used in this project

---

**⭐ If you find this project helpful, please consider giving it a star!**

```

