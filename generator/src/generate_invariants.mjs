#!/usr/bin/env node
// PropertyGPT식 RAG invariant 생성기
//
//   STEP 1  RAG 검색   : 참조 property DB에서 이 코드에 맞는 property 를 뽑는다 (로컬, 무료, 결정론적)
//   STEP 2  LLM 생성   : 검색된 property 를 in-context 예시로 주고, 이 컨트랙트 고유의 invariant 를 생성한다
//   STEP 3  검증(별도) : 생성된 invariant 를 assert 로 심고 공격이 깨는지 Foundry 로 확인 (test/InvariantCheck.t.sol)
//
// 사용법:
//   node src/generate_invariants.mjs src/SimpleBank.sol                  # STEP 1 + 2
//   node src/generate_invariants.mjs src/SimpleBank.sol --step1          # STEP 1 만 (API 키 불필요)
//   node src/generate_invariants.mjs src/SimpleBank.sol --print-prompt   # 프롬프트만 파일로 (API 키 불필요)
//
// --print-prompt 는 STEP 2 가 API 로 보낼 프롬프트를 out/prompt.md 에 그대로 쓴다.
// API 크레딧 없이도 claude.ai 같은 웹 UI 에 붙여넣어 동일한 결과를 얻을 수 있다.
//
// 인증: ANTHROPIC_API_KEY 환경변수, 또는 `ant auth login` 프로필.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Anthropic from "@anthropic-ai/sdk";
import { retrieve } from "./retrieve.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODEL = "claude-opus-5";
const TOP_K = 5;

const CATEGORIES = [
  "reentrancy",
  "money_flow",
  "access_control",
  "special_storage",
  "gas_control",
  "oracle",
  "time_lock",
  "protocol_specific",
];

const INVARIANT_SCHEMA = {
  type: "object",
  properties: {
    invariants: {
      type: "array",
      items: {
        type: "object",
        properties: {
          id: {
            type: "string",
            description: "INV-1 형태의 짧은 식별자",
          },
          category: { type: "string", enum: CATEGORIES },
          statement: {
            type: "string",
            description: "이 컨트랙트에서 항상 참이어야 하는 성질. 한 문장.",
          },
          solidity_assert: {
            type: "string",
            description:
              "Foundry 테스트에 그대로 붙여넣을 수 있는 단일 assert 문. 예: assert(bank._mints(user) <= bank.maxMints());",
          },
          rationale: {
            type: "string",
            description: "이 invariant 가 왜 필요한지, 코드의 어느 부분에 근거하는지",
          },
          breaks_if: {
            type: "string",
            description: "이 invariant 가 깨진다면 어떤 공격이 성립한 것인지",
          },
          derived_from: {
            type: "array",
            items: { type: "string" },
            description: "참고한 reference property 의 id 목록 (없으면 빈 배열)",
          },
          protocol_specific: {
            type: "boolean",
            description:
              "표준 카테고리를 그대로 옮긴 것이 아니라 이 프로토콜 고유의 경제 로직에서 나온 invariant 인지",
          },
          confidence: { type: "string", enum: ["high", "medium", "low"] },
        },
        required: [
          "id",
          "category",
          "statement",
          "solidity_assert",
          "rationale",
          "breaks_if",
          "derived_from",
          "protocol_specific",
          "confidence",
        ],
        additionalProperties: false,
      },
    },
    summary: {
      type: "string",
      description: "코드에서 관찰한 위험 지점 요약. 2~3문장.",
    },
  },
  required: ["invariants", "summary"],
  additionalProperties: false,
};

const SYSTEM_PROMPT = `너는 스마트컨트랙트 형식검증 엔지니어다. 주어진 Solidity 소스 코드만 보고, 그 컨트랙트에서 항상 참이어야 하는 invariant 를 도출한다.

지켜야 할 규칙:

1. 트랜잭션 히스토리나 배포 이력은 주어지지 않는다. 코드 구조만 근거로 삼는다.
2. 각 invariant 는 반드시 실행 가능한 단일 Solidity assert 문으로 표현할 수 있어야 한다. "안전해야 한다" 같은 서술은 invariant 가 아니다.
3. 사후 조건(post-condition)을 노려라. 함수 진입 시점의 require 검사가 이미 있는 성질이라도, 트랜잭션 '종료 시점'에 그것이 여전히 성립하는지는 별개의 성질이다. 이 간극이 재진입 취약점이 숨는 자리다.
4. 참조 property 는 출발점일 뿐이다. 그대로 베끼지 말고 이 컨트랙트의 실제 변수명·함수명·상한값에 맞게 구체화하라.
5. 가능하면 protocol_specific=true 인 invariant 를 최소 하나 만들어라. 표준 카테고리를 옮긴 것이 아니라, 이 컨트랙트의 경제 로직에서만 나오는 성질이어야 한다.
6. solidity_assert 는 외부에서 읽을 수 있는 getter 만 사용하라 (public 변수의 자동 getter 포함). private 변수를 직접 참조하지 마라.
7. 근거 없는 invariant 를 지어내지 마라. 확신이 낮으면 confidence 를 낮게 매겨라.`;

