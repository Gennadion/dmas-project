const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentRegistry", function () {
  it("registers, updates, and revokes an agent", async function () {
    const [pa] = await ethers.getSigners();
    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    const registry = await AgentRegistry.deploy();

    const capHash = ethers.keccak256(ethers.toUtf8Bytes("capability-schema-v1"));

    await expect(registry.register("did:example:pa1", capHash))
      .to.emit(registry, "AgentRegistered")
      .withArgs(pa.address, "did:example:pa1", capHash);

    let [did, hash, active] = await registry.resolve(pa.address);
    expect(did).to.equal("did:example:pa1");
    expect(hash).to.equal(capHash);
    expect(active).to.equal(true);

    const newHash = ethers.keccak256(ethers.toUtf8Bytes("capability-schema-v2"));
    await expect(registry.updateCapability(newHash))
      .to.emit(registry, "CapabilityUpdated")
      .withArgs(pa.address, newHash);

    await expect(registry.revoke()).to.emit(registry, "AgentRevoked").withArgs(pa.address);
    [, , active] = await registry.resolve(pa.address);
    expect(active).to.equal(false);
  });

  it("rejects double registration and actions from unregistered agents", async function () {
    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    const registry = await AgentRegistry.deploy();
    const capHash = ethers.keccak256(ethers.toUtf8Bytes("schema"));

    await registry.register("did:example:pa1", capHash);
    await expect(registry.register("did:example:pa1", capHash)).to.be.revertedWith(
      "already registered"
    );

    const [, other] = await ethers.getSigners();
    await expect(registry.connect(other).revoke()).to.be.revertedWith("not registered");
  });
});

describe("CommunicationLedger", function () {
  async function deployRegisteredPair() {
    const [pa, sa] = await ethers.getSigners();

    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    const registry = await AgentRegistry.deploy();

    await registry.connect(pa).register("did:example:pa", ethers.keccak256(ethers.toUtf8Bytes("pa-cap")));
    await registry.connect(sa).register("did:example:sa", ethers.keccak256(ethers.toUtf8Bytes("sa-cap")));

    const CommunicationLedger = await ethers.getContractFactory("CommunicationLedger");
    const ledger = await CommunicationLedger.deploy(await registry.getAddress());

    return { pa, sa, registry, ledger };
  }

  it("commits a request only between registered agents", async function () {
    const { pa, sa, ledger } = await deployRegisteredPair();
    const payloadHash = ethers.keccak256(ethers.toUtf8Bytes("request-payload"));

    await expect(ledger.connect(pa).commitRequest(sa.address, payloadHash)).to.emit(
      ledger,
      "RequestCommitted"
    );

    const [, , unregistered] = await ethers.getSigners();
    await expect(
      ledger.connect(pa).commitRequest(unregistered.address, payloadHash)
    ).to.be.revertedWith("recipient not registered");
  });

  it("commits a response only from the addressed recipient", async function () {
    const { pa, sa, ledger } = await deployRegisteredPair();
    const payloadHash = ethers.keccak256(ethers.toUtf8Bytes("request-payload"));

    const tx = await ledger.connect(pa).commitRequest(sa.address, payloadHash);
    const receipt = await tx.wait();
    const requestId = receipt.logs[0].args.requestId;

    const responseHash = ethers.keccak256(ethers.toUtf8Bytes("encrypted-response"));
    await expect(
      ledger.connect(pa).commitResponse(requestId, responseHash, 0)
    ).to.be.revertedWith("not addressed to sender");

    await expect(ledger.connect(sa).commitResponse(requestId, responseHash, 100))
      .to.emit(ledger, "ResponseCommitted")
      .withArgs(anyValue(), requestId, sa.address, responseHash, 100n);
  });

  it("enforces the payment condition before releasing funds", async function () {
    const { pa, sa, ledger } = await deployRegisteredPair();
    const payloadHash = ethers.keccak256(ethers.toUtf8Bytes("request-payload"));

    const reqTx = await ledger.connect(pa).commitRequest(sa.address, payloadHash);
    const reqReceipt = await reqTx.wait();
    const requestId = reqReceipt.logs[0].args.requestId;

    const responseHash = ethers.keccak256(ethers.toUtf8Bytes("encrypted-response"));
    const price = ethers.parseEther("0.01");
    const resTx = await ledger.connect(sa).commitResponse(requestId, responseHash, price);
    const resReceipt = await resTx.wait();
    const responseId = resReceipt.logs[0].args.responseId;

    await expect(
      ledger.connect(pa).fulfillCondition(responseId, { value: ethers.parseEther("0.005") })
    ).to.be.revertedWith("wrong payment amount");

    await expect(
      ledger.connect(sa).fulfillCondition(responseId, { value: price })
    ).to.be.revertedWith("not original requester");

    const saBalanceBefore = await ethers.provider.getBalance(sa.address);
    await expect(ledger.connect(pa).fulfillCondition(responseId, { value: price }))
      .to.emit(ledger, "ConditionFulfilled")
      .withArgs(responseId, pa.address, price);
    const saBalanceAfter = await ethers.provider.getBalance(sa.address);
    expect(saBalanceAfter - saBalanceBefore).to.equal(price);

    await expect(
      ledger.connect(pa).fulfillCondition(responseId, { value: price })
    ).to.be.revertedWith("already fulfilled");
  });
});

// Minimal stand-in for chai-matchers' anyValue helper, avoiding an extra dep.
function anyValue() {
  return (arg) => arg !== undefined;
}
