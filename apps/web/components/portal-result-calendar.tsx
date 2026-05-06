"use client";

import { motion } from "framer-motion";
import { AlertCircle, CalendarCheck2, Clock, Loader2, MapPin, RefreshCw, Users } from "lucide-react";
import {
  dayLabels,
  minutesToLabel,
  PortalCalendarEntry,
  PortalOptimizationResult
} from "@/lib/api";

type PortalResultPanelProps = {
  title: string;
  subtitle: string;
  result: PortalOptimizationResult | null;
  loading: boolean;
  lastCheckedAt: Date | null;
  perspective: "student" | "teacher";
  onRefresh?: () => void;
};

export function PortalResultPanel({
  title,
  subtitle,
  result,
  loading,
  lastCheckedAt,
  perspective,
  onRefresh
}: PortalResultPanelProps) {
  const ready = result?.status === "ready";
  const failed = result?.status === "failed";

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f6f8fb] px-3 py-4 text-ink sm:px-5">
      <div className="mx-auto grid max-w-6xl gap-4">
        <header className="rounded-lg border border-slateLine bg-white p-4 shadow-panel sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-normal text-lake">OptiGrade · resultado</p>
              <h1 className="mt-1 break-words text-xl font-semibold leading-tight sm:text-2xl">{title}</h1>
              <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
            </div>
            <StatusPill result={result} loading={loading} />
          </div>
        </header>

        {!ready ? (
          <WaitingPanel
            failed={failed}
            message={result?.message}
            lastCheckedAt={lastCheckedAt}
            loading={loading}
            onRefresh={onRefresh}
          />
        ) : (
          <CalendarPanel result={result} perspective={perspective} lastCheckedAt={lastCheckedAt} onRefresh={onRefresh} />
        )}
      </div>
    </main>
  );
}

function WaitingPanel({
  failed,
  message,
  lastCheckedAt,
  loading,
  onRefresh
}: {
  failed: boolean;
  message?: string | null;
  lastCheckedAt: Date | null;
  loading: boolean;
  onRefresh?: () => void;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid min-h-[62vh] place-items-center rounded-lg border border-slateLine bg-white p-5 text-center shadow-panel"
    >
      <div className="grid max-w-md justify-items-center gap-4">
        <div className={`grid h-16 w-16 place-items-center rounded-full ${failed ? "bg-rose/10 text-rose" : "bg-lake/10 text-lake"}`}>
          {failed ? <AlertCircle size={28} /> : <Loader2 size={28} className="animate-spin" />}
        </div>
        <div>
          <h2 className="text-lg font-semibold">
            {failed ? "Rodada indisponível" : "Aguardando finalização da rodada"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {message || "Assim que a otimização assíncrona terminar, o calendário final aparece aqui automaticamente."}
          </p>
        </div>
        <div className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Consulta automática a cada 2 minutos
          {lastCheckedAt ? ` · última busca ${lastCheckedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}` : ""}
        </div>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slateLine bg-white px-4 text-sm font-semibold transition hover:border-lake hover:text-lake disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Atualizar agora
          </button>
        ) : null}
      </div>
    </motion.section>
  );
}

