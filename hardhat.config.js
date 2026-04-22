require("@nomiclabs/hardhat-waffle");
require("dotenv").config();

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL || process.env.BLOCKCHAIN_RPC_URL || "";
const ADMIN_PRIVATE_KEY = process.env.ADMIN_PRIVATE_KEY || "";

// Load environment variables (optional - will work without .env file)
try {
  require("dotenv").config();
} catch (e) {
  // dotenv not installed, that's ok
}

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.19",
  paths: {
    artifacts: "./artifacts",
  },
  networks: {
    hardhat: {
      chainId: 1337,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    sepolia: {
      url:
        process.env.SEPOLIA_RPC_URL ||
        "https://sepolia.infura.io/v3/YOUR_INFURA_KEY",
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      chainId: 11155111,
    },
    sepolia: {
      url: SEPOLIA_RPC_URL,
      accounts: ADMIN_PRIVATE_KEY ? [ADMIN_PRIVATE_KEY] : [],
      chainId: 11155111,
    },
  },
};
