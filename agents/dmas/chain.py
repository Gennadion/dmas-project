"""web3.py plumbing for the Step 2 contracts (AgentRegistry, CommunicationLedger).

Contract ABIs/bytecode are read straight from Hardhat's compiled artifacts in
`blockchain/artifacts/`, so `npm run compile` is the single source of truth
for both the JS and Python sides. Accounts are derived from the same test
mnemonic `npx hardhat node` uses, and every transaction is signed locally by
the agent's own key (SSI: agents control their keys) rather than relying on
the node's unlocked accounts -- so the same code works against any JSON-RPC
chain, not just a local Hardhat node.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract

BLOCKCHAIN_DIR = Path(__file__).resolve().parents[2] / "blockchain"
ARTIFACTS_DIR = BLOCKCHAIN_DIR / "artifacts" / "contracts"
DEPLOYMENTS_DIR = BLOCKCHAIN_DIR / "deployments"

DEFAULT_RPC_URL = "http://127.0.0.1:8545"
# Hardhat/Foundry's well-known public test mnemonic -- never use for real funds.
TEST_MNEMONIC = "test test test test test test test test test test test junk"


def hardhat_accounts(n: int, mnemonic: str = TEST_MNEMONIC) -> list[LocalAccount]:
    """The first n accounts `npx hardhat node` prints on startup (BIP-44 path)."""
    Account.enable_unaudited_hdwallet_features()
    return [Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}") for i in range(n)]


def load_artifact(contract_name: str) -> dict:
    path = ARTIFACTS_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run `npm run compile` in blockchain/ first")
    return json.loads(path.read_text())


class ChainError(RuntimeError):
    """An on-chain record failed a verification check (not a revert)."""


@dataclass
class Chain:
    w3: Web3
    registry: Contract
    ledger: Contract

    @classmethod
    def deploy(cls, w3: Web3, deployer: LocalAccount) -> Chain:
        """Deploy a fresh AgentRegistry + CommunicationLedger pair."""
        registry_addr = _deploy(w3, deployer, "AgentRegistry")
        ledger_addr = _deploy(w3, deployer, "CommunicationLedger", registry_addr)
        return cls.at(w3, registry_addr, ledger_addr)

    @classmethod
    def from_deployment(cls, w3: Web3, network: str = "localhost") -> Chain | None:
        """Attach to the addresses `npm run deploy:dmas:<network>` wrote, or
        None if there is no deployment file or the chain it points at is gone
        (e.g. the Hardhat node was restarted since)."""
        path = DEPLOYMENTS_DIR / f"{network}.json"
        if not path.exists():
            return None
        deployment = json.loads(path.read_text())
        if deployment["chainId"] != w3.eth.chain_id:
            return None
        if not all(w3.eth.get_code(deployment[name]) for name in ("AgentRegistry", "CommunicationLedger")):
            return None
        return cls.at(w3, deployment["AgentRegistry"], deployment["CommunicationLedger"])

    @classmethod
    def at(cls, w3: Web3, registry_address: str, ledger_address: str) -> Chain:
        return cls(
            w3=w3,
            registry=w3.eth.contract(address=registry_address, abi=load_artifact("AgentRegistry")["abi"]),
            ledger=w3.eth.contract(address=ledger_address, abi=load_artifact("CommunicationLedger")["abi"]),
        )

    def transact(self, account: LocalAccount, fn, value: int = 0):
        """Sign `fn` (a bound contract function) with `account`'s own key,
        send it, and wait for the receipt. Reverts surface as
        web3.exceptions.ContractLogicError during gas estimation."""
        tx = fn.build_transaction(
            {
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "value": value,
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            raise ChainError(f"transaction {tx_hash.hex()} failed")
        return receipt


def _deploy(w3: Web3, deployer: LocalAccount, contract_name: str, *args) -> str:
    artifact = load_artifact(contract_name)
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = factory.constructor(*args).build_transaction(
        {"from": deployer.address, "nonce": w3.eth.get_transaction_count(deployer.address)}
    )
    signed = deployer.sign_transaction(tx)
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))
    return receipt["contractAddress"]
