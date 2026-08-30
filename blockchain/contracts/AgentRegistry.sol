// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Verifiable Agent Registry (VAR), per Ding et al. III-A.2. Binds
/// an on-chain address (the agent's identity anchor) to a DID and a hash of
/// its off-chain JSON-LD capability schema. The schema itself is never
/// stored on-chain — only its hash, so a PA that resolves the schema
/// off-chain can verify it matches what the SA committed here.
contract AgentRegistry {
    struct Agent {
        string did;
        bytes32 capabilityHash;
        bool active;
    }

    mapping(address => Agent) private agents;

    event AgentRegistered(address indexed agent, string did, bytes32 capabilityHash);
    event CapabilityUpdated(address indexed agent, bytes32 capabilityHash);
    event AgentRevoked(address indexed agent);

    function register(string calldata did, bytes32 capabilityHash) external {
        require(bytes(did).length > 0, "did required");
        require(!agents[msg.sender].active, "already registered");

        agents[msg.sender] = Agent(did, capabilityHash, true);
        emit AgentRegistered(msg.sender, did, capabilityHash);
    }

    function updateCapability(bytes32 capabilityHash) external {
        require(agents[msg.sender].active, "not registered");
        agents[msg.sender].capabilityHash = capabilityHash;
        emit CapabilityUpdated(msg.sender, capabilityHash);
    }

    function revoke() external {
        require(agents[msg.sender].active, "not registered");
        agents[msg.sender].active = false;
        emit AgentRevoked(msg.sender);
    }

    function resolve(address agent)
        external
        view
        returns (string memory did, bytes32 capabilityHash, bool active)
    {
        Agent storage a = agents[agent];
        return (a.did, a.capabilityHash, a.active);
    }
}
