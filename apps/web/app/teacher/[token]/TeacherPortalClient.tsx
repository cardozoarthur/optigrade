"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDown,
  ArrowUp,
  BookOpenCheck,
  CalendarClock,
  Loader2,
  MessageSquareText,
  Plus,
  Send,
  Trash2
} from "lucide-react";
import { Course, dayLabels, PortalOptimizationResult } from "@/lib/api";
import { PortalResultPanel } from "@/components/portal-result-calendar";
import { Field, IconButton, Panel, PrimaryButton, inputClass } from "@/components/ui";
import { useToast } from "@/components/toast-provider";

type Portal = {
  professor_id: string;
  professor_name: string;
  semester: string;
  submitted_at?: string | null;
  courses: Course[];
};

type AvailabilityDraft = {
  id: string;
  day: number;
  start: string;
  end: string;
  kind: string;
  strength: string;
};

type CoursePreferenceDraft = {
  id: string;
  courseId: string;
  preference: number;
};

type ConstraintDraft = {
  id: string;
  text: string;
  strength: string;
};

const RESULT_POLL_INTERVAL_MS = 120000;

export default function TeacherPortalClient({ token }: { token: string }) {
  const toast = useToast();
  const [portal, setPortal] = useState<Portal | null>(null);
  const [availabilityDraft, setAvailabilityDraft] = useState<AvailabilityDraft>(() => newAvailabilityDraft());
  const [availabilityQueue, setAvailabilityQueue] = useState<AvailabilityDraft[]>([]);
  const [courseId, setCourseId] = useState("");
  const [preference, setPreference] = useState(5);
  const [courseQueue, setCourseQueue] = useState<CoursePreferenceDraft[]>([]);
  const [constraintDraft, setConstraintDraft] = useState("");
  const [constraintStrength, setConstraintStrength] = useState("soft");
  const [constraintQueue, setConstraintQueue] = useState<ConstraintDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<PortalOptimizationResult | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [lastResultCheck, setLastResultCheck] = useState<Date | null>(null);

  const courseById = useMemo(
    () => Object.fromEntries((portal?.courses ?? []).map((course) => [course.id, course])),
    [portal?.courses]
  );
  const hasItems = availabilityQueue.length > 0 || courseQueue.length > 0 || constraintQueue.length > 0;

  useEffect(() => {
    teacherPortalApi<Portal>(`/${token}`)
      .then((data) => {
        setPortal(data);
        setCourseId(data.courses[0]?.id ?? "");
        if (data.submitted_at) setSubmitted(true);
      })
      .catch((reason: unknown) =>
        toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao carregar portal")
      );
  }, [toast, token]);

  const fetchResult = useCallback(async () => {
    setResultLoading(true);
    try {
      const nextResult = await teacherPortalApi<PortalOptimizationResult>(`/${token}/result`);
      setResult(nextResult);
      setLastResultCheck(new Date());
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao buscar resultado");
    } finally {
      setResultLoading(false);
    }
  }, [toast, token]);

  useEffect(() => {
    if (!submitted || !portal) return;
    void fetchResult();
    const interval = window.setInterval(() => {
      void fetchResult();
    }, RESULT_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [fetchResult, portal, submitted]);

  function addAvailability() {
    if (toMinutes(availabilityDraft.end) <= toMinutes(availabilityDraft.start)) {
      toast.error("Janela de horário inválida.", "Revise a disponibilidade");
      return;
    }
    setAvailabilityQueue((items) => [...items, { ...availabilityDraft, id: nextDraftId() }].sort(sortAvailability));
    setAvailabilityDraft((current) => ({ ...current, start: current.end, end: addHours(current.end, 2) }));
    toast.success("Janela adicionada à fila.");
  }

  function addPreference() {
    if (!courseId) return;
    if (courseQueue.some((item) => item.courseId === courseId)) {
      toast.info("Esta cadeira já está na fila.");
      return;
    }
    setCourseQueue((items) => [...items, { id: nextDraftId(), courseId, preference }]);
    toast.success("Cadeira adicionada à fila.");
  }

  function addNaturalRule() {
    const text = constraintDraft.trim();
    if (!text) return;
    setConstraintQueue((items) => [...items, { id: nextDraftId(), text, strength: constraintStrength }]);
    setConstraintDraft("");
    toast.success("Restrição adicionada à fila.");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasItems) return;
    setBusy(true);
    try {
      await teacherPortalApi(`/${token}/submit`, {
        method: "POST",
        body: JSON.stringify({
          availability: availabilityQueue.map((item) => ({
            day: item.day,
            start_minute: toMinutes(item.start),
            end_minute: toMinutes(item.end),
            kind: item.kind,
            strength: item.strength,
            source: "teacher"
          })),
          course_preferences: courseQueue.map((item, index) => ({
            course_id: item.courseId,
            preference: item.preference,
            strength: "soft",
            note: `Fila de desejo #${index + 1}`
          })),
          natural_language_constraints: constraintQueue.map((item) => ({
            text: item.text,
            strength: item.strength
          }))
        })
      });
      const total = availabilityQueue.length + courseQueue.length + constraintQueue.length;
      setAvailabilityQueue([]);
      setCourseQueue([]);
      setConstraintQueue([]);
      setSubmitted(true);
      toast.success(`${total} restrições enviadas para ${portal?.semester ?? "o semestre"}.`, "Preferências registradas");
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason), "Falha ao enviar restrições");
    } finally {
      setBusy(false);
    }
  }

  if (!portal) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#eef3f7] px-5 text-sm text-slate-600">
        <div className="inline-flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" />
          Carregando portal
        </div>
      </main>
    );
  }

  if (submitted) {
    return (
      <PortalResultPanel
        title={portal.professor_name}
        subtitle={`Portal do professor · ${portal.semester}`}
        result={result}
        loading={resultLoading}
        lastCheckedAt={lastResultCheck}
        perspective="teacher"
        onRefresh={fetchResult}
      />
    );
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#eef3f7]">
      <header className="border-b border-slateLine bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-normal text-lake">Portal do professor</p>
            <h1 className="mt-1 break-words text-xl font-semibold sm:text-2xl">{portal.professor_name}</h1>
            <p className="text-sm text-slate-600">{portal.semester}</p>
          </div>
          <div className="w-full rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:w-auto">
            {availabilityQueue.length} janelas · {courseQueue.length} cadeiras · {constraintQueue.length} regras
          </div>
        </div>
      </header>

      <form onSubmit={submit} className="mx-auto grid max-w-6xl gap-4 px-4 py-5 pb-28 sm:px-5">
        <section className="grid gap-4 lg:grid-cols-[380px_1fr]">
          <Panel>
            <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <CalendarClock size={18} className="text-lake" />
                Janelas por dia
              </h2>
              <button
                type="button"
                onClick={addAvailability}
                className="focus-ring inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-slateLine px-3 text-sm font-semibold transition hover:border-lake hover:text-lake sm:w-auto"
              >
                <Plus size={16} />
                Adicionar
              </button>
            </div>
            <div className="grid gap-3">
              <Field label="Dia">
                <select
                  className={inputClass}
                  value={availabilityDraft.day}
                  onChange={(event) =>
                    setAvailabilityDraft((current) => ({ ...current, day: Number(event.target.value) }))
                  }
                >
                  {dayLabels.map((label, index) => (
                    <option key={label} value={index}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Início">
                  <input
                    className={inputClass}
                    type="time"
                    value={availabilityDraft.start}
                    onChange={(event) => setAvailabilityDraft((current) => ({ ...current, start: event.target.value }))}
                  />
                </Field>
                <Field label="Fim">
                  <input
                    className={inputClass}
                    type="time"
                    value={availabilityDraft.end}
                    onChange={(event) => setAvailabilityDraft((current) => ({ ...current, end: event.target.value }))}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Tipo">
                  <select
                    className={inputClass}
                    value={availabilityDraft.kind}
                    onChange={(event) => setAvailabilityDraft((current) => ({ ...current, kind: event.target.value }))}
                  >
                    <option value="available">Disponível</option>
                    <option value="preferred">Preferido</option>
                    <option value="unavailable">Indisponível</option>
                  </select>
                </Field>
                <Field label="Força">
                  <select
                    className={inputClass}
                    value={availabilityDraft.strength}
                    onChange={(event) =>
                      setAvailabilityDraft((current) => ({ ...current, strength: event.target.value }))
                    }
                  >
                    <option value="hard">Obrigatoria</option>
                    <option value="soft">Preferencia</option>
                  </select>
                </Field>
              </div>
            </div>
          </Panel>

          <Panel>
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <BookOpenCheck size={18} className="text-lake" />
              Fila de cadeiras desejadas
            </h2>
            <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_150px_auto]">
              <Field label="Cadeira">
                <select className={inputClass} value={courseId} onChange={(event) => setCourseId(event.target.value)}>
                  {portal.courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.code ? `${course.code} - ` : ""}
                      {course.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Preferencia">
                <input
                  className={inputClass}
                  type="number"
                  min={-5}
                  max={5}
                  value={preference}
                  onChange={(event) => setPreference(Number(event.target.value))}
                />
              </Field>
              <div className="flex items-end">
                <PrimaryButton type="button" onClick={addPreference} className="w-full md:w-auto">
                  <span className="inline-flex items-center gap-2">
                    <Plus size={16} />
                    Enfileirar
                  </span>
                </PrimaryButton>
              </div>
            </div>
            <CourseQueue
              items={courseQueue}
              courseById={courseById}
              onMove={(id, direction) => setCourseQueue((items) => moveById(items, id, direction))}
              onRemove={(id) => setCourseQueue((items) => items.filter((item) => item.id !== id))}
            />
          </Panel>
        </section>

        <Panel>
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <MessageSquareText size={18} className="text-lake" />
              Restrições complexas
            </h2>
            <button
              type="button"
              onClick={addNaturalRule}
              className="focus-ring inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-slateLine px-3 text-sm font-semibold transition hover:border-lake hover:text-lake sm:w-auto"
            >
              <Plus size={16} />
              Adicionar
            </button>
          </div>
          <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_180px]">
            <Field label="Regra em linguagem natural">
              <textarea
                className="focus-ring min-h-24 rounded-md border border-slateLine bg-white p-3 text-sm text-ink transition hover:border-slate-400"
                value={constraintDraft}
                onChange={(event) => setConstraintDraft(event.target.value)}
                placeholder="Ex.: posso dar Calculo A apenas se as aulas terminarem antes das 17h nas tercas e quintas."
              />
            </Field>
            <Field label="Força da regra">
              <select
                className={inputClass}
                value={constraintStrength}
                onChange={(event) => setConstraintStrength(event.target.value)}
              >
                <option value="soft">Preferencia</option>
                <option value="hard">Obrigatoria</option>
              </select>
            </Field>
          </div>
          <AvailabilityQueue items={availabilityQueue} onRemove={(id) => setAvailabilityQueue((items) => items.filter((item) => item.id !== id))} />
          <ConstraintQueue items={constraintQueue} onRemove={(id) => setConstraintQueue((items) => items.filter((item) => item.id !== id))} />
        </Panel>

        <div className="fixed inset-x-3 bottom-3 z-30 rounded-lg border border-slateLine bg-white/95 p-3 shadow-panel backdrop-blur sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none sm:backdrop-blur-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
          <span className="text-sm text-slate-600">
            {availabilityQueue.length + courseQueue.length + constraintQueue.length} itens na fila
          </span>
          <PrimaryButton type="submit" disabled={!hasItems || busy} className="w-full sm:w-auto">
            <span className="inline-flex items-center gap-2">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Enviar restrições
            </span>
          </PrimaryButton>
          </div>
        </div>
      </form>
    </main>
  );
}

function AvailabilityQueue({ items, onRemove }: { items: AvailabilityDraft[]; onRemove: (id: string) => void }) {
  if (!items.length) return null;
  return (
    <div className="mt-4 grid gap-2">
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: 12 }}
            className="grid gap-3 rounded-md border border-slateLine bg-slate-50 p-3 sm:grid-cols-[1fr_auto]"
          >
            <div className="text-sm">
              <p className="font-semibold text-ink">
                {dayLabels[item.day]} · {item.start}-{item.end}
              </p>
              <p className="text-xs text-slate-600">
                {availabilityKindLabel(item.kind)} · {strengthLabel(item.strength)}
              </p>
            </div>
            <IconButton icon={Trash2} label="Remover janela" onClick={() => onRemove(item.id)} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function CourseQueue({
  items,
  courseById,
  onMove,
  onRemove
}: {
  items: CoursePreferenceDraft[];
  courseById: Record<string, Course>;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-4 grid gap-2">
      <AnimatePresence initial={false}>
        {items.map((item, index) => {
          const course = courseById[item.courseId];
          return (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 12 }}
              className="grid gap-3 rounded-md border border-slateLine bg-slate-50 p-3 md:grid-cols-[48px_1fr_auto]"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white text-sm font-semibold text-lake">
                {index + 1}
              </div>
              <div className="text-sm">
                <p className="font-semibold text-ink">{course?.name ?? "Cadeira removida do catálogo"}</p>
                <p className="text-xs text-slate-600">
                  Preferencia {item.preference}
                  {course?.context_key ? ` · contexto ${course.context_key}` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                <IconButton icon={ArrowUp} label="Subir na fila" onClick={() => onMove(item.id, -1)} disabled={index === 0} />
                <IconButton
                  icon={ArrowDown}
                  label="Descer na fila"
                  onClick={() => onMove(item.id, 1)}
                  disabled={index === items.length - 1}
                />
                <IconButton icon={Trash2} label="Remover cadeira" onClick={() => onRemove(item.id)} />
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

function ConstraintQueue({ items, onRemove }: { items: ConstraintDraft[]; onRemove: (id: string) => void }) {
  if (!items.length) return null;
  return (
    <div className="mt-4 grid gap-2">
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: 12 }}
            className="grid gap-3 rounded-md border border-slateLine bg-slate-50 p-3 sm:grid-cols-[1fr_auto]"
          >
            <div className="text-sm">
              <p className="font-semibold text-ink">{strengthLabel(item.strength)}</p>
              <p className="text-slate-600">{item.text}</p>
            </div>
            <IconButton icon={Trash2} label="Remover regra" onClick={() => onRemove(item.id)} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

async function teacherPortalApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/teacher-portal${path}`, {
    ...init,
    credentials: "omit",
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

function newAvailabilityDraft(): AvailabilityDraft {
  return {
    id: nextDraftId(),
    day: 0,
    start: "08:00",
    end: "10:00",
    kind: "available",
    strength: "hard"
  };
}

function nextDraftId() {
  return crypto.randomUUID();
}

function toMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function addHours(value: string, hoursToAdd: number) {
  const total = Math.min(22 * 60, toMinutes(value) + hoursToAdd * 60);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function sortAvailability(left: AvailabilityDraft, right: AvailabilityDraft) {
  return left.day - right.day || toMinutes(left.start) - toMinutes(right.start);
}

function moveById<T extends { id: string }>(items: T[], id: string, direction: -1 | 1) {
  const index = items.findIndex((item) => item.id === id);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(index, 1);
  next.splice(nextIndex, 0, item);
  return next;
}

function availabilityKindLabel(value: string) {
  if (value === "unavailable") return "indisponível";
  if (value === "preferred") return "preferido";
  return "disponível";
}

function strengthLabel(value: string) {
  return value === "hard" ? "obrigatoria" : "preferencia";
}
