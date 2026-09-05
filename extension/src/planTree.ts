import * as vscode from "vscode";
import { PlanEntry, PlanResult } from "./cli";

export type PlanTreeNode = PlanGroupItem | PlanEntryItem | MessageItem;

export class MessageItem extends vscode.TreeItem {
  constructor(message: string) {
    super(message, vscode.TreeItemCollapsibleState.None);
    this.contextValue = "aimake.message";
    this.iconPath = new vscode.ThemeIcon("info");
  }
}

export class PlanGroupItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly groupKind: "run" | "skip" | "restore",
    public readonly children: PlanEntryItem[]
  ) {
    super(
      label,
      children.length
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.Collapsed
    );
    this.contextValue = `aimake.group.${groupKind}`;
    this.description = `${children.length}`;
    this.iconPath = groupIcon(groupKind);
  }
}

export class PlanEntryItem extends vscode.TreeItem {
  constructor(public readonly entry: PlanEntry) {
    super(entry.name, vscode.TreeItemCollapsibleState.None);
    const action = (entry.action || "").toLowerCase();
    this.contextValue =
      action === "run"
        ? "aimake.run"
        : action === "restore"
          ? "aimake.restore"
          : "aimake.skip";

    this.iconPath = entryIcon(action);
    this.description = formatEntryDescription(entry);
    this.tooltip = new vscode.MarkdownString(
      [
        `**${entry.name}**`,
        `Action: \`${entry.action}\` · Status: \`${entry.status}\``,
        entry.reason ? `\n${entry.reason}` : "",
      ]
        .filter(Boolean)
        .join("\n\n")
    );

    if (action === "run") {
      this.command = {
        command: "aimake.buildTarget",
        title: "Build Target",
        arguments: [this],
      };
    }
  }
}

function groupIcon(kind: "run" | "skip" | "restore"): vscode.ThemeIcon {
  switch (kind) {
    case "run":
      return new vscode.ThemeIcon("warning", new vscode.ThemeColor("list.warningForeground"));
    case "restore":
      return new vscode.ThemeIcon("info", new vscode.ThemeColor("list.highlightForeground"));
    default:
      return new vscode.ThemeIcon("check", new vscode.ThemeColor("testing.iconPassed"));
  }
}

function entryIcon(action: string): vscode.ThemeIcon {
  switch (action) {
    case "run":
      return new vscode.ThemeIcon("warning", new vscode.ThemeColor("list.warningForeground"));
    case "restore":
      return new vscode.ThemeIcon("cloud-download", new vscode.ThemeColor("list.highlightForeground"));
    default:
      return new vscode.ThemeIcon("pass", new vscode.ThemeColor("testing.iconPassed"));
  }
}

function formatEntryDescription(entry: PlanEntry): string {
  const parts: string[] = [];
  if (entry.estimated_cost_usd != null && entry.estimated_cost_usd > 0) {
    parts.push(`~$${entry.estimated_cost_usd.toFixed(2)}`);
  }
  if (entry.estimated_tokens != null && entry.estimated_tokens > 0) {
    parts.push(`${entry.estimated_tokens.toLocaleString()} tok`);
  }
  if (entry.reason) {
    const short =
      entry.reason.length > 48 ? `${entry.reason.slice(0, 45)}…` : entry.reason;
    parts.push(short);
  }
  return parts.join(" · ");
}

export class PlanTreeProvider implements vscode.TreeDataProvider<PlanTreeNode> {
  private _onDidChangeTreeData = new vscode.EventEmitter<PlanTreeNode | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private plan: PlanResult | undefined;
  private message: string | undefined = "Loading plan…";

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  setPlan(plan: PlanResult | undefined): void {
    this.plan = plan;
    this.message = undefined;
    this.refresh();
  }

  setMessage(message: string): void {
    this.plan = undefined;
    this.message = message;
    this.refresh();
  }

  getPlan(): PlanResult | undefined {
    return this.plan;
  }

  getTreeItem(element: PlanTreeNode): vscode.TreeItem {
    return element;
  }

  getChildren(element?: PlanTreeNode): PlanTreeNode[] {
    if (element instanceof PlanGroupItem) {
      return element.children;
    }
    if (element) {
      return [];
    }

    if (this.message) {
      return [new MessageItem(this.message)];
    }

    if (!this.plan) {
      return [new MessageItem("No aimake.yaml — run aimake init")];
    }

    const byAction = (action: string) =>
      this.plan!.entries
        .filter((e) => (e.action || "").toLowerCase() === action)
        .map((e) => new PlanEntryItem(e));

    const run = byAction("run");
    const skip = byAction("skip");
    const restore = byAction("restore");

    // Fall back to name lists if entries are empty but summary lists exist
    if (!this.plan.entries.length) {
      const fromNames = (names: string[], action: string) =>
        names.map(
          (name) =>
            new PlanEntryItem({
              name,
              action,
              status: action === "run" ? "stale" : "up_to_date",
              reason: "",
              estimated_cost_usd: null,
              estimated_tokens: null,
            })
        );
      return [
        new PlanGroupItem("To rebuild", "run", fromNames(this.plan.to_run ?? [], "run")),
        new PlanGroupItem("Reuse", "skip", fromNames(this.plan.to_skip ?? [], "skip")),
        new PlanGroupItem("Restore", "restore", fromNames(this.plan.to_restore ?? [], "restore")),
      ];
    }

    return [
      new PlanGroupItem("To rebuild", "run", run),
      new PlanGroupItem("Reuse", "skip", skip),
      new PlanGroupItem("Restore", "restore", restore),
    ];
  }
}
