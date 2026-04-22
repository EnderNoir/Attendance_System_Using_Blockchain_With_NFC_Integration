require("@nomiclabs/hardhat-waffle");
require("dotenv").config();

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL || process.env.BLOCKCHAIN_RPC_URL || "";
const ADMIN_PRIVATE_KEY = process.env.ADMIN_PRIVATE_KEY || "";

module.exports = {
  solidity: "0.8.19", // Match your contract version
  paths: {
    artifacts: "./artifacts",
    // Optional: Output directly to your Flask app's path
    // artifacts: "./src/artifacts",
  },
  networks: {
    hardhat: {
      chainId: 1337, // Match Ganache's default chain ID for compatibility
    },
    localhost: {
      url: "http://127.0.0.1:8545", // Hardhat Network default
    },
    sepolia: {
      url: SEPOLIA_RPC_URL,
      accounts: ADMIN_PRIVATE_KEY ? [ADMIN_PRIVATE_KEY] : [],
      chainId: 11155111,
    },
  },
};
