/* ============================================================
   Invariant Subnet — Anam145
   STEP 1 은 이 페이지에서 실제로 실행된다 (src/retrieve.mjs 의 브라우저 포트).
   ============================================================ */
"use strict";

/* ─── i18n ────────────────────────────────────────────────── */
const I18N = {
  ko: {
    "hero.eyebrow": "Anam145 · Bittensor 보안 서브넷 제안",
    "hero.title": "취약점 채점은 판단이 아니라 실행이어야 한다",
    "hero.lede":
      "트랜잭션 히스토리가 0건인 신규 컨트랙트에서 검증 가능한 불변식을 만들고, 밸리데이터가 판단 없이 assert만 실행해도 재진입 공격이 탐지되는지 확인한 PoC.",
    "chip.target.k": "대상",
    "chip.target.v": "DeFiVulnLabs / SimpleBank",
    "chip.gen.k": "생성",
    "chip.gen.v": "claude-opus-5 + RAG",
    "chip.verify.k": "검증",
    "chip.verify.v": "Foundry",

    "prob.title": "보안 서브넷은 왜 실패하는가",
    "prob.p1":
      "제출물이 자유 서술 형태의 취약점 리포트면, 밸리데이터가 그것을 읽고 “이게 진짜 취약점인가”를 판정해야 한다. 판정하려면 밸리데이터가 마이너보다 유능해야 하고, 그 순간 신뢰 모델이 뒤집힌다. 서브넷은 그렇게 굴러가지 않는다.",
    "prob.p2":
      "익스플로잇 탐색 자체는 서브넷에 이상적인 문제다. 찾는 건 열려 있고 창의적이고 비싸지만, 확인하는 건 EVM에서 몇 밀리초짜리 결정론적 실행이다. 문제는 그 “확인”을 무엇으로 삼느냐였다.",
    "prob.ansLabel": "우리의 답",
    "prob.ans": "채점 단위를 리포트가 아니라 실행 가능한 assert 로 바꾼다.",
    "role.miner": "마이너",
    "role.minerD": "공격 PoC 탐색. 창의성이 필요한 열린 문제",
    "role.val": "밸리데이터",
    "role.valD": "assert 실행만. 분기·휴리스틱·판정 로직이 없다",
    "role.inv": "회사 / RAG",
    "role.invD": "invariant 공급. 표준은 자동 생성, 고유 로직은 감사자",

    "state.live": "이 페이지에서 실행됨",
    "state.pending": "미실행",
    "state.pendingForge": "Foundry 미실행",

    "s1.title": "코드만으로 검색한다",
    "s1.p1":
      "Trace2Inv 계열은 과거 거래를 관찰해 패턴을 뽑기 때문에 신규 컨트랙트에서는 아예 돌지 않는다. 이 단계는 코드 구조만 본다. 정적 signal 을 추출하고, 참조 property DB 를 그 signal 로 랭킹한다.",
    "s1.p2":
      "아래는 실제 DeFiVulnLabs 취약 컨트랙트다. 고쳐서 넣어보면 랭킹이 어떻게 움직이는지 볼 수 있다.",
    "s1.input": "입력 · Solidity",
    "s1.run": "분석 실행",
    "s1.fix": "CEI 순서 고쳐보기",
    "s1.reset": "원본 복원",
    "s1.sig": "탐지된 signal",
    "s1.cei": "check-effect-interaction 순서",
    "s1.rank": "참조 property 랭킹",
    "s1.rankNote": "강조된 상위 항목이 STEP 2 의 in-context 예시로 넘어간다.",
    "s1.ceiOk": "위반 없음 — 모든 상태 갱신이 외부 호출보다 먼저 실행된다.",
    "s1.ceiHit": "위반",
    "s1.ceiMid": "이",
    "s1.ceiTail": "보다 먼저 실행됨",

    "s2.title": "검색 결과를 예시로 주고 생성한다",
    "s2.p1":
      "출력은 JSON schema 로 강제되고, 각 항목은 반드시 실행 가능한 단일 assert 문을 포함해야 한다. “안전해야 한다” 같은 서술은 애초에 스키마를 통과하지 못한다.",
    "s2.warn":
      "<strong>이 단계는 아직 실행되지 않았다.</strong> 생성 환경에 API 키가 없었다. 아래는 실제로 전송되는 요청의 구조이며, 결과를 지어내지 않았다. 로컬에서 <code>npm run generate</code> 로 실행하면 채워진다.",
    "s2.req": "요청 구조",
    "s2.schema": "강제되는 출력 스키마 (발췌)",
    "s2.note":
      "<strong>solidity_assert 필드가 이 설계의 핵심이다.</strong> invariant 가 실행 가능한 형태로 강제되기 때문에, 밸리데이터는 그것을 심고 돌리기만 하면 된다.",

    "s3.title": "공격을 실행하고 invariant 를 평가한다",
    "s3.p1":
      "계정당 상한은 1,000 이고 공격자는 900 만 요청한다. claim() 이 token.transfer() 다음에 _mints[account] += 를 실행하므로, ERC777 훅 안에서 재진입하면 require 가 아직 갱신되지 않은 값을 다시 본다.",
    "s3.run": "공격 트레이스 실행",
    "s3.rewind": "되감기",
    "s3.warn":
      "<strong>이 트레이스는 코드에서 손으로 따라간 것이고, Foundry 로 측정한 값이 아니다.</strong> 생성 환경에 forge 가 설치돼 있지 않았다. 최종 잔액 1,900 은 DeFiVulnLabs 원본 주석 (“Expect 900, but we will get the 1,900 due to reenter to claim 1,000”) 과 일치한다.",
    "s3.code": "밸리데이터가 실제로 실행하는 코드 전부",
    "s3.codeNote":
      "분기도, 휴리스틱도, “이게 취약점인가”를 판정하는 로직도 없다. assert 가 Panic(0x01) 로 revert 하면 그것이 탐지다.",
    "s3.wait": "invariant 평가 대기",
    "s3.broken": "INVARIANT BROKEN · Panic(0x01)",
    "s3.concl": "밸리데이터는 판단하지 않았다. assert 를 실행했을 뿐이다.",

    "ev.title": "어디까지 확인됐나",
    "ev.h1": "주장",
    "ev.h2": "출처",
    "ev.h3": "상태",
    "lim.title": "정직하게 남는 한계",

    "foot.src":
      "DeFiVulnLabs / ERC777-reentrancy.sol (MIT) · Trace2Inv (MIT) · PropertyGPT, NDSS 2025",
    "foot.run":
      "STEP 1 은 이 페이지 안에서 실행됩니다. STEP 2·3 은 로컬 저장소에서 실행하세요."
  },

  en: {
    "hero.eyebrow": "Anam145 · Bittensor security subnet proposal",
    "hero.title": "Scoring an exploit should be execution, not judgment",
    "hero.lede":
      "A proof of concept: generate machine-checkable invariants for a contract with zero transaction history, then check whether a reentrancy attack is caught by a validator that only executes an assert and never judges anything.",
    "chip.target.k": "Target",
    "chip.target.v": "DeFiVulnLabs / SimpleBank",
    "chip.gen.k": "Generation",
    "chip.gen.v": "claude-opus-5 + RAG",
    "chip.verify.k": "Verification",
    "chip.verify.v": "Foundry",

    "prob.title": "Why security subnets fail",
    "prob.p1":
      "If a submission is a free-form vulnerability report, a validator has to read it and decide whether it is real. Deciding requires the validator to be more capable than the miner, which inverts the trust model. A subnet does not run that way.",
    "prob.p2":
      "Exploit discovery itself is an ideal subnet problem. Finding one is open-ended, creative and expensive; checking one is a few milliseconds of deterministic EVM execution. The open question was what to make that check out of.",
    "prob.ansLabel": "Our answer",
    "prob.ans": "Make the unit of scoring an executable assert, not a report.",
    "role.miner": "Miner",
    "role.minerD": "Searches for a working exploit — open-ended, creative work",
    "role.val": "Validator",
    "role.valD": "Runs the assert. No branching, no heuristic, no verdict logic",
    "role.inv": "Firm / RAG",
    "role.invD":
      "Supplies invariants. Standard classes generated, protocol-specific ones written by auditors",

    "state.live": "Runs in this page",
    "state.pending": "Not yet run",
    "state.pendingForge": "Foundry not yet run",

    "s1.title": "Retrieval from source alone",
    "s1.p1":
      "Trace2Inv-style tools mine patterns out of past transactions, so they cannot run at all on a fresh contract. This stage looks only at code structure: extract static signals, then rank a reference property corpus against them.",
    "s1.p2":
      "Below is the real DeFiVulnLabs contract. Edit it and the ranking moves.",
    "s1.input": "Input · Solidity",
    "s1.run": "Analyze",
    "s1.fix": "Fix the CEI order",
    "s1.reset": "Restore original",
    "s1.sig": "Detected signals",
    "s1.cei": "Check-effect-interaction order",
    "s1.rank": "Reference property ranking",
    "s1.rankNote":
      "The highlighted rows are passed to STEP 2 as in-context examples.",
    "s1.ceiOk":
      "No violation — every state write happens before any external call.",
    "s1.ceiHit": "Violation",
    "s1.ceiMid": "runs before",
    "s1.ceiTail": "",

    "s2.title": "Generate, using retrieval as the example set",
    "s2.p1":
      "Output is constrained by a JSON schema, and every item must carry a single executable assert. A sentence like “the contract should be safe” cannot pass the schema in the first place.",
    "s2.warn":
      "<strong>This stage has not been run yet.</strong> No API key was available in the environment that produced this page. What follows is the actual request shape — no output has been fabricated. Run <code>npm run generate</code> locally to fill it in.",
    "s2.req": "Request shape",
    "s2.schema": "Enforced output schema (excerpt)",
    "s2.note":
      "<strong>The solidity_assert field is the whole design.</strong> Because the invariant is forced into executable form, a validator only has to plant it and run it.",

    "s3.title": "Run the exploit, evaluate the invariant",
    "s3.p1":
      "The per-account cap is 1,000 and the attacker asks for only 900. Because claim() writes _mints[account] += after token.transfer(), reentering inside the ERC777 hook makes require read a value that has not been updated yet.",
    "s3.run": "Run attack trace",
    "s3.rewind": "Rewind",
    "s3.warn":
      "<strong>This trace was traced by hand from the source, not measured with Foundry.</strong> forge was not installed in the environment that produced this page. The final balance of 1,900 matches the upstream DeFiVulnLabs comment (“Expect 900, but we will get the 1,900 due to reenter to claim 1,000”).",
    "s3.code": "Everything the validator actually runs",
    "s3.codeNote":
      "No branching, no heuristic, no logic that decides whether something is a vulnerability. If the assert reverts with Panic(0x01), that is the detection.",
    "s3.wait": "Awaiting invariant evaluation",
    "s3.broken": "INVARIANT BROKEN · Panic(0x01)",
    "s3.concl": "The validator judged nothing. It executed an assert.",

    "ev.title": "What has actually been verified",
    "ev.h1": "Claim",
    "ev.h2": "Source",
    "ev.h3": "Status",
    "lim.title": "Limitations we are not hiding",

    "foot.src":
      "DeFiVulnLabs / ERC777-reentrancy.sol (MIT) · Trace2Inv (MIT) · PropertyGPT, NDSS 2025",
    "foot.run":
      "STEP 1 runs inside this page. STEP 2 and 3 run from the local repository."
  }
};

