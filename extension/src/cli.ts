import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { spawn } from "child_process";

export interface PlanEntry {
  name: string;
  action: string;
  status: string;
  reason: string;
  estimated_cost_usd: number | null;
  estimated_tokens: number | null;
}

export interface PlanResult {
  to_run: string[];
  to_skip: string[];
  to_restore: string[];
  estimated_total_cost_usd: number;
  estimated_total_tokens: number;
  entries: PlanEntry[];
}

export interface ExplainResult {
  target: string;
  chain: string[];
  root_cause: string;
  conclusion: string;
  old_fingerprint?: string | null;
  new_fingerprint?: string | null;
  estimated_cost_usd?: number | null;
  estimated_tokens?: number | null;
  tree?: Array<{
    name: string;
    status: string;
    reason: string;
    estimated_cost_usd?: number | null;
    estimated_tokens?: number | null;
    validation_errors?: string[];
    external_notes?: string[];
  }>;
}

export interface AimakeConfig {
  cliPath: string;
  configPath: string;
  autoRefresh: boolean;
  project: string;
}

export function getConfig(): AimakeConfig {
  const cfg = vscode.workspace.getConfiguration("aimake");
  return {
    cliPath: cfg.get<string>("cliPath", "aimake"),
    configPath: cfg.get<string>("configPath", ""),
    autoRefresh: cfg.get<boolean>("autoRefresh", true),
    project: cfg.get<string>("project", ""),
  };
}

/** Find the workspace folder (or nested dir) that contains aimake.yaml. */
export async function findProjectRoot(): Promise<string | undefined> {
  const config = getConfig();
  if (config.configPath) {
    const configured = path.isAbsolute(config.configPath)
      ? config.configPath
      : path.join(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "", config.configPath);
    if (fs.existsSync(configured)) {
      return path.dirname(configured);
    }
  }

  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return undefined;
  }

  for (const folder of folders) {
    const direct = path.join(folder.uri.fsPath, "aimake.yaml");
    if (fs.existsSync(direct)) {
      return folder.uri.fsPath;
    }
  }

  const found = await vscode.workspace.findFiles("**/aimake.yaml", "**/node_modules/**", 1);
  if (found.length) {
    return path.dirname(found[0].fsPath);
  }

  return undefined;
}

export function configFilePath(projectRoot: string): string {
  const config = getConfig();
  if (config.configPath) {
    return path.isAbsolute(config.configPath)
      ? config.configPath
      : path.join(projectRoot, config.configPath);
  }
  return path.join(projectRoot, "aimake.yaml");
}

function buildArgs(extra: string[], cwd: string): string[] {
  const config = getConfig();
  const args = [...extra];
  const yamlPath = configFilePath(cwd);
  if (fs.existsSync(yamlPath)) {
    args.push("--config", yamlPath);
  }
  if (config.project) {
    args.push("--project", config.project);
  }
  return args;
}

export class CliError extends Error {
  constructor(
    message: string,
    public readonly stderr: string = "",
    public readonly code: number | null = null
  ) {
    super(message);
    this.name = "CliError";
  }
}

function candidateCliNames(): string[] {
  return process.platform === "win32"
    ? ["aimake.exe", "aimake.cmd", "aimake.bat", "aimake"]
    : ["aimake"];
}

function venvScriptDirs(venvRoot: string): string[] {
  return process.platform === "win32"
    ? [path.join(venvRoot, "Scripts"), path.join(venvRoot, "bin")]
    : [path.join(venvRoot, "bin"), path.join(venvRoot, "Scripts")];
}

/** Walk up from start dirs looking for venv/.venv aimake executables. */
export function findCliInVenvs(...startDirs: Array<string | undefined>): string | undefined {
  const seen = new Set<string>();
  const names = candidateCliNames();

  for (const start of startDirs) {
    if (!start) {
      continue;
    }
    let dir = path.resolve(start);
    for (let i = 0; i < 8; i++) {
      if (seen.has(dir)) {
        break;
      }
      seen.add(dir);
      for (const venvName of ["venv", ".venv"]) {
        const venvRoot = path.join(dir, venvName);
        for (const scripts of venvScriptDirs(venvRoot)) {
          for (const name of names) {
            const candidate = path.join(scripts, name);
            if (fs.existsSync(candidate)) {
              return candidate;
            }
          }
        }
      }
      const parent = path.dirname(dir);
      if (parent === dir) {
        break;
      }
      dir = parent;
    }
  }
  return undefined;
}

