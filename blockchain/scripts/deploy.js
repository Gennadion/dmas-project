const hre = require("hardhat");

async function main() {
  console.log(`Deploying to network: ${hre.network.name}`);

  const Ping = await hre.ethers.getContractFactory("Ping");
  const ping = await Ping.deploy();
  await ping.waitForDeployment();

  const address = await ping.getAddress();
  console.log(`Ping deployed to: ${address}`);
  console.log(
    "Watch it live: in the terminal running `npx hardhat node`, every " +
      "call below will show up as it happens."
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