const EVIDENCE = {
  ko: [
    ["배포 컨트랙트: 23/27 차단 @ FP 3.99% · 20/27 @ FP 0.28%",
     "Trace2Inv (MIT) Docker 재현 — 저자 Expected 파일과 일치", "직접 재현", "ok"],
    ["신규 컨트랙트: 코드만으로 property 생성, recall 80% · 0-day 12건",
     "PropertyGPT (NDSS 2025) 논문값. 도구는 상업화되어 비공개", "인용 · 재현 불가", "partial"],
    ["STEP 1 검색이 reentrancy 를 최상위로 뽑는다",
     "이 페이지에서 실행 중 (score 7)", "라이브", "ok"],
    ["STEP 2 LLM 생성 결과", "API 키 부재로 미실행", "미검증", "no"],
    ["STEP 3 Foundry 실측", "forge 미설치. 트레이스는 수기 추적 + 원본 주석 대조", "미검증", "no"]
  ],
  en: [
    ["Deployed contracts: 23/27 exploits blocked @ 3.99% FP · 20/27 @ 0.28% FP",
     "Trace2Inv (MIT) reproduced in Docker — matches the authors' expected output",
     "Reproduced", "ok"],
    ["Fresh contracts: properties from source alone, 80% recall · 12 zero-days",
     "PropertyGPT (NDSS 2025) reported figures. Prototype is commercialized and closed",
     "Cited · not reproducible", "partial"],
    ["STEP 1 retrieval ranks reentrancy first", "Running in this page (score 7)", "Live", "ok"],
    ["STEP 2 LLM generation output", "Not run — no API key", "Unverified", "no"],
    ["STEP 3 Foundry measurement",
     "forge not installed. Trace hand-derived and cross-checked against the upstream comment",
     "Unverified", "no"]
  ]
};

