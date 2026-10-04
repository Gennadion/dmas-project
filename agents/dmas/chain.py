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

LOCAL_CHAIN_IDS = {31337, 1337}
MAINNET_CHAIN_ID = 1
# Many hosted RPC providers cap eth_getLogs block ranges; scan in chunks.
LOG_CHUNK_BLOCKS = 1_000
# Public testnets take ~12s per block and can be congested.
TX_TIMEOUT_SECONDS = 300


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


def check_network(chain_id: int, mnemonic: str) -> None:
    """Refuse to run where this demo could lose real money: mainnet at all,
    or any non-local chain with the public test mnemonic (whose keys anyone
    can use to drain the accounts)."""
    if chain_id == MAINNET_CHAIN_ID:
        raise ChainError("refusing to run on Ethereum mainnet")
    if chain_id not in LOCAL_CHAIN_IDS and mnemonic == TEST_MNEMONIC:
        raise ChainError(
            f"chain {chain_id} is not a local node -- set CHAIN_MNEMONIC to your own "
            "testnet-only mnemonic instead of the public test one"
        )


@dataclass
class Chain:
    w3: Web3
    registry: Contract
    ledger: Contract
    deploy_block: int = 0  # where to start scanning contract events

    @classmethod
    def deploy(cls, w3: Web3, deployer: LocalAccount) -> Chain:
        """Deploy a fresh AgentRegistry + CommunicationLedger pair."""
        registry = _deploy(w3, deployer, "AgentRegistry")
        ledger = _deploy(w3, deployer, "CommunicationLedger", registry["contractAddress"])
        return cls.at(w3, registry["contractAddress"], ledger["contractAddress"], registry["blockNumber"])

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
        return cls.at(
            w3, deployment["AgentRegistry"], deployment["CommunicationLedger"], deployment.get("deployBlock", 0)
        )

    @classmethod
    def at(cls, w3: Web3, registry_address: str, ledger_address: str, deploy_block: int = 0) -> Chain:
        return cls(
            w3=w3,
            registry=w3.eth.contract(address=registry_address, abi=load_artifact("AgentRegistry")["abi"]),
            ledger=w3.eth.contract(address=ledger_address, abi=load_artifact("CommunicationLedger")["abi"]),
            deploy_block=deploy_block,
        )

    def save_deployment(self, network: str) -> Path:
        """Write the same deployments/<network>.json `deploy-dmas.js` does."""
        DEPLOYMENTS_DIR.mkdir(exist_ok=True)
        path = DEPLOYMENTS_DIR / f"{network}.json"
        deployment = {
            "chainId": self.w3.eth.chain_id,
            "AgentRegistry": self.registry.address,
            "CommunicationLedger": self.ledger.address,
            "deployBlock": self.deploy_block,
        }
        path.write_text(json.dumps(deployment, indent=2) + "\n")
        return path

    def logs(self, event, from_block: int, to_block: int) -> list:
        """event.get_logs over [from_block, to_block], in provider-friendly chunks."""
        logs = []
        for start in range(from_block, to_block + 1, LOG_CHUNK_BLOCKS):
            end = min(start + LOG_CHUNK_BLOCKS - 1, to_block)
            logs.extend(event.get_logs(from_block=start, to_block=end))
        return logs

    def fund(self, funder: LocalAccount, recipients: list[LocalAccount], min_balance_wei: int) -> None:
        """Top every recipient up to min_balance_wei from funder: on a real
        network each agent pays its own gas. A no-op on a local node."""
        for account in recipients:
            shortfall = min_balance_wei - self.w3.eth.get_balance(account.address)
            if shortfall <= 0:
                continue
            tx = {
                "from": funder.address,
                "to": account.address,
                "value": shortfall,
                "nonce": self.w3.eth.get_transaction_count(funder.address),
                "chainId": self.w3.eth.chain_id,
            }
            tx["gas"] = self.w3.eth.estimate_gas(tx)
            tx["maxPriorityFeePerGas"] = self.w3.eth.max_priority_fee
            tx["maxFeePerGas"] = 2 * self.w3.eth.get_block("latest")["baseFeePerGas"] + tx["maxPriorityFeePerGas"]
            self._send(funder, tx)

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
        return self._send(account, tx)

    def _send(self, account: LocalAccount, tx: dict):
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=TX_TIMEOUT_SECONDS)
        if receipt["status"] != 1:
            raise ChainError(f"transaction {tx_hash.hex()} failed")
        return receipt


def _deploy(w3: Web3, deployer: LocalAccount, contract_name: str, *args):
    """Deploy one contract and return its receipt."""
    artifact = load_artifact(contract_name)
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = factory.constructor(*args).build_transaction(
        {"from": deployer.address, "nonce": w3.eth.get_transaction_count(deployer.address)}
    )
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=TX_TIMEOUT_SECONDS)
