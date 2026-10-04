"""Demo entry point: runs the Ding et al. III-B.1 discovery algorithm, both
strategies, against the on-chain AgentRegistry/CommunicationLedger, printing
each step -- watch the matching transactions stream past in the terminal
running `npx hardhat node`.
"""

import os
import sys

from dotenv import load_dotenv
from web3 import Web3

from dmas.chain import DEFAULT_RPC_URL, TEST_MNEMONIC, Chain, hardhat_accounts
from dmas.chain_topology import ChainTopology, did_for, example_chain_topology
from dmas.proxy_agent import ProxyAgent
from dmas.termination import any_of, max_communications, min_terminal_responses
from dmas.types import Request


def connect() -> tuple[Chain, list]:
    rpc_url = os.getenv("CHAIN_RPC_URL", DEFAULT_RPC_URL)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        sys.exit(f"No chain at {rpc_url} -- start one with `npx hardhat node` in blockchain/")

    accounts = hardhat_accounts(8, os.getenv("CHAIN_MNEMONIC", TEST_MNEMONIC))
    chain = Chain.from_deployment(w3, os.getenv("CHAIN_NETWORK", "localhost"))
    if chain is None:
        print("No live deployment found (`npm run deploy:dmas:local`) -- deploying fresh contracts.")
        chain = Chain.deploy(w3, accounts[0])
    print(f"AgentRegistry:       {chain.registry.address}")
    print(f"CommunicationLedger: {chain.ledger.address}")
    return chain, accounts


def run(topology: ChainTopology, strategy: str) -> None:
    print(f"\n=== {strategy.upper()} discovery ===")
    pa = ProxyAgent(user_id="user-1", topology=topology)
    request = Request(capability="code", payload="review this pull request")

    termination = any_of(min_terminal_responses(2), max_communications(10))
    responses = pa.discover(request, strategy=strategy, termination=termination)

    for line in pa.context[-1]["trace"]:
        print(f"  {line}")

    print(f"  R (terminal responses, in order): {[r.sa_id for r in responses]}")


def main() -> None:
    load_dotenv()
    chain, accounts = connect()
    topology = example_chain_topology(chain, accounts)
    topology.register_all(did_for("pa-user-1"))

    before = chain.w3.eth.get_balance(topology.requester.address)
    run(topology, "dfs")
    run(topology, "bfs")
    spent = before - chain.w3.eth.get_balance(topology.requester.address)
    print(f"\nPA spent {Web3.from_wei(spent, 'ether')} ETH (eta payments + gas)")


if __name__ == "__main__":
    main()
