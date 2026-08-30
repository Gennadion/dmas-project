const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Ping", function () {
  it("increments pingCount and emits an event", async function () {
    const Ping = await ethers.getContractFactory("Ping");
    const ping = await Ping.deploy();

    await expect(ping.ping()).to.emit(ping, "Pinged");
    expect(await ping.pingCount()).to.equal(1n);

    await ping.ping();
    expect(await ping.pingCount()).to.equal(2n);
  });
});
