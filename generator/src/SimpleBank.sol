// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC777/ERC777.sol";

/*
  TARGET CONTRACT — the only input to the invariant generator (stages 1 and 2).

  Source (extracted without modifying the logic):
    https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol

  Vulnerability: reentrancy through the ERC777 tokensReceived hook.
  claim() does not follow check-effect-interaction — it calls token.transfer()
  (the interaction) before _mints[account] += amount (the effect). An attacker
  reenters claim() from inside the hook and bypasses the per-account cap of 1,000.

  No comment hinting at the bug is left in this file, on purpose: the point is to
  test whether the model derives the invariants from code structure alone. The
  upstream `// Do not follow check-effect-interaction` comment was removed.
*/

contract SimpleBank is Test {
    ERC777 private token;
    uint maxMintsPerAddress = 1000;
    mapping(address => uint256) public _mints;
    bytes32 private constant _TOKENS_RECIPIENT_INTERFACE_HASH =
        keccak256("ERC777TokensRecipient");

    constructor(address tokenAddress) {
        token = ERC777(tokenAddress);

        IERC1820Registry registry = IERC1820Registry(
            address(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24)
        );
        registry.setInterfaceImplementer(
            address(this),
            _TOKENS_RECIPIENT_INTERFACE_HASH,
            address(this)
        );
    }

    function claim(address account, uint256 amount) public returns (bool) {
        require(
            _mints[account] + amount <= maxMintsPerAddress,
            "Exceeds max mints per address"
        );

        token.transfer(account, amount);
        _mints[account] += amount;

        return true;
    }

    function maxMints() external view returns (uint256) {
        return maxMintsPerAddress;
    }

    function tokenAddress() external view returns (address) {
        return address(token);
    }

    function tokensReceived(
        address operator,
        address from,
        address to,
        uint256 amount,
        bytes calldata data,
        bytes calldata operatorData
    ) external {}

    receive() external payable {}
}
