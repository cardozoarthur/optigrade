"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  Assignment,
  OptimizationRun,
  PresentationLink,
  PresentationStats,
  api
} from "@/lib/api";

type PresentationState = {
  teacherLink: PresentationLink | null;
  studentLink: PresentationLink | null;
  stats: PresentationStats | null;
  run: OptimizationRun | null;
  assignments: Assignment[];
  optimizationStartedAt: number | null;
  loadStats: () => Promise<void>;
  createTeacherLink: () => Promise<void>;
  createStudentLink: () => Promise<void>;
  revokeTeacherLink: () => Promise<void>;
  revokeStudentLink: () => Promise<void>;
  startOptimization: () => Promise<void>;
  refreshOptimization: () => Promise<void>;
};

const PresentationContext = createContext<PresentationState | null>(null);

export function PresentationProvider({ children }: { children: React.ReactNode }) {
  const [teacherLink, setTeacherLink] = useState<PresentationLink | null>(null);
  const [studentLink, setStudentLink] = useState<PresentationLink | null>(null);
  const [stats, setStats] = useState<PresentationStats | null>(null);
  const [run, setRun] = useState<OptimizationRun | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [optimizationStartedAt, setOptimizationStartedAt] = useState<number | null>(null);

  useEffect(() => {
    const saved = window.sessionStorage.getItem("optigrade:trabalho");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as {
        run?: OptimizationRun;
        optimizationStartedAt?: number;
      };
      setRun(parsed.run ?? null);
      setOptimizationStartedAt(parsed.optimizationStartedAt ?? null);
    } catch {
      window.sessionStorage.removeItem("optigrade:trabalho");
    }
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem(
      "optigrade:trabalho",
      JSON.stringify({ run, optimizationStartedAt })
    );
  }, [run, optimizationStartedAt]);

  async function loadStats() {
    setStats(await api<PresentationStats>("/presentation/stats"));
  }

  async function createTeacherLink() {
    if (teacherLink) return;
    const link = await api<PresentationLink>("/presentation/teacher-link", {
      method: "POST",
      body: JSON.stringify({ semester: "2026/2" })
    });
    setTeacherLink(link);
  }

  async function createStudentLink() {
    if (studentLink) return;
    const link = await api<PresentationLink>("/presentation/student-link", {
      method: "POST",
      body: JSON.stringify({ semester: "2026/2" })
    });
    setStudentLink(link);
  }

  async function revokeTeacherLink() {
    if (!teacherLink) return;
    await api(`/presentation/teacher-link/${teacherLink.token}/revoke`, { method: "POST" });
    setTeacherLink(null);
  }

  async function revokeStudentLink() {
    if (!studentLink) return;
    await api(`/presentation/student-link/${studentLink.token}/revoke`, { method: "POST" });
    setStudentLink(null);
  }

  async function startOptimization() {
    if (run && (run.status === "pending" || run.status === "running")) return;
    if (run?.finished_at) return;
    const nextRun = await api<OptimizationRun>("/optimization/runs", {
      method: "POST",
      body: JSON.stringify({
        semester: "2026/2",
        profile: "deep",
        parameters: {
          student_demand_only: true,
          auto_enrollment: true,
          enrollment_stage: "pre_enrollment",
          source: "trabalho"
        }
      })
    });
    setRun(nextRun);
    setAssignments([]);
    setOptimizationStartedAt(Date.now());
  }

  async function refreshOptimization() {
    const targetRun = run ?? (await latestRun());
    if (!targetRun) return;
    const fresh = await api<OptimizationRun>(`/optimization/runs/${targetRun.id}`);
    setRun(fresh);
    if (fresh.status === "feasible" || fresh.status === "infeasible" || fresh.status === "failed") {
      setAssignments(await api<Assignment[]>(`/optimization/runs/${fresh.id}/assignments`));
    }
  }

  async function latestRun() {
    const runs = await api<OptimizationRun[]>("/optimization/runs");
    const latest = runs[0] ?? null;
    setRun(latest);
    return latest;
  }

  const value = useMemo(
    () => ({
      teacherLink,
      studentLink,
      stats,
      run,
      assignments,
      optimizationStartedAt,
      loadStats,
      createTeacherLink,
      createStudentLink,
      revokeTeacherLink,
      revokeStudentLink,
      startOptimization,
      refreshOptimization
    }),
    [teacherLink, studentLink, stats, run, assignments, optimizationStartedAt]
  );

  return <PresentationContext.Provider value={value}>{children}</PresentationContext.Provider>;
}

export function usePresentation() {
  const context = useContext(PresentationContext);
  if (!context) {
    throw new Error("usePresentation deve ser usado dentro de PresentationProvider");
  }
  return context;
}
