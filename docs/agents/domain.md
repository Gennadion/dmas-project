# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: system-wide decisions. Also check `<component>/docs/adr/` for component-scoped decisions.

If any of these files don't exist yet, proceed silently. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT-MAP.md
├── docs/adr/                 ← system-wide decisions
├── agents/
│   ├── CONTEXT.md            ← Python/LangGraph DMAS baseline domain
│   └── docs/adr/
└── blockchain/
    ├── CONTEXT.md            ← Hardhat/on-chain domain (already exists)
    └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept, use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding.
