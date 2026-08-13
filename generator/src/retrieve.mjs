// STEP 1 — RAG 검색 (정적 signal 추출 + 참조 property 랭킹)
//
// 입력: Solidity 소스 문자열 하나. 트랜잭션 히스토리는 쓰지 않는다.
// 출력: { signals, ranked } — 신규 컨트랙트에서도 API 키 없이 로컬로 돌아간다.
//
// 이건 임베딩 검색이 아니라 lexical/정적 retriever다. 결정론적이고 오프라인이라는 것이
// 장점이고, 의미적 일반화가 안 된다는 것이 한계다 (README의 "정직하게 남는 한계" 참고).

/** 컨트랙트 본문에서 상태 변수(특히 mapping) 이름을 수집한다. */
function collectStateVars(src) {
  const names = new Set();
  const re =
    /^\s*(?:mapping\s*\([^;]*?\)|u?int\d*|address|bool|bytes\d*)\s+(?:public\s+|private\s+|internal\s+|constant\s+|immutable\s+)*(\w+)\s*(?:=|;)/gm;
  let m;
  while ((m = re.exec(src)) !== null) names.add(m[1]);
  return names;
}

/** `function name(...) ... { body }` 를 중괄호 매칭으로 잘라낸다. */
function extractFunctions(src) {
  const out = [];
  const header = /function\s+(\w+)\s*\(/g;
  let m;
  while ((m = header.exec(src)) !== null) {
    const open = src.indexOf("{", m.index);
    if (open === -1) continue;
    let depth = 0;
    let end = -1;
    for (let i = open; i < src.length; i++) {
      if (src[i] === "{") depth++;
      else if (src[i] === "}") {
        depth--;
        if (depth === 0) {
          end = i;
          break;
        }
      }
    }
    if (end === -1) continue;
    out.push({ name: m[1], body: src.slice(open + 1, end) });
  }
  return out;
}

/**
 * CEI(check-effect-interaction) 위반 탐지.
 * 함수 본문에서 "외부 호출"이 "상태 변수 쓰기"보다 먼저 나오면 위반으로 본다.
 */
export function detectCEIViolations(src) {
  const stateVars = collectStateVars(src);
  const violations = [];

  for (const fn of extractFunctions(src)) {
    const callRe =
      /\b(\w+)\s*\.\s*(transfer|transferFrom|send|safeTransfer|safeTransferFrom|call)\s*[({]/g;
    let firstCall = Infinity;
    let callSite = null;
    let c;
    while ((c = callRe.exec(fn.body)) !== null) {
      // 지역 계산이 아니라 외부 컨트랙트/주소로의 호출만 센다.
      if (c.index < firstCall) {
        firstCall = c.index;
        callSite = `${c[1]}.${c[2]}(...)`;
      }
    }
    if (firstCall === Infinity) continue;

    const writeRe = /\b(\w+)\s*(?:\[[^\]]*\]\s*)?(\+=|-=|=)(?!=)/g;
    let w;
    while ((w = writeRe.exec(fn.body)) !== null) {
      if (!stateVars.has(w[1])) continue; // 지역변수 무시
      if (w.index > firstCall) {
        violations.push({
          fn: fn.name,
          call: callSite,
          write: `${w[1]} ${w[2]} ...`,
        });
        break;
      }
    }
  }
  return violations;
}

/** 소스에서 정적 signal 을 뽑는다. */
export function extractSignals(src) {
  const ceiViolations = detectCEIViolations(src);
  const has = (re) => re.test(src);

  const signals = {
    erc777_hook: has(/ERC777|tokensReceived|tokensToSend|1820/),
    external_call_before_state_write: ceiViolations.length > 0,
    no_reentrancy_guard: !has(/nonReentrant|ReentrancyGuard/),
    per_account_cap:
      has(/mapping\s*\(\s*address\s*=>\s*uint\d*\s*\)/) && has(/<=\s*max\w*/i),
    value_transfer: has(/\.\s*(transfer|send)\s*\(|\.\s*call\s*\{\s*value/),
    tx_origin: has(/tx\s*\.\s*origin/),
    owner_check: has(/onlyOwner|require\s*\(\s*msg\s*\.\s*sender\s*==/),
    price_oracle: has(/getPrice|oracle|getReserves|latestAnswer|priceFeed/i),
    timestamp_dep: has(/block\s*\.\s*(timestamp|number)/),
    total_supply: has(/totalSupply/),
    payable_receive: has(/receive\s*\(\s*\)\s*external\s+payable|\bpayable\b/),
  };

  return { signals, ceiViolations };
}

/** 참조 DB의 property 를 signal 매칭 점수로 랭킹한다. */
export function rankProperties(signals, db) {
  return db.properties
    .map((p) => {
      const matched = [];
      let score = 0;
      for (const [sig, w] of Object.entries(p.weights)) {
        if (signals[sig]) {
          score += w;
          matched.push(`${sig}(+${w})`);
        }
      }
      return { ...p, score, matched };
    })
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
}

export function retrieve(src, db, topK = 5) {
  const { signals, ceiViolations } = extractSignals(src);
  const ranked = rankProperties(signals, db);
  return {
    signals,
    ceiViolations,
    ranked,
    selected: ranked.filter((p) => p.score > 0).slice(0, topK),
  };
}
