import * as vscode from "vscode";
import { PlanResult } from "./cli";

export class AimakeStatusBar {
  private item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.command = "aimake.showCost";
    this.item.tooltip = "aimake plan cost estimate — click for details";
    this.setIdle();
    this.item.show();
  }

  dispose(): void {
    this.item.dispose();
  }

  setIdle(): void {
    this.item.text = "$(flame) aimake";
    this.item.backgroundColor = undefined;
  }

  setLoading(): void {
    this.item.text = "$(sync~spin) aimake · refreshing";
    this.item.backgroundColor = undefined;
  }

  setNoProject(): void {
    this.item.text = "$(flame) aimake · no project";
    this.item.backgroundColor = undefined;
  }

  setError(message?: string): void {
    this.item.text = "$(error) aimake · error";
    this.item.tooltip = message ?? "aimake plan failed";
    this.item.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
  }

  updateFromPlan(plan: PlanResult): void {
    const stale = plan.to_run?.length ?? 0;
    const cost = plan.estimated_total_cost_usd ?? 0;
    const costPart = cost > 0 ? ` · ~$${cost.toFixed(2)}` : "";
    this.item.text = `$(flame) aimake · ${stale} stale${costPart}`;
    this.item.tooltip = [
      `${stale} to rebuild`,
      `${plan.to_skip?.length ?? 0} reuse`,
      `${plan.to_restore?.length ?? 0} restore`,
      cost > 0 ? `est. $${cost.toFixed(2)}` : undefined,
      plan.estimated_total_tokens
        ? `est. ${plan.estimated_total_tokens.toLocaleString()} tokens`
        : undefined,
    ]
      .filter(Boolean)
      .join(" · ");
    this.item.backgroundColor =
      stale > 0
        ? new vscode.ThemeColor("statusBarItem.warningBackground")
        : undefined;
  }
}
