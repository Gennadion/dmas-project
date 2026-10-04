"""Serialize discovery runs into the JSON the static demo page replays
(`demo/run.json`).

The recording is the PA's view of Gamma(u): for every Com(u, s) exchange,
the transactions that committed it, the exact request bytes the PA hashed,
the ciphertext the SA committed to, and the key kappa the SA released. With
those, anyone can re-check the exchange against the chain without trusting
the recording: H(request bytes) and H(ciphertext) must match the on-chain
commitments, and kappa must decrypt the ciphertext to the recorded response.

Deliberately excluded: the RPC URL (often carries a provider API key) and
anything derived from the mnemonic other than public addresses.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dmas.chain_topology import ChainTopology, endpoint_schema
from dmas.discovery import DiscoveryState

# Block explorers the page links to, by chain id. Local chains have none.
EXPLORERS = {11155111: "https://sepolia.etherscan.io"}
NETWORK_NAMES = {11155111: "sepolia", 31337: "hardhat-localhost", 1337: "localhost"}


def _hex(data: bytes) -> str:
    return "0x" + data.hex()


def _exchange(topology: ChainTopology, response) -> dict:
    c = response.commitment
    return {
        "sa": response.sa_id,
        "address": topology.endpoints[response.sa_id].account.address,
        "terminal": response.is_terminal,
        "requestId": _hex(c.request_id),
        "responseId": _hex(c.response_id),
        "etaWei": str(c.eta_wei),  # string: wei amounts overflow JS numbers
        "txs": {"request": _hex(c.request_tx), "response": _hex(c.response_tx), "fulfill": _hex(c.fulfill_tx)},
        "ciphertext": _hex(c.ciphertext),
        "key": _hex(c.key),
        "response": {"payload": response.payload, "forwarded": response.forwarded},
    }


def _run(topology: ChainTopology, state: DiscoveryState) -> dict:
    request = state["request"]
    return {
        "strategy": state["strategy"],
        "request": {"capability": request.capability, "payload": request.payload},
        "requestBytes": _hex(request.to_bytes()),
        "trace": state["trace"],
        "exchanges": [_exchange(topology, r) for r in state["exchanges"]],
        "results": [r.sa_id for r in state["responses"]],
    }


def record(topology: ChainTopology, requester_did: str, runs: list[DiscoveryState]) -> dict:
    chain = topology.chain
    chain_id = chain.w3.eth.chain_id
    return {
        "version": 1,
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chainId": chain_id,
        "network": NETWORK_NAMES.get(chain_id, f"chain-{chain_id}"),
        "explorer": EXPLORERS.get(chain_id),
        "contracts": {
            "AgentRegistry": chain.registry.address,
            "CommunicationLedger": chain.ledger.address,
            "deployBlock": chain.deploy_block,
        },
        "proxyAgent": {"did": requester_did, "address": topology.requester.address},
        "serviceAgents": [
            {**endpoint_schema(e), "address": e.account.address, "etaWei": str(e.eta_wei)}
            for e in topology.endpoints.values()
        ],
        "runs": [_run(topology, state) for state in runs],
    }
