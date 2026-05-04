import React from "react";
import type { LucideIcon } from "lucide-react";

export function PageHeader({
  icon: Icon,
  title,
  subtitle,
  actions
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="border-b border-slateLine bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-lake/10 text-lake">
            <Icon size={20} />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold tracking-normal">{title}</h1>
            <p className="truncate text-sm text-slate-600">{subtitle}</p>
          </div>
        </div>
        {actions}
      </div>
    </div>
  );
}
