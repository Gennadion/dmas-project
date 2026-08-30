require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

// Shared test mnemonic (this is Hardhat/Foundry's well-known public test
// mnemonic — never use it, or any mnemonic, for real funds). Passing it
// explicitly to both `npx hardhat node` and Ganache means the same test
// accounts/addresses show up on either chain, so scripts don't care which
// one is running underneath.
const TEST_MNEMONIC =
  process.env.CHAIN_MNEMONIC ||
  "test test test test test test test test test test test junk";

module.exports = {
  solidity: "0.8.24",
  networks: {
    // `npx hardhat node` — recommended default. Actively maintained,
    // streams every tx/call to the terminal in real time, better tracebacks.
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    // Optional: point at a Ganache instance instead (see package.json's
    // "ganache" script). Ganache was sunset by Consensys in 2023 and is
    // archived/unmaintained, so only use this if you have a specific reason
    // to match an existing Ganache-based setup.
    ganache: {
      url: process.env.GANACHE_RPC_URL || "http://127.0.0.1:8545",
      chainId: 1337,
      accounts: {
        mnemonic: TEST_MNEMONIC,
      },
    },
  },
};
