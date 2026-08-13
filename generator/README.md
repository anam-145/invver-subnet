# generator

신규 컨트랙트(트랜잭션 히스토리 0건)에서 **코드만으로 검증 가능한 invariant를 생성**하고,
밸리데이터가 **판단하지 않고 assert만 실행해도** 재진입 공격이 탐지되는지 확인하는 PoC.

Anam145 Bittensor 서브넷 설계의 부품 검증용.

---

## 무엇을 증명하려는가

설계의 핵심 모순은 이거였다: 제출물이 자유 서술이면 밸리데이터가 "이게 취약점인가"를 판단해야 하고,
그럼 밸리데이터가 마이너보다 유능해야 한다. 서브넷은 그렇게 굴러가지 않는다.

invariant를 **실행 가능한 assert 형태로 강제**하면 판단이 실행으로 바뀐다.

```
마이너      = 공격 PoC 탐색          →  test/InvariantCheck.t.sol 의 Attacker
밸리데이터  = assert 실행만          →  같은 파일의 InvariantChecker (분기 없음)
invariant   = 회사/RAG가 공급        →  src/generate_invariants.mjs
```

---

## 대상 컨트랙트

**DeFiVulnLabs / `SimpleBank`** — ERC777 reentrancy.

- 원본: https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol
- `src/SimpleBank.sol` 은 위 파일에서 `SimpleBank` 컨트랙트를 발췌한 것이다.
  로직은 **수정하지 않았다.** 원본의 `// Do not follow check-effect-interaction` 주석만 제거했다 —
  LLM이 힌트 없이 코드 구조만으로 invariant를 뽑는지 보기 위함.

왜 DeFiHackLabs가 아니라 DeFiVulnLabs인가: DeFiHackLabs는 실제 사건이라 메인넷 fork(아카이브 RPC + API 키)가
필요하다. DeFiVulnLabs는 교육용 단일 파일 예제라 fork 없이 코드만으로 돌아가고,
"코드만으로 invariant 생성"이라는 명제에 정확히 맞는다.

### 취약점

```solidity
function claim(address account, uint256 amount) public returns (bool) {
    require(_mints[account] + amount <= maxMintsPerAddress, "Exceeds max mints per address");

    token.transfer(account, amount);   // ← interaction 이 먼저
    _mints[account] += amount;         // ← effect 가 나중  (CEI 위반)

    return true;
}
```

상한 1,000. 공격자가 900을 요청 → `transfer` 중 ERC777 훅이 발동 →
훅 안에서 `claim(this, 1000)` 재진입 → `require`가 아직 0인 `_mints`를 다시 봄 → 통과.
최종 잔액 1,900.

---

## 파이프라인

| 단계 | 하는 일 | API 키 | 실행 상태 |
|---|---|---|---|
| STEP 1 | RAG 검색 — 정적 signal 추출 + 참조 property 랭킹 | 불필요 | ✅ 검증됨 |
| STEP 2 | LLM invariant 생성 (`claude-opus-5`, JSON schema 강제) | 필요 | ⬜ 미실행 |
| STEP 3 | Foundry로 공격 실행 + invariant 평가 | 불필요 (forge 필요) | ⬜ 미실행 |

STEP 2·3이 미실행인 이유는 아래 **"아직 검증되지 않은 것"** 참고.

---

## 실행

### 준비

```bash
cd generator
npm install
```

### STEP 1 — API 키 없이 바로

```bash
npm run step1
```

실측 출력:

```
탐지된 signal:
  ✓ erc777_hook
  ✓ external_call_before_state_write
  ✓ no_reentrancy_guard
  ✓ per_account_cap
  ✓ value_transfer
  · tx_origin / owner_check / price_oracle / timestamp_dep / total_supply
  ✓ payable_receive

check-effect-interaction 위반:
  ! claim(): token.transfer(...)  →  _mints += ...

참조 property 랭킹:
  → [score  7] reentrancy/NonReentrantLock
  → [score  6] reentrancy/CheckEffectInteraction
  → [score  5] money_flow/PerAccountUpperBound
  → [score  4] money_flow/AccountingConservation
  → [score  2] gas_control/GasUpperBound
    [score  2] special_storage/MonotonicCounter
    [score  1] access_control/OnlyEOA
    [score  0] access_control/OnlySenderOwner
    [score  0] money_flow/TotalSupplyConsistency
    [score  0] oracle/PriceDeviationBound
    [score  0] time_lock/MinDelay
```

트랜잭션 히스토리 0건 상태에서 reentrancy를 1위로 검색했고, CEI 위반 함수를 자동으로 짚었다.
**"신규 컨트랙트도 검색 단계는 API 없이 작동한다"가 여기서 확인된다.**

### STEP 2 — LLM 생성

두 경로가 있다. 결과물은 같다.

**(a) API 키가 있을 때**

```bash
# PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
npm run generate

# bash
export ANTHROPIC_API_KEY=sk-ant-...
npm run generate
```

`ant auth login` 으로 프로필을 만들어 두었다면 환경변수 없이도 동작한다.
결과는 콘솔에 출력되고 `out/invariants.json` 에 저장된다.

**(b) API 크레딧 없이 — 웹 UI 로 수동 실행**

```bash
npm run prompt
```

