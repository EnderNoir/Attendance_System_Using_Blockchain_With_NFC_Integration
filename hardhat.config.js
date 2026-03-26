/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.28",
};

require("@nomiclabs/hardhat-waffle");

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
  },
};
