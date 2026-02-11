pragma solidity ^0.8.0;

import "@truffle/hdwallet-provider";

module.exports = {
  networks: {
    development: {
      host: "127.0.0.1",
      port: 8545,
      network_id: "*",
      from: "0xd41c057fd1cff8d3ebb689728db6d6cb0409945e"
    },
    
    ropsten: {
      provider: () => new HDWalletProvider(
        process.env.MNEMONIC,
        `https://ropsten.infura.io/v3/${process.env.INFURA_KEY}`
      ),
      network_id: 3,
      gas: 5500000,
      gasPrice: 10000000000,
      timeoutBlocks: 200,
      skipDryRun: true,
      from: process.env.ACCOUNT_ADDRESS
    }
  },

  compilers: {
    solc: {
      version: "0.8.0",
      settings: {
        optimizer: {
          enabled: true,
          runs: 200
        }
      }
    }
  },

  plugins: ["truffle-plugin-verify"],
  
  api_keys: {
    etherscan: process.env.ETHERSCAN_API_KEY
  }
};
