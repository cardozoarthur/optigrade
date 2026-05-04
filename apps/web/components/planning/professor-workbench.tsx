"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDown,
  ArrowUp,
  BookOpenCheck,
  CalendarClock,
  Check,
  Loader2,
  MessageSquareText,
  Plus,
  Send,
  Trash2
} from "lucide-react";
import { Course, Professor, api, dayLabels } from "@/lib/api";
import { Field, IconButton, Panel, PrimaryButton, inputClass } from "@/components/ui";

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

export function ProfessorWorkbench({ professorId }: { professorId?: string | null }) {
  const [professors, setProfessors] = useState<Professor[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedProfessorId, setSelectedProfessorId] = useState(professorId ?? "");
  const [availabilityDraft, setAvailabilityDraft] = useState<AvailabilityDraft>(() => newAvailabilityDraft());
  const [availabilityQueue, setAvailabilityQueue] = useState<AvailabilityDraft[]>([]);
  const [courseId, setCourseId] = useState("");
  const [preference, setPreference] = useState(5);
  const [courseQueue, setCourseQueue] = useState<CoursePreferenceDraft[]>([]);
  const [constraintDraft, setConstraintDraft] = useState("");
  const [constraintStrength, setConstraintStrength] = useState("soft");
  const [constraintQueue, setConstraintQueue] = useState<ConstraintDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedProfessor = useMemo(
    () => professors.find((professor) => professor.id === selectedProfessorId),
    [professors, selectedProfessorId]
  );
  const courseById = useMemo(() => Object.fromEntries(courses.map((course) => [course.id, course])), [courses]);
  const hasItems = availabilityQueue.length > 0 || courseQueue.length > 0 || constraintQueue.length > 0;

  useEffect(() => {
    async function load() {
      const [nextProfessors, nextCourses] = await Promise.all([
        api<Professor[]>("/professors"),
        api<Course[]>("/courses")
      ]);
      setProfessors(nextProfessors);
      setCourses(nextCourses);
      setSelectedProfessorId(professorId ?? nextProfessors[0]?.id ?? "");
      setCourseId(nextCourses[0]?.id ?? "");
    }

    load().catch((reason: unknown) => setError(String(reason)));
  }, [professorId]);

  function addAvailability() {
    setError(null);
    if (toMinutes(availabilityDraft.end) <= toMinutes(availabilityDraft.start)) {
      setError("Janela de horario invalida.");
      return;
    }
    setAvailabilityQueue((current) => [...current, { ...availabilityDraft, id: nextDraftId() }]);
    setAvailabilityDraft((current) => ({ ...current, start: current.end, end: addHours(current.end, 2) }));
  }

  function addCoursePreference() {
    if (!courseId) return;
    setError(null);
    if (courseQueue.some((item) => item.courseId === courseId)) {
      setError("Esta cadeira ja esta na fila.");
      return;
    }
    setCourseQueue((current) => [...current, { id: nextDraftId(), courseId, preference }]);
  }

  function addConstraint() {
    const text = constraintDraft.trim();
    if (!text) return;
    setConstraintQueue((current) => [...current, { id: nextDraftId(), text, strength: constraintStrength }]);
    setConstraintDraft("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfessorId || !hasItems) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      await api(`/professors/${selectedProfessorId}/preference-batch`, {
        method: "POST",
        body: JSON.stringify({
          availability: availabilityQueue.map((item) => ({
            day: item.day,
            start_minute: toMinutes(item.start),
            end_minute: toMinutes(item.end),
            kind: item.kind,
            strength: item.strength,
            source: "authenticated-professor"
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
      setStatus(`${total} restricoes registradas para a proxima otimizacao`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-4 px-5 py-5">
      <AnimatePresence>
        {status ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="flex items-center gap-2 rounded-md border border-moss/30 bg-moss/10 px-4 py-3 text-sm text-moss"
          >
            <Check size={18} /> {status}
          </motion.div>
        ) : null}
      </AnimatePresence>
      {error ? (
        <div className="rounded-md border border-rose/30 bg-rose/10 px-4 py-3 text-sm text-rose">{error}</div>
      ) : null}

      <form onSubmit={submit} className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Panel>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold">Perfil docente</h2>
              <p className="text-sm text-slate-600">{selectedProfessor?.department ?? "Selecione um professor"}</p>
            </div>
            <CalendarClock size={20} className="text-lake" />
          </div>
          <div className="grid gap-3">
            <Field label="Professor">
              <select
                className={inputClass}
                value={selectedProfessorId}
                onChange={(event) => setSelectedProfessorId(event.target.value)}
                disabled={Boolean(professorId)}
                required
              >
                <option value="">Selecione</option>
                {professors.map((professor) => (
                  <option key={professor.id} value={professor.id}>
                    {professor.name}
                    {professor.contract?.is_borrowed ? " · emprestado" : ""}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Carga minima">
                <input className={inputClass} value={selectedProfessor?.contract?.min_hours ?? "-"} readOnly />
              </Field>
              <Field label="Carga maxima">
                <input className={inputClass} value={selectedProfessor?.contract?.max_hours ?? "-"} readOnly />
              </Field>
            </div>
            <div className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-xs text-slate-600">
              {availabilityQueue.length} janelas · {courseQueue.length} cadeiras · {constraintQueue.length} regras
            </div>
          </div>
        </Panel>

        <div className="grid gap-4">
          <Panel>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <CalendarClock size={18} className="text-lake" />
                Janelas de disponibilidade
              </h2>
              <button
                type="button"
                onClick={addAvailability}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slateLine px-3 text-sm font-semibold transition hover:border-lake hover:text-lake"
              >
                <Plus size={16} />
                Adicionar
              </button>
            </div>
            <div className="grid gap-3 md:grid-cols-5">
              <Field label="Dia">
                <select
                  className={inputClass}
                  value={availabilityDraft.day}
                  onChange={(event) =>
                    setAvailabilityDraft((current) => ({ ...current, day: Number(event.target.value) }))
                  }
                >
                  {dayLabels.slice(0, 6).map((label, index) => (
                    <option key={label} value={index}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Inicio">
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
              <Field label="Tipo">
                <select
                  className={inputClass}
                  value={availabilityDraft.kind}
                  onChange={(event) => setAvailabilityDraft((current) => ({ ...current, kind: event.target.value }))}
                >
                  <option value="available">Disponivel</option>
                  <option value="preferred">Preferido</option>
                  <option value="unavailable">Indisponivel</option>
                </select>
              </Field>
              <Field label="Forca">
                <select
                  className={inputClass}
                  value={availabilityDraft.strength}
                  onChange={(event) => setAvailabilityDraft((current) => ({ ...current, strength: event.target.value }))}
                >
                  <option value="hard">Obrigatoria</option>
                  <option value="soft">Preferencia</option>
                </select>
              </Field>
            </div>
            <AvailabilityQueue items={availabilityQueue} onRemove={(id) => removeById(id, setAvailabilityQueue)} />
          </Panel>

          <section className="grid gap-4 xl:grid-cols-2">
            <Panel>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <BookOpenCheck size={18} className="text-lake" />
                  Fila de cadeiras desejadas
                </h2>
                <button
                  type="button"
                  onClick={addCoursePreference}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slateLine px-3 text-sm font-semibold transition hover:border-lake hover:text-lake"
                >
                  <Plus size={16} />
                  Adicionar
                </button>
              </div>
              <div className="grid gap-3">
                <Field label="Disciplina">
                  <select className={inputClass} value={courseId} onChange={(event) => setCourseId(event.target.value)}>
                    {courses.map((course) => (
                      <option key={course.id} value={course.id}>
                        {course.code ? `${course.code} · ` : ""}
                        {course.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Preferencia (-5 a 5)">
                  <input
                    className={inputClass}
                    type="number"
                    min={-5}
                    max={5}
                    value={preference}
                    onChange={(event) => setPreference(Number(event.target.value))}
                  />
                </Field>
                <CourseQueue
                  items={courseQueue}
                  courseById={courseById}
                  onMove={setCourseQueue}
                  onRemove={(id) => removeById(id, setCourseQueue)}
                />
              </div>
            </Panel>

            <Panel>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <MessageSquareText size={18} className="text-lake" />
                  Restricoes complexas
                </h2>
                <button
                  type="button"
                  onClick={addConstraint}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slateLine px-3 text-sm font-semibold transition hover:border-lake hover:text-lake"
                >
                  <Plus size={16} />
                  Adicionar
                </button>
              </div>
              <div className="grid gap-3">
                <Field label="Forca">
                  <select
                    className={inputClass}
                    value={constraintStrength}
                    onChange={(event) => setConstraintStrength(event.target.value)}
                  >
                    <option value="soft">Preferencia</option>
                    <option value="hard">Obrigatoria</option>
                    <option value="manual_override">Exige revisao</option>
                  </select>
                </Field>
                <textarea
                  className="focus-ring min-h-28 rounded-md border border-slateLine bg-white p-3 text-sm text-ink transition"
                  value={constraintDraft}
                  onChange={(event) => setConstraintDraft(event.target.value)}
                  placeholder="Ex.: prefiro nao concentrar aulas teoricas depois das 20h nas sextas."
                />
                <ConstraintQueue items={constraintQueue} onRemove={(id) => removeById(id, setConstraintQueue)} />
              </div>
            </Panel>
          </section>

          <div className="flex justify-end">
            <PrimaryButton type="submit" disabled={busy || !selectedProfessorId || !hasItems}>
              <span className="inline-flex items-center gap-2">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                Enviar lote
              </span>
            </PrimaryButton>
          </div>
        </div>
      </form>
    </div>
  );
}

function AvailabilityQueue({
  items,
  onRemove
}: {
  items: AvailabilityDraft[];
  onRemove: (id: string) => void;
}) {
  const ordered = [...items].sort((left, right) => left.day - right.day || toMinutes(left.start) - toMinutes(right.start));
  return (
    <div className="mt-3 grid gap-2 md:grid-cols-2">
      <AnimatePresence initial={false}>
        {ordered.map((item) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-between gap-3 rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm"
          >
            <span>
              <span className="font-semibold text-ink">{dayLabels[item.day]}</span>{" "}
              <span className="text-slate-600">
                {item.start}-{item.end} · {availabilityKindLabel(item.kind)} · {strengthLabel(item.strength)}
              </span>
            </span>
            <IconButton icon={Trash2} label="Remover janela" onClick={() => onRemove(item.id)} />
          </motion.div>
        ))}
      </AnimatePresence>
      {items.length === 0 ? <EmptyQueue text="Nenhuma janela adicionada." /> : null}
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
  onMove: React.Dispatch<React.SetStateAction<CoursePreferenceDraft[]>>;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="grid gap-2">
      <AnimatePresence initial={false}>
        {items.map((item, index) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-xs font-semibold text-lake">
              {index + 1}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{courseById[item.courseId]?.name ?? item.courseId}</span>
              <span className="text-xs text-slate-600">Preferencia {item.preference}</span>
            </span>
            <span className="flex gap-1">
              <IconButton icon={ArrowUp} label="Subir" onClick={() => onMove((current) => moveItem(current, index, -1))} />
              <IconButton icon={ArrowDown} label="Descer" onClick={() => onMove((current) => moveItem(current, index, 1))} />
              <IconButton icon={Trash2} label="Remover cadeira" onClick={() => onRemove(item.id)} />
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
      {items.length === 0 ? <EmptyQueue text="Nenhuma cadeira na fila." /> : null}
    </div>
  );
}

function ConstraintQueue({ items, onRemove }: { items: ConstraintDraft[]; onRemove: (id: string) => void }) {
  return (
    <div className="grid gap-2">
      <AnimatePresence initial={false}>
        {items.map((item, index) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm"
          >
            <span className="min-w-0">
              <span className="block text-xs font-semibold text-lake">Regra {index + 1} · {strengthLabel(item.strength)}</span>
              <span className="block break-words text-slate-700">{item.text}</span>
            </span>
            <IconButton icon={Trash2} label="Remover restricao" onClick={() => onRemove(item.id)} />
          </motion.div>
        ))}
      </AnimatePresence>
      {items.length === 0 ? <EmptyQueue text="Nenhuma restricao adicionada." /> : null}
    </div>
  );
}

function EmptyQueue({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-dashed border-slateLine px-3 py-4 text-center text-sm text-slate-600">
      {text}
    </div>
  );
}

function newAvailabilityDraft(): AvailabilityDraft {
  return {
    id: nextDraftId(),
    day: 0,
    start: "08:00",
    end: "12:00",
    kind: "available",
    strength: "hard"
  };
}

function nextDraftId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function removeById<T extends { id: string }>(id: string, setItems: React.Dispatch<React.SetStateAction<T[]>>) {
  setItems((current) => current.filter((item) => item.id !== id));
}

function moveItem<T>(items: T[], index: number, direction: -1 | 1) {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(index, 1);
  next.splice(nextIndex, 0, item);
  return next;
}

function availabilityKindLabel(value: string) {
  if (value === "preferred") return "preferido";
  if (value === "unavailable") return "indisponivel";
  return "disponivel";
}

function strengthLabel(value: string) {
  if (value === "hard") return "obrigatoria";
  if (value === "manual_override") return "revisao";
  return "preferencia";
}

function toMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function addHours(value: string, hoursToAdd: number) {
  const minutes = Math.min(toMinutes(value) + hoursToAdd * 60, 23 * 60 + 59);
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}