const LIMITS = {
  ko: [
    "<b>검색기가 임베딩이 아니다.</b> STEP 1 은 정적 signal 매칭 기반의 lexical retriever 다. 결정론적이고 오프라인이라는 게 장점이지만, 참조 DB 에 없는 유형에는 일반화되지 않는다.",
    "<b>참조 DB 가 인간 property 의 대용품이다.</b> 실제 Certora 감사 리포트를 임베딩한 게 아니라, Trace2Inv 의 8개 카테고리 체계를 따라 손으로 쓴 11개 항목이다.",
    "<b>결국 표준 카테고리에 몰린다.</b> money_flow, reentrancy 같은 교과서 항목은 나오지만 프로토콜 고유 경제 invariant 는 안 나온다 — 참조 DB 에 없으니까. 그 부분이 감사자의 몫이고, 이게 사업의 근거이기도 하다.",
    "<b>단일 컨트랙트 데모다.</b> 실제 서브넷은 마이너가 다양한 컨트랙트에 이걸 해야 하므로 규모 문제는 별개로 남는다."
  ],
  en: [
    "<b>The retriever is not embedding-based.</b> STEP 1 is a lexical retriever over static signals. Deterministic and offline, which suits a demo — but it does not generalize to classes absent from the reference corpus.",
    "<b>The reference corpus is a stand-in for human properties.</b> It is not an embedding of real Certora audit reports; it is eleven entries written by hand, following Trace2Inv's eight-category taxonomy.",
    "<b>Output clusters in standard categories.</b> Textbook classes such as money_flow and reentrancy come out; protocol-specific economic invariants do not, because they are not in the corpus. That tier is the auditor's job — and it is exactly why the business exists.",
    "<b>This is a single-contract demo.</b> A real subnet needs miners doing this across many contracts, so the scaling question is separate and still open."
  ]
};

