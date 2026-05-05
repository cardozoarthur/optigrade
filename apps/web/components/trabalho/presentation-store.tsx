"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
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
  refreshOptimization: (runId?: string) => Promise<void>;
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
  const runRef = useRef<OptimizationRun | null>(null);
  const startPromiseRef = useRef<Promise<void> | null>(null);
  const presentationRunIdRef = useRef(newRunId());
  const requestedAtRef = useRef<string | null>(null);

  useEffect(() => {
    runRef.current = run;
  }, [run]);

  const loadStats = useCallback(async () => {
    setStats(await api<PresentationStats>("/presentation/stats"));
  }, []);

  const createTeacherLink = useCallback(async () => {
    if (teacherLink) return;
    const link = await api<PresentationLink>("/presentation/teacher-link", {
      method: "POST",
      body: JSON.stringify({ semester: "2026/2" })
    });
    setTeacherLink(link);
  }, [teacherLink]);

  const createStudentLink = useCallback(async () => {
    if (studentLink) return;
    const link = await api<PresentationLink>("/presentation/student-link", {
      method: "POST",
      body: JSON.stringify({ semester: "2026/2" })
    });
    setStudentLink(link);
  }, [studentLink]);

  const revokeTeacherLink = useCallback(async () => {
    if (!teacherLink) return;
    await api(`/presentation/teacher-link/${teacherLink.token}/revoke`, { method: "POST" });
    setTeacherLink(null);
  }, [teacherLink]);

  const revokeStudentLink = useCallback(async () => {
    if (!studentLink) return;
    await api(`/presentation/student-link/${studentLink.token}/revoke`, { method: "POST" });
    setStudentLink(null);
  }, [studentLink]);

  const startOptimization = useCallback(async () => {
    const currentRun = runRef.current;
    if (currentRun && (currentRun.status === "pending" || currentRun.status === "running")) return;
    if (startPromiseRef.current) return startPromiseRef.current;

    const startedAt = Date.now();
    if (!requestedAtRef.current) {
      requestedAtRef.current = new Date(startedAt).toISOString();
    }
    setOptimizationStartedAt(startedAt);
    setOptimizationError(null);
    setAssignments([]);

    startPromiseRef.current = (async () => {
      const nextRun = await api<OptimizationRun>("/optimization/runs", {
        method: "POST",
        body: JSON.stringify({
          semester: "2026/2",
          profile: "balanced",
          parameters: {
            student_demand_only: true,
            auto_enrollment: true,
            enrollment_stage: "pre_enrollment",
            source: "trabalho",
            presentation_run_id: presentationRunIdRef.current,
            requested_at: requestedAtRef.current
          }
        })
      });
      runRef.current = nextRun;
      setRun(nextRun);
    })();

    try {
      await startPromiseRef.current;
    } catch (error) {
      setOptimizationError(error instanceof Error ? error.message : "Falha ao iniciar otimização");
      runRef.current = null;
      setRun(null);
    } finally {
      startPromiseRef.current = null;
    }
  }, []);

  const refreshOptimization = useCallback(async (runId?: string) => {
    const targetRunId = runId ?? runRef.current?.id;
    if (!targetRunId) return;
    const fresh = await api<OptimizationRun>(`/optimization/runs/${targetRunId}`);
    runRef.current = fresh;
    setRun(fresh);
    if (fresh.status === "feasible" || fresh.status === "infeasible" || fresh.status === "failed") {
      setAssignments(await api<Assignment[]>(`/optimization/runs/${fresh.id}/assignments`));
    }
  }, []);

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
    [
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
    ]
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