function buildUserPrompt(sourcePath, source, retrieval) {
  const refs = retrieval.selected
    .map(
      (p, i) =>
        `${i + 1}. [${p.id}] (검색 점수 ${p.score} — 매칭 signal: ${p.matched.join(", ")})
   성질: ${p.statement}
   형식화 스케치: ${p.formal_sketch}
   근거: ${p.why}`
    )
    .join("\n\n");

  const cei = retrieval.ceiViolations.length
    ? retrieval.ceiViolations
        .map(
          (v) =>
            `- 함수 ${v.fn}(): 외부 호출 \`${v.call}\` 이 상태 갱신 \`${v.write}\` 보다 먼저 실행됨`
        )
        .join("\n")
    : "- 없음";

  return `## 대상 컨트랙트 (${sourcePath})

\`\`\`solidity
${source}
\`\`\`

## 정적 분석 결과 (STEP 1)

탐지된 signal:
${Object.entries(retrieval.signals)
  .filter(([, v]) => v)
  .map(([k]) => `- ${k}`)
  .join("\n")}

check-effect-interaction 순서 위반:
${cei}

## 검색된 참조 property (STEP 1 — 인간이 쓴 감사 property DB에서 상위 ${retrieval.selected.length}개)

${refs}

## 요청

위 코드에 대해 invariant 를 3~6개 생성하라. 각각은 실행 가능한 assert 로 표현되어야 하고, 최소 하나는 이 컨트랙트의 재진입 경로를 실제로 잡아낼 수 있어야 한다.`;
}

function printStep1(sourcePath, retrieval) {
  console.log("═".repeat(72));
  console.log("STEP 1 — RAG 검색 (로컬, API 키 불필요)");
  console.log("═".repeat(72));
  console.log(`대상: ${sourcePath}\n`);

  console.log("탐지된 signal:");
  for (const [k, v] of Object.entries(retrieval.signals)) {
    console.log(`  ${v ? "✓" : "·"} ${k}`);
  }

  console.log("\ncheck-effect-interaction 위반:");
  if (retrieval.ceiViolations.length === 0) {
    console.log("  (없음)");
  } else {
    for (const v of retrieval.ceiViolations) {
      console.log(`  ! ${v.fn}(): ${v.call}  →  ${v.write}`);
    }
  }

  console.log("\n참조 property 랭킹:");
  for (const p of retrieval.ranked) {
    const mark = retrieval.selected.includes(p) ? "→" : " ";
    console.log(
      `  ${mark} [score ${String(p.score).padStart(2)}] ${p.id}${
        p.matched.length ? `   ${p.matched.join(" ")}` : ""
      }`
    );
  }
  console.log(
    `\n상위 ${retrieval.selected.length}개를 STEP 2 의 in-context 예시로 넘긴다.\n`
  );
}

async function step2(sourcePath, source, retrieval) {
  console.log("═".repeat(72));
  console.log(`STEP 2 — LLM invariant 생성 (${MODEL})`);
  console.log("═".repeat(72));

  const client = new Anthropic();

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 16000,
    system: SYSTEM_PROMPT,
    output_config: {
      effort: "high",
      format: { type: "json_schema", schema: INVARIANT_SCHEMA },
    },
    messages: [
      { role: "user", content: buildUserPrompt(sourcePath, source, retrieval) },
    ],
  });

  if (response.stop_reason === "refusal") {
    console.error("모델이 요청을 거부했습니다:", response.stop_details);
    process.exit(1);
  }
  if (response.stop_reason === "max_tokens") {
    console.error("출력이 max_tokens 에서 잘렸습니다. max_tokens 를 올리세요.");
    process.exit(1);
  }

  const text = response.content.find((b) => b.type === "text")?.text ?? "";
  const result = JSON.parse(text);

  console.log(`\n요약: ${result.summary}\n`);
  for (const inv of result.invariants) {
    console.log("─".repeat(72));
    console.log(
      `${inv.id}  [${inv.category}]  confidence=${inv.confidence}${
        inv.protocol_specific ? "  ★ protocol-specific" : ""
      }`
    );
    console.log(`  성질   : ${inv.statement}`);
    console.log(`  assert : ${inv.solidity_assert}`);
    console.log(`  근거   : ${inv.rationale}`);
    console.log(`  깨지면 : ${inv.breaks_if}`);
    if (inv.derived_from.length) {
      console.log(`  참조    : ${inv.derived_from.join(", ")}`);
    }
  }
  console.log("─".repeat(72));

  const u = response.usage;
  console.log(
    `\n토큰: input=${u.input_tokens} output=${u.output_tokens}` +
      (u.cache_read_input_tokens
        ? ` cache_read=${u.cache_read_input_tokens}`
        : "")
  );

  return result;
}

