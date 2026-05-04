"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { Route } from "next";
import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";
import {
  BarChart3,
  Building2,
  ChevronRight,
  Database,
  GraduationCap,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  School,
  ShieldCheck,
  UserRound
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AcademicRole, academicRoleLabels } from "@/lib/auth/permissions";
import { IconButton } from "@/components/ui";

type ShellSession = {
  user: {
    name: string;
    email: string;
  };
  organization: {
    name: string;
  } | null;
  role: AcademicRole;
  roleLabel: string;
};

type NavItem = {
  href: Route;
  label: string;
  icon: LucideIcon;
  roles: AcademicRole[];
};

const allNav: NavItem[] = [
  {
    href: "/app/planejamento",
    label: "Planejamento",
    icon: BarChart3,
    roles: ["admin", "pro_reitoria", "chefe_departamento", "coordenador"]
  },
  {
    href: "/app/cadastros",
    label: "Cadastros",
    icon: Database,
    roles: ["admin", "pro_reitoria", "chefe_departamento", "coordenador"]
  },
  {
    href: "/app/professor",
    label: "Professor",
    icon: UserRound,
    roles: ["admin", "pro_reitoria", "chefe_departamento", "coordenador", "professor"]
  },
  {
    href: "/app/aluno",
    label: "Aluno",
    icon: GraduationCap,
    roles: ["admin", "pro_reitoria", "chefe_departamento", "coordenador", "student"]
  }
];

export function AppShell({ session, children }: { session: ShellSession; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const nav = useMemo(() => allNav.filter((item) => item.roles.includes(session.role)), [session.role]);

  async function signOut() {
    await fetch("/api/auth/sign-out", { method: "POST" });
    router.push("/sign-in");
    router.refresh();
  }

  return (
    <div className="min-h-screen bg-[#f6f8fb] text-ink">
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-slateLine bg-white/95 shadow-panel backdrop-blur md:block",
          "transition-[width] duration-200 ease-out",
          collapsed ? "w-[76px]" : "w-[260px]"
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center gap-3 border-b border-slateLine px-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-ink text-white">
              <School size={21} />
            </div>
            <AnimatePresence initial={false}>
              {!collapsed ? (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  className="min-w-0"
                >
                  <p className="truncate text-sm font-semibold">OptiGrade</p>
                  <p className="truncate text-xs text-slate-600">{session.organization?.name ?? "Sem organizacao"}</p>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>

          <nav className="grid gap-1 px-3 py-4">
            {nav.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={item.label}
                  className={clsx(
                    "group relative flex h-11 items-center gap-3 rounded-md px-3 text-sm font-semibold transition duration-150 ease-out",
                    active ? "bg-lake text-white shadow-panel" : "text-slate-700 hover:bg-slate-100 hover:text-ink",
                    collapsed && "justify-center px-0"
                  )}
                >
                  <Icon size={18} className="shrink-0 transition-transform duration-150 group-hover:scale-110" />
                  {!collapsed ? <span className="truncate">{item.label}</span> : null}
                  {!collapsed && active ? <ChevronRight size={16} className="ml-auto" /> : null}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto grid gap-3 border-t border-slateLine p-3">
            <div
              className={clsx(
                "rounded-md border border-slateLine bg-slate-50 p-3 transition duration-150",
                collapsed && "flex justify-center p-2"
              )}
            >
              {collapsed ? (
                <ShieldCheck size={18} className="text-moss" />
              ) : (
                <div className="grid gap-1">
                  <span className="inline-flex items-center gap-2 text-xs font-semibold text-moss">
                    <ShieldCheck size={14} /> {academicRoleLabels[session.role]}
                  </span>
                  <span className="truncate text-xs text-slate-600">{session.user.email}</span>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between gap-2">
              <IconButton
                icon={collapsed ? PanelLeftOpen : PanelLeftClose}
                label={collapsed ? "Expandir menu" : "Recolher menu"}
                onClick={() => setCollapsed((value) => !value)}
              />
              {!collapsed ? <IconButton icon={LogOut} label="Sair" onClick={signOut} /> : null}
            </div>
          </div>
        </div>
      </aside>

      <div className={clsx("transition-[padding] duration-200 ease-out md:pl-[260px]", collapsed && "md:pl-[76px]")}>
        <header className="sticky top-0 z-20 border-b border-slateLine bg-white/90 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-3 px-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink text-white md:hidden">
                <School size={19} />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{session.organization?.name ?? "OptiGrade"}</p>
                <p className="truncate text-xs text-slate-600">
                  {session.roleLabel} · {session.user.name}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden h-9 items-center gap-2 rounded-md border border-slateLine px-3 text-xs font-semibold text-slate-700 sm:inline-flex">
                <Building2 size={14} />
                {session.organization?.name ?? "Sem organizacao"}
              </span>
              <IconButton icon={LogOut} label="Sair" onClick={signOut} />
            </div>
          </div>
          <div className="flex gap-2 overflow-x-auto border-t border-slateLine px-4 py-2 md:hidden">
            {nav.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    "inline-flex h-9 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition",
                    active ? "border-lake bg-lake text-white" : "border-slateLine bg-white text-slate-700"
                  )}
                >
                  <Icon size={15} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </header>

        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="min-h-[calc(100vh-64px)]"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
}
