// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Minimal sanity-check contract for verifying the Hardhat toolchain
/// (compile -> deploy -> call -> observe) end to end, before the real DMAS
/// observability/audit contracts are designed in a later step.
contract Ping {
    uint256 public pingCount;

    event Pinged(address indexed sender, uint256 newCount, uint256 timestamp);

    function ping() external {
        pingCount += 1;
        emit Pinged(msg.sender, pingCount, block.timestamp);
    }
}
