// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC777/ERC777.sol";

/*
  TARGET CONTRACT — 이 파일이 invariant 생성기(STEP 1/2)의 유일한 입력이다.

  출처 (수정 없이 발췌):
    https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol

  취약점: ERC777 tokensReceived 훅을 통한 reentrancy.
  claim()이 check-effect-interaction 을 지키지 않는다 —
  token.transfer() (interaction) 를 _mints[account] += amount (effect) 보다 먼저 호출한다.
  공격자는 훅 안에서 claim()을 재진입해 계정당 상한 1,000을 우회할 수 있다.

  이 파일에는 "취약하다"는 힌트를 주는 주석을 일부러 남겨두지 않았다 —
  LLM이 코드 구조만 보고 invariant를 뽑아내는지 검증하기 위함이다.
  (원본의 `// Do not follow check-effect-interaction` 주석은 제거했다.)
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
