"use client";

import React, { createContext, useContext, useMemo, useState } from "react";
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
  optimizationError: string | null;
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
  const [optimizationError, setOptimizationError] = useState<string | null>(null);

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
    const startedAt = Date.now();
    setOptimizationStartedAt(startedAt);
    setOptimizationError(null);
    setAssignments([]);
    try {
      const nextRun = await api<OptimizationRun>("/optimization/runs", {
        method: "POST",
        body: JSON.stringify({
          semester: "2026/2",
          profile: "deep",
          parameters: {
            student_demand_only: true,
            auto_enrollment: true,
            enrollment_stage: "pre_enrollment",
            source: "trabalho",
            presentation_run_id: newRunId(),
            requested_at: new Date(startedAt).toISOString()
          }
        })
      });
      setRun(nextRun);
    } catch (error) {
      setOptimizationError(error instanceof Error ? error.message : "Falha ao iniciar otimização");
      setRun(null);
    }
  }

  async function refreshOptimization() {
    const targetRun = run;
    if (!targetRun) return;
    const fresh = await api<OptimizationRun>(`/optimization/runs/${targetRun.id}`);
    setRun(fresh);
    if (fresh.status === "feasible" || fresh.status === "infeasible" || fresh.status === "failed") {
      setAssignments(await api<Assignment[]>(`/optimization/runs/${fresh.id}/assignments`));
    }
  }

  const value = useMemo(
    () => ({
      teacherLink,
      studentLink,
      stats,
      run,
      assignments,
      optimizationStartedAt,
      optimizationError,
      loadStats,
      createTeacherLink,
      createStudentLink,
      revokeTeacherLink,
      revokeStudentLink,
      startOptimization,
      refreshOptimization
    }),
    [teacherLink, studentLink, stats, run, assignments, optimizationStartedAt, optimizationError]
  );

  return <PresentationContext.Provider value={value}>{children}</PresentationContext.Provider>;
}

function newRunId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function usePresentation() {
  const context = useContext(PresentationContext);
  if (!context) {
    throw new Error("usePresentation deve ser usado dentro de PresentationProvider");
  }
  return context;
}