/**
 * Resolve which binary to run.
 * Order: configured absolute path → setting if exists → venv near project → "aimake" on PATH.
 */
export function resolveCliPath(cwd: string): { command: string; via: string } {
  const { cliPath } = getConfig();
  const workspaceRoots =
    vscode.workspace.workspaceFolders?.map((f) => f.uri.fsPath) ?? [];

  if (cliPath && cliPath !== "aimake" && path.isAbsolute(cliPath) && fs.existsSync(cliPath)) {
    return { command: cliPath, via: "setting (absolute)" };
  }

  if (cliPath && cliPath !== "aimake") {
    const relative = path.isAbsolute(cliPath) ? cliPath : path.join(cwd, cliPath);
    if (fs.existsSync(relative)) {
      return { command: relative, via: "setting" };
    }
  }

  const fromVenv = findCliInVenvs(cwd, ...workspaceRoots);
  if (fromVenv) {
    return { command: fromVenv, via: "project venv" };
  }

  return { command: cliPath || "aimake", via: "PATH" };
}

/** Pull the first JSON object from CLI stdout (tolerates banners / BOM). */
export function extractJson<T>(stdout: string): T {
  const text = stdout.replace(/^\uFEFF/, "").trim();
  try {
    return JSON.parse(text) as T;
  } catch {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start >= 0 && end > start) {
      return JSON.parse(text.slice(start, end + 1)) as T;
    }
    throw new Error("no JSON object in output");
  }
}

function spawnCommand(
  command: string,
  args: string[],
  cwd: string
): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      // Avoid shell:true arg-injection warning; on Windows still resolve .cmd via PATHEXT when needed
      shell: process.platform === "win32" && !path.isAbsolute(command),
      env: { ...process.env },
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", (err: NodeJS.ErrnoException) => {
      reject(err);
    });

    child.on("close", (code) => {
      resolve({ code, stdout, stderr });
    });
  });
}

export async function runAimake(
  args: string[],
  cwd: string,
  options?: { showError?: boolean }
): Promise<string> {
  const showError = options?.showError !== false;
  const fullArgs = buildArgs(args, cwd);
  const { command, via } = resolveCliPath(cwd);

  try {
    const { code, stdout, stderr } = await spawnCommand(command, fullArgs, cwd);
    if (code !== 0) {
      const detail = (stderr || stdout).trim() || `exit code ${code}`;
      const notFound =
        /not recognized|ENOENT|No such file/i.test(detail) ||
        detail.includes("is not recognized");
      const msg = notFound
        ? `aimake CLI not found (tried "${command}" via ${via}). ` +
          `Install with pip install aimake, activate your venv, or set aimake.cliPath ` +
          `to the full path (e.g. .../venv/Scripts/aimake.exe).`
        : `aimake ${fullArgs[0] ?? ""} failed: ${detail}`;
      if (showError) {
        void vscode.window.showErrorMessage(msg);
      }
      throw new CliError(msg, stderr, code);
    }
    return stdout;
  } catch (err) {
    if (err instanceof CliError) {
      throw err;
    }
    const e = err as NodeJS.ErrnoException;
    const msg =
      e.code === "ENOENT"
        ? `aimake CLI not found ("${command}" via ${via}). ` +
          `Install with pip install aimake or set aimake.cliPath to your venv Scripts/aimake.exe.`
        : `Failed to run aimake: ${e.message}`;
    if (showError) {
      void vscode.window.showErrorMessage(msg);
    }
    throw new CliError(msg);
  }
}

export async function runPlan(cwd: string): Promise<PlanResult> {
  const stdout = await runAimake(["plan", "--format", "json"], cwd);
  try {
    return extractJson<PlanResult>(stdout);
  } catch {
    const msg = "Failed to parse aimake plan JSON output";
    void vscode.window.showErrorMessage(msg);
    throw new CliError(msg, stdout);
  }
}

export async function runExplain(cwd: string, target: string): Promise<ExplainResult> {
  const stdout = await runAimake(["explain", target, "--format", "json"], cwd);
  try {
    return extractJson<ExplainResult>(stdout);
  } catch {
    const msg = "Failed to parse aimake explain JSON output";
    void vscode.window.showErrorMessage(msg);
    throw new CliError(msg, stdout);
  }
}

export async function runBuild(cwd: string, targets?: string[]): Promise<string> {
  const args = ["build", ...(targets ?? [])];
  return runAimake(args, cwd);
}

export async function runDoctor(cwd: string): Promise<string> {
  return runAimake(["doctor"], cwd);
}
