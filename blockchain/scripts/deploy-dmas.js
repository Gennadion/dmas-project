const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  console.log(`Deploying to network: ${hre.network.name}`);

  const AgentRegistry = await hre.ethers.getContractFactory("AgentRegistry");
  const registry = await AgentRegistry.deploy();
  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();
  console.log(`AgentRegistry deployed to: ${registryAddress}`);

  const CommunicationLedger = await hre.ethers.getContractFactory("CommunicationLedger");
  const ledger = await CommunicationLedger.deploy(registryAddress);
  await ledger.waitForDeployment();
  const ledgerAddress = await ledger.getAddress();
  console.log(`CommunicationLedger deployed to: ${ledgerAddress}`);

  // Read by the Python agents (dmas/chain.py) to attach to these contracts.
  const { chainId } = await hre.ethers.provider.getNetwork();
  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `${hre.network.name}.json`);
  fs.writeFileSync(
    outFile,
    JSON.stringify(
      { chainId: Number(chainId), AgentRegistry: registryAddress, CommunicationLedger: ledgerAddress },
      null,
      2
    ) + "\n"
  );
  console.log(`Addresses written to: ${outFile}`);

  console.log(
    "Watch it live: in the terminal running `npx hardhat node`, every " +
      "call below will show up as it happens."
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
