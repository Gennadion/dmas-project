# DMAS baseline — context for Claude Code

## Goal
Reimplement the anchor paper's (Ding et al., "Decentralized Multi-Agent
System with Trust-Aware Communication," 2025 IEEE ISPA, arXiv:2512.02410)
multi-agent architecture as a baseline, but with **LangGraph instead of
Autogen**, so it can be benchmarked against/extended for the dissertation's
anonymous-credential work.

## Status: Step 4 done — agents wired to the on-chain registry and ledger
`blockchain/` contains a Hardhat project (see `blockchain/README.md` for
full rationale/commands). Confirmed working: `npm install`, `npm run
compile`, `npm test`, `npm run deploy:local`, `npm run deploy:dmas:local`.

Key decision: using Hardhat's own network (`npx hardhat node`) rather than
Ganache. Ganache/Truffle were sunset by Consensys in 2023 (archived,
unmaintained, won't track future hard forks) — Hardhat's built-in network is
actively maintained and streams every tx/call live to the terminal, which is
what "observing the chain" actually needed. The `ganache` fallback network
was later removed entirely: its bundled `fsevents` dependency broke
`npm ci` on Linux/Windows (and so CI), and nothing used it.

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
path. Deploy via `npm run deploy:dmas:local`.

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

### Step 4 — agents wired to chain (done)
`agents/dmas/` now talks to `AgentRegistry` and `CommunicationLedger` via
`web3.py`, each agent signing with its own key derived from the shared test
mnemonic (local signing, not the node's unlocked accounts — SSI, and it
works unchanged against any JSON-RPC chain, e.g. a public testnet). ABIs/bytecode are read from Hardhat's
`artifacts/`; `deploy-dmas.js` now also writes
`deployments/<network>.json` (gitignored) for Python to attach to.

- **Registry → `FirstSelect`.** `ChainTopology` (`dmas/chain_topology.py`)
  replaces `dmas/topology.py` as the registry. `AgentRegistry` has no
  enumeration, so the directory is its `AgentRegistered` event log; each
  agent is then `resolve()`d and its off-chain JSON-LD capability schema
  (`id`, `capability`, `role`) checked against the on-chain hash before
  it is selected or contacted. SA ids are now DIDs (`did:dmas:<name>`).
- **`Com(u, s)`** (`dmas/commitment.py`) is the full III-B.2 protocol:
  `commitRequest(H(P(▷)))` → SA verifies payload vs. commitment, encrypts
  its response under a fresh κ (AES-GCM, `pycryptodome`), `commitResponse
  (H(enc), η)` → PA verifies `H(enc)` vs. commitment, `fulfillCondition`
  pays η → SA checks `fulfilled` on-chain before releasing κ → PA decrypts.
  The PA's `Response` carries the request/response ids as its
  non-repudiation evidence in Γ(u).
- η stays payment-only (see open questions): terminal SAs charge 0.001
  ETH, routing SAs 0 — every exchange, including forwarding, still goes
  through all three on-chain steps.
- The in-process `Topology` is kept behind the same `ServiceNetwork`
  interface so the graph stays unit-testable without a chain; the graph
  itself only changed to call `topology.communicate(...)`.

Tests: `agents/tests/test_chain.py` (8 tests, own Hardhat node on port
8546) — on-chain DFS/BFS order matches the in-process version exactly,
every exchange is committed and paid, and revoked SAs, tampered schemas,
and ciphertexts that differ from their commitment are rejected.
`python run_baseline.py` runs the demo against `npx hardhat node`.

### Public demo — Sepolia + GitHub Pages (built, awaiting a recording)
The agents run unchanged against Sepolia (`CHAIN_RPC_URL`/`CHAIN_MNEMONIC`/
`CHAIN_NETWORK=sepolia`); `run_baseline.py --record` writes `demo/run.json`
and `demo/index.html` replays it on GitHub Pages
(`.github/workflows/pages.yml`). Chosen over running a chain in the browser
or hosting a backend: real public transactions are the stronger evidence
for a dissertation about verifiable communication, and the page stays
static.

- The recording is the PA's view of Γ(u). Per exchange it holds the three
  tx hashes, the request bytes, the ciphertext, and the released κ, so
  anyone can re-check it: H(request), H(ciphertext) and η against the
  ledger, and κ decrypting the ciphertext to the shown response. Publishing κ
  after the fact is what makes the exchange non-repudiable to third
  parties. `Commitment` now carries these fields.
- `demo/verify.js` is the single implementation of those checks. The page
  runs it with ethers + WebCrypto in the browser, and
  `agents/tests/test_recording.py` runs it via Node over genuine and
  tampered recordings, so CI tests what visitors run.
- Safety: `check_network` refuses mainnet, and refuses any non-local chain
  with the public test mnemonic. Recordings never include the RPC URL (it
  often carries a provider key) or key material other than the κ's.
- Real-network plumbing: deployments record `deployBlock`, and registry
  events are scanned incrementally from it in 1,000-block chunks (hosted
  RPCs cap `eth_getLogs` ranges). SAs are topped up from account 0 to pay
  their own gas. η and the top-up amount are configurable via `.env`.
- Optional Etherscan source verification: `npm run verify:dmas:sepolia`
  with `ETHERSCAN_API_KEY` in Hardhat's `vars` store (outside the repo).

Still to do by hand (needs a funded testnet wallet): record a Sepolia run
and commit `demo/run.json` — steps in `demo/README.md`.

## Next steps (in order)

**Step 5 — baseline parity check.** Confirm the LangGraph reimplementation
behaves equivalently to the paper's Autogen version before building the
dissertation's actual contribution (zk-based / anonymous-credential layer)
on top.

## Open questions not yet resolved
- Whether `η` (the response-release condition) needs to support anything
  beyond payment for the baseline. Step 4 kept the payment-only version
  (η = 0 for routing SAs), since the paper never generalizes past it.
- Off-chain transport is still in-process after Step 4: P(▷), the
  encrypted response, κ, and capability-schema resolution are method
  calls on `ServiceEndpoint`, though each side verifies everything against
  the chain. Plain HTTP between local processes is still the likely answer
  if Step 5 needs process separation — not yet decided.
- Real LLM calls (GPT-4o, matching the paper's setup) were *not* wired in
  Step 4; `ServiceAgent.handle()` is still the deterministic stub. Decide
  whether Step 5's parity check needs them.
