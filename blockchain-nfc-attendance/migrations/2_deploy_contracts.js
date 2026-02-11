// Migrations file for deploying contracts

const Attendance = artifacts.require("./Attendance.sol");

module.exports = function (deployer) {
  deployer.deploy(Attendance).then(function (instance) {
    console.log("✓ Attendance contract deployed successfully!");
    console.log(`Contract address: ${instance.address}`);
    console.log("\nUpdate your .env file with:");
    console.log(`CONTRACT_ADDRESS=${instance.address}`);
  });
};
