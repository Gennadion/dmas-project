"""Demo entry point: runs the Ding et al. III-B.1 discovery algorithm, both
strategies, against the on-chain AgentRegistry/CommunicationLedger, printing
each step -- watch the matching transactions stream past in the terminal
running `npx hardhat node`.

Also runs against a public testnet (see demo/README.md): point CHAIN_RPC_URL
at Sepolia, set your own CHAIN_MNEMONIC, and pass `--record` to save the run
for the GitHub Pages replay.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

from dmas.chain import DEFAULT_RPC_URL, LOCAL_CHAIN_IDS, TEST_MNEMONIC, Chain, ChainError, check_network, hardhat_accounts
from dmas.chain_topology import TERMINAL_ETA_WEI, ChainTopology, did_for, example_chain_topology
from dmas.discovery import DiscoveryState
from dmas.proxy_agent import ProxyAgent
from dmas.recording import record
from dmas.termination import any_of, max_communications, min_terminal_responses
from dmas.types import Request

REQUESTER_DID = did_for("pa-user-1")
# Each SA pays its own gas on a real network: registration once, then one
# commitResponse per exchange. Topped up from account 0 (the PA) as needed.
DEFAULT_AGENT_MIN_BALANCE_ETH = "0.005"


def connect() -> tuple[Chain, list]:
    rpc_url = os.getenv("CHAIN_RPC_URL", DEFAULT_RPC_URL)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        sys.exit("No chain at CHAIN_RPC_URL -- start one with `npx hardhat node` in blockchain/")

    mnemonic = os.getenv("CHAIN_MNEMONIC", TEST_MNEMONIC)
    try:
        check_network(w3.eth.chain_id, mnemonic)
    except ChainError as e:
        sys.exit(str(e))
    accounts = hardhat_accounts(8, mnemonic)

    network = os.getenv("CHAIN_NETWORK", "localhost")
    chain = Chain.from_deployment(w3, network)
    if chain is None:
        print(f"No live deployment for '{network}' -- deploying fresh contracts.")
        chain = Chain.deploy(w3, accounts[0])
        print(f"Addresses written to: {chain.save_deployment(network)}")
    print(f"AgentRegistry:       {chain.registry.address}")
    print(f"CommunicationLedger: {chain.ledger.address}")
    return chain, accounts


def run(topology: ChainTopology, strategy: str) -> DiscoveryState:
    print(f"\n=== {strategy.upper()} discovery ===")
    if topology.chain.w3.eth.chain_id not in LOCAL_CHAIN_IDS:
        print("  (three transactions per exchange on a public chain -- this takes a few minutes)")
    pa = ProxyAgent(user_id="user-1", topology=topology)
    request = Request(capability="code", payload="review this pull request")

    termination = any_of(min_terminal_responses(2), max_communications(10))
    responses = pa.discover(request, strategy=strategy, termination=termination)

    for line in pa.context[-1]["trace"]:
        print(f"  {line}")

    print(f"  R (terminal responses, in order): {[r.sa_id for r in responses]}")
    return pa.context[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", type=Path, help="write the run as JSON for the demo page (e.g. ../demo/run.json)")
    args = parser.parse_args()

    load_dotenv()
    chain, accounts = connect()
    eta = Web3.to_wei(os.getenv("CHAIN_TERMINAL_ETA", Web3.from_wei(TERMINAL_ETA_WEI, "ether")), "ether")
    topology = example_chain_topology(chain, accounts, terminal_eta_wei=eta)

    min_balance = Web3.to_wei(os.getenv("CHAIN_AGENT_MIN_BALANCE", DEFAULT_AGENT_MIN_BALANCE_ETH), "ether")
    chain.fund(topology.requester, [e.account for e in topology.endpoints.values()], min_balance)
    topology.register_all(REQUESTER_DID)

    before = chain.w3.eth.get_balance(topology.requester.address)
    runs = [run(topology, "dfs"), run(topology, "bfs")]
    spent = before - chain.w3.eth.get_balance(topology.requester.address)
    print(f"\nPA spent {Web3.from_wei(spent, 'ether')} ETH (eta payments + gas)")

    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record(topology, REQUESTER_DID, runs), indent=2) + "\n")
        print(f"Recording written to: {args.record}")


if __name__ == "__main__":
    main()
