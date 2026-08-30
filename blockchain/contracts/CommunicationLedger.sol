// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AgentRegistry.sol";

/// @notice On-chain half of Ding et al.'s trust-aware communication protocol
/// (III-B.2): request commitment, response commitment, and condition
/// fulfillment (Property IV.4). Off-chain payloads/responses (P(▷), the raw
/// response) never touch the chain, per the paper's design — only their
/// hashes and the payment condition η are committed here. The response
/// decryption key exchange (κ, κ̄) also stays off-chain, exactly as the
/// paper specifies for Response Retrieval steps 3-4.
contract CommunicationLedger {
    AgentRegistry public immutable registry;

    struct RequestCommitment {
        address sender;
        address recipient;
        bytes32 payloadHash;
        uint256 timestamp;
        bool exists;
    }

    struct ResponseCommitment {
        bytes32 requestId;
        address responder;
        bytes32 encryptedResponseHash;
        uint256 conditionAmount; // eta: wei payable to the responder to release kappa
        bool fulfilled;
        bool exists;
    }

    mapping(bytes32 => RequestCommitment) public requests;
    mapping(bytes32 => ResponseCommitment) public responses;
    uint256 private nonce;

    event RequestCommitted(
        bytes32 indexed requestId,
        address indexed sender,
        address indexed recipient,
        bytes32 payloadHash,
        uint256 timestamp
    );
    event ResponseCommitted(
        bytes32 indexed responseId,
        bytes32 indexed requestId,
        address indexed responder,
        bytes32 encryptedResponseHash,
        uint256 conditionAmount
    );
    event ConditionFulfilled(bytes32 indexed responseId, address indexed payer, uint256 amount);

    constructor(address registryAddress) {
        registry = AgentRegistry(registryAddress);
    }

    function _isActive(address agent) private view returns (bool) {
        (, , bool active) = registry.resolve(agent);
        return active;
    }

    /// @dev Corresponds to X(P(▷)) = <DID(u), DID(s), H(P(▷))>.
    function commitRequest(address recipient, bytes32 payloadHash)
        external
        returns (bytes32 requestId)
    {
        require(_isActive(msg.sender), "sender not registered");
        require(_isActive(recipient), "recipient not registered");

        requestId = keccak256(
            abi.encodePacked(msg.sender, recipient, payloadHash, block.timestamp, nonce++)
        );
        requests[requestId] = RequestCommitment(msg.sender, recipient, payloadHash, block.timestamp, true);
        emit RequestCommitted(requestId, msg.sender, recipient, payloadHash, block.timestamp);
    }

    /// @dev Corresponds to X(◁) = <H(X(P(▷))), H(◁̄), η>, with η simplified
    /// to the paper's own example condition: payment of conditionAmount.
    function commitResponse(
        bytes32 requestId,
        bytes32 encryptedResponseHash,
        uint256 conditionAmount
    ) external returns (bytes32 responseId) {
        RequestCommitment storage req = requests[requestId];
        require(req.exists, "unknown request");
        require(req.recipient == msg.sender, "not addressed to sender");

        responseId = keccak256(abi.encodePacked(requestId, encryptedResponseHash, block.timestamp));
        responses[responseId] = ResponseCommitment(
            requestId,
            msg.sender,
            encryptedResponseHash,
            conditionAmount,
            false,
            true
        );
        emit ResponseCommitted(responseId, requestId, msg.sender, encryptedResponseHash, conditionAmount);
    }

    /// @dev Property IV.4: the requester satisfies η on-chain; the contract
    /// verifies and forwards payment, giving an irrefutable, timestamped
    /// state change the responder can check before releasing κ off-chain.
    function fulfillCondition(bytes32 responseId) external payable {
        ResponseCommitment storage res = responses[responseId];
        require(res.exists, "unknown response");
        require(!res.fulfilled, "already fulfilled");

        RequestCommitment storage req = requests[res.requestId];
        require(req.sender == msg.sender, "not original requester");
        require(msg.value == res.conditionAmount, "wrong payment amount");

        res.fulfilled = true;
        emit ConditionFulfilled(responseId, msg.sender, msg.value);

        (bool sent, ) = payable(res.responder).call{value: msg.value}("");
        require(sent, "payment transfer failed");
    }
}
