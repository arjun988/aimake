/**
 * Headless smoke test mirroring extension/src/cli.ts spawn + parse.
 * Run: node scripts/smoke-cli.mjs
 */
import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const rag = path.join(repoRoot, "examples", "rag");
const venvAimake = path.join(repoRoot, "venv", "Scripts", "aimake.exe");
const cliPath = fs.existsSync(venvAimake) ? venvAimake : "aimake";

function run(args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(cliPath, args, {
      cwd,
      shell: process.platform === "win32",
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c.toString()));
    child.stderr.on("data", (c) => (stderr += c.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`exit ${code}: ${stderr || stdout}`));
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const results = [];

async function step(name, fn) {
  try {
    await fn();
    results.push({ name, ok: true });
    console.log(`PASS  ${name}`);
  } catch (e) {
    results.push({ name, ok: false, error: String(e.message || e) });
    console.log(`FAIL  ${name}: ${e.message || e}`);
  }
}

await step("project has aimake.yaml", async () => {
  assert(fs.existsSync(path.join(rag, "aimake.yaml")), "missing examples/rag/aimake.yaml");
});

await step("aimake --version", async () => {
  const { stdout } = await run(["--version"], rag);
  assert(/aimake\s+\d/.test(stdout.trim()), `unexpected version: ${stdout}`);
});

let plan;
await step("plan --format json parses", async () => {
  const { stdout } = await run(["plan", "--format", "json"], rag);
  plan = JSON.parse(stdout);
  assert(Array.isArray(plan.to_run), "missing to_run");
  assert(Array.isArray(plan.to_skip), "missing to_skip");
  assert(Array.isArray(plan.entries), "missing entries");
  assert(typeof plan.estimated_total_cost_usd === "number", "missing cost");
  console.log(
    `      → skip=${plan.to_skip.length} run=${plan.to_run.length} cost=$${plan.estimated_total_cost_usd}`
  );
});

await step("tree groups match plan actions", async () => {
  assert(plan, "no plan");
  const actions = new Set(plan.entries.map((e) => e.action.toLowerCase()));
  for (const a of actions) {
    assert(["run", "skip", "restore"].includes(a), `unknown action ${a}`);
  }
  assert(plan.entries.every((e) => e.name), "entry missing name");
});

await step("stale flow: edit prompt → plan shows run", async () => {
  const prompt = path.join(rag, "prompts", "system.txt");
  const original = fs.readFileSync(prompt, "utf8");
  try {
    fs.appendFileSync(prompt, `\n# smoke ${Date.now()}\n`, "utf8");
    const { stdout } = await run(["plan", "--format", "json"], rag);
    const p = JSON.parse(stdout);
    assert(p.to_run.length >= 1, `expected to_run after edit, got ${JSON.stringify(p.to_run)}`);
    assert(
      p.to_run.includes("prompt") || p.entries.some((e) => e.name === "prompt" && e.action === "run"),
      "prompt should be stale"
    );
    const cost = p.estimated_total_cost_usd ?? 0;
    console.log(`      → stale=${p.to_run.join(",")} cost=$${cost}`);
    plan = p;
  } finally {
    fs.writeFileSync(prompt, original, "utf8");
  }
});

await step("explain evaluation --format json", async () => {
  const { stdout } = await run(["explain", "evaluation", "--format", "json"], rag);
  const ex = JSON.parse(stdout);
  assert(ex.target === "evaluation", "bad target");
  assert("root_cause" in ex || "conclusion" in ex, "missing explain fields");
  console.log(`      → root_cause=${(ex.root_cause || ex.conclusion || "").slice(0, 80)}`);
});

await step("doctor exits 0", async () => {
  await run(["doctor"], rag);
});

await step("build completes", async () => {
  await run(["build"], rag);
});

await step("venv walk from examples/rag finds CLI", async () => {
  const rag = path.join(repoRoot, "examples", "rag");
  // Mirror extension findCliInVenvs
  const names = process.platform === "win32"
    ? ["aimake.exe", "aimake.cmd", "aimake.bat", "aimake"]
    : ["aimake"];
  let found;
  let dir = rag;
  for (let i = 0; i < 8; i++) {
    for (const venvName of ["venv", ".venv"]) {
      for (const scripts of ["Scripts", "bin"]) {
        for (const name of names) {
          const c = path.join(dir, venvName, scripts, name);
          if (fs.existsSync(c)) {
            found = c;
            break;
          }
        }
        if (found) break;
      }
      if (found) break;
    }
    if (found) break;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  assert(found, "should find repo venv/Scripts/aimake.exe from examples/rag");
  console.log(`      → ${found}`);
});

await step("extension out/ bundle present", async () => {
  const out = path.join(__dirname, "..", "out");
  for (const f of ["extension.js", "cli.js", "planTree.js", "statusBar.js"]) {
    assert(fs.existsSync(path.join(out, f)), `missing out/${f}`);
  }
});

const failed = results.filter((r) => !r.ok);
console.log("\n---");
console.log(`${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
