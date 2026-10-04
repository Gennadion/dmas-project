// Publishes the AgentRegistry + CommunicationLedger source on Etherscan for
// the addresses in deployments/<network>.json, so the demo's contract links
// show readable Solidity instead of bytecode.
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function verify(name, address, constructorArguments) {
  console.log(`Verifying ${name} at ${address}...`);
  try {
    await hre.run("verify:verify", { address, constructorArguments });
  } catch (error) {
    if (!/already verified/i.test(error.message)) throw error;
    console.log(`${name} is already verified.`);
  }
}

async function main() {
  const file = path.join(__dirname, "..", "deployments", `${hre.network.name}.json`);
  if (!fs.existsSync(file)) {
    throw new Error(`${file} not found -- deploy first (see demo/README.md)`);
  }
  const deployment = JSON.parse(fs.readFileSync(file, "utf8"));

  await verify("AgentRegistry", deployment.AgentRegistry, []);
  await verify("CommunicationLedger", deployment.CommunicationLedger, [deployment.AgentRegistry]);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
