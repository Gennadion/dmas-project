# DMAS baseline — context for Claude Code

## Goal
Reimplement the anchor paper's (Ding et al., "Decentralized Multi-Agent
System with Trust-Aware Communication," 2025 IEEE ISPA, arXiv:2512.02410)
multi-agent architecture as a baseline, but with **LangGraph instead of
Autogen**, so it can be benchmarked against/extended for the dissertation's
anonymous-credential work.

## Status: Step 3 done — Python/LangGraph discovery scaffold verified working
`blockchain/` contains a Hardhat project (see `blockchain/README.md` for
full rationale/commands). Confirmed working: `npm install`, `npm run
compile`, `npm test`, `npm run deploy:local`, `npm run deploy:dmas:local`.

Key decision: using Hardhat's own network (`npx hardhat node`) rather than
Ganache. Ganache/Truffle were sunset by Consensys in 2023 (archived,
unmaintained, won't track future hard forks) — Hardhat's built-in network is
actively maintained and streams every tx/call live to the terminal, which is
what "observing the chain" actually needed. A `ganache` network is still
configured in `hardhat.config.js` as a fallback if needed later.

`contracts/Ping.sol` is a throwaway sanity contract only — not part of the
real system.

### Step 2 — on-chain observability contracts (done)
Read the anchor paper (arXiv:2512.02410) closely to pull the exact on-chain
surface rather than guessing. Two contracts, mirroring the paper's own
split between the Verifiable Agent Registry (III-A.2) and the trust-aware
communication protocol (III-B.2):

- `contracts/AgentRegistry.sol` — the paper's VAR/VDR. Binds an address
  (identity anchor) to a DID string + a hash of the off-chain JSON-LD
  capability schema. `register` / `updateCapability` / `revoke`, all
  self-service (SSI: the agent controls its own keys).
- `contracts/CommunicationLedger.sol` — the three on-chain steps of
  III-B.2: `commitRequest` (⟨DID(u), DID(s), H(P(▷))⟩), `commitResponse`
  (⟨H(X(P▷)), H(encrypted response), η⟩), and `fulfillCondition`
  (Property IV.4's on-chain enforcement of η). η is simplified to the
  paper's own worked example — a wei payment to the responder — since the
  paper never generalizes η beyond that. Off-chain payloads/responses and
  the κ/κ̄ key exchange are deliberately NOT on-chain, matching the paper.

Important nuance found while re-reading: the paper's "trust-aware" comes
from cryptographic non-repudiation/verifiability, not a numeric reputation
score. "Reputation scores" appears exactly once, as an optional heuristic
for `FirstSelect` during service discovery — it is never formalized as an
on-chain update mechanism. So there is deliberately no reputation/trust-score
ledger here; adding one would be scope creep beyond the anchor paper. This
resolves the open question below about single-vs-split contracts: split,
matching the paper's own VAR/communication-protocol division.

Tests: `test/dmas.test.js` covers registry lifecycle + the three
commitment/fulfillment steps, including the payment-condition enforcement
path. Deploy via `npm run deploy:dmas:local` (or `:ganache`).

### Step 3 — Python/LangGraph discovery scaffold (done)
`agents/` is a Python env (`venv` + `requirements.txt`: `langgraph`,
`langchain-core`, `web3`, `python-dotenv`, `pytest`) implementing the
paper's service discovery algorithm (III-B.1) as a single parameterized
LangGraph `StateGraph`:

- `dmas/types.py` — `Request`/`Response` (▷/P(▷) and ◁, tagged terminal/
  non-terminal).
- `dmas/termination.py` — τ as composable predicates
  (`min_terminal_responses`, `max_communications`, `timeout`,
  `human_intervention`, combined via `any_of`/`all_of`).
- `dmas/service_agent.py` — `ServiceAgent`: a deterministic stub for a
  routing SA (always forwards to its children, `SA(r)` in Algorithm 1) or
  a terminal SA (always returns a stub payload). No LLM — this is the seam
  a real LLM-backed implementation drops into later.
- `dmas/topology.py` — small example SA registry (2 routing SAs, 5
  terminal SAs) standing in for the on-chain `AgentRegistry` for now, plus
  `FirstSelect` (hardcoded-list capability match, falling back to all
  routing agents).
- `dmas/discovery.py` — the actual graph: `select_candidates` →
  `[τ or empty?]` → `pop_and_communicate` → `[terminal?]` →
  `record_response`/`push_candidates` → loop. DFS and BFS are the *same*
  graph — they only differ in whether `pop_and_communicate` pops from the
  end (LIFO stack, Algorithm 1) or the front (FIFO queue) of the candidate
  list; `push_candidates` always appends, so that's the only branch point.
- `dmas/proxy_agent.py` — `ProxyAgent`: holds Γ(u) (accumulated discovery
  results across calls), the only stateful role, matching III-A.4 ("memory
  lives on the PA, SAs are stateless").

Two scope decisions made with the user before building this: **no real LLM
calls yet** (stub reasoning behind a clean seam) and **in-process, not
HTTP services** (PA/SA are logical roles, not separate processes) — this
also resolves the "off-chain transport" open question below: there's
nothing to transport yet, since everything runs as plain Python calls in
one process. Revisit if/when Step 4 or 5 actually needs process
separation.

`Com(u, s)` (III-B.2's verifiable commitment protocol) is deliberately
*not* implemented here — `ServiceAgent.handle()` stands in for it. Step 4
replaces that stub with real calls to `CommunicationLedger`.

Tests: `agents/tests/` (12 tests) cover the termination predicates, the
`ServiceAgent` stub, and the discovery graph itself — including that DFS
visits in LIFO order, BFS in FIFO order, and that a termination predicate
actually halts discovery early. `python run_baseline.py` prints a live
trace of both strategies for manual inspection.

## Next steps (in order)

**Step 4 — wire agents to chain.** Replace the `dmas/topology.py` stub
registry with `resolve()` calls against the deployed `AgentRegistry`, and
replace `ServiceAgent.handle()`'s stub `Com(u, s)` with the real protocol:
`commitRequest` → `commitResponse` → `fulfillCondition` on
`CommunicationLedger`, via `web3.py`, using the same deterministic test
accounts Hardhat's node prints on startup.

**Step 5 — baseline parity check.** Confirm the LangGraph reimplementation
behaves equivalently to the paper's Autogen version before building the
dissertation's actual contribution (zk-based / anonymous-credential layer)
on top.

## Open questions not yet resolved
- Whether `η` (the response-release condition) needs to support anything
  beyond payment for the baseline, or whether the payment-only version
  built in Step 2 is sufficient since the paper never generalizes past it.
- Off-chain payload transport (P(▷), the encrypted response, D(◁̄) storage)
  is moot for now (Step 3 runs everything in-process), but will need an
  answer in Step 4 once `AgentRegistry` capability schemas plausibly point
  at real endpoints — plain HTTP between local processes is still the
  likely answer, not yet decided.
- Whether real LLM calls (GPT-4o, matching the paper's setup) get wired
  into `ServiceAgent.handle()`/PA reasoning in Step 4, or stay stubbed
  until Step 5's parity check specifically needs them.