import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "brand" | "warning" | "danger";
  className?: string;
}) {
  const accent = {
    default: "bg-surface-border-strong",
    brand: "bg-brand-600",
    warning: "bg-warning",
    danger: "bg-danger",
  }[tone];

  const valueTone = {
    default: "text-ink",
    brand: "text-brand-600 dark:text-brand-500",
    warning: "text-warning",
    danger: "text-danger",
  }[tone];

  return (
    <div className={cn("panel relative overflow-hidden animate-slide-up p-5", className)}>
      <span className={cn("absolute bottom-0 left-0 top-0 w-[3px]", accent)} />
      <p className="label">{label}</p>
      <p className={cn("metric mt-2", valueTone)}>{value}</p>
      {hint ? <p className="mt-2 text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}
