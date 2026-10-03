# DMAS Baseline

LangGraph-based reimplementation of the Decentralized Multi-Agent System (DMAS)
baseline from Ding et al., "Decentralized Multi-Agent System with Trust-Aware
Communication" (arXiv:2512.02410), replacing the paper's Autogen implementation.

- [`agents/`](agents/) — Python/LangGraph side: service discovery (Proxy Agent /
  Service Agent roles, `FirstSelect`, delegation, termination predicate τ).
- [`blockchain/`](blockchain/) — Hardhat side: on-chain observability contracts
  (Verifiable Agent Registry, trust-aware communication protocol).

See each subfolder's README and `blockchain/CONTEXT.md` for details and roadmap.

## Prerequisites

- Python 3.10+ and pip — `agents/`
- Node.js 18+ and npm — `blockchain/`

## Installation

```powershell
cd agents
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..

cd blockchain
npm install
cd ..
```

## Launch

The two sides run independently for now — `agents/`'s `Com(u, s)` calls are
still stubbed and don't hit the chain yet (wiring them together is Step 4).

**Agents demo** (no chain needed):
```powershell
cd agents
.venv\Scripts\activate
python run_baseline.py
```

**Blockchain** (two terminals):
```powershell
# Terminal 1 — leave running
cd blockchain
npx hardhat node
```
```powershell
# Terminal 2
cd blockchain
npm run compile
npm run deploy:dmas:local
```

See `agents/README.md` and `blockchain/README.md` for full details (tests,
contract descriptions).
