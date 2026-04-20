# HEROKU DEPLOYMENT GUIDE

# Attendance System - Blockchain + NFC

## Step 1: Prerequisites

- Heroku CLI installed (https://devcenter.heroku.com/articles/heroku-cli)
- Git installed
- GitHub account (optional but recommended)
- Infura account for Sepolia testnet (https://infura.io)

## Step 2: Prepare Your Project

```bash
# Navigate to your project directory
cd c:\path\to\your\System

# If not already a git repository, initialize it
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Blockchain attendance system"
```

## Step 3: Deploy Smart Contracts to Sepolia Testnet

```bash
# Install Hardhat dependencies
npm install

# Compile contracts
npx hardhat compile

# Deploy to Sepolia (requires .env with SEPOLIA_RPC_URL and PRIVATE_KEY)
npx hardhat run scripts/deploy.js --network sepolia

# Save the deployed contract address - you'll need it later!
```

## Step 4: Set Up Heroku

```bash
# Log in to Heroku
heroku login

# Create a new Heroku app
heroku create your-app-name

# Or if app already exists:
heroku apps:create your-app-name
```

## Step 5: Configure Environment Variables

```bash
# Set production environment variables on Heroku
heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=your-super-secret-key-here
heroku config:set WEB3_PROVIDER_URI=https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID
heroku config:set ATTENDANCE_CONTRACT_ADDRESS=0x...  # From step 3
heroku config:set PRIVATE_KEY=your-wallet-private-key
heroku config:set SMTP_SERVER=smtp.gmail.com
heroku config:set SMTP_PORT=587
heroku config:set SMTP_USER=your-email@gmail.com
heroku config:set SMTP_PASSWORD=your-app-password

# View all config vars
heroku config
```

## Step 6: Deploy to Heroku

```bash
# Push code to Heroku
git push heroku main  # or master depending on your branch

# View logs in real-time
heroku logs --tail
```

## Step 7: Run Database Migrations (if needed)

```bash
# Run migration script
heroku run python migrate_db.py

# Or seed dummy data
heroku run python seed_dummy_data.py
```

## Step 8: Verify Deployment

```bash
# Open your app in browser
heroku open

# Check app status
heroku ps

# View logs for errors
heroku logs
```

## Troubleshooting

### App won't start

```bash
# Check logs for errors
heroku logs --tail

# Restart the app
heroku restart
```

### Database issues

```bash
# Check database connection
heroku run python -c "import sqlite3; print('DB OK')"
```

### Web3 connection issues

- Verify INFURA_PROJECT_ID is correct
- Check contract address is deployed on Sepolia testnet
- Confirm private key has test ETH for transactions

## Production Considerations

1. Replace SQLite with PostgreSQL for production:

   ```bash
   heroku addons:create heroku-postgresql:hobby-dev
   ```

2. Enable HTTPS (default with Heroku subdomain)

3. Set up proper error logging

4. Configure firewall/DDoS protection if needed

## Useful Heroku Commands

- `heroku logs --tail` - View live logs
- `heroku ps` - View running processes
- `heroku config` - View environment variables
- `heroku run bash` - Open shell in dyno
- `heroku restart` - Restart the app
- `heroku destroy --app your-app-name` - Delete app

## Questions?

Refer to Heroku Documentation: https://devcenter.heroku.com/