/* ─── 대상 컨트랙트 ───────────────────────────────────────── */
const ORIGINAL = `contract SimpleBank is Test {
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

    function tokensReceived(
        address operator, address from, address to,
        uint256 amount, bytes calldata data, bytes calldata operatorData
    ) external {}

    receive() external payable {}
}`;

const FIXED = ORIGINAL.replace(
  "        token.transfer(account, amount);\n        _mints[account] += amount;",
  "        _mints[account] += amount;\n        token.transfer(account, amount);"
);

/* ─── 참조 property DB ────────────────────────────────────── */
const SIGNAL_LABELS = {
  ko: {
    erc777_hook: "ERC777 / 1820 수신자 훅",
    external_call_before_state_write: "외부 호출 → 상태 갱신 순서",
    no_reentrancy_guard: "재진입 가드 없음",
    per_account_cap: "계정별 누적 상한",
    value_transfer: "자산 이동",
    tx_origin: "tx.origin 사용",
    owner_check: "owner 접근 제어",
    price_oracle: "외부 가격 소스",
    timestamp_dep: "타임스탬프 의존",
    total_supply: "totalSupply 참조",
    payable_receive: "payable 수신"
  },
  en: {
    erc777_hook: "ERC777 / 1820 recipient hook",
    external_call_before_state_write: "External call before state write",
    no_reentrancy_guard: "No reentrancy guard",
    per_account_cap: "Per-account accumulation cap",
    value_transfer: "Value transfer",
    tx_origin: "tx.origin used",
    owner_check: "Owner access control",
    price_oracle: "External price source",
    timestamp_dep: "Timestamp dependency",
    total_supply: "totalSupply referenced",
    payable_receive: "Payable receive"
  }
};

