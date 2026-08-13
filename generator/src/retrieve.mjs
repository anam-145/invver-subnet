// Stage 1 — retrieval (static signal extraction + reference property ranking)
//
// Input: one Solidity source string. No transaction history is used.
// Output: { signals, ceiViolations, ranked, selected } — runs locally with no
// API key, which is the point: it works on a contract deployed minutes ago.
//
// This is a lexical/static retriever, not an embedding search. Deterministic
// and offline, which is its strength; no semantic generalization, which is its
// weakness. See the limitations section of the README.

/** Collect state variable names (mappings especially) from the contract body. */
function collectStateVars(src) {
  const names = new Set();
  const re =
    /^\s*(?:mapping\s*\([^;]*?\)|u?int\d*|address|bool|bytes\d*)\s+(?:public\s+|private\s+|internal\s+|constant\s+|immutable\s+)*(\w+)\s*(?:=|;)/gm;
  let m;
  while ((m = re.exec(src)) !== null) names.add(m[1]);
  return names;
}

/** Split out `function name(...) ... { body }` by brace matching. */
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
 * Detect check-effect-interaction violations.
 * Within a function body, an external call appearing before a state variable
 * write counts as a violation.
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
      // Only calls out to another contract or address count, not local math.
      if (c.index < firstCall) {
        firstCall = c.index;
        callSite = `${c[1]}.${c[2]}(...)`;
      }
    }
    if (firstCall === Infinity) continue;

    const writeRe = /\b(\w+)\s*(?:\[[^\]]*\]\s*)?(\+=|-=|=)(?!=)/g;
    let w;
    while ((w = writeRe.exec(fn.body)) !== null) {
      if (!stateVars.has(w[1])) continue; // skip locals
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

/** Extract static signals from the source. */
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

/** Rank the reference corpus by signal-match score. */
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
