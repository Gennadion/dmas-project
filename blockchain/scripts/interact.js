const hre = require("hardhat");

async function main() {
  const address = '0x5fbdb2315678afecb367f032d93f642f64180aa3'
  if (!address) throw new Error("Set PING_ADDRESS env var to the deployed contract address");

  const ping = await hre.ethers.getContractAt("Ping", address);

  const tx = await ping.ping();
  await tx.wait();
  console.log("pingCount is now:", (await ping.pingCount()).toString());
}

main().catch((e) => { console.error(e); process.exitCode = 1; });