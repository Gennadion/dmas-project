"""Discovery over the deployed contracts: AgentRegistry-backed FirstSelect
and the full Com(u, s) commitment protocol on CommunicationLedger."""

import pytest
from eth_account import Account

from dmas.chain import TEST_MNEMONIC, Chain, ChainError, check_network, hardhat_accounts
from dmas.chain_topology import TERMINAL_ETA_WEI, ChainTopology, did_for, example_chain_topology
from dmas.commitment import ServiceEndpoint
from dmas.discovery import run_discovery
from dmas.termination import max_communications
from dmas.topology import example_topology
from dmas.types import Request

NEVER = max_communications(1000)
ACCOUNTS = hardhat_accounts(8)


@pytest.fixture
def network(w3) -> ChainTopology:
    chain = Chain.deploy(w3, ACCOUNTS[0])
    topology = example_chain_topology(chain, ACCOUNTS)
    topology.register_all(did_for("pa-test"))
    return topology


def _strip(ids):
    return [i.removeprefix("did:dmas:") for i in ids]


@pytest.mark.parametrize("strategy", ["dfs", "bfs"])
def test_chain_discovery_matches_in_process_discovery(network, strategy):
    request = Request("code", "payload")
    offline = run_discovery(request, example_topology(), strategy, NEVER)
    onchain = run_discovery(request, network, strategy, NEVER)

    assert _strip(r.sa_id for r in onchain["responses"]) == [r.sa_id for r in offline["responses"]]
    assert [r.payload for r in onchain["responses"]] == [
        r.payload.replace("result[", "result[did:dmas:") for r in offline["responses"]
    ]


def test_every_exchange_is_committed_on_chain(network):
    result = run_discovery(Request("code", "payload"), network, "dfs", NEVER)
    ledger = network.chain.ledger

    # 1 routing SA + 3 terminal SAs contacted, each a request/response pair.
    assert result["call_count"] == 4
    for response in result["responses"]:
        c = response.commitment
        sender, recipient, *_ = ledger.functions.requests(c.request_id).call()
        request_id, responder, _, eta, fulfilled, _ = ledger.functions.responses(c.response_id).call()
        assert sender == network.requester.address
        assert recipient == responder == network.endpoints[response.sa_id].account.address
        assert request_id == c.request_id
        assert fulfilled and eta == c.eta_wei == TERMINAL_ETA_WEI


def test_terminal_sas_are_paid_eta(network):
    w3 = network.chain.w3
    terminal = network.endpoints[did_for("term-code-1")].account.address
    router = network.endpoints[did_for("router-code")].account.address
    before = {a: w3.eth.get_balance(a) for a in (terminal, router)}

    run_discovery(Request("code", "payload"), network, "dfs", NEVER)

    # SAs pay no gas to *receive* eta, but do pay gas for commitResponse.
    terminal_delta = w3.eth.get_balance(terminal) - before[terminal]
    router_delta = w3.eth.get_balance(router) - before[router]
    assert 0 < terminal_delta < TERMINAL_ETA_WEI
    assert router_delta < 0


def test_first_select_reads_the_registry(network):
    result = run_discovery(Request("unknown-capability", "payload"), network, "dfs", max_communications(0))
    assert f"FirstSelect(u, req) -> {[did_for('router-data'), did_for('router-code')]}" in result["trace"]


def test_revoked_sa_is_not_selected_or_contacted(network):
    router = network.endpoints[did_for("router-code")]
    network.chain.transact(router.account, network.chain.registry.functions.revoke())

    assert network.first_select(Request("code", "payload")) == [did_for("router-data")]
    with pytest.raises(ChainError, match="not an active registered agent"):
        network.communicate(did_for("router-code"), Request("code", "payload"))


def test_tampered_capability_schema_is_rejected(network):
    did = did_for("term-code-1")
    honest = network.endpoints[did]
    # Same key and DID, but the off-chain schema now claims a different capability.
    network.endpoints[did] = ServiceEndpoint(
        agent=type(honest.agent)(did, "data"), account=honest.account, eta_wei=honest.eta_wei
    )

    with pytest.raises(ChainError, match="does not match its on-chain hash"):
        network.communicate(did, Request("code", "payload"))


def test_pa_refuses_to_pay_for_a_response_that_differs_from_its_commitment(network):
    class SwappingEndpoint(ServiceEndpoint):
        """Commits to one ciphertext, then hands the PA a different one."""

        def respond(self, chain, request_id, payload):
            response_id, enc, tx = super().respond(chain, request_id, payload)
            return response_id, enc[:-1] + bytes([enc[-1] ^ 1]), tx

    did = did_for("term-code-1")
    honest = network.endpoints[did]
    network.endpoints[did] = SwappingEndpoint(agent=honest.agent, account=honest.account, eta_wei=honest.eta_wei)
    balance_before = network.chain.w3.eth.get_balance(honest.account.address)

    with pytest.raises(ChainError, match="does not match its commitment"):
        network.communicate(did, Request("code", "payload"))

    # It paid gas for commitResponse but was never paid eta.
    assert network.chain.w3.eth.get_balance(honest.account.address) < balance_before


@pytest.mark.parametrize(
    "chain_id, mnemonic, allowed",
    [
        (31337, TEST_MNEMONIC, True),  # local Hardhat node
        (11155111, TEST_MNEMONIC, False),  # public chain + public keys: drainable
        (11155111, "a private testnet mnemonic", True),
        (1, "a private testnet mnemonic", False),  # never mainnet
    ],
)
def test_check_network(chain_id, mnemonic, allowed):
    if allowed:
        check_network(chain_id, mnemonic)
    else:
        with pytest.raises(ChainError):
            check_network(chain_id, mnemonic)


def test_fund_tops_up_only_accounts_below_the_minimum(w3):
    chain = Chain.deploy(w3, ACCOUNTS[0])
    empty = Account.create()
    rich = ACCOUNTS[1]
    rich_before = w3.eth.get_balance(rich.address)

    chain.fund(ACCOUNTS[0], [empty, rich], min_balance_wei=10**15)

    assert w3.eth.get_balance(empty.address) == 10**15
    assert w3.eth.get_balance(rich.address) == rich_before