/**
 * API 크레딧 없이 STEP 2 를 돌리기 위한 경로.
 * API 가 받을 것과 바이트 단위로 같은 프롬프트를 파일로 쓴다.
 */
function writePromptFile(target, source, retrieval) {
  const outDir = path.resolve(process.cwd(), "out");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "prompt.md");

  const body = `# STEP 2 프롬프트 (${target})

생성기가 \`${MODEL}\` 에 보내는 것과 동일한 프롬프트다.
API 크레딧 없이 돌리려면: 아래 두 블록을 claude.ai 새 대화에 그대로 붙여넣어라.
(권장 설정: 모델 ${MODEL}, extended thinking on)

받은 JSON 을 \`out/invariants.json\` 으로 저장하면 나머지 파이프라인이 그대로 이어진다.

---

## 1. SYSTEM PROMPT

\`\`\`
${SYSTEM_PROMPT}
\`\`\`

---

## 2. USER MESSAGE

${buildUserPrompt(target, source, retrieval)}

---

## 3. 출력 형식 지시 (API 에서는 output_config.format 으로 강제되는 부분)

웹 UI 에는 스키마 강제 기능이 없으므로, 위 USER MESSAGE 끝에 다음을 덧붙여라:

\`\`\`
아래 JSON 스키마를 정확히 따르는 JSON 객체 하나만 출력하라. 다른 텍스트는 쓰지 마라.

${JSON.stringify(INVARIANT_SCHEMA, null, 2)}
\`\`\`
`;

  fs.writeFileSync(outFile, body);
  return path.relative(process.cwd(), outFile);
}

async function main() {
  const args = process.argv.slice(2);
  const step1Only = args.includes("--step1");
  const promptOnly = args.includes("--print-prompt");
  const target = args.find((a) => !a.startsWith("--")) ?? "src/SimpleBank.sol";

  const sourcePath = path.resolve(process.cwd(), target);
  if (!fs.existsSync(sourcePath)) {
    console.error(`파일을 찾을 수 없습니다: ${sourcePath}`);
    process.exit(1);
  }
  const source = fs.readFileSync(sourcePath, "utf8");
  const db = JSON.parse(
    fs.readFileSync(path.join(HERE, "reference_db.json"), "utf8")
  );

  const retrieval = retrieve(source, db, TOP_K);
  printStep1(target, retrieval);

  if (step1Only) {
    console.log("(--step1 지정: STEP 2 를 건너뜁니다)");
    return;
  }

  if (promptOnly) {
    const rel = writePromptFile(target, source, retrieval);
    console.log("═".repeat(72));
    console.log("STEP 2 프롬프트를 파일로 출력했습니다 (API 호출 없음)");
    console.log("═".repeat(72));
    console.log(`\n  ${rel}\n`);
    console.log("다음:");
    console.log("  1. 이 파일을 열어 SYSTEM PROMPT / USER MESSAGE 를 claude.ai 에 붙여넣는다");
    console.log("  2. 받은 JSON 을 out/invariants.json 으로 저장한다");
    console.log("  3. 그 JSON 의 solidity_assert 를 test/InvariantCheck.t.sol 에 심는다");
    return;
  }

  const generated = await step2(target, source, retrieval);

  const outDir = path.resolve(process.cwd(), "out");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "invariants.json");
  fs.writeFileSync(
    outFile,
    JSON.stringify(
      { model: MODEL, target, step1: retrieval, step2: generated },
      null,
      2
    )
  );
  console.log(`\n결과 저장: ${path.relative(process.cwd(), outFile)}`);
  console.log(
    "다음: 생성된 assert 를 test/InvariantCheck.t.sol 에 심고 `forge test` 로 검증하세요."
  );
}

main().catch((err) => {
  if (err instanceof Anthropic.AuthenticationError) {
    console.error(
      "\n인증 실패. ANTHROPIC_API_KEY 를 설정하거나 `ant auth login` 을 실행하세요."
    );
  } else if (err instanceof Anthropic.RateLimitError) {
    console.error("\nRate limit. 잠시 후 다시 시도하세요.");
  } else {
    console.error("\n실패:", err.message);
  }
  process.exit(1);
});
