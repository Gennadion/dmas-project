# DMAS baseline — Python/LangGraph scaffold (Step 3)

This is the Python side of the LangGraph-based DMAS baseline, replacing the
Autogen implementation in the anchor paper (Ding et al., "Decentralized
Multi-Agent System with Trust-Aware Communication," arXiv:2512.02410). It
implements the paper's **service discovery algorithm** (Section III-B.1) —
Proxy Agent / Service Agent roles, `FirstSelect`, depth-first and
breadth-first delegation, and the termination predicate τ — as a LangGraph
`StateGraph`. See `blockchain/CONTEXT.md` for the overall roadmap.

## Scope of this step

Two things are deliberately **not** here yet:

- **No real LLM calls.** `ServiceAgent.handle()` (in `dmas/service_agent.py`)
  is a deterministic stub standing in for an SA's off-chain reasoning. It's
  the seam a real LLM-backed implementation drops into later without
  touching the discovery graph.
- **No chain wiring.** `Com(u, s)` (the paper's verifiable request/response
  commitment protocol, III-B.2) is stubbed as a plain function call. Step 4
  wires this to the `AgentRegistry`/`CommunicationLedger` contracts in
  `blockchain/` via `web3.py`.

Both `web3` and `python-dotenv` are already in `requirements.txt`, installed
now so Step 4 can start importing them immediately.

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

```powershell
python run_baseline.py
```

Runs the discovery algorithm over a small example topology (two routing
SAs, five terminal SAs — a scaled-down version of the paper's 4x7
performance-section setup), once depth-first and once breadth-first,
printing each `FirstSelect`/`Com(u, s)` step as it happens — same
"watch it happen in the terminal" idea as `npx hardhat node` in
`blockchain/`.

## Running the tests

```powershell
pytest
```

Covers the termination predicates (`tests/test_termination.py`), the
`ServiceAgent` stub's terminal/forwarding behavior
(`tests/test_service_agent.py`), and the discovery graph itself
(`tests/test_discovery.py`) — including that DFS visits in LIFO stack
order, BFS visits in FIFO queue order, and that a termination predicate
actually halts discovery before the whole topology is exhausted.

## Files

```
agents/
├── requirements.txt        # langgraph, langchain-core, web3, python-dotenv, pytest
├── run_baseline.py         # demo: runs DFS + BFS discovery, prints the trace
├── dmas/
│   ├── types.py            # Request / Response
│   ├── termination.py      # tau: atomic predicates + any_of/all_of composition
│   ├── service_agent.py    # SA stub: forwards (routing) or terminates
│   ├── topology.py         # example SA registry (stands in for the on-chain VAR for now)
│   ├── discovery.py        # the LangGraph StateGraph implementing Algorithm 1 (+ BFS)
│   └── proxy_agent.py      # PA: holds Gamma(u), runs discovery
└── tests/
    ├── test_termination.py
    ├── test_service_agent.py
    └── test_discovery.py
```

## Next (Step 4)

Wire `Com(u, s)` to the real protocol: `commitRequest` /
`commitResponse` / `fulfillCondition` on `CommunicationLedger.sol`, and
`ServiceAgent` lookups against the deployed `AgentRegistry.sol` instead of
`dmas/topology.py`'s in-process stand-in — via `web3.py`, using the same
deterministic test accounts Hardhat's node prints on startup.
