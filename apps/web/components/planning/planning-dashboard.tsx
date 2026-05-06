"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  BrainCircuit,
  Building2,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Database,
  GraduationCap,
  Hourglass,
  Play,
  RefreshCcw,
  School,
  UserPlus,
  Users
} from "lucide-react";
import {
  Assignment,
  Campus,
  Course,
  CourseRestriction,
  DegreeProgram,
  EnrollmentRoundSummary,
  OptimizationRun,
  Professor,
  Room,
  Student,
  StudentSuggestions,
  TimeSlot,
  api,
  dayLabels,
  minutesToLabel
} from "@/lib/api";
import { Field, IconButton, Panel, PrimaryButton, inputClass } from "@/components/ui";

type LoadState = {
  campuses: Campus[];
  degreePrograms: DegreeProgram[];
  courses: Course[];
  courseRestrictions: CourseRestriction[];
  students: Student[];
  professors: Professor[];
  rooms: Room[];
  slots: TimeSlot[];
  runs: OptimizationRun[];
};

const emptyState: LoadState = {
  campuses: [],
  degreePrograms: [],
  courses: [],
  courseRestrictions: [],
  students: [],
  professors: [],
  rooms: [],
  slots: [],
  runs: []
};

export default function PlanningDashboard({ embedded = false }: { embedded?: boolean }) {
  const [state, setState] = useState<LoadState>(emptyState);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [profile, setProfile] = useState("balanced");
  const [semester, setSemester] = useState("2026/2");
  const [selectedDegreeProgramId, setSelectedDegreeProgramId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestRun = useMemo(() => preferredAdminRun(state.runs), [state.runs]);
  const courseById = useMemo(() => indexBy(state.courses), [state.courses]);
  const professorById = useMemo(() => indexBy(state.professors), [state.professors]);
  const roomById = useMemo(() => indexBy(state.rooms), [state.rooms]);
  const campusById = useMemo(() => indexBy(state.campuses), [state.campuses]);
  const degreeProgramById = useMemo(() => indexBy(state.degreePrograms), [state.degreePrograms]);
  const borrowedCount = state.professors.filter((item) => item.contract?.is_borrowed).length;
  const contextCount = new Set(state.courses.map((item) => item.context_key).filter(Boolean)).size;
  const enrollmentRound = latestRun?.metrics?.enrollment_round as EnrollmentRoundSummary | undefined;
  const demandRequests = Number(latestRun?.metrics?.student_demand_requests ?? 0);
  const studentsWithoutEnrollment = enrollmentRound
    ? enrollmentRound.students_without_enrollment_after_rescue ?? enrollmentRound.unallocated_groups
    : 0;
  const unsatisfiedChoiceGroups = enrollmentRound?.unallocated_groups ?? 0;
  const runInProgress = latestRun ? isRunInProgress(latestRun) : false;
  const processing = busy || runInProgress;

  async function load() {
    setError(null);
    const [campuses, degreePrograms, courses, courseRestrictions, students, professors, rooms, slots, runs] =
      await Promise.all([
      api<Campus[]>("/campuses"),
      api<DegreeProgram[]>("/degree-programs"),
      api<Course[]>("/courses"),
      api<CourseRestriction[]>("/course-restrictions"),
      api<Student[]>("/students"),
      api<Professor[]>("/professors"),
      api<Room[]>("/rooms"),
      api<TimeSlot[]>("/timeslots"),
      api<OptimizationRun[]>("/optimization/runs")
    ]);
    const nextRun = preferredAdminRun(runs);
    setState({ campuses, degreePrograms, courses, courseRestrictions, students, professors, rooms, slots, runs });
    if (nextRun && isRunFinal(nextRun)) {
      setAssignments(await api<Assignment[]>(`/optimization/runs/${nextRun.id}/assignments`));
    } else if (nextRun) {
      setAssignments([]);
    }
  }

  useEffect(() => {
    load().catch((reason: unknown) => setError(String(reason)));
  }, []);

  useEffect(() => {
    if (!runInProgress) return;
    const timer = window.setInterval(() => {
      load().catch((reason: unknown) => setError(String(reason)));
    }, 5000);
    return () => window.clearInterval(timer);
  }, [latestRun?.id, latestRun?.status, runInProgress]);

  async function runOptimization() {
    setBusy(true);
    setError(null);
    try {
      const run = await api<OptimizationRun>("/optimization/runs", {
        method: "POST",
        body: JSON.stringify({
          semester,
          profile,
          parameters: {
            student_demand_only: profile !== "official_ufpel",
            auto_enrollment: true,
            enrollment_stage: "pre_enrollment",
            source: "admin"
          }
        })
      });
      setState((current) => ({ ...current, runs: [run, ...current.runs.filter((item) => item.id !== run.id)] }));
      setAssignments([]);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function reoptimize() {
    if (!latestRun) return;
    setBusy(true);
    setError(null);
    try {
      const run = await api<OptimizationRun>(`/optimization/runs/${latestRun.id}/reoptimize`, {
        method: "POST"
      });
      setState((current) => ({ ...current, runs: [run, ...current.runs.filter((item) => item.id !== run.id)] }));
      setAssignments([]);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={embedded ? "min-h-screen" : "min-h-screen"}>
      {!embedded ? (
      <header className="border-b border-slateLine bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
              <School size={21} />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">OptiGrade</h1>
              <p className="text-sm text-slate-600">Planejamento inteligente de oferta UFPel</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <IconButton icon={RefreshCcw} label="Atualizar dados" onClick={() => load()} />
            <IconButton icon={Play} label="Gerar grade" onClick={runOptimization} disabled={processing} />
          </div>
        </div>
      </header>
      ) : null}

      <div className="mx-auto grid max-w-7xl gap-4 px-5 py-5">
        {error ? (
          <div className="rounded-lg border border-rose/30 bg-rose/10 px-4 py-3 text-sm text-rose">
            {error}
          </div>
        ) : null}

        <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-9">
          <Metric icon={Activity} label="Conflitos hard" value={latestRun?.metrics?.hard_conflicts ?? "-"} />
          <Metric icon={BrainCircuit} label="Score" value={latestRun?.score ?? "-"} />
          <Metric icon={Database} label="Cobertura útil" value={formatPercent(latestRun?.metrics?.coverage)} />
          <Metric icon={CheckCircle2} label="Matriculados" value={enrollmentRound?.enrolled ?? "-"} />
          <Metric icon={AlertTriangle} label="Sem matrícula" value={enrollmentRound ? studentsWithoutEnrollment : "-"} />
          <Metric icon={AlertTriangle} label="Carga mín." value={latestRun?.metrics?.min_load_warnings ?? "-"} />
          <Metric icon={BookOpen} label="Contextos" value={contextCount} />
          <Metric icon={GraduationCap} label="Alunos" value={state.students.length} />
          <Metric icon={Users} label="Docentes" value={state.professors.length} />
          <Metric icon={UserPlus} label="Emprestados" value={borrowedCount} />
        </section>

        <section className="grid gap-4 lg:grid-cols-[420px_1fr]">
          <Panel>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">Gerador</h2>
                <p className="text-sm text-slate-600">
                  {latestRun
                    ? `${latestRun.explanation ?? "Grade em processamento"} · origem ${runSourceLabel(latestRun)}`
                    : "Nenhuma grade gerada"}
                </p>
              </div>
              <CalendarDays size={20} className="text-lake" />
            </div>
            <div className="grid gap-3">
              <Field label="Semestre">
                <input className={inputClass} value={semester} onChange={(event) => setSemester(event.target.value)} />
              </Field>
              <Field label="Perfil">
                <select value={profile} onChange={(event) => setProfile(event.target.value)} className={inputClass}>
                  <option value="fast">fast</option>
                  <option value="balanced">balanced</option>
                  <option value="deep">deep</option>
                  <option value="official_ufpel">official_ufpel</option>
                </select>
              </Field>
              <div className="flex gap-2">
                <PrimaryButton onClick={runOptimization} disabled={processing}>
                  {processing ? "Processando" : "Gerar grade"}
                </PrimaryButton>
                <button
                  type="button"
                  onClick={reoptimize}
                  disabled={processing || !latestRun}
                  className="focus-ring h-10 rounded-md border border-slateLine px-4 text-sm font-semibold text-ink hover:border-lake disabled:opacity-50"
                >
                  Reotimizar
                </button>
              </div>
              <AutomaticEnrollmentCard
                busy={processing}
                latestRun={latestRun}
                enrollmentRound={enrollmentRound}
                demandRequests={demandRequests}
                studentsWithoutEnrollment={studentsWithoutEnrollment}
                unsatisfiedChoiceGroups={unsatisfiedChoiceGroups}
              />
              <div className="grid gap-2">
                {(latestRun?.pareto_front ?? []).slice(0, 4).map((item) => (
                  <div key={item.rank} className="rounded-md border border-slateLine p-3">
                    <div className="flex items-center justify-between text-sm font-semibold">
                      <span>Solução {item.rank}</span>
                      <span>{Number(item.score).toFixed(1)}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      hard {item.objectives?.hard_conflicts ?? "-"} · pref{" "}
                      {Number(item.objectives?.preference_loss ?? 0).toFixed(1)} · salas{" "}
                      {Number(item.objectives?.room_waste ?? 0).toFixed(1)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          <CalendarGrid
            slots={state.slots}
            assignments={assignments}
            courses={state.courses}
            degreePrograms={state.degreePrograms}
            courseById={courseById}
            professorById={professorById}
            roomById={roomById}
            campusById={campusById}
            selectedDegreeProgramId={selectedDegreeProgramId}
            onSelectedDegreeProgramIdChange={setSelectedDegreeProgramId}
          />
        </section>

        <Panel>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">Cadastros separados</h2>
              <p className="text-sm text-slate-600">
                Campus, cursos, cadeiras, restricoes, alunos, professores, salas e horarios agora ficam em paginas proprias.
              </p>
            </div>
            <Link
              href="/app/cadastros"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-md border border-slateLine px-4 text-sm font-semibold transition hover:border-lake hover:text-lake"
            >
              Abrir cadastros
            </Link>
          </div>
        </Panel>
      </div>
    </main>
  );
}

function Metric({
  icon: Icon,
  label,
  value
}: {
  icon: typeof Activity;
  label: string;
  value: string | number;
}) {
  return (
    <Panel className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">{label}</span>
        <Icon size={18} className="text-moss" />
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </Panel>
  );
}

function AutomaticEnrollmentCard({
  busy,
  latestRun,
  enrollmentRound,
  demandRequests,
  studentsWithoutEnrollment,
  unsatisfiedChoiceGroups
}: {
  busy: boolean;
  latestRun?: OptimizationRun;
  enrollmentRound?: EnrollmentRoundSummary;
  demandRequests: number;
  studentsWithoutEnrollment: number;
  unsatisfiedChoiceGroups: number;
}) {
  const ready = Boolean(enrollmentRound);
  const Icon = busy ? Hourglass : ready ? CheckCircle2 : demandRequests > 0 ? AlertTriangle : CalendarDays;
  const title = busy ? "Rodadas automaticas em execucao" : ready ? "Matricula automatica pronta" : "Matricula automatica";
  const subtitle = busy
    ? "O administrador pode aguardar nesta tela; a grade e as vagas aparecem juntas ao terminar."
    : ready
      ? `Rodada ${enrollmentRound?.stage ?? "pre_enrollment"} concluida para ${enrollmentRound?.target_semester ?? latestRun?.semester}.`
      : demandRequests > 0
        ? "A proxima geracao da grade dispara a alocacao de vagas sem uma etapa manual separada."
        : "Depois que os alunos enviarem as listas, a geracao administrativa roda a alocacao automaticamente.";

  return (
    <motion.div
      layout
      className={`rounded-md border px-3 py-3 transition ${
        ready
          ? "border-moss/30 bg-moss/10"
          : busy
            ? "border-lake/30 bg-lake/10"
            : "border-slateLine bg-slate-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded bg-white text-lake">
          <Icon size={17} className={busy ? "animate-pulse" : ""} />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink">{title}</div>
          <p className="mt-1 text-xs leading-relaxed text-slate-600">{subtitle}</p>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <RoundStat label="Alocados" value={enrollmentRound?.enrolled ?? 0} />
        <RoundStat label="Em espera" value={enrollmentRound?.waitlisted ?? 0} tone={enrollmentRound?.waitlisted ? "warning" : "default"} />
        <RoundStat label="Bloqueados" value={enrollmentRound?.blocked ?? 0} tone={enrollmentRound?.blocked ? "warning" : "default"} />
        <RoundStat label="Sem matrícula" value={enrollmentRound ? studentsWithoutEnrollment : 0} tone={studentsWithoutEnrollment ? "warning" : "default"} />
        <RoundStat label="Alternativas pend." value={enrollmentRound ? unsatisfiedChoiceGroups : 0} tone={unsatisfiedChoiceGroups ? "warning" : "default"} />
      </div>
    </motion.div>
  );
}

function RoundStat({
  label,
  value,
  tone = "default"
}: {
  label: string;
  value: number;
  tone?: "default" | "warning";
}) {
  return (
    <div className="rounded border border-white/70 bg-white px-2 py-2">
      <div className={tone === "warning" ? "text-lg font-semibold text-amber-700" : "text-lg font-semibold text-ink"}>
        {value}
      </div>
      <div className="text-slate-600">{label}</div>
    </div>
  );
}

function CalendarGrid({
  slots,
  assignments,
  courses,
  degreePrograms,
  courseById,
  professorById,
  roomById,
  campusById,
  selectedDegreeProgramId,
  onSelectedDegreeProgramIdChange
}: {
  slots: TimeSlot[];
  assignments: Assignment[];
  courses: Course[];
  degreePrograms: DegreeProgram[];
  courseById: Record<string, Course>;
  professorById: Record<string, Professor>;
  roomById: Record<string, Room>;
  campusById: Record<string, Campus>;
  selectedDegreeProgramId: string;
  onSelectedDegreeProgramIdChange: (value: string) => void;
}) {
  const sortedSlots = [...slots].sort((a, b) => a.day - b.day || a.start_minute - b.start_minute);
  const days = Array.from(new Set(sortedSlots.map((slot) => slot.day))).sort();
  const timeStarts = Array.from(new Set(sortedSlots.map((slot) => slot.start_minute))).sort((a, b) => a - b);
  const slotByDayStart = new Map(sortedSlots.map((slot) => [`${slot.day}:${slot.start_minute}`, slot]));
  const visibleAssignments = selectedDegreeProgramId
    ? assignments.filter((assignment) =>
        assignmentBelongsToProgram(assignment, selectedDegreeProgramId, courses, courseById)
      )
    : assignments;
  const selectedProgram = degreePrograms.find((item) => item.id === selectedDegreeProgramId);

  return (
    <Panel className="overflow-hidden p-0">
      <div className="flex flex-col gap-3 border-b border-slateLine px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Calendários por curso</h2>
          <p className="text-sm text-slate-600">
            {selectedProgram ? selectedProgram.name : "Visão global de todas as ofertas"}
          </p>
        </div>
        <select
          className={`${inputClass} sm:w-72`}
          value={selectedDegreeProgramId}
          onChange={(event) => onSelectedDegreeProgramIdChange(event.target.value)}
        >
          <option value="">Todos os cursos</option>
          {degreePrograms.map((program) => (
            <option key={program.id} value={program.id}>
              {program.code ? `${program.code} · ` : ""}
              {program.name}
            </option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[760px]" style={{ gridTemplateColumns: `110px repeat(${days.length}, 1fr)` }}>
          <div className="border-b border-slateLine bg-slate-50 p-3 text-xs font-semibold uppercase text-slate-500">
            Horário
          </div>
          {days.map((day) => (
            <div key={day} className="border-b border-l border-slateLine bg-slate-50 p-3 text-sm font-semibold">
              {dayLabels[day]}
            </div>
          ))}
          {timeStarts.map((start) => (
            <Row
              key={start}
              start={start}
              days={days}
              slotByDayStart={slotByDayStart}
              assignments={visibleAssignments}
              courses={courses}
              courseById={courseById}
              professorById={professorById}
              roomById={roomById}
              campusById={campusById}
              selectedDegreeProgramId={selectedDegreeProgramId}
            />
          ))}
        </div>
      </div>
    </Panel>
  );
}

function Row({
  start,
  days,
  slotByDayStart,
  assignments,
  courses,
  courseById,
  professorById,
  roomById,
  campusById,
  selectedDegreeProgramId
}: {
  start: number;
  days: number[];
  slotByDayStart: Map<string, TimeSlot>;
  assignments: Assignment[];
  courses: Course[];
  courseById: Record<string, Course>;
  professorById: Record<string, Professor>;
  roomById: Record<string, Room>;
  campusById: Record<string, Campus>;
  selectedDegreeProgramId: string;
}) {
  const firstSlot = days.map((day) => slotByDayStart.get(`${day}:${start}`)).find(Boolean);
  return (
    <>
      <div className="border-b border-slateLine p-3 text-sm text-slate-600">
        {minutesToLabel(start)}
        {firstSlot ? `-${minutesToLabel(firstSlot.end_minute)}` : ""}
      </div>
      {days.map((day) => {
        const slot = slotByDayStart.get(`${day}:${start}`);
        const cellAssignments = slot ? assignments.filter((item) => item.time_slot_id === slot.id) : [];
        return (
          <div key={`${day}:${start}`} className="min-h-24 border-b border-l border-slateLine p-2">
            <div className="grid gap-2">
              {cellAssignments.map((assignment) => {
                const course = resolveCourseForProgram(assignment, selectedDegreeProgramId, courses, courseById);
                const room = roomById[assignment.room_id];
                const campusName = campusById[room?.campus_id ?? ""]?.name;
                return (
                  <div
                    key={assignment.id}
                    className="rounded-md border border-lake/20 bg-lake/10 p-2 text-xs leading-snug"
                  >
                    <div className="font-semibold text-ink">{course?.name ?? assignment.course_id}</div>
                    <div className="text-slate-600">
                      {professorById[assignment.professor_id]?.name}
                      {professorById[assignment.professor_id]?.contract?.is_borrowed ? " · emprestado" : ""}
                    </div>
                    <div className="text-slate-600">
                      {room?.name}
                      {campusName ? ` · ${campusName}` : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </>
  );
}

function assignmentBelongsToProgram(
  assignment: Assignment,
  degreeProgramId: string,
  courses: Course[],
  courseById: Record<string, Course>
) {
  const course = courseById[assignment.course_id];
  if (!course) return false;
  if (course.degree_program_id === degreeProgramId) return true;
  if (!course.shareable || !course.context_key) return false;
  return courses.some(
    (item) =>
      item.degree_program_id === degreeProgramId &&
      item.shareable &&
      item.context_key === course.context_key &&
      (!course.campus_id || !item.campus_id || item.campus_id === course.campus_id)
  );
}

function resolveCourseForProgram(
  assignment: Assignment,
  degreeProgramId: string,
  courses: Course[],
  courseById: Record<string, Course>
) {
  const course = courseById[assignment.course_id];
  if (!course || !degreeProgramId || course.degree_program_id === degreeProgramId) return course;
  if (!course.shareable || !course.context_key) return course;
  return (
    courses.find(
      (item) =>
        item.degree_program_id === degreeProgramId &&
        item.shareable &&
        item.context_key === course.context_key &&
        (!course.campus_id || !item.campus_id || item.campus_id === course.campus_id)
    ) ?? course
  );
}

function QuickCampusForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("Pelotas");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Campus>("/campuses", {
      method: "POST",
      body: JSON.stringify({ name, city })
    });
    setName("");
    await onCreated();
  }

  return (
    <Panel>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
        <Building2 size={18} className="text-lake" />
        Novo campus
      </h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <Field label="Cidade">
          <input className={inputClass} value={city} onChange={(event) => setCity(event.target.value)} />
        </Field>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickDegreeProgramForm({
  campuses,
  onCreated
}: {
  campuses: Campus[];
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [campusId, setCampusId] = useState("");
  const [scheduleStart, setScheduleStart] = useState("");
  const [scheduleEnd, setScheduleEnd] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<DegreeProgram>("/degree-programs", {
      method: "POST",
      body: JSON.stringify({
        name,
        code: code || null,
        campus_id: campusId || null,
        schedule_start_minute: scheduleStart ? toMinutes(scheduleStart) : null,
        schedule_end_minute: scheduleEnd ? toMinutes(scheduleEnd) : null
      })
    });
    setName("");
    setCode("");
    setScheduleStart("");
    setScheduleEnd("");
    await onCreated();
  }

  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">Novo curso</h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Codigo">
            <input className={inputClass} value={code} onChange={(event) => setCode(event.target.value)} />
          </Field>
          <Field label="Campus">
            <select className={inputClass} value={campusId} onChange={(event) => setCampusId(event.target.value)}>
              <option value="">Sem campus</option>
              {campuses.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {campus.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Inicio regular">
            <input
              className={inputClass}
              type="time"
              value={scheduleStart}
              onChange={(event) => setScheduleStart(event.target.value)}
            />
          </Field>
          <Field label="Fim regular">
            <input
              className={inputClass}
              type="time"
              value={scheduleEnd}
              onChange={(event) => setScheduleEnd(event.target.value)}
            />
          </Field>
        </div>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickCourseForm({
  campuses,
  degreePrograms,
  onCreated
}: {
  campuses: Campus[];
  degreePrograms: DegreeProgram[];
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [campusId, setCampusId] = useState("");
  const [degreeProgramId, setDegreeProgramId] = useState("");
  const [workloadHours, setWorkloadHours] = useState(4);
  const [theoreticalHours, setTheoreticalHours] = useState(4);
  const [practicalHours, setPracticalHours] = useState(0);
  const [expectedDemand, setExpectedDemand] = useState(40);
  const [recommendedSemester, setRecommendedSemester] = useState(1);
  const [contextKey, setContextKey] = useState("");
  const [requiresLab, setRequiresLab] = useState(false);
  const [shareable, setShareable] = useState(true);
  const filteredPrograms = degreePrograms.filter(
    (program) => !campusId || !program.campus_id || program.campus_id === campusId
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Course>("/courses", {
      method: "POST",
      body: JSON.stringify({
        code: code || null,
        name,
        campus_id: campusId || null,
        degree_program_id: degreeProgramId || null,
        workload_hours: workloadHours,
        theoretical_hours: theoreticalHours,
        practical_hours: practicalHours,
        kind: "mandatory",
        recommended_semester: recommendedSemester,
        expected_demand: expectedDemand,
        requires_lab: requiresLab,
        context_key: contextKey || null,
        shareable,
        criticality: 3
      })
    });
    setName("");
    setCode("");
    await onCreated();
  }
  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">Nova cadeira</h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Codigo">
            <input className={inputClass} value={code} onChange={(event) => setCode(event.target.value)} />
          </Field>
          <Field label="Semestre">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={20}
              value={recommendedSemester}
              onChange={(event) => setRecommendedSemester(Number(event.target.value))}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Campus">
            <select
              className={inputClass}
              value={campusId}
              onChange={(event) => {
                setCampusId(event.target.value);
                setDegreeProgramId("");
              }}
            >
              <option value="">Sem campus</option>
              {campuses.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {campus.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Curso">
            <select
              className={inputClass}
              value={degreeProgramId}
              onChange={(event) => setDegreeProgramId(event.target.value)}
            >
              <option value="">Sem curso</option>
              {filteredPrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.code ? `${program.code} · ` : ""}
                  {program.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Total">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={120}
              value={workloadHours}
              onChange={(event) => setWorkloadHours(Number(event.target.value))}
            />
          </Field>
          <Field label="Teoricas">
            <input
              className={inputClass}
              type="number"
              min={0}
              max={120}
              value={theoreticalHours}
              onChange={(event) => setTheoreticalHours(Number(event.target.value))}
            />
          </Field>
          <Field label="Praticas">
            <input
              className={inputClass}
              type="number"
              min={0}
              max={120}
              value={practicalHours}
              onChange={(event) => setPracticalHours(Number(event.target.value))}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Demanda">
            <input
              className={inputClass}
              type="number"
              min={1}
              value={expectedDemand}
              onChange={(event) => setExpectedDemand(Number(event.target.value))}
            />
          </Field>
          <Field label="Contexto">
            <input
              className={inputClass}
              placeholder="calculo-a:engenharias"
              value={contextKey}
              onChange={(event) => setContextKey(event.target.value)}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex h-10 items-center gap-2 rounded-md border border-slateLine px-3 text-sm">
            <input type="checkbox" checked={requiresLab} onChange={(event) => setRequiresLab(event.target.checked)} />
            Laboratorio
          </label>
          <label className="flex h-10 items-center gap-2 rounded-md border border-slateLine px-3 text-sm">
            <input type="checkbox" checked={shareable} onChange={(event) => setShareable(event.target.checked)} />
            Compartilhavel
          </label>
        </div>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickStudentForm({
  degreePrograms,
  onCreated
}: {
  degreePrograms: DegreeProgram[];
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [registration, setRegistration] = useState("");
  const [degreeProgramId, setDegreeProgramId] = useState("");
  const [currentSemester, setCurrentSemester] = useState(1);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Student>("/students", {
      method: "POST",
      body: JSON.stringify({
        name,
        registration_number: registration || null,
        degree_program_id: degreeProgramId,
        current_semester: currentSemester
      })
    });
    setName("");
    setRegistration("");
    await onCreated();
  }

  return (
    <Panel>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
        <GraduationCap size={18} className="text-lake" />
        Novo aluno
      </h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <Field label="Matricula">
          <input className={inputClass} value={registration} onChange={(event) => setRegistration(event.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Curso">
            <select
              className={inputClass}
              value={degreeProgramId}
              onChange={(event) => setDegreeProgramId(event.target.value)}
              required
            >
              <option value="">Selecione</option>
              {degreePrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.code ? `${program.code} · ` : ""}
                  {program.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Semestre atual">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={20}
              value={currentSemester}
              onChange={(event) => setCurrentSemester(Number(event.target.value))}
            />
          </Field>
        </div>
        <PrimaryButton type="submit" disabled={!degreeProgramId}>
          Adicionar
        </PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickCourseRestrictionForm({
  courses,
  onCreated
}: {
  courses: Course[];
  onCreated: () => Promise<void>;
}) {
  const [courseId, setCourseId] = useState("");
  const [requiredCourseId, setRequiredCourseId] = useState("");
  const [kind, setKind] = useState<"prerequisite" | "corequisite">("prerequisite");
  const [minimumGrade, setMinimumGrade] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<CourseRestriction>("/course-restrictions", {
      method: "POST",
      body: JSON.stringify({
        course_id: courseId,
        required_course_id: requiredCourseId,
        kind,
        strength: "hard",
        minimum_grade: minimumGrade ? Number(minimumGrade) : null
      })
    });
    setCourseId("");
    setRequiredCourseId("");
    setMinimumGrade("");
    await onCreated();
  }

  return (
    <Panel>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
        <ClipboardList size={18} className="text-lake" />
        Restricao de cadeira
      </h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Cadeira">
          <select className={inputClass} value={courseId} onChange={(event) => setCourseId(event.target.value)} required>
            <option value="">Selecione</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code ? `${course.code} · ` : ""}
                {course.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Exige">
          <select
            className={inputClass}
            value={requiredCourseId}
            onChange={(event) => setRequiredCourseId(event.target.value)}
            required
          >
            <option value="">Selecione</option>
            {courses
              .filter((course) => course.id !== courseId)
              .map((course) => (
                <option key={course.id} value={course.id}>
                  {course.code ? `${course.code} · ` : ""}
                  {course.name}
                </option>
              ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Tipo">
            <select className={inputClass} value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
              <option value="prerequisite">pre-requisito</option>
              <option value="corequisite">corequisito</option>
            </select>
          </Field>
          <Field label="Nota minima">
            <input
              className={inputClass}
              type="number"
              min={0}
              max={10}
              step="0.1"
              value={minimumGrade}
              onChange={(event) => setMinimumGrade(event.target.value)}
            />
          </Field>
        </div>
        <PrimaryButton type="submit" disabled={!courseId || !requiredCourseId}>
          Adicionar
        </PrimaryButton>
      </form>
    </Panel>
  );
}

function StudentSelectionForm({
  students,
  courses,
  semester,
  onCreated
}: {
  students: Student[];
  courses: Course[];
  semester: string;
  onCreated: () => Promise<void>;
}) {
  const [studentId, setStudentId] = useState("");
  const [suggestions, setSuggestions] = useState<StudentSuggestions | null>(null);
  const [selectedCourseIds, setSelectedCourseIds] = useState<string[]>([]);
  const courseById = useMemo(() => indexBy(courses), [courses]);

  async function loadSuggestions(nextStudentId = studentId) {
    if (!nextStudentId) return;
    const data = await api<StudentSuggestions>(
      `/students/${nextStudentId}/suggestions?target_semester=${encodeURIComponent(semester)}`
    );
    setSuggestions(data);
    setSelectedCourseIds(
      data.suggestions
        .filter((item) => item.eligible && !item.already_requested)
        .slice(0, 4)
        .map((item) => item.course.id)
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!studentId || selectedCourseIds.length === 0) return;
    await api<unknown>(`/students/${studentId}/course-requests`, {
      method: "POST",
      body: JSON.stringify({
        target_semester: semester,
        course_ids: selectedCourseIds,
        priority: 3
      })
    });
    await loadSuggestions();
    await onCreated();
  }

  function toggleCourse(courseId: string) {
    setSelectedCourseIds((current) =>
      current.includes(courseId)
        ? current.filter((item) => item !== courseId)
        : [...current, courseId]
    );
  }

  return (
    <Panel>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Escolha de cadeiras</h2>
        <span className="text-xs font-medium text-slate-600">{semester}</span>
      </div>
      <form onSubmit={submit} className="grid gap-3">
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <Field label="Aluno">
            <select
              className={inputClass}
              value={studentId}
              onChange={(event) => {
                setStudentId(event.target.value);
                setSuggestions(null);
                setSelectedCourseIds([]);
              }}
            >
              <option value="">Selecione</option>
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.registration_number ? `${student.registration_number} · ` : ""}
                  {student.name}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="button"
            onClick={() => loadSuggestions()}
            disabled={!studentId}
            className="focus-ring mt-6 h-10 rounded-md border border-slateLine px-4 text-sm font-semibold text-ink hover:border-lake disabled:opacity-50"
          >
            Sugerir
          </button>
        </div>
        <div className="grid max-h-72 gap-2 overflow-auto">
          {(suggestions?.suggestions ?? []).slice(0, 12).map((item) => (
            <label
              key={item.course.id}
              className="grid gap-1 rounded-md border border-slateLine px-3 py-2 text-sm"
            >
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="checkbox"
                  checked={selectedCourseIds.includes(item.course.id)}
                  disabled={!item.eligible}
                  onChange={() => toggleCourse(item.course.id)}
                />
                {courseById[item.course.id]?.name ?? item.course.name}
                <span className="ml-auto text-xs text-slate-500">score {item.score}</span>
              </span>
              <span className={item.eligible ? "text-xs text-slate-600" : "text-xs text-rose"}>
                {item.reasons.join(" · ")}
              </span>
            </label>
          ))}
        </div>
        <PrimaryButton type="submit" disabled={!studentId || selectedCourseIds.length === 0}>
          Registrar escolhas
        </PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickProfessorForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [name, setName] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Professor>("/professors", {
      method: "POST",
      body: JSON.stringify({ name, department: "Computacao" })
    });
    setName("");
    await onCreated();
  }
  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">Novo professor</h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickBorrowedProfessorForm({
  semester,
  onCreated
}: {
  semester: string;
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [origin, setOrigin] = useState("Departamento externo");
  const [maxHours, setMaxHours] = useState(4);
  const [day, setDay] = useState(0);
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("12:00");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Professor>("/professors/borrowed", {
      method: "POST",
      body: JSON.stringify({
        name,
        department: "Computacao",
        borrowed_from_department: origin,
        semester,
        min_hours: 0,
        max_hours: maxHours,
        regime: "emprestado",
        availability: [
          {
            day,
            start_minute: toMinutes(start),
            end_minute: toMinutes(end),
            kind: "available",
            strength: "hard",
            source: "coordinator"
          }
        ]
      })
    });
    setName("");
    await onCreated();
  }

  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">Professor emprestado</h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <Field label="Origem">
          <input className={inputClass} value={origin} onChange={(event) => setOrigin(event.target.value)} required />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Carga max">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={20}
              value={maxHours}
              onChange={(event) => setMaxHours(Number(event.target.value))}
            />
          </Field>
          <Field label="Dia">
            <select className={inputClass} value={day} onChange={(event) => setDay(Number(event.target.value))}>
              {dayLabels.slice(0, 5).map((label, index) => (
                <option key={label} value={index}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Inicio">
            <input className={inputClass} type="time" value={start} onChange={(event) => setStart(event.target.value)} />
          </Field>
          <Field label="Fim">
            <input className={inputClass} type="time" value={end} onChange={(event) => setEnd(event.target.value)} />
          </Field>
        </div>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function QuickRoomForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [name, setName] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await api<Room>("/rooms", {
      method: "POST",
      body: JSON.stringify({ name, capacity: 40, kind: "lecture", availability: {} })
    });
    setName("");
    await onCreated();
  }
  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">Nova sala</h2>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <PrimaryButton type="submit">Adicionar</PrimaryButton>
      </form>
    </Panel>
  );
}

function DataList({ title, items }: { title: string; items: string[] }) {
  return (
    <Panel>
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      <div className="grid max-h-72 gap-2 overflow-auto">
        {items.map((item) => (
          <div key={item} className="rounded-md border border-slateLine px-3 py-2 text-sm">
            {item}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function indexBy<T extends { id: string }>(items: T[]) {
  return Object.fromEntries(items.map((item) => [item.id, item])) as Record<string, T>;
}

function formatPercent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function isRunInProgress(run: OptimizationRun) {
  return run.status === "pending" || run.status === "running";
}

function isRunFinal(run: OptimizationRun) {
  return run.status === "feasible" || run.status === "infeasible" || run.status === "failed";
}

function runSourceLabel(run: OptimizationRun) {
  const source = run.parameters?.source;
  if (source === "trabalho") return "apresentação";
  if (typeof source === "string" && source.trim()) return source;
  return "admin";
}

function preferredAdminRun(runs: OptimizationRun[]) {
  return runs.find((run) => run.parameters?.source !== "trabalho") ?? runs[0];
}

function toMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function formatCourse(
  item: Course,
  degreeProgramById: Record<string, DegreeProgram>,
  campusById: Record<string, Campus>
) {
  const program = degreeProgramById[item.degree_program_id ?? ""];
  const campus = campusById[item.campus_id ?? ""];
  const theoretical = item.theoretical_hours ?? item.workload_hours - item.practical_hours;
  const context = item.context_key ? ` · ${item.context_key}` : "";
  const shareable = item.shareable ? " · compartilhavel" : "";
  return `${item.name} · ${program?.code ?? program?.name ?? "sem curso"} · ${
    campus?.name ?? "sem campus"
  } · ${theoretical}T/${item.practical_hours}P · ${item.expected_demand} alunos${context}${shareable}`;
}

function formatDegreeProgram(item: DegreeProgram, campusById: Record<string, Campus>) {
  const campus = campusById[item.campus_id ?? ""]?.name ?? "sem campus";
  const schedule =
    item.schedule_start_minute !== null &&
    item.schedule_start_minute !== undefined &&
    item.schedule_end_minute !== null &&
    item.schedule_end_minute !== undefined
      ? ` · ${minutesToLabel(item.schedule_start_minute)}-${minutesToLabel(item.schedule_end_minute)}`
      : "";
  return `${item.name} · ${campus}${schedule}`;
}

function formatStudent(item: Student, degreeProgramById: Record<string, DegreeProgram>) {
  const program = degreeProgramById[item.degree_program_id];
  return `${item.name} · ${program?.code ?? program?.name ?? "sem curso"} · S${item.current_semester}`;
}

function formatRestriction(item: CourseRestriction, courseById: Record<string, Course>) {
  const course = courseById[item.course_id]?.name ?? item.course_id;
  const required = courseById[item.required_course_id]?.name ?? item.required_course_id;
  const grade = item.minimum_grade === null || item.minimum_grade === undefined ? "" : ` · nota ${item.minimum_grade}`;
  return `${course} exige ${required} · ${item.kind}${grade}`;
}

function formatProfessor(item: Professor) {
  if (!item.contract?.is_borrowed) {
    return `${item.name} · ${item.department}`;
  }
  return `${item.name} · emprestado · ${item.contract.semester} · max ${item.contract.max_hours}h`;
}
