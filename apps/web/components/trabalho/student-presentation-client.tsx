"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { GraduationCap, Loader2, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import {
  Course,
  PortalOptimizationResult,
  PresentationStudentCreated,
  PresentationStudentToken,
  Student,
  StudentCourseSuggestion
} from "@/lib/api";
import { PortalResultPanel } from "@/components/portal-result-calendar";
import { useToast } from "@/components/toast-provider";

type TimePreferenceStrength = "hard" | "soft" | "manual_override";

type PresentationPlanItem = {
  id: string;
  courseId: string;
  day: string;
  start: string;
  end: string;
  strength: TimePreferenceStrength;
};

type PresentationPlanBranch = {
  id: string;
  label: string;
  priority: number;
  items: PresentationPlanItem[];
};

type PresentationChoiceUnit = {
  id: string;
  label: string;
  alternatives: PresentationPlanBranch[];
};

const weekDays = [
  { value: "0", label: "Segunda" },
  { value: "1", label: "Terça" },
  { value: "2", label: "Quarta" },
  { value: "3", label: "Quinta" },
  { value: "4", label: "Sexta" },
  { value: "5", label: "Sábado" }
];

const RESULT_POLL_INTERVAL_MS = 120000;

export function StudentPresentationClient({ token }: { token: string }) {
  const toast = useToast();
  const [portal, setPortal] = useState<PresentationStudentToken | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [student, setStudent] = useState<Student | null>(null);
  const [suggestions, setSuggestions] = useState<StudentCourseSuggestion[]>([]);
  const [units, setUnits] = useState<PresentationChoiceUnit[]>(() => defaultPresentationUnits());
  const [activeUnitId, setActiveUnitId] = useState("");
  const [activeAlternativeId, setActiveAlternativeId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<PortalOptimizationResult | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [lastResultCheck, setLastResultCheck] = useState<Date | null>(null);
  const activeUnit = units.find((unit) => unit.id === activeUnitId) ?? units[0];
  const activeAlternative =
    activeUnit?.alternatives.find((alternative) => alternative.id === activeAlternativeId) ??
    activeUnit?.alternatives[0];
  const activeAlternativeCourseIds = activeAlternative?.items.map((item) => item.courseId) ?? [];
  const eligibleCourseIds = useMemo(
    () => new Set(suggestions.filter((item) => item.eligible).map((item) => item.course.id)),
    [suggestions]
  );
  const courseById = useMemo(
    () => Object.fromEntries(suggestions.map((item) => [item.course.id, item.course])) as Record<string, Course>,
    [suggestions]
  );
  const selectedCourseIds = useMemo(
    () =>
      Array.from(
        new Set(
          units.flatMap((unit) =>
            unit.alternatives.flatMap((alternative) => alternative.items.map((item) => item.courseId))
          )
        )
      ),
    [units]
  );
  const selectedItems = useMemo(
    () => suggestions.filter((item) => selectedCourseIds.includes(item.course.id)),
    [selectedCourseIds, suggestions]
  );

  useEffect(() => {
    publicApi<PresentationStudentToken>(`/api/trabalho/alunos/${token}`)
      .then(setPortal)
      .catch((reason: unknown) => {
        setLoadFailed(true);
        toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao carregar QR Code");
      });
  }, [toast, token]);

  useEffect(() => {
    if (!activeUnitId && units[0]) {
      setActiveUnitId(units[0].id);
      setActiveAlternativeId(units[0].alternatives[0]?.id ?? "");
      return;
    }
    const nextActiveUnit = units.find((unit) => unit.id === activeUnitId) ?? units[0];
    if (nextActiveUnit && !nextActiveUnit.alternatives.some((alternative) => alternative.id === activeAlternativeId)) {
      setActiveAlternativeId(nextActiveUnit.alternatives[0]?.id ?? "");
    }
  }, [activeAlternativeId, activeUnitId, units]);

  const fetchResult = useCallback(async () => {
    if (!student) return;
    setResultLoading(true);
    try {
      const nextResult = await publicApi<PortalOptimizationResult>(
        `/api/trabalho/alunos/${token}/students/${student.id}/result`
      );
      setResult(nextResult);
      setLastResultCheck(new Date());
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao buscar resultado");
    } finally {
      setResultLoading(false);
    }
  }, [student, toast, token]);

  useEffect(() => {
    if (!submitted || !student) return;
    void fetchResult();
    const interval = window.setInterval(() => {
      void fetchResult();
    }, RESULT_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [fetchResult, student, submitted]);

  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await publicApi<PresentationStudentCreated>(`/api/trabalho/alunos/${token}/students`, {
        method: "POST",
        body: JSON.stringify({ name, email: email || null })
      });
      setStudent(created.student);
      setSuggestions(created.suggestions.suggestions);
      const seededUnits = seedPresentationUnits(created.suggestions.suggestions);
      setUnits(seededUnits);
      setActiveUnitId(seededUnits[0]?.id ?? "");
      setActiveAlternativeId(seededUnits[0]?.alternatives[0]?.id ?? "");
      setSubmitted(false);
      setResult(null);
      toast.success("Histórico gerado. Agora revise seu plano de preferência.", "Aluno criado");
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao criar aluno");
    } finally {
      setBusy(false);
    }
  }

  async function submitChoices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!student) return;
    const plan = buildPresentationPayload(units, eligibleCourseIds);
    if (plan.error || !plan.branches.length) {
      toast.error(plan.error ?? "Adicione ao menos uma cadeira elegível ao plano.", "Revise suas escolhas");
      return;
    }
    setBusy(true);
    try {
      await publicApi(`/api/trabalho/alunos/${token}/students/${student.id}/choices`, {
        method: "POST",
        body: JSON.stringify({ course_ids: [], queue_mode: true, branches: plan.branches })
      });
      setSubmitted(true);
      toast.success("Fila enviada. O resultado aparecerá após a rodada administrativa.", "Escolhas registradas");
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao enviar escolhas");
    } finally {
      setBusy(false);
    }
  }

  function toggleCourse(courseId: string) {
    const unitId = activeUnit?.id ?? units[0]?.id;
    const alternativeId = activeAlternative?.id ?? activeUnit?.alternatives[0]?.id;
    if (!unitId || !alternativeId) return;
    setUnits((current) =>
      current.map((unit) => {
        if (unit.id !== unitId) return unit;
        return {
          ...unit,
          alternatives: unit.alternatives.map((alternative) => {
            if (alternative.id !== alternativeId) return alternative;
            if (alternative.items.some((item) => item.courseId === courseId)) {
              return { ...alternative, items: alternative.items.filter((item) => item.courseId !== courseId) };
            }
            return { ...alternative, items: [...alternative.items, createPresentationItem(courseId)] };
          })
        };
      })
    );
  }

  function addUnit() {
    const unit = createPresentationUnit(`Demanda ${units.length + 1}`);
    setUnits((current) => [...current, unit]);
    setActiveUnitId(unit.id);
    setActiveAlternativeId(unit.alternatives[0]?.id ?? "");
  }

  function removeUnit(unitId: string) {
    if (units.length <= 1) return;
    const nextActive = units.find((unit) => unit.id !== unitId);
    setUnits((current) => current.filter((unit) => unit.id !== unitId));
    if (activeUnitId === unitId) {
      setActiveUnitId(nextActive?.id ?? "");
      setActiveAlternativeId(nextActive?.alternatives[0]?.id ?? "");
    }
  }

  function addAlternative() {
    if (!activeUnit) return;
    const alternative = createPresentationBranch(`Opção ${activeUnit.alternatives.length + 1}`, Math.max(1, 5 - activeUnit.alternatives.length));
    setUnits((current) =>
      current.map((unit) =>
        unit.id === activeUnit.id ? { ...unit, alternatives: [...unit.alternatives, alternative] } : unit
      )
    );
    setActiveAlternativeId(alternative.id);
  }

  function removeAlternative(alternativeId: string) {
    if (!activeUnit || activeUnit.alternatives.length <= 1) return;
    const nextAlternative = activeUnit.alternatives.find((alternative) => alternative.id !== alternativeId);
    setUnits((current) =>
      current.map((unit) =>
        unit.id === activeUnit.id
          ? { ...unit, alternatives: unit.alternatives.filter((alternative) => alternative.id !== alternativeId) }
          : unit
      )
    );
    if (activeAlternativeId === alternativeId) setActiveAlternativeId(nextAlternative?.id ?? "");
  }

  function updateItem(itemId: string, patch: Partial<PresentationPlanItem>) {
    if (!activeUnit || !activeAlternative) return;
    setUnits((current) =>
      current.map((unit) =>
        unit.id === activeUnit.id
          ? {
              ...unit,
              alternatives: unit.alternatives.map((alternative) =>
                alternative.id === activeAlternative.id
                  ? {
                      ...alternative,
                      items: alternative.items.map((item) => (item.id === itemId ? { ...item, ...patch } : item))
                    }
                  : alternative
              )
            }
          : unit
      )
    );
  }

  function removeItem(itemId: string) {
    if (!activeUnit || !activeAlternative) return;
    setUnits((current) =>
      current.map((unit) =>
        unit.id === activeUnit.id
          ? {
              ...unit,
              alternatives: unit.alternatives.map((alternative) =>
                alternative.id === activeAlternative.id
                  ? { ...alternative, items: alternative.items.filter((item) => item.id !== itemId) }
                  : alternative
              )
            }
          : unit
      )
    );
  }

  if (!portal && !loadFailed) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f6f8fb] px-5 text-sm text-slate-600">
        <span className="inline-flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Carregando QR Code</span>
      </main>
    );
  }

  if (!portal && loadFailed) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f6f8fb] px-5 text-center text-sm text-slate-600">
        QR Code expirado ou indisponível.
      </main>
    );
  }

  if (portal && student && submitted) {
    return (
      <PortalResultPanel
        title={`Calendário de ${student.name}`}
        subtitle={`${portal.degree_program.name} · ${portal.semester}`}
        result={result}
        loading={resultLoading}
        lastCheckedAt={lastResultCheck}
        perspective="student"
        onRefresh={fetchResult}
      />
    );
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f6f8fb] px-3 py-4 pb-28 text-ink sm:px-4 sm:py-5">
      <div className="mx-auto grid max-w-5xl gap-4">
        <header className="rounded-lg border border-slateLine bg-white p-4 shadow-panel sm:p-5">
          <p className="text-xs font-semibold uppercase text-lake">OptiGrade · apresentação</p>
          <h1 className="mt-1 text-xl font-semibold leading-tight sm:text-2xl">Escolha de cadeiras para o próximo semestre</h1>
          <p className="mt-1 text-sm text-slate-600">
            {portal?.degree_program.name ?? "Curso"} · {portal?.semester ?? "2026/2"}
          </p>
        </header>

        {!student ? (
          <form onSubmit={createStudent} className="grid gap-4 rounded-lg border border-slateLine bg-white p-4 shadow-panel sm:p-5">
            <div className="flex items-start gap-3">
              <GraduationCap className="mt-1 shrink-0 text-lake" />
              <div className="min-w-0">
                <h2 className="font-semibold">Criar aluno de teste</h2>
                <p className="text-sm text-slate-600">O sistema vai gerar um histórico acadêmico aleatório para simular dependências.</p>
              </div>
            </div>
            <label className="grid gap-1 text-sm font-medium">
              Nome
              <input required value={name} onChange={(event) => setName(event.target.value)} className={inputClass} />
            </label>
            <label className="grid gap-1 text-sm font-medium">
              E-mail opcional
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} />
            </label>
            <button disabled={busy} className={`${primaryClass} w-full sm:w-auto`}>
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Gerar sugestões
            </button>
          </form>
        ) : (
          <form onSubmit={submitChoices} className="grid gap-4">
            <section className="rounded-lg border border-slateLine bg-white p-4 shadow-panel sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold">Demandas independentes por cadeira</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    {activeUnit?.label ?? "Demanda"} · {activeAlternative?.label ?? "Opção"} ·{" "}
                    {activeAlternative?.items.length ?? 0} cadeiras nesta alternativa.
                  </p>
                </div>
                <div className="grid gap-2 sm:flex">
                  <button type="button" onClick={addUnit} className={`${secondaryClass} w-full sm:w-auto`}>
                    <Plus size={16} />
                    Demanda
                  </button>
                  <button type="button" onClick={addAlternative} className={`${secondaryClass} w-full sm:w-auto`}>
                    <Plus size={16} />
                    Opção
                  </button>
                </div>
              </div>
              <div className="mt-4 flex max-w-full gap-2 overflow-x-auto pb-1">
                {units.map((unit, index) => (
                  <button
                    type="button"
                    key={unit.id}
                    onClick={() => {
                      setActiveUnitId(unit.id);
                      setActiveAlternativeId(unit.alternatives[0]?.id ?? "");
                    }}
                    className={`h-10 shrink-0 rounded-md border px-3 text-sm font-semibold transition ${
                      activeUnit?.id === unit.id
                        ? "border-lake bg-lake text-white"
                        : "border-slateLine bg-white hover:border-lake"
                    }`}
                  >
                    {index + 1}. {unit.label} · {unit.alternatives.length}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => activeUnit && removeUnit(activeUnit.id)}
                  disabled={units.length <= 1}
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-slateLine text-rose transition hover:border-rose disabled:opacity-40"
                  title="Remover demanda"
                  aria-label="Remover demanda"
                >
                  <Trash2 size={16} />
                </button>
              </div>
              {activeUnit ? (
                <div className="mt-2 flex max-w-full gap-2 overflow-x-auto pb-1">
                  {activeUnit.alternatives.map((alternative, index) => (
                    <button
                      type="button"
                      key={alternative.id}
                      onClick={() => setActiveAlternativeId(alternative.id)}
                      className={`h-9 shrink-0 rounded-md border px-3 text-xs font-semibold transition ${
                        activeAlternative?.id === alternative.id
                          ? "border-moss bg-moss text-white"
                          : "border-slateLine bg-slate-50 hover:border-moss"
                      }`}
                    >
                      {index + 1}. {alternative.label} · {alternative.items.length}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => activeAlternative && removeAlternative(activeAlternative.id)}
                    disabled={activeUnit.alternatives.length <= 1}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slateLine text-rose transition hover:border-rose disabled:opacity-40"
                    title="Remover opção"
                    aria-label="Remover opção"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ) : null}
              <p className="mt-1 text-sm text-slate-600">
                Cada demanda é decidida separadamente; uma opção pode ter uma ou várias cadeiras. Ex.: Cálculo A senão Álgebra + Geometria.
              </p>
              <div className="mt-4 grid gap-2">
                {suggestions.slice(0, 14).map((item) => (
                  <CourseChoice
                    key={item.course.id}
                    item={item}
                    selected={activeAlternativeCourseIds.includes(item.course.id)}
                    order={activeAlternativeCourseIds.indexOf(item.course.id) + 1}
                    onClick={() => item.eligible && toggleCourse(item.course.id)}
                  />
                ))}
              </div>
              {activeAlternative?.items.length ? (
                <div className="mt-4 grid gap-2">
                  {activeAlternative.items.map((item) => (
                    <div
                      key={item.id}
                      className="grid min-w-0 gap-2 rounded-md border border-slateLine bg-slate-50 p-3 md:grid-cols-[minmax(160px,1fr)_110px_100px_100px_120px_40px]"
                    >
                      <label className="grid gap-1 text-xs font-semibold">
                        Cadeira
                        <select
                          className={inputClass}
                          value={item.courseId}
                          onChange={(event) => updateItem(item.id, { courseId: event.target.value })}
                        >
                          {suggestions.filter((suggestion) => suggestion.eligible).map((suggestion) => (
                            <option key={suggestion.course.id} value={suggestion.course.id}>
                              {suggestion.course.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="grid gap-1 text-xs font-semibold">
                        Dia
                        <select className={inputClass} value={item.day} onChange={(event) => updateItem(item.id, { day: event.target.value })}>
                          <option value="">Livre</option>
                          {weekDays.map((day) => (
                            <option key={day.value} value={day.value}>
                              {day.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="grid gap-1 text-xs font-semibold">
                        Início
                        <input className={inputClass} type="time" value={item.start} onChange={(event) => updateItem(item.id, { start: event.target.value })} />
                      </label>
                      <label className="grid gap-1 text-xs font-semibold">
                        Fim
                        <input className={inputClass} type="time" value={item.end} onChange={(event) => updateItem(item.id, { end: event.target.value })} />
                      </label>
                      <label className="grid gap-1 text-xs font-semibold">
                        Força
                        <select
                          className={inputClass}
                          value={item.strength}
                          onChange={(event) => updateItem(item.id, { strength: event.target.value as TimePreferenceStrength })}
                        >
                          <option value="soft">Preferência</option>
                          <option value="hard">Forte</option>
                          <option value="manual_override">Manual</option>
                        </select>
                      </label>
                      <div className="flex items-end">
                        <button
                          type="button"
                          onClick={() => removeItem(item.id)}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slateLine text-rose transition hover:border-rose"
                          title={`Remover ${courseById[item.courseId]?.name ?? "cadeira"}`}
                          aria-label={`Remover ${courseById[item.courseId]?.name ?? "cadeira"}`}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
            <section className="fixed inset-x-3 bottom-3 z-30 rounded-lg border border-slateLine bg-white/95 p-3 shadow-panel backdrop-blur sm:sticky sm:inset-x-auto">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">
                  {selectedItems.length} cadeiras na fila de {student.name}
                </p>
                <button disabled={busy || selectedItems.length === 0} className={`${primaryClass} w-full sm:w-auto`}>
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  Enviar escolhas
                </button>
              </div>
            </section>
          </form>
        )}
      </div>
    </main>
  );
}

function CourseChoice({
  item,
  selected,
  order,
  onClick
}: {
  item: StudentCourseSuggestion;
  selected: boolean;
  order: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!item.eligible}
      className={`grid gap-1 rounded-md border px-3 py-3 text-left text-sm transition ${
        selected
          ? "border-lake bg-lake/10"
          : item.eligible
            ? "border-slateLine bg-slate-50 hover:border-lake"
            : "border-rose/30 bg-rose/10 opacity-70"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-semibold">{item.course.name}</span>
        <span className="rounded bg-white px-2 py-1 text-xs font-semibold">{selected ? `#${order}` : item.score}</span>
      </div>
      <p className="text-xs text-slate-600">{item.reasons.slice(0, 2).join(" · ")}</p>
    </button>
  );
}

async function publicApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const inputClass =
  "focus:outline-none focus:ring-2 focus:ring-lake focus:ring-offset-2 h-10 rounded-md border border-slateLine bg-white px-3 text-sm text-ink transition hover:border-slate-400";

const primaryClass =
  "focus:outline-none focus:ring-2 focus:ring-lake focus:ring-offset-2 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-lake px-4 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#155876] disabled:cursor-not-allowed disabled:opacity-50";

const secondaryClass =
  "focus:outline-none focus:ring-2 focus:ring-lake focus:ring-offset-2 inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:border-lake hover:text-lake disabled:cursor-not-allowed disabled:opacity-50";

function createDraftId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createPresentationItem(courseId = "", id = createDraftId("item")): PresentationPlanItem {
  return {
    id,
    courseId,
    day: "",
    start: "",
    end: "",
    strength: "soft"
  };
}

function createPresentationBranch(
  label: string,
  priority: number,
  items: PresentationPlanItem[] = [],
  id = createDraftId("branch")
): PresentationPlanBranch {
  return {
    id,
    label,
    priority,
    items
  };
}

function createPresentationUnit(
  label: string,
  alternatives: PresentationPlanBranch[] = [
    createPresentationBranch("Opção principal", 5),
    createPresentationBranch("Se não", 4)
  ],
  id = createDraftId("unit")
): PresentationChoiceUnit {
  return {
    id,
    label,
    alternatives
  };
}

function defaultPresentationUnits() {
  return [
    createPresentationUnit(
      "Demanda 1",
      [
        createPresentationBranch("Opção principal", 5, [], "presentation-default-a1"),
        createPresentationBranch("Se não", 4, [], "presentation-default-a2")
      ],
      "presentation-demand-a"
    ),
    createPresentationUnit(
      "Demanda 2",
      [
        createPresentationBranch("Opção principal", 5, [], "presentation-default-b1"),
        createPresentationBranch("Se não", 4, [], "presentation-default-b2")
      ],
      "presentation-demand-b"
    )
  ];
}

function seedPresentationUnits(suggestions: StudentCourseSuggestion[]) {
  const eligible = suggestions.filter((item) => item.eligible).map((item) => item.course.id);
  if (!eligible.length) return defaultPresentationUnits();
  return [
    createPresentationUnit(
      "Recuperar prioridade",
      [
        createPresentationBranch("Opção principal", 5, eligible.slice(0, 1).map((courseId) => createPresentationItem(courseId))),
        createPresentationBranch("Se não", 4, eligible.slice(1, 3).map((courseId) => createPresentationItem(courseId)))
      ],
      "presentation-demand-a"
    ),
    createPresentationUnit(
      "Completar carga",
      [
        createPresentationBranch("Opção principal", 5, eligible.slice(3, 4).map((courseId) => createPresentationItem(courseId))),
        createPresentationBranch("Se não", 4, eligible.slice(4, 6).map((courseId) => createPresentationItem(courseId)))
      ],
      "presentation-demand-b"
    )
  ];
}

function buildPresentationPayload(units: PresentationChoiceUnit[], eligibleCourseIds: Set<string>) {
  const payloadBranches = [];
  for (const unit of units) {
    for (const [index, alternative] of unit.alternatives.entries()) {
      const items = [];
      for (const item of alternative.items) {
        if (!item.courseId || !eligibleCourseIds.has(item.courseId)) continue;
        const time = parseOptionalTimeWindow(item);
        if (time.error) return { branches: [], error: time.error };
        items.push({
          course_id: item.courseId,
          priority: null,
          desired_day: time.day,
          desired_start_minute: time.start,
          desired_end_minute: time.end,
          time_preference_strength: item.strength,
          note: null
        });
      }
      if (items.length) {
        payloadBranches.push({
          choice_group: unit.id,
          preference_order: index + 1,
          priority: alternative.priority,
          label: `${unit.label}: ${alternative.label}`,
          items
        });
      }
    }
  }
  return { branches: payloadBranches };
}

function parseOptionalTimeWindow(item: PresentationPlanItem) {
  const hasAny = Boolean(item.day || item.start || item.end);
  const hasAll = Boolean(item.day && item.start && item.end);
  if (hasAny && !hasAll) {
    return { error: "Preencha dia, início e fim para cada janela de horário.", day: null, start: null, end: null };
  }
  if (!hasAll) return { day: null, start: null, end: null };
  const start = timeToMinutes(item.start);
  const end = timeToMinutes(item.end);
  if (end <= start) {
    return { error: "O horário final deve ser posterior ao inicial.", day: null, start: null, end: null };
  }
  return { day: Number(item.day), start, end };
}

function timeToMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}
