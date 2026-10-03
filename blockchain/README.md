# DMAS baseline — blockchain scaffold (Steps 1-2)

This is the blockchain-side tooling for the LangGraph-based DMAS baseline
(replacing the Autogen implementation in the anchor paper, Ding et al.,
arXiv:2512.02410). Step 1 set up the chain and a sanity-check contract.
Step 2 adds the real on-chain observability contracts, built directly from
the paper's Verifiable Agent Registry (III-A.2) and trust-aware
communication protocol (III-B.2). See `CONTEXT.md` for the full rationale.

## Why Hardhat's own network instead of Ganache

Ganache (and Truffle) was sunset by Consensys in 2023 — the repo is now an
archived read-only project, last released at v7.9.0, and it won't track
future hard forks. It still runs and is fine for a quick local EVM, but it's
not actively maintained, which is a real consideration for tooling you'll
depend on for months.

`npx hardhat node` is the actively-maintained alternative and does the job
you actually need — "observe the chain" — better anyway: it streams every
transaction, contract call, and revert reason to the terminal in real time
as your agents interact with it, and gives real Solidity stack traces.


## Prerequisites

- Node.js 18+
- npm

## Installation (Windows, PowerShell — same commands work on macOS/Linux)

```powershell
cd blockchain
npm install
```

## Launch

Two terminals:

**Terminal 1 — the chain (leave running, this is what you "watch"):**
```powershell
npx hardhat node
```
This prints 20 funded test accounts and their private keys (deterministic —
same every time), then blocks, waiting. Every tx anyone sends will print
here as it happens.

**Terminal 2 — compile, test, deploy:**
```powershell
npm run compile
npm test
npm run deploy:local        # Ping.sol sanity check
npm run deploy:dmas:local   # AgentRegistry + CommunicationLedger
```

`deploy:local` deploys `Ping.sol` to the node from Terminal 1 and prints its
address — watch Terminal 1 light up when it happens. `deploy:dmas:local`
deploys the real observability contracts, prints both addresses, and
writes them to `deployments/<network>.json` (gitignored) — that's what the
Python agents in `agents/` attach to.

## The DMAS contracts (Step 2)

- **`contracts/AgentRegistry.sol`** — the paper's Verifiable Agent Registry
  / VDR. Each agent self-registers a DID string plus a hash of its
  off-chain JSON-LD capability schema; supports update and revocation.
- **`contracts/CommunicationLedger.sol`** — the on-chain half of the
  trust-aware protocol: `commitRequest`, `commitResponse`, and
  `fulfillCondition`, corresponding to the paper's request commitment,
  response commitment, and Property IV.4 (verifiable condition
  fulfillment). The condition `η` is modeled as a wei payment, matching the
  paper's own worked example. Raw payloads/responses and the response
  decryption key never go on-chain — only their hashes — matching the
  paper's hybrid on-chain/off-chain design.

`test/dmas.test.js` exercises the full lifecycle for both contracts,
including the payment-condition enforcement path (wrong amount, wrong
payer, double-fulfillment all rejected).

## Files

```
blockchain/
├── contracts/
│   ├── Ping.sol                 # sanity-check contract only
│   ├── AgentRegistry.sol        # Verifiable Agent Registry (III-A.2)
│   └── CommunicationLedger.sol  # trust-aware protocol on-chain steps (III-B.2)
├── scripts/
│   ├── deploy.js                 # deploys Ping.sol
│   └── deploy-dmas.js            # deploys AgentRegistry + CommunicationLedger, writes deployments/
├── test/
│   ├── ping.test.js              # basic Hardhat test
│   └── dmas.test.js              # AgentRegistry + CommunicationLedger tests
├── hardhat.config.js         # localhost network (`npx hardhat node`)
└── package.json
```

## Used by the agents (Steps 3–4)

`agents/` (Python/LangGraph) runs the paper's service discovery against
these contracts: SAs self-register on `AgentRegistry`, `FirstSelect` reads
the registry, and every PA→SA exchange runs `commitRequest` /
`commitResponse` / `fulfillCondition` on `CommunicationLedger`. Keep
`npx hardhat node` open and run `python run_baseline.py` there to watch the
transactions land. See `agents/README.md` and `CONTEXT.md`.
