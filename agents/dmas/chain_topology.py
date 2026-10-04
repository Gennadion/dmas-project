"""SA registry backed by the deployed AgentRegistry (Ding et al. III-A.2).

The chain holds only DID + H(capability schema) per agent address. The
JSON-LD capability schema itself lives off-chain -- here, on each SA's
ServiceEndpoint, which also stands in for the DID's service endpoint.
Every SA the PA selects or contacts is resolved on-chain and its off-chain
schema is checked against the committed hash first, so a revoked SA or a
tampered schema is never used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eth_account.signers.local import LocalAccount
from web3 import Web3

from dmas.chain import Chain, ChainError
from dmas.commitment import ServiceEndpoint, communicate
from dmas.service_agent import ServiceAgent
from dmas.topology import example_topology
from dmas.types import Request, Response, canonical_json

SCHEMA_CONTEXT = "https://schema.org/"
TERMINAL_ETA_WEI = Web3.to_wei(0.001, "ether")


def did_for(name: str) -> str:
    return f"did:dmas:{name}"


def capability_schema(did: str, capability: str, role: str) -> dict:
    """Minimal JSON-LD capability schema; only its hash is committed on-chain."""
    return {"@context": SCHEMA_CONTEXT, "@type": "Service", "id": did, "capability": capability, "role": role}


def schema_hash(schema: dict) -> bytes:
    return Web3.keccak(canonical_json(schema))


def endpoint_schema(endpoint: ServiceEndpoint) -> dict:
    agent = endpoint.agent
    return capability_schema(agent.sa_id, agent.capability, "routing" if agent.is_routing() else "terminal")


def register(chain: Chain, account: LocalAccount, did: str, schema: dict) -> None:
    """Idempotent self-registration: register, or update the capability hash
    if this account is already registered with a different schema."""
    current_did, current_hash, active = chain.registry.functions.resolve(account.address).call()
    if not active:
        chain.transact(account, chain.registry.functions.register(did, schema_hash(schema)))
    elif current_did != did:
        raise ChainError(f"{account.address} is already registered as {current_did}")
    elif current_hash != schema_hash(schema):
        chain.transact(account, chain.registry.functions.updateCapability(schema_hash(schema)))


@dataclass
class ChainTopology:
    """ServiceNetwork whose source of truth is the on-chain AgentRegistry.

    `requester` is the PA's account: every communicate() is a Com(u, s)
    exchange signed by it. `endpoints` maps DID -> ServiceEndpoint and is
    the off-chain half of DID resolution (schema + how to reach the SA).
    """

    chain: Chain
    requester: LocalAccount
    endpoints: dict[str, ServiceEndpoint]
    _addresses: dict[str, str] = field(default_factory=dict, repr=False)  # DID -> address, from chain events

    def register_all(self, requester_did: str) -> None:
        register(self.chain, self.requester, requester_did, capability_schema(requester_did, "*", "proxy"))
        for endpoint in self.endpoints.values():
            register(self.chain, endpoint.account, endpoint.agent.sa_id, endpoint_schema(endpoint))

    def _index_registry(self) -> None:
        """Rebuild the DID -> address index from AgentRegistered events (the
        contract has no enumeration, so event logs are the directory)."""
        logs = self.chain.registry.events.AgentRegistered().get_logs(from_block=0)
        self._addresses = {log["args"]["did"]: log["args"]["agent"] for log in logs}

    def verified_endpoint(self, did: str) -> ServiceEndpoint:
        """Resolve `did` on-chain and check the off-chain schema against it."""
        if did not in self._addresses:
            self._index_registry()
        address = self._addresses.get(did)
        endpoint = self.endpoints.get(did)
        if address is None or endpoint is None:
            raise ChainError(f"{did} is not resolvable")

        onchain_did, onchain_hash, active = self.chain.registry.functions.resolve(address).call()
        if not active or onchain_did != did:
            raise ChainError(f"{did} is not an active registered agent")
        if endpoint.account.address != address:
            raise ChainError(f"{did}'s endpoint is not controlled by its registered address")
        if onchain_hash != schema_hash(endpoint_schema(endpoint)):
            raise ChainError(f"{did}'s capability schema does not match its on-chain hash")
        return endpoint

    def _verified_schemas(self) -> list[dict]:
        self._index_registry()
        schemas = []
        for did in self._addresses:
            try:
                schemas.append(endpoint_schema(self.verified_endpoint(did)))
            except ChainError:
                continue  # revoked, tampered, or no off-chain endpoint (e.g. the PA itself)
        return schemas

    def first_select(self, request: Request) -> list[str]:
        """FirstSelect(u, triangle-right) (III-B.1.a) over verified on-chain
        agents: routing SAs advertising the capability, falling back to all
        routing SAs if none match."""
        routing = [s for s in self._verified_schemas() if s["role"] == "routing"]
        matches = [s["id"] for s in routing if s["capability"] == request.capability]
        return matches or [s["id"] for s in routing]

    def communicate(self, sa_id: str, request: Request) -> Response:
        return communicate(self.chain, self.requester, self.verified_endpoint(sa_id), request)


def example_chain_topology(chain: Chain, accounts: list[LocalAccount]) -> ChainTopology:
    """dmas.topology.example_topology(), with each SA bound to its own test
    account (accounts[1:]) and the PA to accounts[0]. Terminal SAs charge
    TERMINAL_ETA_WEI per response; routing SAs forward for free."""
    agents = list(example_topology().agents.values())
    if len(accounts) < len(agents) + 1:
        raise ValueError(f"need {len(agents) + 1} accounts, got {len(accounts)}")

    endpoints = {}
    for agent, account in zip(agents, accounts[1:]):
        did = did_for(agent.sa_id)
        on_chain_agent = ServiceAgent(did, agent.capability, children=[did_for(c) for c in agent.children])
        eta = 0 if agent.is_routing() else TERMINAL_ETA_WEI
        endpoints[did] = ServiceEndpoint(agent=on_chain_agent, account=account, eta_wei=eta)

    return ChainTopology(chain=chain, requester=accounts[0], endpoints=endpoints)
