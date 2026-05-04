import React from "react";
import { AppShell } from "@/components/shell/app-shell";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const session = await requireAcademicSession();
  return <AppShell session={session}>{children}</AppShell>;
}