function CalendarPanel({
  result,
  perspective,
  lastCheckedAt,
  onRefresh
}: {
  result: PortalOptimizationResult;
  perspective: "student" | "teacher";
  lastCheckedAt: Date | null;
  onRefresh?: () => void;
}) {
  const sortedEntries = [...result.calendar].sort(
    (left, right) => left.day - right.day || left.start_minute - right.start_minute || left.course_name.localeCompare(right.course_name)
  );
  const entriesByDay = dayLabels.map((label, day) => ({
    label,
    entries: sortedEntries.filter((entry) => entry.day === day)
  }));

  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-slateLine bg-white p-4 shadow-panel sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Calendário final</h2>
          <p className="mt-1 text-sm text-slate-600">
            {sortedEntries.length} horários confirmados
            {lastCheckedAt ? ` · atualizado ${lastCheckedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}` : ""}
          </p>
        </div>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            className="focus-ring inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-slateLine bg-white px-4 text-sm font-semibold transition hover:border-lake hover:text-lake sm:w-auto"
          >
            <RefreshCw size={16} />
            Atualizar
          </button>
        ) : null}
      </div>

      {sortedEntries.length ? (
        <div className="grid gap-3 lg:grid-cols-6">
          {entriesByDay.slice(0, 6).map((day) => (
            <div key={day.label} className="grid content-start gap-2 rounded-lg border border-slateLine bg-white p-3 shadow-panel">
              <p className="text-xs font-semibold uppercase text-slate-500">{day.label}</p>
              {day.entries.length ? (
                day.entries.map((entry) => (
                  <CalendarCard key={entry.id} entry={entry} perspective={perspective} />
                ))
              ) : (
                <div className="rounded-md border border-dashed border-slateLine px-3 py-4 text-center text-xs text-slate-500">
                  Sem aulas
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <EmptyCalendar result={result} />
      )}
    </motion.section>
  );
}

function CalendarCard({ entry, perspective }: { entry: PortalCalendarEntry; perspective: "student" | "teacher" }) {
  return (
    <motion.article
      layout
      whileHover={{ y: -2 }}
      className="rounded-md border border-slateLine bg-slate-50 p-3 text-left text-xs transition hover:border-lake"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-ink">{entry.course_name}</p>
          <p className="mt-0.5 text-slate-500">{entry.section_label ?? "Turma"}</p>
        </div>
        {typeof entry.enrolled_count === "number" ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded bg-white px-2 py-1 font-semibold text-lake">
            <Users size={12} />
            {entry.enrolled_count}
          </span>
        ) : null}
      </div>
      <p className="mt-2 inline-flex items-center gap-1 font-semibold text-lake">
        <Clock size={13} />
        {minutesToLabel(entry.start_minute)}-{minutesToLabel(entry.end_minute)}
      </p>
      <p className="mt-2 text-slate-600">
        {perspective === "student" ? entry.professor_name : entry.origin_degree_program_name || entry.course_degree_program_name}
      </p>
      <p className="mt-1 inline-flex items-start gap-1 text-slate-600">
        <MapPin size={13} className="mt-0.5 shrink-0" />
        <span>{[entry.room_name, entry.campus_name].filter(Boolean).join(" · ") || "Sala a definir"}</span>
      </p>
      {entry.reason || entry.decision_type ? (
        <p className="mt-2 rounded bg-white px-2 py-1 text-slate-600">
          {entry.decision_type || "alocação"}{entry.reason ? ` · ${entry.reason}` : ""}
        </p>
      ) : null}
    </motion.article>
  );
}

function EmptyCalendar({ result }: { result: PortalOptimizationResult }) {
  return (
    <section className="rounded-lg border border-slateLine bg-white p-5 text-sm text-slate-600 shadow-panel">
      <div className="flex items-start gap-3">
        <CalendarCheck2 className="mt-0.5 shrink-0 text-lake" />
        <div className="min-w-0">
          <h2 className="font-semibold text-ink">Nenhum horário confirmado para este perfil</h2>
          <p className="mt-1">A rodada terminou, mas não retornou aulas confirmadas para este acesso.</p>
        </div>
      </div>
      {result.unallocated?.length ? (
        <div className="mt-4 grid gap-2">
          {result.unallocated.map((item) => (
            <div key={item.id} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <span className="font-semibold">{item.course_name}</span>
              {item.reason ? ` · ${item.reason}` : ""}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function StatusPill({ result, loading }: { result: PortalOptimizationResult | null; loading: boolean }) {
  const label = statusLabel(result?.status, loading);
  return (
    <span className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-slateLine bg-slate-50 px-3 text-xs font-semibold text-slate-600 sm:w-auto">
      {loading && result?.status !== "ready" ? <Loader2 size={14} className="animate-spin" /> : null}
      {label}
    </span>
  );
}

function statusLabel(status: PortalOptimizationResult["status"] | undefined, loading: boolean) {
  if (status === "ready") return "Calendário pronto";
  if (status === "failed") return "Falha na rodada";
  if (status === "running") return "Rodada em execução";
  if (loading) return "Consultando";
  return "Aguardando rodada";
}
