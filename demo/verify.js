// Re-checks one recorded Com(u, s) exchange against the chain, trusting
// nothing in the recording that the chain (or the math) can't confirm.
// Shared by the page (ethers from a CDN, the browser's WebCrypto) and by
// check-recording.mjs (ethers from blockchain/node_modules, Node's WebCrypto),
// so CI exercises exactly the code visitors run.

export const LEDGER_ABI = [
  "function requests(bytes32) view returns (address sender, address recipient, bytes32 payloadHash, uint256 timestamp, bool exists)",
  "function responses(bytes32) view returns (bytes32 requestId, address responder, bytes32 encryptedResponseHash, uint256 conditionAmount, bool fulfilled, bool exists)",
];
export const REGISTRY_ABI = [
  "function resolve(address) view returns (string did, bytes32 capabilityHash, bool active)",
];

// Ciphertext layout from agents/dmas/commitment.py: nonce(12) | tag(16) | ct.
const NONCE_LEN = 12;
const TAG_LEN = 16;

async function decrypt(ethers, subtle, keyHex, blobHex) {
  const blob = ethers.getBytes(blobHex);
  const nonce = blob.slice(0, NONCE_LEN);
  const tag = blob.slice(NONCE_LEN, NONCE_LEN + TAG_LEN);
  const body = blob.slice(NONCE_LEN + TAG_LEN);
  // WebCrypto expects ciphertext || tag.
  const sealed = new Uint8Array(body.length + TAG_LEN);
  sealed.set(body);
  sealed.set(tag, body.length);
  const key = await subtle.importKey("raw", ethers.getBytes(keyHex), "AES-GCM", false, ["decrypt"]);
  const plain = await subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, sealed);
  return JSON.parse(new TextDecoder().decode(plain));
}

const same = (a, b) => a.toLowerCase() === b.toLowerCase();

/**
 * @returns {Promise<{label: string, ok: boolean, detail: string}[]>}
 */
export async function verifyExchange({ ethers, provider, subtle, recording, run, exchange }) {
  const ledger = new ethers.Contract(recording.contracts.CommunicationLedger, LEDGER_ABI, provider);
  const registry = new ethers.Contract(recording.contracts.AgentRegistry, REGISTRY_ABI, provider);
  const checks = [];
  const check = (label, ok, detail) => checks.push({ label, ok: Boolean(ok), detail });

  const [did, , active] = await registry.resolve(exchange.address);
  check(
    "Service agent is registered",
    did === exchange.sa,
    `AgentRegistry.resolve(${exchange.address}) → ${did || "nothing"}${active ? "" : " (inactive now)"}`
  );

  const req = await ledger.requests(exchange.requestId);
  const payloadHash = ethers.keccak256(run.requestBytes);
  check(
    "Request commitment matches",
    req.exists &&
      same(req.sender, recording.proxyAgent.address) &&
      same(req.recipient, exchange.address) &&
      req.payloadHash === payloadHash,
    `on-chain H(P(▷)) ${req.payloadHash.slice(0, 18)}…, recomputed ${payloadHash.slice(0, 18)}…`
  );

  const res = await ledger.responses(exchange.responseId);
  const encHash = ethers.keccak256(exchange.ciphertext);
  check(
    "Response commitment matches",
    res.exists &&
      res.requestId === exchange.requestId &&
      same(res.responder, exchange.address) &&
      res.encryptedResponseHash === encHash &&
      res.conditionAmount.toString() === exchange.etaWei,
    `on-chain H(enc) ${res.encryptedResponseHash.slice(0, 18)}…, recomputed ${encHash.slice(0, 18)}…; η = ${res.conditionAmount} wei`
  );

  check("Condition η fulfilled on-chain", res.fulfilled, res.fulfilled ? "payment recorded" : "not fulfilled");

  const txs = await Promise.all(Object.values(exchange.txs).map((h) => provider.getTransactionReceipt(h)));
  check(
    "All three transactions succeeded",
    txs.every((r) => r && r.status === 1 && same(r.to, recording.contracts.CommunicationLedger)),
    txs.map((r) => (r ? `block ${r.blockNumber}` : "missing")).join(", ")
  );

  try {
    const plain = await decrypt(ethers, subtle, exchange.key, exchange.ciphertext);
    check(
      "κ decrypts the committed ciphertext to the recorded response",
      plain.sa_id === exchange.sa &&
        plain.is_terminal === exchange.terminal &&
        plain.payload === exchange.response.payload &&
        JSON.stringify(plain.forwarded) === JSON.stringify(exchange.response.forwarded),
      plain.is_terminal ? `“${plain.payload}”` : `forward → ${plain.forwarded.join(", ")}`
    );
  } catch (error) {
    check("κ decrypts the committed ciphertext to the recorded response", false, `decryption failed: ${error.message}`);
  }

  return checks;
}
