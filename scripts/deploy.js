const hre = require("hardhat");

async function main() {
  console.log("Getting deployer account...");
  const [deployer] = await hre.ethers.getSigners();

  if (!deployer) {
    console.error("❌ No signer available. Make sure you have:");
    console.error("  1. Set PRIVATE_KEY in .env file");
    console.error(
      "  2. Or run 'npx hardhat node' in another terminal for localhost",
    );
    process.exit(1);
  }

  console.log("Deploying contracts with account:", deployer.address);

  const Attendance = await hre.ethers.getContractFactory("Attendance");
  console.log("Deploying Attendance contract...");
  const attendance = await Attendance.deploy();

  // Wait for deployment to complete
  const deployedContract =
    (await attendance.waitForDeployment?.()) || attendance;

  // Get the deployed contract address
  const contractAddress = deployedContract.address || deployedContract.target;

  if (!contractAddress) {
    console.error("❌ Failed to get contract address after deployment");
    process.exit(1);
  }

  console.log("✅ Attendance contract deployed to:", contractAddress);

  // Save contract address and ABI for Flask
  const fs = require("fs");
  const path = require("path");

  // Update .env file with contract address
  const envPath = path.join(__dirname, "..", ".env");
  let envContent = fs.existsSync(envPath)
    ? fs.readFileSync(envPath, "utf-8")
    : "";

  // Update or add ATTENDANCE_CONTRACT_ADDRESS
  if (envContent.includes("ATTENDANCE_CONTRACT_ADDRESS=")) {
    envContent = envContent.replace(
      /ATTENDANCE_CONTRACT_ADDRESS=.*/,
      `ATTENDANCE_CONTRACT_ADDRESS=${contractAddress}`,
    );
  } else {
    envContent += `\nATTENDANCE_CONTRACT_ADDRESS=${contractAddress}`;
  }

  fs.writeFileSync(envPath, envContent);
  console.log("✅ Contract address updated in .env file");

  // Write ABI only to JSON file (address comes from .env)
  const contractJson = {
    abi: JSON.parse(attendance.interface.format("json")),
  };

  fs.writeFileSync(
    "./attendance-contract.json",
    JSON.stringify(contractJson, null, 2),
  );
  console.log(
    "✅ Contract ABI saved to attendance-contract.json (address sourced from .env)",
  );
}

main().catch((error) => {
  console.error("❌ Deployment error:", error.message);
  process.exitCode = 1;
});
