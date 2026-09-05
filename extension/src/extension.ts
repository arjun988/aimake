import * as vscode from "vscode";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";
import {
  findProjectRoot,
  configFilePath,
  getConfig,
  runPlan,
  runBuild,
  runExplain,
  runDoctor,
  PlanResult,
  CliError,
} from "./cli";
import { PlanTreeProvider, PlanEntryItem } from "./planTree";
import { AimakeStatusBar } from "./statusBar";

let treeProvider: PlanTreeProvider;
let statusBar: AimakeStatusBar;
let outputChannel: vscode.OutputChannel;
let refreshTimer: NodeJS.Timeout | undefined;
let refreshing = false;

export function activate(context: vscode.ExtensionContext): void {
  treeProvider = new PlanTreeProvider();
  statusBar = new AimakeStatusBar();
  outputChannel = vscode.window.createOutputChannel("aimake");

  const treeView = vscode.window.createTreeView("aimake.planView", {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });

  context.subscriptions.push(
    treeView,
    statusBar,
    outputChannel,
    vscode.commands.registerCommand("aimake.refreshPlan", () => refreshPlan()),
    vscode.commands.registerCommand("aimake.buildAll", () => buildTargets()),
    vscode.commands.registerCommand("aimake.buildStale", () => buildStale()),
    vscode.commands.registerCommand("aimake.buildTarget", (item?: PlanEntryItem) =>
      buildTarget(item)
    ),
    vscode.commands.registerCommand("aimake.explainTarget", (item?: PlanEntryItem) =>
      explainTarget(item)
    ),
    vscode.commands.registerCommand("aimake.openConfig", () => openConfig()),
    vscode.commands.registerCommand("aimake.doctor", () => runDoctorCommand()),
    vscode.commands.registerCommand("aimake.showCost", () => showCost()),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("aimake")) {
        scheduleRefresh();
      }
    })
  );

  setupWatchers(context);
  void refreshPlan();
}

export function deactivate(): void {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
  }
}

function scheduleRefresh(delayMs = 400): void {
  if (!getConfig().autoRefresh) {
    return;
  }
  if (refreshTimer) {
    clearTimeout(refreshTimer);
  }
  refreshTimer = setTimeout(() => {
    void refreshPlan();
  }, delayMs);
}

function setupWatchers(context: vscode.ExtensionContext): void {
  const yamlWatcher = vscode.workspace.createFileSystemWatcher("**/aimake.yaml");
  context.subscriptions.push(
    yamlWatcher,
    yamlWatcher.onDidChange(() => scheduleRefresh()),
    yamlWatcher.onDidCreate(() => scheduleRefresh()),
    yamlWatcher.onDidDelete(() => scheduleRefresh()),
    // Re-plan when likely inputs change (prompts, data, sources)
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (!getConfig().autoRefresh) {
        return;
      }
      const p = doc.uri.fsPath.replace(/\\/g, "/").toLowerCase();
      if (
        p.endsWith("aimake.yaml") ||
        p.includes("/prompts/") ||
        p.includes("/data/") ||
        p.includes("/src/") ||
        p.endsWith(".txt") ||
        p.endsWith(".jsonl") ||
        p.endsWith(".py") ||
        p.endsWith(".yaml") ||
        p.endsWith(".yml")
      ) {
        scheduleRefresh(600);
      }
    })
  );
}

async function refreshPlan(): Promise<void> {
  if (refreshing) {
    return;
  }
  refreshing = true;
  statusBar.setLoading();

  try {
    const root = await findProjectRoot();
    if (!root) {
      treeProvider.setMessage("No aimake.yaml — run aimake init");
      statusBar.setNoProject();
      return;
    }

    const plan = await runPlan(root);
    treeProvider.setPlan(plan);
    statusBar.updateFromPlan(plan);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    treeProvider.setMessage(`Plan failed: ${msg}`);
    statusBar.setError(msg);
  } finally {
    refreshing = false;
  }
}

async function requireRoot(): Promise<string | undefined> {
  const root = await findProjectRoot();
  if (!root) {
    void vscode.window.showErrorMessage("No aimake.yaml found in this workspace");
    treeProvider.setMessage("No aimake.yaml — run aimake init");
    statusBar.setNoProject();
    return undefined;
  }
  return root;
}

async function buildTargets(targets?: string[]): Promise<void> {
  const root = await requireRoot();
  if (!root) {
    return;
  }

  const label = targets?.length ? `aimake build ${targets.join(" ")}` : "aimake build";
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: label,
      cancellable: false,
    },
    async () => {
      try {
        const out = await runBuild(root, targets);
        outputChannel.appendLine(`$ ${label}`);
        outputChannel.appendLine(out || "(no output)");
        outputChannel.appendLine("");
        void vscode.window.showInformationMessage(
          targets?.length
            ? `Built: ${targets.join(", ")}`
            : "aimake build finished"
        );
      } catch (err) {
        if (!(err instanceof CliError)) {
          void vscode.window.showErrorMessage(String(err));
        }
      } finally {
        await refreshPlan();
      }
    }
  );
}

async function buildStale(): Promise<void> {
  const plan = treeProvider.getPlan();
  if (!plan?.to_run?.length) {
    // Refresh first in case tree is stale
    await refreshPlan();
  }
  const current = treeProvider.getPlan();
  const stale = current?.to_run ?? [];
  if (!stale.length) {
    void vscode.window.showInformationMessage("Nothing stale to rebuild");
    return;
  }
  await buildTargets(stale);
}

