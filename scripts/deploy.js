const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  const Attendance = await hre.ethers.getContractFactory("Attendance");
  const attendance = await Attendance.deploy();
  await attendance.deployed();

  console.log("Attendance contract deployed to:", attendance.address);

  // Save contract address and ABI for Flask
  const fs = require("fs");
  const contractJson = {
    address: attendance.address,
    abi: JSON.parse(attendance.interface.format("json")),
  };

  fs.writeFileSync(
    "./attendance-contract.json",
    JSON.stringify(contractJson, null, 2),
  );
  console.log("✅ Contract data saved to attendance-contract.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
