# Complete Setup Guide - Windows

## System Requirements

Before starting, ensure you have:

- **Windows 10 or higher** (Windows 11 recommended)
- **8 GB RAM** minimum
- **5 GB disk space** for dependencies and project
- **Administrator access** (for npm global install)
- **Internet connection**

## Prerequisites Installation

### Step 1: Install Node.js

1. Download from: https://nodejs.org/
2. Choose **LTS (Long Term Support)** version
3. Run the installer
4. Check "Add to PATH"
5. Verify installation:
   ```powershell
   node --version
   npm --version
   ```

### Step 2: Install Python

1. Download from: https://www.python.org/downloads/
2. Choose **Python 3.9+**
3. **IMPORTANT:** Check "Add Python to PATH" during installation
4. Verify installation:
   ```powershell
   python --version
   pip --version
   ```

### Step 3: Install Git (Optional but Recommended)

1. Download from: https://git-scm.com/
2. Use default installation options
3. Verify:
   ```powershell
   git --version
   ```

## Project Setup

### Step 1: Open PowerShell or Command Prompt

Press `Win + X`, then select "Windows Terminal" or "PowerShell"

### Step 2: Navigate to Project Directory

```powershell
cd "c:\Users\marclain\Documents\4th year\System\blockchain-nfc-attendance"
```

### Step 3: Install Global Tools

```powershell
npm install -g truffle
npm install -g ganache
```

Wait for completion (this may take 2-3 minutes)

### Step 4: Install Project Dependencies

**Install Node.js packages:**

```powershell
npm install
```

**Install Python packages:**

```powershell
cd backend
pip install -r requirements.txt
cd ..
```

---

## Running the System

### Option A: Manual Setup (Recommended for Understanding)

**Terminal 1 - Start Ganache Blockchain:**

```powershell
ganache --deterministic --accounts 10 --host 0.0.0.0 --port 8545
```

Expected output:

```
Ganache started, available at http://127.0.0.1:8545/
...
Accounts:
(0) 0xd41c057fd1cff8d3ebb689728db6d6cb0409945e
(1) 0x...
...
```

⏰ **Keep this terminal running**

---

**Terminal 2 - Deploy Smart Contract:**

```powershell
cd "c:\Users\marclain\Documents\4th year\System\blockchain-nfc-attendance"
truffle migrate --network development
```

Expected output:

```
Deploying 'Attendance'
   ----------------------
   > contract address:    0x123abc456def...  ← COPY THIS!
```

⚠️ **IMPORTANT:** Copy the contract address (starts with 0x)

---

**Terminal 3 - Configure Environment:**

1. Open `backend\.env` in a text editor
2. Update it with:
   ```
   WEB3_PROVIDER=http://127.0.0.1:8545
   CONTRACT_ADDRESS=0x123abc456def...     ← Paste address from Step 2
   PRIVATE_KEY=0xd41c057fd1cff8d3ebb689728db6d6cb0409945e
   ```
3. Save the file

---

**Terminal 3 - Start Flask Backend:**

```powershell
cd backend
python app.py
```

Expected output:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

⏰ **Keep this terminal running**

---

### Step 5: Access Web Interface

Open your browser and go to:

```
http://localhost:5000
```

---

## First Test

### 1. Register a Student

1. On home page, click "Register Student"
2. Fill in the form:
   - **Wallet Address:** `0xd41c057fd1cff8d3ebb689728db6d6cb0409945e`
   - **Student ID:** `TEST001`
   - **Name:** `Test Student`
   - **NFC ID:** `NFC001`
3. Click "Register"
4. Wait for confirmation

### 2. Mark Attendance

1. Click "View Dashboard"
2. Fill in:
   - **Subject:** `Mathematics`
   - **NFC Tag:** `NFC001`
3. Click "Mark Present"
4. View the record in the table

---

## Troubleshooting

### Problem: "Port 8545 already in use"

**Solution:**

```powershell
# Kill the process on port 8545
netstat -ano | findstr :8545
taskkill /PID <PID> /F

# Or use a different port
ganache --port 8546
```

Then update `WEB3_PROVIDER` in `.env` to `http://127.0.0.1:8546`

---

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution:**

```powershell
cd backend
pip install -r requirements.txt --upgrade
```

---

### Problem: "Contract address not set"

**Solution:**

1. Make sure you copied the address from `truffle migrate`
2. Paste it in `backend\.env` as `CONTRACT_ADDRESS`
3. No quotes needed
4. Restart Flask backend

---

### Problem: "Connection refused to 127.0.0.1:8545"