const PROPERTIES = [
  { id: "reentrancy/NonReentrantLock",
    w: { external_call_before_state_write: 3, erc777_hook: 2, no_reentrancy_guard: 1, value_transfer: 1 } },
  { id: "reentrancy/CheckEffectInteraction",
    w: { external_call_before_state_write: 4, no_reentrancy_guard: 1, value_transfer: 1 } },
  { id: "money_flow/PerAccountUpperBound",
    w: { per_account_cap: 3, value_transfer: 1, external_call_before_state_write: 1 } },
  { id: "money_flow/AccountingConservation",
    w: { value_transfer: 2, per_account_cap: 1, payable_receive: 1 } },
  { id: "special_storage/MonotonicCounter", w: { per_account_cap: 2 } },
  { id: "gas_control/GasUpperBound",
    w: { erc777_hook: 1, external_call_before_state_write: 1 } },
  { id: "access_control/OnlyEOA", w: { tx_origin: 3, erc777_hook: 1 } },
  { id: "access_control/OnlySenderOwner", w: { owner_check: 3 } },
  { id: "money_flow/TotalSupplyConsistency", w: { total_supply: 3 } },
  { id: "oracle/PriceDeviationBound", w: { price_oracle: 4, timestamp_dep: 1 } },
  { id: "time_lock/MinDelay", w: { timestamp_dep: 3, owner_check: 1 } }
];

const TOP_K = 5;

/* ─── 정적 분석 ───────────────────────────────────────────── */
function collectStateVars(src) {
  const names = new Set();
  const re = /^\s*(?:mapping\s*\([^;]*?\)|u?int\d*|address|bool|bytes\d*)\s+(?:public\s+|private\s+|internal\s+|constant\s+|immutable\s+)*(\w+)\s*(?:=|;)/gm;
  let m;
  while ((m = re.exec(src)) !== null) names.add(m[1]);
  return names;
}

