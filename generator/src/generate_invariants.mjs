#!/usr/bin/env node
// RAG invariant generator (PropertyGPT-style).
//
//   STAGE 1  Retrieval    Rank a reference property corpus against static signals
//                         extracted from the source. Local, free, deterministic.
//   STAGE 2  Generation   Hand the retrieved properties to a model as in-context
//                         examples; get back invariants specific to this contract.
//   STAGE 3  Verification (separate) Plant the assert, run an exploit against it
//                         in a forked EVM — see test/InvariantCheck.t.sol
//
// Usage:
//   node src/generate_invariants.mjs src/SimpleBank.sol                  # stage 1 + 2
//   node src/generate_invariants.mjs src/SimpleBank.sol --step1          # stage 1 only (no API key)
//   node src/generate_invariants.mjs src/SimpleBank.sol --print-prompt   # write the prompt to a file (no API key)
//
// --print-prompt writes exactly what stage 2 would send to out/prompt.md, so the
// same result can be obtained by pasting it into a chat interface when no API
// credits are available.
//
// Auth: ANTHROPIC_API_KEY, or an `ant auth login` profile.

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
          id: { type: "string", description: "Short identifier, e.g. INV-1" },
          category: { type: "string", enum: CATEGORIES },
          statement: {
            type: "string",
            description:
              "A property that must always hold for this contract. One sentence.",
          },
          solidity_assert: {
            type: "string",
            description:
              "A single assert statement that can be pasted into a Foundry test verbatim. " +
              "Example: assert(bank._mints(user) <= bank.maxMints());",
          },
          rationale: {
            type: "string",
            description:
              "Why this invariant is needed and which part of the code it rests on",
          },
          breaks_if: {
            type: "string",
            description:
              "If this invariant breaks, what attack has succeeded",
          },
          derived_from: {
            type: "array",
            items: { type: "string" },
            description:
              "Ids of the reference properties this drew on; empty array if none",
          },
          protocol_specific: {
            type: "boolean",
            description:
              "True if this comes from this protocol's own economic logic rather than " +
              "being a standard category transplanted onto it",
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
      description: "The risk you observed in the code. Two or three sentences.",
    },
  },
  required: ["invariants", "summary"],
  additionalProperties: false,
};

const SYSTEM_PROMPT = `You are a smart contract formal-verification engineer. Given only Solidity source, derive the invariants that must always hold for that contract.

Rules:

1. You are given no transaction history and no deployment record. Reason from code structure alone.
2. Every invariant must be expressible as a single executable Solidity assert statement. A sentence like "the contract should be safe" is not an invariant.
3. Target post-conditions. Even where a require check already enforces a property at function entry, whether it still holds at transaction *end* is a separate property. That gap is where reentrancy hides.
4. The reference properties are a starting point, not a template. Do not copy them — specialize them to this contract's actual variable names, function names, and bounds.
5. Where possible, produce at least one invariant with protocol_specific=true: a property that comes from this contract's own economic logic rather than a standard category transplanted onto it.
6. solidity_assert may only use externally readable getters, including the automatic getters of public variables. Do not reference private variables directly.
7. Do not invent invariants you cannot ground in the code. If your confidence is low, say so in the confidence field.`;

function buildUserPrompt(sourcePath, source, retrieval) {
  const refs = retrieval.selected
    .map(
      (p, i) =>
        `${i + 1}. [${p.id}] (retrieval score ${p.score} — matched signals: ${p.matched.join(", ")})
   Property: ${p.statement}
   Formal sketch: ${p.formal_sketch}
   Rationale: ${p.why}`
    )
    .join("\n\n");

  const cei = retrieval.ceiViolations.length
    ? retrieval.ceiViolations
        .map(
          (v) =>
            `- ${v.fn}(): the external call \`${v.call}\` executes before the state write \`${v.write}\``
        )
        .join("\n")
    : "- none";

  return `## Target contract (${sourcePath})

\`\`\`solidity
${source}
\`\`\`

## Static analysis (stage 1)

Detected signals:
${Object.entries(retrieval.signals)
  .filter(([, v]) => v)
  .map(([k]) => `- ${k}`)
  .join("\n")}

Check-effect-interaction ordering violations:
${cei}

## Retrieved reference properties (stage 1 — top ${retrieval.selected.length} from a corpus of human-written audit properties)

${refs}

## Task

Produce 3 to 6 invariants for the code above. Each must be expressed as an executable assert, and at least one must be capable of catching this contract's reentrancy path.`;
}

