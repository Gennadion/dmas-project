# Sepolia demo (GitHub Pages)

A static page that replays one recorded run of the agents on the Sepolia
testnet. Every exchange links to its three transactions on Etherscan, and the
**Verify** buttons re-check each exchange live against the chain from the
visitor's browser, through a public RPC. The page doesn't ask anyone to trust
the recording:

- the request bytes hash to the request commitment on-chain;
- the ciphertext hashes to the service agent's response commitment;
- the payment condition η is fulfilled on-chain;
- the released key κ decrypts that ciphertext to the response shown.

```
demo/
├── index.html            # the page
├── verify.js             # the checks above; shared by the page and CI
├── check-recording.mjs   # run verify.js from Node over a whole recording
└── run.json              # the recording (you create it, steps below)
```

## Recording a run on Sepolia

You do this once. It costs only testnet ETH, which has no real value.

### 1. Get a Sepolia RPC URL

Any Sepolia JSON-RPC endpoint works. A free key from
[Alchemy](https://www.alchemy.com/) or [Infura](https://www.infura.io/) is the
most reliable choice. The keyless public endpoint
`https://ethereum-sepolia-rpc.publicnode.com` also works but can rate-limit.

### 2. Make a fresh testnet-only wallet

The agents run from 8 accounts derived from one mnemonic: account 0 is the
proxy agent, and 1–7 are the service agents. **Don't use the public Hardhat
test mnemonic**, because anyone can take funds sent to it (the scripts refuse
to run on a public network with it). **Don't use a mnemonic that has ever held
real funds** either. Generate a new one:

```powershell
cd agents
.venv\Scripts\activate
python -c "from eth_account import Account; Account.enable_unaudited_hdwallet_features(); a, m = Account.create_with_mnemonic(); print(m); print('account 0:', a.address)"
```

### 3. Fund account 0

Send about **0.05 Sepolia ETH** to account 0 from a faucet, for example
[Google Cloud's](https://cloud.google.com/application/web3/faucet/ethereum/sepolia)
or [Alchemy's](https://www.alchemy.com/faucets/ethereum-sepolia). The script
tops each service agent up from account 0 so each one can pay its own gas.

To spend less, lower the defaults in `.env`, for example
`CHAIN_TERMINAL_ETA=0.0001` and `CHAIN_AGENT_MIN_BALANCE=0.002`.

### 4. Point the agents at Sepolia

In `agents/.env` (copy `.env.example`; this file is gitignored):

```
CHAIN_RPC_URL=<your Sepolia RPC URL>
CHAIN_MNEMONIC=<the mnemonic from step 2>
CHAIN_NETWORK=sepolia
```

### 5. Record

```powershell
cd agents
python run_baseline.py --record ..\demo\run.json
```

The first run deploys `AgentRegistry` and `CommunicationLedger` and saves their
addresses to `blockchain/deployments/sepolia.json`. Later runs reuse them. It
then funds and registers the agents and runs depth-first and breadth-first
discovery. On a public chain each exchange waits for three blocks, so expect
a few minutes.

The recording contains public addresses, transaction hashes, ciphertexts and
the released keys. It contains no RPC URL, mnemonic or private key.

### 6. Check it the way the page will

```powershell
node ..\demo\check-recording.mjs ..\demo\run.json
```

This reads Sepolia through the public RPC, exactly like a visitor's browser
does, and should end with `all checks passed`.

### 7. (Optional) Publish the contract source on Etherscan

This makes the contract links show readable Solidity instead of bytecode.
Get a free API key at [etherscan.io](https://etherscan.io/myapikey), then:

```powershell
cd ..\blockchain
npx hardhat vars set ETHERSCAN_API_KEY
npm run verify:dmas:sepolia
```

Hardhat stores the key outside the repo.

### 8. Publish

Commit `demo/run.json` on a branch and open a PR. Once it merges to `main`,
the **Demo page** workflow (`.github/workflows/pages.yml`) publishes `demo/`
to GitHub Pages.

## Previewing locally

Record against your local node (`npx hardhat node`, default `.env`), then
serve the folder:

```powershell
cd agents
python run_baseline.py --record ..\demo\run.json
cd ..\demo
python -m http.server 8000
```

Open <http://localhost:8000>. Verification reads `http://127.0.0.1:8545`; to
use another node, add `?rpc=<url>` to the address. Don't commit a local
recording: its transactions exist only on your machine.
