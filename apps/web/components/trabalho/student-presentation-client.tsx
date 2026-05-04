"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, GraduationCap, Loader2, Send, Sparkles } from "lucide-react";
import {
  Course,
  PresentationStudentCreated,
  PresentationStudentToken,
  Student,
  StudentCourseSuggestion
} from "@/lib/api";

export function StudentPresentationClient({ token }: { token: string }) {
  const [portal, setPortal] = useState<PresentationStudentToken | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [suggestions, setSuggestions] = useState<StudentCourseSuggestion[]>([]);
  const [selectedCourseIds, setSelectedCourseIds] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedItems = useMemo(
    () => suggestions.filter((item) => selectedCourseIds.includes(item.course.id)),
    [selectedCourseIds, suggestions]
  );

  useEffect(() => {
    publicApi<PresentationStudentToken>(`/api/trabalho/alunos/${token}`)
      .then(setPortal)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [token]);

  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await publicApi<PresentationStudentCreated>(`/api/trabalho/alunos/${token}/students`, {
        method: "POST",
        body: JSON.stringify({ name, email: email || null })
      });
      setStudent(created.student);
      setSuggestions(created.suggestions.suggestions);
      setSelectedCourseIds(
        created.suggestions.suggestions
          .filter((item) => item.eligible)
          .slice(0, 4)
          .map((item) => item.course.id)
      );
      setStatus("Histórico gerado. Agora revise sua fila de preferência.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function submitChoices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!student || selectedCourseIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await publicApi(`/api/trabalho/alunos/${token}/students/${student.id}/choices`, {
        method: "POST",
        body: JSON.stringify({ course_ids: selectedCourseIds, queue_mode: true })
      });
      setStatus("Fila enviada. O resultado aparecerá após a rodada administrativa.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  function toggleCourse(courseId: string) {
    setSelectedCourseIds((current) =>
      current.includes(courseId) ? current.filter((item) => item !== courseId) : [...current, courseId]
    );
  }

  if (!portal && !error) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f6f8fb] px-5 text-sm text-slate-600">
        <span className="inline-flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Carregando QR Code</span>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f6f8fb] px-4 py-5 text-ink">
      <div className="mx-auto grid max-w-5xl gap-4">
        <header className="rounded-lg border border-slateLine bg-white p-4 shadow-panel">
          <p className="text-xs font-semibold uppercase text-lake">OptiGrade · apresentação</p>
          <h1 className="mt-1 text-2xl font-semibold">Escolha de cadeiras para o próximo semestre</h1>
          <p className="mt-1 text-sm text-slate-600">
            {portal?.degree_program.name ?? "Curso"} · {portal?.semester ?? "2026/2"}
          </p>
        </header>

        <AnimatePresence>
          {status ? (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex items-center gap-2 rounded-md border border-moss/30 bg-moss/10 px-4 py-3 text-sm text-moss"
            >
              <Check size={17} /> {status}
            </motion.div>
          ) : null}
        </AnimatePresence>
        {error ? <div className="rounded-md border border-rose/30 bg-rose/10 px-4 py-3 text-sm text-rose">{error}</div> : null}

        {!student ? (
          <form onSubmit={createStudent} className="grid gap-4 rounded-lg border border-slateLine bg-white p-4 shadow-panel">
            <div className="flex items-center gap-3">
              <GraduationCap className="text-lake" />
              <div>
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
            <button disabled={busy} className={primaryClass}>
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Gerar sugestões
            </button>
          </form>
        ) : (
          <form onSubmit={submitChoices} className="grid gap-4">
            <section className="rounded-lg border border-slateLine bg-white p-4 shadow-panel">
              <h2 className="text-base font-semibold">Fila principal: quero X, senão Y, senão Z</h2>
              <p className="mt-1 text-sm text-slate-600">
                Toque nas cadeiras para montar a ordem. A matrícula automática tentará respeitar esta fila.
              </p>
              <div className="mt-4 grid gap-2">
                {suggestions.slice(0, 14).map((item) => (
                  <CourseChoice
                    key={item.course.id}
                    item={item}
                    selected={selectedCourseIds.includes(item.course.id)}
                    order={selectedCourseIds.indexOf(item.course.id) + 1}
                    onClick={() => item.eligible && toggleCourse(item.course.id)}
                  />
                ))}
              </div>
            </section>
            <section className="sticky bottom-3 rounded-lg border border-slateLine bg-white/95 p-3 shadow-panel backdrop-blur">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">
                  {selectedItems.length} cadeiras na fila de {student.name}
                </p>
                <button disabled={busy || selectedItems.length === 0} className={primaryClass}>
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