function printStep1(sourcePath, retrieval) {
  console.log("═".repeat(72));
  console.log("STAGE 1 — retrieval (local, no API key)");
  console.log("═".repeat(72));
  console.log(`target: ${sourcePath}\n`);

  console.log("detected signals:");
  for (const [k, v] of Object.entries(retrieval.signals)) {
    console.log(`  ${v ? "✓" : "·"} ${k}`);
  }

  console.log("\ncheck-effect-interaction violations:");
  if (retrieval.ceiViolations.length === 0) {
    console.log("  (none)");
  } else {
    for (const v of retrieval.ceiViolations) {
      console.log(`  ! ${v.fn}(): ${v.call}  →  ${v.write}`);
    }
  }

  console.log("\nreference property ranking:");
  for (const p of retrieval.ranked) {
    const mark = retrieval.selected.includes(p) ? "→" : " ";
    console.log(
      `  ${mark} [score ${String(p.score).padStart(2)}] ${p.id}${
        p.matched.length ? `   ${p.matched.join(" ")}` : ""
      }`
    );
  }
  console.log(
    `\nThe top ${retrieval.selected.length} are passed to stage 2 as in-context examples.\n`
  );
}

async function step2(sourcePath, source, retrieval) {
  console.log("═".repeat(72));
  console.log(`STAGE 2 — invariant generation (${MODEL})`);
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
    console.error("The model declined the request:", response.stop_details);
    process.exit(1);
  }
  if (response.stop_reason === "max_tokens") {
    console.error("Output was truncated at max_tokens. Raise max_tokens.");
    process.exit(1);
  }

  const text = response.content.find((b) => b.type === "text")?.text ?? "";
  const result = JSON.parse(text);

  console.log(`\nSummary: ${result.summary}\n`);
  for (const inv of result.invariants) {
    console.log("─".repeat(72));
    console.log(
      `${inv.id}  [${inv.category}]  confidence=${inv.confidence}${
        inv.protocol_specific ? "  ★ protocol-specific" : ""
      }`
    );
    console.log(`  property  : ${inv.statement}`);
    console.log(`  assert    : ${inv.solidity_assert}`);
    console.log(`  rationale : ${inv.rationale}`);
    console.log(`  breaks if : ${inv.breaks_if}`);
    if (inv.derived_from.length) {
      console.log(`  derived   : ${inv.derived_from.join(", ")}`);
    }
  }
  console.log("─".repeat(72));

  const u = response.usage;
  console.log(
    `\ntokens: input=${u.input_tokens} output=${u.output_tokens}` +
      (u.cache_read_input_tokens
        ? ` cache_read=${u.cache_read_input_tokens}`
        : "")
  );

  return result;
}

/**
 * Path for running stage 2 without API credits: write the prompt the API would
 * receive, byte for byte, so it can be pasted into a chat interface.
 */
function writePromptFile(target, source, retrieval) {
  const outDir = path.resolve(process.cwd(), "out");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "prompt.md");

  const body = `# Stage 2 prompt (${target})

This is exactly what the generator sends to \`${MODEL}\`.

To run stage 2 without API credits, paste the two blocks below into a new chat
(recommended settings: model ${MODEL}, extended thinking on). Save the returned
JSON as \`out/invariants.json\` and the rest of the pipeline continues unchanged.

---

## 1. SYSTEM PROMPT

\`\`\`
${SYSTEM_PROMPT}
\`\`\`

---

## 2. USER MESSAGE

${buildUserPrompt(target, source, retrieval)}

---

## 3. Output format instruction

The API enforces this through \`output_config.format\`. A chat interface has no
equivalent, so append the following to the user message above:

\`\`\`
Output a single JSON object conforming exactly to the schema below. Write nothing else.

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
    console.error(`File not found: ${sourcePath}`);
    process.exit(1);
  }
  const source = fs.readFileSync(sourcePath, "utf8");
  const db = JSON.parse(
    fs.readFileSync(path.join(HERE, "reference_db.json"), "utf8")
  );

  const retrieval = retrieve(source, db, TOP_K);
  printStep1(target, retrieval);

  if (step1Only) {
    console.log("(--step1: skipping stage 2)");
    return;
  }

  if (promptOnly) {
    const rel = writePromptFile(target, source, retrieval);
    console.log("═".repeat(72));
    console.log("Stage 2 prompt written to a file (no API call made)");
    console.log("═".repeat(72));
    console.log(`\n  ${rel}\n`);
    console.log("Next:");
    console.log("  1. Open it and paste the system prompt and user message into a chat interface");
    console.log("  2. Save the returned JSON as out/invariants.json");
    console.log("  3. Plant its solidity_assert values in test/InvariantCheck.t.sol");
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
  console.log(`\nSaved: ${path.relative(process.cwd(), outFile)}`);
  console.log(
    "Next: plant the generated asserts in test/InvariantCheck.t.sol and run `forge test`."
  );
}

main().catch((err) => {
  if (err instanceof Anthropic.AuthenticationError) {
    console.error(
      "\nAuthentication failed. Set ANTHROPIC_API_KEY, or run `ant auth login`."
    );
  } else if (err instanceof Anthropic.RateLimitError) {
    console.error("\nRate limited. Retry shortly.");
  } else {
    console.error("\nFailed:", err.message);
  }
  process.exit(1);
});