`out/prompt.md` 에 API 가 보낼 것과 동일한 프롬프트가 쓰인다.
SYSTEM PROMPT / USER MESSAGE / 스키마 블록을 claude.ai 새 대화에 붙여넣고,
받은 JSON 을 `out/invariants.json` 으로 저장하면 이후 단계가 그대로 이어진다.

동일한 프롬프트·동일한 모델이므로 결과는 실제 실행 결과다.
다만 출력이 스키마로 **강제**되지는 않으므로(웹 UI 에는 `output_config.format` 이 없다),
받은 JSON 이 스키마를 지키는지 눈으로 확인할 것. 인용할 때는 실행 경로를 밝힐 것 —
"generated via the web interface using the pipeline's prompt".

### STEP 3 — Foundry 검증

```bash
# Foundry 설치 (없다면)
curl -L https://foundry.paradigm.xyz | bash && foundryup

forge init --force --no-commit .
forge install foundry-rs/forge-std --no-commit
forge install OpenZeppelin/openzeppelin-contracts@v4.9.6 --no-commit   # ERC777 은 v5 에서 제거됨

forge test --match-contract InvariantCheckTest -vv
```

기대 결과 — **3개 모두 `[PASS]`**:

| 테스트 | 뜻 |
|---|---|
| `testExploitSucceedsWithoutInvariant` | assert가 없으면 공격이 revert 없이 성공한다 (잔액 1,900) |
| `testInvariantCatchesExploit` | invariant를 심으면 공격이 그것을 깬다 — Panic(0x01) |
| `testInvariantAllowsBenign` | 정상 거래에서는 안 깨진다 (FP 0) |

> `testInvariantCatchesExploit` 은 `vm.expectRevert(stdError.assertionError)` 로 감쌌기 때문에
> **탐지 성공 = PASS** 다. "FAIL이 정상"인 구조가 아니다.

---

## 파일 구조

```
generator/
├── src/
│   ├── SimpleBank.sol           대상 취약 컨트랙트 (DeFiVulnLabs 발췌, 로직 무수정)
│   ├── reference_db.json        참조 property DB — 11개 항목, 손으로 작성
│   ├── retrieve.mjs             STEP 1: 정적 signal 추출 + CEI 탐지 + 랭킹
│   └── generate_invariants.mjs  CLI: STEP 1 + STEP 2 (Anthropic SDK)
├── test/
│   └── InvariantCheck.t.sol     STEP 3: Attacker / InvariantChecker / BenignUser
├── demo.html                    브라우저 데모 — STEP 1 은 실제로 돌아감
├── foundry.toml
└── package.json
```

---

## 아직 검증되지 않은 것 (정직하게)

생성 환경(Windows, Node v22)에는 **API 키도 `forge`도 없었다.** 따라서:

- **STEP 2는 한 번도 실행되지 않았다.** LLM이 실제로 어떤 invariant를 뽑는지는 미확인이다.
  `README`·`demo.html` 어디에도 지어낸 LLM 출력은 넣지 않았다.
- **STEP 3의 Foundry 테스트는 컴파일조차 되지 않았다.** 위의 "기대 결과"는 코드에서 손으로 따라간 것이다.
  최종 잔액 1,900은 DeFiVulnLabs 원본 주석
  (*"Expect 900 (the claim amount), but we will get the 1,900 due to reenter to claim 1,000"*)과 일치한다.
- `test/InvariantCheck.t.sol` 은 처음 `forge test` 를 돌릴 때 컴파일 에러가 날 수 있다
  (특히 OZ v4 경로·pragma). 그건 정상적인 첫 실행이다.

---

## 설계상 남는 한계

1. **검색기가 임베딩이 아니다.** STEP 1은 정적 signal 매칭 기반의 lexical retriever다.
   결정론적이고 오프라인이라는 게 장점이지만, 참조 DB에 없는 유형에는 일반화되지 않는다.
   PropertyGPT의 실제 방식(Certora 리포트 임베딩 + 유사도 검색)과는 다르다.
2. **참조 DB가 인간 property의 대용품이다.** 실제 Certora 감사 리포트를 임베딩한 게 아니라,
   Trace2Inv의 8개 카테고리 체계를 따라 손으로 쓴 11개 항목이다.
3. **결국 표준 카테고리에 몰린다.** money_flow, reentrancy 같은 교과서 항목은 나오지만
   **프로토콜 고유 경제 invariant는 여전히 안 나온다** — 참조 DB에 없으니까.
   그 부분이 Anam145 감사자의 몫이고, 이게 사업의 근거이기도 하다.
4. **단일 컨트랙트 데모다.** 실제 서브넷은 마이너가 다양한 컨트랙트에 이걸 해야 하므로
   규모 문제는 별개로 남는다.

---

## 근거 출처

| 주장 | 출처 | 상태 |
|---|---|---|
| 배포 컨트랙트: 23/27 차단 @ FP 3.99% · 20/27 @ FP 0.28% | Trace2Inv (MIT), Docker 재현 — 저자 Expected 파일과 일치 | 직접 재현 |
| 신규 컨트랙트: recall 80%, 0-day 12건 | PropertyGPT (NDSS 2025) 논문값. 프로토타입은 MetaTrust Labs가 상업화, 비공개 | 인용 · 재현 불가 |
| 대상 취약 컨트랙트 | DeFiVulnLabs (MIT) | 원본 그대로 |