**Solution:**

1. Check that Ganache is running in Terminal 1
2. Verify it shows "accounts" section
3. If not, restart Ganache

---

### Problem: "Transaction failed"

**Solution:**

1. Check that you're using a Ganache account address
2. Ensure the account has sufficient balance (should have 100 ETH)
3. Check contract address is correct in `.env`

---

## Using the CLI Tool

### Check System Status

```powershell
cd backend
python cli.py status
```

Expected output:

```
📋 System Status

✓ Connected to blockchain
  Provider: http://127.0.0.1:8545
  Latest block: 5
  Gas price: 2 gwei

✓ Contract deployed
  Address: 0x123abc...
  Admin: 0xd41c057...
```

### View Attendance Records

```powershell
python cli.py records 20
```

### Get Student Attendance Count

```powershell
python cli.py attendance TEST001
```

### Create New Account

```powershell
python cli.py create-account
```

---

## Advanced Configuration

### Change Network Port

Edit `.env`:

```
WEB3_PROVIDER=http://127.0.0.1:8546
```

### Use Production Settings

Edit `backend\config.py` and use `ProductionConfig`

### Deploy to Testnet

1. Get Ropsten ETH from faucet
2. Update `truffle-config.js` with Infura key
3. Run: `truffle migrate --network ropsten`

---

## Useful Commands Reference

| Command                                                            | Purpose                 |
| ------------------------------------------------------------------ | ----------------------- |
| `npm install`                                                      | Install Node packages   |
| `pip install -r requirements.txt`                                  | Install Python packages |
| `truffle compile`                                                  | Compile smart contract  |
| `truffle migrate --network development`                            | Deploy contract         |
| `truffle test`                                                     | Run contract tests      |
| `ganache --deterministic --accounts 10 --host 0.0.0.0 --port 8545` | Start blockchain        |
| `python app.py`                                                    | Start Flask server      |
| `python cli.py status`                                             | Check system status     |
| `python cli.py records`                                            | View records            |

---

## Stopping the System

In each terminal window, press `Ctrl + C` to stop the service:

1. **Terminal 1 (Ganache):** `Ctrl + C`
2. **Terminal 2 (Already stopped)**
3. **Terminal 3 (Flask):** `Ctrl + C`

---

## Project Structure Summary

```
📁 blockchain-nfc-attendance/
├─ 📁 contracts/           (Smart contracts)
├─ 📁 migrations/          (Deployment scripts)
├─ 📁 backend/             (Python Flask backend)
│  ├─ app.py              (Main server)
│  ├─ requirements.txt    (Dependencies)
│  └─ .env                (Configuration)
├─ 📁 frontend/            (Web interface)
│  ├─ templates/          (HTML files)
│  └─ static/             (CSS/JavaScript)
├─ 📁 test/               (Tests)
├─ package.json           (Node config)
├─ truffle-config.js      (Truffle config)
└─ README.md              (Documentation)
```

---

## Next Steps

1. ✅ Follow setup guide
2. ✅ Register test students
3. ✅ Mark test attendance
4. ✅ View dashboard analytics
5. ✅ Export attendance records
6. ✅ Explore smart contract in Ganache
7. ✅ Integrate real NFC hardware
8. ✅ Deploy to testnet

---

## Getting Help

1. **Check README.md** for detailed documentation
2. **Check ARCHITECTURE.md** for system design
3. **Check error messages** in Terminal 3 (Flask)
4. **Check Ganache Terminal** (Terminal 1) for blockchain errors
5. **Browser console** (F12) for frontend errors

---

## System Health Check

Verify everything is working:

```powershell
# Check Node.js
node --version

# Check Python
python --version

# Check Truffle
truffle version

# Check npm packages
npm list

# Check Python packages
pip list | findstr flask web3
```

---

## Performance Tips

1. **Keep Ganache running** - Don't restart unless necessary
2. **Use simulation mode** for testing without NFC hardware
3. **Index database table** for faster queries in production
4. **Use pagination** for large record sets
5. **Cache contract ABI** to avoid re-reading

---

## Backup & Recovery

### Backup Important Files

```powershell
# Backup .env with contract address
Copy-Item backend\.env backup_env.txt

# Backup contract deployment address
```

### Recovery

If something goes wrong:

1. Keep a copy of your `.env` file
2. Redeploy contract: `truffle migrate --network development --reset`
3. Update new contract address in `.env`
4. Restart Flask

---

**Setup Complete!** 🎉

You now have a fully functional Blockchain NFC Attendance System running on your local machine.
