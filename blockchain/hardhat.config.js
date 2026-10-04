require("@nomicfoundation/hardhat-toolbox");
const { vars } = require("hardhat/config");

module.exports = {
  solidity: "0.8.24",
  networks: {
    // `npx hardhat node` — streams every tx/call to the terminal in real
    // time. Its accounts come from Hardhat/Foundry's well-known public test
    // mnemonic ("test test ... junk") — never use it for real funds.
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    // Public testnet for the GitHub Pages demo. The Python agents deploy and
    // transact there themselves (see demo/README.md); Hardhat only needs it
    // to verify the contract source on Etherscan, so no accounts are set.
    sepolia: {
      url: vars.get("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com"),
      chainId: 11155111,
    },
  },
  // Set with `npx hardhat vars set ETHERSCAN_API_KEY` (stored outside the repo).
  etherscan: {
    apiKey: vars.get("ETHERSCAN_API_KEY", ""),
  },
};
