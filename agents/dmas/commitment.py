"""Com(u, s): the verifiable request/response commitment protocol (Ding et
al. III-B.2), run against CommunicationLedger.

    PA                                 chain                              SA
    commitRequest(s, H(P(req)))  ->  X(P(req))
    -- P(req), requestId (off-chain) ------------------------------------->
                                                  verify H(P(req)) == commitment
                                                  reason, encrypt under fresh kappa
                                 <-  X(resp) = commitResponse(requestId, H(enc), eta)
    <------------------------------------ enc, responseId (off-chain) --
    verify H(enc) == commitment
    fulfillCondition(responseId) ->  pays eta to SA (Property IV.4)
                                                  verify fulfilled on-chain
    <------------------------------------------ kappa (off-chain) --
    decrypt enc

Only hashes and eta go on-chain. The off-chain legs are plain in-process
method calls (Step 3's in-process decision still holds), but each side only
trusts what it can check against the chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from eth_account.signers.local import LocalAccount
from web3 import Web3

from dmas.chain import Chain, ChainError
from dmas.service_agent import ServiceAgent
from dmas.types import Commitment, Request, Response

_NONCE_LEN = 12
_TAG_LEN = 16


def _h(data: bytes) -> bytes:
    return Web3.keccak(data)


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    nonce = get_random_bytes(_NONCE_LEN)
    ciphertext, tag = AES.new(key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(plaintext)
    return nonce + tag + ciphertext


def decrypt(key: bytes, blob: bytes) -> bytes:
    nonce, tag, ciphertext = blob[:_NONCE_LEN], blob[_NONCE_LEN : _NONCE_LEN + _TAG_LEN], blob[_NONCE_LEN + _TAG_LEN :]
    return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ciphertext, tag)


@dataclass
class ServiceEndpoint:
    """The SA's side of Com(u, s): its on-chain identity (account), its
    off-chain reasoning (ServiceAgent), and the price eta it charges per
    response. Holds kappa only between committing a response and releasing
    it -- per-exchange state, not memory across requests (III-A.4)."""

    agent: ServiceAgent
    account: LocalAccount
    eta_wei: int = 0
    _pending_keys: dict[bytes, bytes] = field(default_factory=dict, repr=False)

    def respond(self, chain: Chain, request_id: bytes, payload: bytes) -> tuple[bytes, bytes]:
        """Verify the request against its on-chain commitment, reason over
        it, and commit to the encrypted response. Returns (responseId, enc)."""
        sender, recipient, payload_hash, _, exists = chain.ledger.functions.requests(request_id).call()
        if not exists or recipient != self.account.address:
            raise ChainError(f"{self.agent.sa_id}: request {request_id.hex()} is not addressed to me")
        if payload_hash != _h(payload):
            raise ChainError(f"{self.agent.sa_id}: payload does not match its on-chain commitment")

        response = self.agent.handle(Request.from_bytes(payload))

        key = get_random_bytes(32)
        enc = encrypt(key, response.to_bytes())
        receipt = chain.transact(
            self.account, chain.ledger.functions.commitResponse(request_id, _h(enc), self.eta_wei)
        )
        response_id = chain.ledger.events.ResponseCommitted().process_receipt(receipt)[0]["args"]["responseId"]
        self._pending_keys[response_id] = key
        return response_id, enc

    def release_key(self, chain: Chain, response_id: bytes) -> bytes:
        """Release kappa only once eta is satisfied on-chain."""
        *_, fulfilled, exists = chain.ledger.functions.responses(response_id).call()
        if not (exists and fulfilled):
            raise ChainError(f"{self.agent.sa_id}: condition for {response_id.hex()} not fulfilled")
        return self._pending_keys.pop(response_id)


def communicate(chain: Chain, requester: LocalAccount, endpoint: ServiceEndpoint, request: Request) -> Response:
    """Run Com(u, s) end to end from the PA's side and return the decrypted,
    verified response with its on-chain Commitment attached."""
    payload = request.to_bytes()
    receipt = chain.transact(
        requester, chain.ledger.functions.commitRequest(endpoint.account.address, _h(payload))
    )
    request_id = chain.ledger.events.RequestCommitted().process_receipt(receipt)[0]["args"]["requestId"]

    response_id, enc = endpoint.respond(chain, request_id, payload)

    committed_request_id, responder, enc_hash, eta_wei, _, exists = chain.ledger.functions.responses(
        response_id
    ).call()
    if not exists or committed_request_id != request_id or responder != endpoint.account.address:
        raise ChainError(f"response {response_id.hex()} does not answer request {request_id.hex()}")
    if enc_hash != _h(enc):
        raise ChainError(f"encrypted response from {endpoint.agent.sa_id} does not match its commitment")

    chain.transact(requester, chain.ledger.functions.fulfillCondition(response_id), value=eta_wei)

    key = endpoint.release_key(chain, response_id)
    response = Response.from_bytes(decrypt(key, enc))
    if response.sa_id != endpoint.agent.sa_id:
        raise ChainError(f"response claims to be from {response.sa_id}, expected {endpoint.agent.sa_id}")

    return replace(
        response,
        commitment=Commitment(request_id=request_id, response_id=response_id, eta_wei=eta_wei),
    )