function extractFunctions(src) {
  const out = [];
  const header = /function\s+(\w+)\s*\(/g;
  let m;
  while ((m = header.exec(src)) !== null) {
    const open = src.indexOf("{", m.index);
    if (open === -1) continue;
    let depth = 0, end = -1;
    for (let i = open; i < src.length; i++) {
      if (src[i] === "{") depth++;
      else if (src[i] === "}") { depth--; if (depth === 0) { end = i; break; } }
    }
    if (end === -1) continue;
    out.push({ name: m[1], body: src.slice(open + 1, end) });
  }
  return out;
}

function detectCEI(src) {
  const stateVars = collectStateVars(src);
  const violations = [];
  for (const fn of extractFunctions(src)) {
    const callRe = /\b(\w+)\s*\.\s*(transfer|transferFrom|send|safeTransfer|safeTransferFrom|call)\s*[({]/g;
    let firstCall = Infinity, callSite = null, c;
    while ((c = callRe.exec(fn.body)) !== null) {
      if (c.index < firstCall) { firstCall = c.index; callSite = c[1] + "." + c[2] + "(...)"; }
    }
    if (firstCall === Infinity) continue;
    const writeRe = /\b(\w+)\s*(?:\[[^\]]*\]\s*)?(\+=|-=|=)(?!=)/g;
    let w;
    while ((w = writeRe.exec(fn.body)) !== null) {
      if (!stateVars.has(w[1])) continue;
      if (w.index > firstCall) {
        violations.push({ fn: fn.name, call: callSite, write: w[1] + " " + w[2] + " ..." });
        break;
      }
    }
  }
  return violations;
}

function extractSignals(src) {
  const cei = detectCEI(src);
  const has = (re) => re.test(src);
  return {
    cei,
    signals: {
      erc777_hook: has(/ERC777|tokensReceived|tokensToSend|1820/),
      external_call_before_state_write: cei.length > 0,
      no_reentrancy_guard: !has(/nonReentrant|ReentrancyGuard/),
      per_account_cap: has(/mapping\s*\(\s*address\s*=>\s*uint\d*\s*\)/) && has(/<=\s*max\w*/i),
      value_transfer: has(/\.\s*(transfer|send)\s*\(|\.\s*call\s*\{\s*value/),
      tx_origin: has(/tx\s*\.\s*origin/),
      owner_check: has(/onlyOwner|require\s*\(\s*msg\s*\.\s*sender\s*==/),
      price_oracle: has(/getPrice|oracle|getReserves|latestAnswer|priceFeed/i),
      timestamp_dep: has(/block\s*\.\s*(timestamp|number)/),
      total_supply: has(/totalSupply/),
      payable_receive: has(/receive\s*\(\s*\)\s*external\s+payable|\bpayable\b/)
    }
  };
}

function rankProperties(signals) {
  return PROPERTIES.map((p) => {
    let score = 0; const matched = [];
    for (const [sig, weight] of Object.entries(p.w)) {
      if (signals[sig]) { score += weight; matched.push(sig + "(+" + weight + ")"); }
    }
    return { id: p.id, score, matched };
  }).sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
}

/* ─── 공격 트레이스 ───────────────────────────────────────── */
const CAP = 1000;
const TRACE = {
  ko: [
    ["depth 0", "attacker.attack()", "계정당 상한 1,000. 공격자는 900만 요청한다.", 0, 0, false],
    ["depth 1", "bank.claim(attacker, 900)", "require(_mints 0 + 900 <= 1000) — 통과", 0, 0, false],
    ["depth 1", "token.transfer(attacker, 900)", "interaction 이 먼저 실행된다. _mints 는 아직 0.", 900, 0, false],
    ["depth 2", "→ tokensReceived() 훅 진입", "ERC777 이 수신자에게 제어를 넘긴다.", 900, 0, true],
    ["depth 2", "bank.claim(attacker, 1000)", "require(_mints 0 + 1000 <= 1000) — 또 통과. stale 한 값을 봤다.", 900, 0, true],
    ["depth 2", "token.transfer(attacker, 1000)", "훅 재진입 없음 — 잔액이 1,000 을 넘었다.", 1900, 0, false],
    ["depth 2", "_mints[attacker] += 1000", "안쪽 호출의 effect 가 이제야 반영된다.", 1900, 1000, false],
    ["depth 1", "_mints[attacker] += 900", "바깥 호출의 effect. 누적 1,900.", 1900, 1900, false]
  ],
  en: [
    ["depth 0", "attacker.attack()", "Per-account cap is 1,000. The attacker asks for 900.", 0, 0, false],
    ["depth 1", "bank.claim(attacker, 900)", "require(_mints 0 + 900 <= 1000) — passes", 0, 0, false],
    ["depth 1", "token.transfer(attacker, 900)", "Interaction runs first. _mints is still 0.", 900, 0, false],
    ["depth 2", "→ tokensReceived() hook", "ERC777 hands control to the recipient.", 900, 0, true],
    ["depth 2", "bank.claim(attacker, 1000)", "require(_mints 0 + 1000 <= 1000) — passes again on a stale read.", 900, 0, true],
    ["depth 2", "token.transfer(attacker, 1000)", "No further reentry — balance now exceeds 1,000.", 1900, 0, false],
    ["depth 2", "_mints[attacker] += 1000", "The inner call's effect finally lands.", 1900, 1000, false],
    ["depth 1", "_mints[attacker] += 900", "The outer call's effect. Total 1,900.", 1900, 1900, false]
  ]
};

/* ─── 렌더링 ──────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
let lang = "ko";
const t = (k) => I18N[lang][k] ?? k;

function applyStaticText() {
  document.documentElement.lang = lang;
  for (const el of document.querySelectorAll("[data-i]")) {
    const v = t(el.dataset.i);
    if (/<[a-z]/i.test(v)) el.innerHTML = v;
    else el.textContent = v;
  }
}

function renderEvidence() {
  $("evbody").replaceChildren(...EVIDENCE[lang].map(([claim, src, verdict, kind]) => {
    const tr = document.createElement("tr");
    const a = document.createElement("td"); a.textContent = claim;
    const b = document.createElement("td"); b.textContent = src;
    const c = document.createElement("td");
    c.className = "verdict-cell " + kind;
    c.textContent = verdict;
    tr.append(a, b, c);
    return tr;
  }));
}

function renderLimits() {
  $("limits").replaceChildren(...LIMITS[lang].map((html) => {
    const li = document.createElement("li");
    li.innerHTML = html;
    return li;
  }));
}

function renderStep1() {
  const { signals, cei } = extractSignals($("src").value);
  const ranked = rankProperties(signals);
  const selected = new Set(ranked.filter((r) => r.score > 0).slice(0, TOP_K).map((r) => r.id));
  const labels = SIGNAL_LABELS[lang];

  $("sigs").replaceChildren(...Object.entries(signals).map(([key, on]) => {
    const d = document.createElement("div");
    d.className = "sig " + (on ? "on" : "off");
    const dot = document.createElement("span"); dot.className = "dot";
    const txt = document.createElement("span"); txt.textContent = labels[key] || key;
    d.append(dot, txt);
    return d;
  }));

  const box = $("ceibox");
  if (cei.length === 0) {
    box.className = "cei-ok";
    box.textContent = t("s1.ceiOk");
  } else {
    box.className = "cei";
    box.replaceChildren(...cei.map((v) => {
      const d = document.createElement("div");
      const b = document.createElement("b");
      b.textContent = t("s1.ceiHit") + " ";
      d.append(b, document.createTextNode(
        v.fn + "() : " + v.call + " " + t("s1.ceiMid") + " " + v.write + " " + t("s1.ceiTail")
      ));
      return d;
    }));
  }

  $("rank").replaceChildren(...ranked.map((r) => {
    const row = document.createElement("div");
    row.className = "row " + (selected.has(r.id) ? "sel" : "dim");
    const s = document.createElement("span");
    s.className = "score"; s.textContent = r.score;
    const body = document.createElement("span");
    const pid = document.createElement("span");
    pid.className = "pid"; pid.textContent = r.id;
    body.append(pid);
    if (r.matched.length) {
      const sg = document.createElement("span");
      sg.className = "sigs"; sg.textContent = r.matched.join("  ");
      body.append(sg);
    }
    row.append(s, body);
    return row;
  }));
}

let timers = [];
const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };

function buildTrace() {
  $("trace").replaceChildren(...TRACE[lang].map(([depth, what, note, bal, mints, reenter]) => {
    const row = document.createElement("div");
    row.className = "tstep" + (reenter ? " reenter" : "");
    const d = document.createElement("span");
    d.className = "depth"; d.textContent = depth;
    const w = document.createElement("span");
    w.className = "what";
    w.append(document.createTextNode(what));
    const n = document.createElement("span");
    n.className = "note"; n.textContent = note;
    w.append(n);
    const st = document.createElement("span");
    st.className = "state-n";
    st.textContent = "bal " + bal + " · _mints " + mints;
    row.append(d, w, st);
    return row;
  }));
  const v = $("verdict");
  v.className = "verdict";
  v.textContent = t("s3.wait");
}

function runTrace() {
  clearTimers();
  buildTrace();
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const gap = reduced ? 0 : 480;
  const rows = $("trace").children;

  for (let i = 0; i < rows.length; i++) {
    timers.push(setTimeout(() => rows[i].classList.add("shown"), i * gap));
  }
  timers.push(setTimeout(() => {
    const last = TRACE[lang][TRACE[lang].length - 1];
    const [, , , bal, mints] = last;
    const v = $("verdict");
    v.className = "verdict shown broken";
    v.replaceChildren();
    const tag = document.createElement("span");
    tag.className = "tag"; tag.textContent = t("s3.broken");
    const e1 = document.createElement("span");
    e1.className = "expr";
    e1.textContent = "assert(bank._mints(attacker) <= bank.maxMints())  →  " + mints + " <= " + CAP + "  →  false";
    const e2 = document.createElement("span");
    e2.className = "expr";
    e2.textContent = "assert(token.balanceOf(attacker) <= bank.maxMints())  →  " + bal + " <= " + CAP + "  →  false";
    const c = document.createElement("span");
    c.className = "concl"; c.textContent = t("s3.concl");
    v.append(tag, e1, e2, c);
  }, rows.length * gap + (reduced ? 0 : 180)));
}

function setLang(next) {
  lang = next;
  for (const b of document.querySelectorAll(".lang button")) {
    b.classList.toggle("on", b.dataset.lang === next);
  }
  applyStaticText();
  renderEvidence();
  renderLimits();
  renderStep1();
  clearTimers();
  buildTrace();
}

/* ─── init ────────────────────────────────────────────────── */
$("src").value = ORIGINAL;
$("run1").addEventListener("click", renderStep1);
$("fix").addEventListener("click", () => { $("src").value = FIXED; renderStep1(); });
$("reset").addEventListener("click", () => { $("src").value = ORIGINAL; renderStep1(); });
$("run3").addEventListener("click", runTrace);
$("reset3").addEventListener("click", () => { clearTimers(); buildTrace(); });
for (const b of document.querySelectorAll(".lang button")) {
  b.addEventListener("click", () => setLang(b.dataset.lang));
}

setLang(new URLSearchParams(location.search).get("lang") === "en" ? "en" : "ko");