async function resolveEntry(item?: PlanEntryItem): Promise<string | undefined> {
  if (item?.entry?.name) {
    return item.entry.name;
  }
  const plan = treeProvider.getPlan();
  const names = plan?.entries?.map((e) => e.name) ?? plan?.to_run ?? [];
  if (!names.length) {
    void vscode.window.showErrorMessage("No targets available");
    return undefined;
  }
  return vscode.window.showQuickPick(names, { placeHolder: "Select target" });
}

async function buildTarget(item?: PlanEntryItem): Promise<void> {
  const name = await resolveEntry(item);
  if (!name) {
    return;
  }
  await buildTargets([name]);
}

async function explainTarget(item?: PlanEntryItem): Promise<void> {
  const root = await requireRoot();
  if (!root) {
    return;
  }
  const name = await resolveEntry(item);
  if (!name) {
    return;
  }

  try {
    const result = await runExplain(root, name);
    const md = formatExplainMarkdown(result);
    const choice = await vscode.window.showInformationMessage(
      `Explain ${name}: ${result.root_cause || result.conclusion || "see details"}`,
      "Open Preview",
      "Show Output"
    );
    if (choice === "Show Output") {
      outputChannel.clear();
      outputChannel.appendLine(md);
      outputChannel.show(true);
    } else if (choice === "Open Preview") {
      const tmp = path.join(os.tmpdir(), `aimake-explain-${name}.md`);
      fs.writeFileSync(tmp, md, "utf8");
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(tmp));
      await vscode.commands.executeCommand("markdown.showPreview", doc.uri);
    } else {
      // Default: show in output channel when the prompt is dismissed
      outputChannel.clear();
      outputChannel.appendLine(md);
      outputChannel.show(true);
    }
  } catch (err) {
    if (!(err instanceof CliError)) {
      void vscode.window.showErrorMessage(String(err));
    }
  }
}

function formatExplainMarkdown(result: Awaited<ReturnType<typeof runExplain>>): string {
  const lines: string[] = [
    `# Explain: ${result.target}`,
    "",
    `**Root cause:** ${result.root_cause || "—"}`,
    "",
    `**Conclusion:** ${result.conclusion || "—"}`,
    "",
  ];

  if (result.estimated_cost_usd != null && result.estimated_cost_usd > 0) {
    lines.push(`**Estimated cost:** ~$${result.estimated_cost_usd.toFixed(2)}`);
  }
  if (result.estimated_tokens != null && result.estimated_tokens > 0) {
    lines.push(`**Estimated tokens:** ${result.estimated_tokens.toLocaleString()}`);
  }
  if (result.chain?.length) {
    lines.push("", "## Stale chain", "", result.chain.map((c) => `- ${c}`).join("\n"));
  }
  if (result.old_fingerprint || result.new_fingerprint) {
    lines.push(
      "",
      "## Fingerprints",
      "",
      `- Old: \`${result.old_fingerprint ?? "—"}\``,
      `- New: \`${result.new_fingerprint ?? "—"}\``
    );
  }
  if (result.tree?.length) {
    lines.push("", "## Dependency tree", "");
    for (const node of result.tree) {
      const cost =
        node.estimated_cost_usd != null && node.estimated_cost_usd > 0
          ? ` (~$${node.estimated_cost_usd.toFixed(2)})`
          : "";
      lines.push(`- **${node.name}** — \`${node.status}\`${cost}`);
      if (node.reason) {
        lines.push(`  - ${node.reason}`);
      }
    }
  }
  lines.push("");
  return lines.join("\n");
}

async function openConfig(): Promise<void> {
  const root = await findProjectRoot();
  if (!root) {
    void vscode.window.showErrorMessage("No aimake.yaml found — run aimake init");
    return;
  }
  const cfgPath = configFilePath(root);
  const doc = await vscode.workspace.openTextDocument(cfgPath);
  await vscode.window.showTextDocument(doc);
}

async function runDoctorCommand(): Promise<void> {
  const root = await requireRoot();
  if (!root) {
    return;
  }
  try {
    const out = await runDoctor(root);
    outputChannel.clear();
    outputChannel.appendLine("$ aimake doctor");
    outputChannel.appendLine(out || "(no output)");
    outputChannel.show(true);
  } catch (err) {
    if (!(err instanceof CliError)) {
      void vscode.window.showErrorMessage(String(err));
    }
  }
}

async function showCost(): Promise<void> {
  let plan: PlanResult | undefined = treeProvider.getPlan();
  if (!plan) {
    await refreshPlan();
    plan = treeProvider.getPlan();
  }
  if (!plan) {
    void vscode.window.showInformationMessage("No plan available");
    return;
  }

  const cost = plan.estimated_total_cost_usd ?? 0;
  const tokens = plan.estimated_total_tokens ?? 0;
  const lines = [
    `To rebuild: ${plan.to_run?.length ?? 0}`,
    `Reuse: ${plan.to_skip?.length ?? 0}`,
    `Restore: ${plan.to_restore?.length ?? 0}`,
    cost > 0 ? `Estimated cost: ~$${cost.toFixed(2)}` : "Estimated cost: —",
    tokens > 0 ? `Estimated tokens: ${tokens.toLocaleString()}` : undefined,
  ].filter(Boolean);

  void vscode.window.showInformationMessage(lines.join(" · "));
}
