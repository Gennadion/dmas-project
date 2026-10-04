# DMAS Baseline

LangGraph-based reimplementation of the Decentralized Multi-Agent System (DMAS)
baseline from Ding et al., "Decentralized Multi-Agent System with Trust-Aware
Communication" (arXiv:2512.02410), replacing the paper's Autogen implementation.
It is the baseline the dissertation's anonymous-credential work is benchmarked
against and built on.

- [`agents/`](agents/) — Python/LangGraph: the paper's service discovery
  (Proxy Agent / Service Agent roles, `FirstSelect`, depth-/breadth-first
  delegation, termination predicate τ) and the PA side of every exchange.
- [`blockchain/`](blockchain/) — Hardhat: the on-chain contracts the agents
  use — `AgentRegistry` (the paper's Verifiable Agent Registry) and
  `CommunicationLedger` (the trust-aware communication protocol).
- [`demo/`](demo/) — a static GitHub Pages page that replays a run recorded
  on the Sepolia testnet and lets visitors verify every exchange against the
  chain from their browser.

## How the two fit together

Service agents register a DID and the hash of their capability schema on
`AgentRegistry`. When the Proxy Agent runs discovery, `FirstSelect` reads the
registry, and every exchange with a service agent (`Com(u, s)`) runs the
paper's commitment protocol on `CommunicationLedger`:

1. The PA commits to the hash of its request.
2. The SA checks the request against that commitment, encrypts its response,
   and commits to the ciphertext's hash and its price η.
3. The PA checks the ciphertext against that commitment and pays η on-chain.
4. The SA releases the decryption key once the payment is visible on-chain.

Only hashes and payments go on-chain; payloads, responses and keys stay
off-chain (in-process for now). Agent reasoning is still a deterministic stub —
no LLM calls yet.

## Status

| Step | What | State |
| --- | --- | --- |
| 1 | Local chain (Hardhat node) | done |
| 2 | `AgentRegistry` + `CommunicationLedger` contracts | done |
| 3 | LangGraph service discovery, in-process | done |
| 4 | Agents wired to the contracts via web3.py | done |
| — | Public demo: recorded Sepolia run on GitHub Pages | built; needs a recording (see [`demo/README.md`](demo/README.md)) |
| 5 | Parity check against the paper's Autogen version | next |

Rationale, design decisions and open questions: [`blockchain/CONTEXT.md`](blockchain/CONTEXT.md).

## Prerequisites

- Python 3.10+ and pip — `agents/`
- Node.js 18+ and npm — `blockchain/` (CI uses Node 22)

## Installation

```powershell
cd blockchain
npm ci
npm run compile
cd ..

cd agents
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

Commands are shown for Windows PowerShell; on macOS/Linux activate the venv
with `source .venv/bin/activate` instead.

## Launch

Two terminals.

```powershell
# Terminal 1 — the chain; leave running and watch the transactions arrive
cd blockchain
npx hardhat node
```

```powershell
# Terminal 2 — deploy the contracts, then run discovery against them
cd blockchain
npm run deploy:dmas:local
cd ..\agents
.venv\Scripts\activate
python run_baseline.py
```

`run_baseline.py` registers the example agents, then runs discovery once
depth-first and once breadth-first, printing each exchange with its on-chain
request/response ids and η. If you skip the deploy step it deploys fresh
contracts itself, and it is safe to re-run.

## Public demo (Sepolia + GitHub Pages)

The same agents run unchanged against the Sepolia testnet. Pass `--record` to
save the run, and the page in [`demo/`](demo/) replays it with Etherscan links
for every transaction and in-browser verification of each exchange.
[`demo/README.md`](demo/README.md) walks through getting an RPC URL, a
testnet-only wallet and faucet ETH, then recording and publishing.

## Tests

```powershell
cd blockchain
npm test        # contract tests

cd ..\agents
pytest          # discovery, on-chain, and demo-verification tests
```

The on-chain agent tests start their own Hardhat node on port 8546, so they
don't interfere with one you have running on 8545. They need `blockchain/`
installed and compiled, and are skipped otherwise. They also run the demo
page's own verification code (`demo/verify.js`) over a fresh recording, and
check that tampered recordings fail it.

## Contributing

`main` is protected: every change goes through a pull request, and both CI
jobs (`blockchain (Hardhat)` and `agents (pytest)`, see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)) must pass on a branch
that is up to date with `main`. Changes to `demo/` that land on `main` are
published to GitHub Pages by
[`.github/workflows/pages.yml`](.github/workflows/pages.yml).

See [`agents/README.md`](agents/README.md) and
[`blockchain/README.md`](blockchain/README.md) for full details.
