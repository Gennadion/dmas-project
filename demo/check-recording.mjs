// Runs the page's verification (verify.js) over every exchange in a
// recording, from Node. Used by agents/tests/test_recording.py, and handy
// for checking a fresh Sepolia recording before committing it:
//
//   node demo/check-recording.mjs demo/run.json [rpc-url]
//
// Exits non-zero if any check fails.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { verifyExchange } from "./verify.js";

const PUBLIC_RPCS = {
  11155111: "https://ethereum-sepolia-rpc.publicnode.com",
  31337: "http://127.0.0.1:8545",
};

// ethers lives in blockchain/node_modules (via hardhat-toolbox).
const require = createRequire(fileURLToPath(new URL("../blockchain/package.json", import.meta.url)));
const { ethers } = require("ethers");

const [file, rpcArg] = process.argv.slice(2);
if (!file) {
  console.error("usage: node demo/check-recording.mjs <run.json> [rpc-url]");
  process.exit(2);
}
const recording = JSON.parse(readFileSync(file, "utf8"));
const provider = new ethers.JsonRpcProvider(rpcArg ?? PUBLIC_RPCS[recording.chainId]);

let failures = 0;
for (const run of recording.runs) {
  for (const exchange of run.exchanges) {
    const checks = await verifyExchange({ ethers, provider, subtle: globalThis.crypto.subtle, recording, run, exchange });
    for (const c of checks) {
      if (!c.ok) failures++;
      console.log(`${c.ok ? "ok  " : "FAIL"} [${run.strategy}] ${exchange.sa}: ${c.label} — ${c.detail}`);
    }
  }
}
provider.destroy();
console.log(failures ? `${failures} check(s) failed` : "all checks passed");
process.exit(failures ? 1 : 0);
