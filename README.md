# DMAS Baseline

LangGraph-based reimplementation of the Decentralized Multi-Agent System (DMAS)
baseline from Ding et al., "Decentralized Multi-Agent System with Trust-Aware
Communication" (arXiv:2512.02410), replacing the paper's Autogen implementation.

- [`agents/`](agents/) — Python/LangGraph side: service discovery (Proxy Agent /
  Service Agent roles, `FirstSelect`, delegation, termination predicate τ).
- [`blockchain/`](blockchain/) — Hardhat side: on-chain observability contracts
  (Verifiable Agent Registry, trust-aware communication protocol).

See each subfolder's README and `blockchain/CONTEXT.md` for details and roadmap.
