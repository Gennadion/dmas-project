require("@nomicfoundation/hardhat-toolbox");

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
  },
};
