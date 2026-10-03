# DMAS baseline — Python/LangGraph agents (Steps 3–4)

This is the Python side of the LangGraph-based DMAS baseline, replacing the
Autogen implementation in the anchor paper (Ding et al., "Decentralized
Multi-Agent System with Trust-Aware Communication," arXiv:2512.02410). It
implements the paper's **service discovery algorithm** (Section III-B.1) —
Proxy Agent / Service Agent roles, `FirstSelect`, depth-first and
breadth-first delegation, and the termination predicate τ — as a LangGraph
`StateGraph` (Step 3), wired to the on-chain contracts in `blockchain/`
(Step 4). See `blockchain/CONTEXT.md` for the overall roadmap.

## What runs on-chain (Step 4)

- **Agent registry.** Every SA (and the PA) self-registers a DID plus the
  hash of its off-chain JSON-LD capability schema on `AgentRegistry`, each
  signing with its own test account. `FirstSelect` enumerates the registry
  from its `AgentRegistered` events, and every SA is resolved on-chain and
  its schema checked against the committed hash before it is selected or
  contacted — revoked SAs and tampered schemas are refused.
- **`Com(u, s)`** (III-B.2) runs the full commitment protocol on
  `CommunicationLedger`: the PA commits `H(P(▷))`; the SA checks the
  payload against that commitment, encrypts its response under a fresh key
  κ (AES-GCM) and commits `H(enc)` plus its price η; the PA checks the
  ciphertext against the commitment and pays η via `fulfillCondition`; the
  SA releases κ only after seeing the condition fulfilled on-chain.
  Terminal SAs charge 0.001 ETH, routing SAs forward for free.

Still deliberately **not** here:

- **No real LLM calls.** `ServiceAgent.handle()` is a deterministic stub —
  the seam a real LLM-backed implementation drops into later.
- **No network transport.** The off-chain legs of `Com(u, s)` (payload,
  ciphertext, κ) and schema resolution are in-process method calls; each
  side only trusts what it can verify against the chain.

The in-process `dmas/topology.py` registry is kept so the discovery graph
can be tested without a chain; both it and the on-chain `ChainTopology`
implement the same `ServiceNetwork` interface.

## Prerequisites

- Python 3.10+
- pip

## Installation (Windows, PowerShell — same commands work on macOS/Linux)

```powershell
cd agents
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Launch

Needs the chain running and the contracts compiled (see
`blockchain/README.md`):

```powershell
# blockchain/, terminal 1
npx hardhat node
# blockchain/, terminal 2
npm run compile
npm run deploy:dmas:local   # optional — writes deployments/localhost.json
```

Then, in `agents/`:

```powershell
python run_baseline.py
```

Attaches to the contracts from `blockchain/deployments/localhost.json`
(or deploys fresh ones if there is no live deployment), registers the PA
and the example topology's SAs (two routing SAs, five terminal SAs — a
scaled-down version of the paper's 4x7 performance-section setup), then
runs discovery once depth-first and once breadth-first. Each `Com(u, s)`
line shows its on-chain request/response ids and η; the matching
`commitRequest` / `commitResponse` / `fulfillCondition` transactions stream
past in terminal 1. Safe to re-run: registration is idempotent.

Defaults match `npx hardhat node`; copy `.env.example` to `.env` to point
at a different RPC URL, mnemonic, or deployment.

## Running the tests

```powershell
pytest
```

The on-chain tests (`tests/test_chain.py`) start their own throwaway
Hardhat node on port 8546 (so they don't touch one you have open on 8545)
and are skipped if `blockchain/` hasn't been `npm install`ed and compiled.
They check that on-chain discovery visits SAs in the same DFS/BFS order as
the in-process version, that every exchange leaves a request/response
commitment and pays η, and that revoked SAs, tampered capability schemas,
and ciphertexts that don't match their commitment are all rejected.

The rest cover the termination predicates (`tests/test_termination.py`),
the `ServiceAgent` stub (`tests/test_service_agent.py`), and the discovery
graph itself (`tests/test_discovery.py`) — including that DFS visits in
LIFO stack order, BFS in FIFO queue order, and that a termination predicate
actually halts discovery before the whole topology is exhausted.

## Files

```
agents/
├── requirements.txt        # langgraph, langchain-core, web3, python-dotenv, pycryptodome, pytest
├── .env.example            # RPC URL / mnemonic / deployment overrides
├── run_baseline.py         # demo: runs DFS + BFS discovery on-chain, prints the trace
├── dmas/
│   ├── types.py            # Request / Response / Commitment
│   ├── termination.py      # tau: atomic predicates + any_of/all_of composition
│   ├── service_agent.py    # SA reasoning stub: forwards (routing) or terminates
│   ├── topology.py         # ServiceNetwork interface + in-process example registry
│   ├── chain.py            # web3.py: artifacts, test accounts, deploy/attach, signed txs
│   ├── commitment.py       # Com(u, s): the III-B.2 commitment protocol (PA + SA sides)
│   ├── chain_topology.py   # AgentRegistry-backed ServiceNetwork + example on-chain topology
│   ├── discovery.py        # the LangGraph StateGraph implementing Algorithm 1 (+ BFS)
│   └── proxy_agent.py      # PA: holds Gamma(u), runs discovery
└── tests/
    ├── conftest.py         # throwaway Hardhat node for the on-chain tests
    ├── test_chain.py
    ├── test_termination.py
    ├── test_service_agent.py
    └── test_discovery.py
```

## Next (Step 5)

Baseline parity check: confirm the LangGraph reimplementation behaves
equivalently to the paper's Autogen version before building the
dissertation's anonymous-credential layer on top.
