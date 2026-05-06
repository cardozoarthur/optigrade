import React from "react";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

export function Panel({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "rounded-lg border border-slateLine bg-white p-4 shadow-panel transition duration-150 ease-out",
        "motion-safe:animate-fade-in",
        className
      )}
    >
      {children}
    </section>
  );
}

export function IconButton({
  icon: Icon,
  label,
  onClick,
  disabled
}: {
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="focus-ring group inline-flex h-10 w-10 items-center justify-center rounded-md border border-slateLine bg-white text-ink transition duration-150 ease-out hover:-translate-y-0.5 hover:border-lake hover:text-lake hover:shadow-panel active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
    >
      <Icon size={18} className="transition-transform duration-150 group-hover:scale-105" />
    </button>
  );
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
  className
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "focus-ring inline-flex h-10 items-center justify-center rounded-md bg-lake px-4 text-sm font-semibold text-white transition duration-150 ease-out hover:-translate-y-0.5 hover:bg-[#155876] hover:shadow-panel active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0",
        className
      )}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-ink">
      <span>{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "focus-ring h-10 rounded-md border border-slateLine bg-white px-3 text-sm text-ink transition duration-150 ease-out hover:border-slate-400";
