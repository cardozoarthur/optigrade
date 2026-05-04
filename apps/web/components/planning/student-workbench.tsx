"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarCheck, Check, CircleAlert, ClipboardCheck, Clock3, GraduationCap, Loader2, Send, Sparkles } from "lucide-react";
import { Course, Student, StudentCourseSuggestion, StudentEnrollment, StudentSuggestions, api } from "@/lib/api";
import { Field, Panel, PrimaryButton, inputClass } from "@/components/ui";

export function StudentWorkbench({
  studentId,
  studentEmail,
  semester = "2026/2"
}: {
  studentId?: string | null;
  studentEmail?: string | null;
  semester?: string;
}) {
  const [students, setStudents] = useState<Student[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [enrollments, setEnrollments] = useState<StudentEnrollment[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState(studentId ?? "");
  const [targetSemester, setTargetSemester] = useState(semester);
  const [selectionMode, setSelectionMode] = useState<"independent" | "queue">("independent");
  const [suggestions, setSuggestions] = useState<StudentSuggestions | null>(null);
  const [selectedCourseIds, setSelectedCourseIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [enrollmentsLoading, setEnrollmentsLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const courseById = useMemo(() => Object.fromEntries(courses.map((course) => [course.id, course])), [courses]);
  const selectedStudent = useMemo(
    () => students.find((student) => student.id === selectedStudentId),
    [students, selectedStudentId]
  );
  const suggestionItems = suggestions?.suggestions ?? [];
  const selectedItems = useMemo(
    () => suggestionItems.filter((item) => selectedCourseIds.includes(item.course.id)),
    [selectedCourseIds, suggestionItems]
  );
  const regularItems = useMemo(
    () => suggestionItems.filter((item) => item.is_regular_for_student),
    [suggestionItems]
  );
  const selectedRegularItems = selectedItems.filter((item) => item.is_regular_for_student);
  const missingRegularItems = regularItems.filter(
    (item) => item.eligible && !selectedCourseIds.includes(item.course.id)
  );
  const blockedSelectedItems = selectedItems.filter((item) => !item.eligible);
  const eligibleSelectedItems = selectedItems.filter((item) => item.eligible);

  useEffect(() => {
    async function load() {
      const [nextStudents, nextCourses] = await Promise.all([api<Student[]>("/students"), api<Course[]>("/courses")]);
      const visibleStudents = studentEmail
        ? nextStudents.filter((student) => !student.email || student.email.toLowerCase() === studentEmail.toLowerCase())
        : nextStudents;
      setStudents(visibleStudents);
      setCourses(nextCourses);
      setSelectedStudentId(studentId ?? visibleStudents[0]?.id ?? "");
    }

    load().catch((reason: unknown) => setError(String(reason)));
  }, [studentEmail, studentId]);

  useEffect(() => {
    loadEnrollments().catch((reason: unknown) => setError(String(reason)));
  }, [selectedStudentId, targetSemester]);

  async function loadSuggestions(nextStudentId = selectedStudentId, preserveStatus = false) {
    if (!nextStudentId) return;
    setBusy(true);
    setError(null);
    if (!preserveStatus) setStatus(null);
    try {
      const data = await api<StudentSuggestions>(
        `/students/${nextStudentId}/suggestions?target_semester=${encodeURIComponent(targetSemester)}`
      );
      setSuggestions(data);
      setSelectedCourseIds(
        data.suggestions
          .filter((item) => item.already_requested)
          .map((item) => item.course.id)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function loadEnrollments(nextStudentId = selectedStudentId) {
    if (!nextStudentId) {
      setEnrollments([]);
      return;
    }
    setEnrollmentsLoading(true);
    try {
      const data = await api<StudentEnrollment[]>(
        `/students/${nextStudentId}/enrollments?target_semester=${encodeURIComponent(targetSemester)}&stage=pre_enrollment`
      );
      setEnrollments(data);
    } finally {
      setEnrollmentsLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedStudentId || eligibleSelectedItems.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      if (selectionMode === "queue") {
        await api(`/students/${selectedStudentId}/course-requests/choices`, {
          method: "POST",
          body: JSON.stringify({
            target_semester: targetSemester,
            choices: eligibleSelectedItems.map((item, index) => ({
              course_id: item.course.id,
              preference_order: index + 1,
              alternative_group: "fila-principal",
              priority: Math.max(1, 5 - index),
              note: "Fila de alternativas enviada pela area autenticada do aluno"
            }))
          })
        });
      } else {
        await api(`/students/${selectedStudentId}/course-requests`, {
          method: "POST",
          body: JSON.stringify({
            target_semester: targetSemester,
            course_ids: eligibleSelectedItems.map((item) => item.course.id),
            priority: 4,
            note: "Escolha enviada pela area autenticada do aluno"
          })
        });
      }
      setStatus("Escolhas registradas para o planejamento do semestre");
      await loadSuggestions(selectedStudentId, true);
      await loadEnrollments(selectedStudentId);
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

      <form onSubmit={submit} className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Panel>
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-lake">1ª etapa</p>
              <h2 className="text-base font-semibold">Escolha de cadeiras</h2>
              <p className="text-sm text-slate-600">{selectedStudent?.registration_number ?? "Historico academico"}</p>
            </div>
            <GraduationCap size={20} className="text-lake" />
          </div>
          <div className="grid gap-3">
            <Field label="Aluno">
              <select
                className={inputClass}
                value={selectedStudentId}
                onChange={(event) => {
                  setSelectedStudentId(event.target.value);
                  setSuggestions(null);
                  setSelectedCourseIds([]);
                  setEnrollments([]);
                }}
                disabled={Boolean(studentId)}
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
            <Field label="Semestre alvo">
              <input className={inputClass} value={targetSemester} onChange={(event) => setTargetSemester(event.target.value)} />
            </Field>
            <Field label="Modo de escolha">
              <select
                className={inputClass}
                value={selectionMode}
                onChange={(event) => setSelectionMode(event.target.value as "independent" | "queue")}
              >
                <option value="independent">Quero cursar todas as selecionadas</option>
                <option value="queue">Fila: X, senao Y, senao Z</option>
              </select>
            </Field>
            <button
              type="button"
              onClick={() => loadSuggestions()}
              disabled={!selectedStudentId || busy}
              className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slateLine text-sm font-semibold transition hover:border-lake hover:text-lake disabled:opacity-50"
            >
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Sugerir cadeiras
            </button>
          </div>
        </Panel>

        <Panel>
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-lake">Formulário</p>
              <h2 className="text-base font-semibold">Cadeiras disponíveis</h2>
              <p className="text-sm text-slate-600">
                {suggestions ? `${suggestions.suggestions.length} cadeiras avaliadas` : "Use o historico e as restricoes cadastradas"}
              </p>
            </div>
            <Sparkles size={20} className="text-lake" />
          </div>

          <div className="grid max-h-[520px] gap-2 overflow-auto pr-1">
            {(suggestions?.suggestions ?? []).map((item) => (
              <SuggestionOption
                key={item.course.id}
                course={item.course}
                eligible={item.eligible}
                selected={selectedCourseIds.includes(item.course.id)}
                order={selectedCourseIds.indexOf(item.course.id) + 1}
                score={item.score}
                relation={item.regular_relation}
                reasons={item.reasons}
                onToggle={() => toggleCourse(item.course.id)}
              />
            ))}
            {!suggestions ? (
              <div className="rounded-md border border-dashed border-slateLine px-4 py-8 text-center text-sm text-slate-600">
                As sugestoes aparecem aqui depois da selecao do aluno.
              </div>
            ) : null}
          </div>

        </Panel>
        </div>

        {selectedStudentId ? (
          <EnrollmentResultsPanel
            loading={enrollmentsLoading}
            enrollments={enrollments}
            courseById={courseById}
            targetSemester={targetSemester}
          />
        ) : null}

        {suggestions ? (
          <section className="grid gap-4 lg:grid-cols-3">
            <FlowPanel
              icon={CalendarCheck}
              step="2ª etapa"
              title="Comparação regular"
              primary={`${selectedRegularItems.length}/${regularItems.length}`}
              subtitle="cadeiras regulares selecionadas"
              items={[
                ...selectedRegularItems.slice(0, 4).map((item) => item.course.name),
                ...missingRegularItems.slice(0, 4).map((item) => `Pendente: ${item.course.name}`)
              ]}
            />
            <FlowPanel
              icon={ClipboardCheck}
              step="3ª etapa"
              title="Restrições"
              primary={String(eligibleSelectedItems.length)}
              subtitle="escolhas elegíveis para demanda"
              tone={blockedSelectedItems.length ? "warning" : "default"}
              items={
                blockedSelectedItems.length
                  ? blockedSelectedItems.map((item) => `${item.course.name}: ${item.reasons.join(" · ")}`)
                  : ["Pré-requisitos hard atendidos nas escolhas marcadas"]
              }
            />
            <Panel>
              <div className="flex h-full flex-col justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-lake">Demanda</p>
                  <h2 className="text-base font-semibold">Enviar formulário</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    {selectionMode === "queue"
                      ? "A matricula automatica tenta a fila na ordem informada ate encontrar vaga."
                      : "A otimizacao usa apenas escolhas elegiveis; bloqueios continuam visiveis para ajuste academico."}
                  </p>
                </div>
                <PrimaryButton type="submit" disabled={!selectedStudentId || eligibleSelectedItems.length === 0 || busy}>
                  <span className="inline-flex items-center gap-2">
                    {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    Enviar escolhas
                  </span>
                </PrimaryButton>
              </div>
            </Panel>
          </section>
        ) : null}
      </form>
    </div>
  );
}

function EnrollmentResultsPanel({
  loading,
  enrollments,
  courseById,
  targetSemester
}: {
  loading: boolean;
  enrollments: StudentEnrollment[];
  courseById: Record<string, Course>;
  targetSemester: string;
}) {
  const visibleEnrollments = [...enrollments]
    .filter((item) => item.status !== "superseded")
    .sort((first, second) => enrollmentStatusOrder(first.status) - enrollmentStatusOrder(second.status));
  const enrolled = enrollments.filter((item) => item.status === "enrolled").length;
  const waitlisted = enrollments.filter((item) => item.status === "waitlisted").length;
  const blocked = enrollments.filter((item) => item.status === "blocked").length;
  const superseded = enrollments.filter((item) => item.status === "superseded").length;

  return (
    <Panel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-lake">Resultado automatico</p>
          <h2 className="text-base font-semibold">Matricula e correção</h2>
          <p className="mt-1 text-sm text-slate-600">
            {enrollments.length
              ? `Rodada processada para ${targetSemester}; pendencias ficam listadas aqui para o aluno.`
              : `Aguardando a rodada administrativa de ${targetSemester}.`}
          </p>
        </div>
        <span className="inline-flex h-9 items-center gap-2 rounded-md border border-slateLine px-3 text-xs font-semibold text-slate-700">
          {loading ? <Loader2 size={15} className="animate-spin" /> : enrollments.length ? <Check size={15} /> : <Clock3 size={15} />}
          {loading ? "Atualizando" : enrollments.length ? "Pronto" : "Aguardando"}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <EnrollmentStat label="Alocadas" value={enrolled} />
        <EnrollmentStat label="Sem vaga" value={waitlisted} tone={waitlisted ? "warning" : "default"} />
        <EnrollmentStat label="Bloqueadas" value={blocked} tone={blocked ? "warning" : "default"} />
        <EnrollmentStat label="Alternativas" value={superseded} />
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {visibleEnrollments.length ? (
          visibleEnrollments.map((enrollment) => (
            <EnrollmentOutcomeItem
              key={enrollment.id}
              enrollment={enrollment}
              course={courseById[enrollment.course_id]}
            />
          ))
        ) : (
          <div className="rounded-md border border-dashed border-slateLine px-4 py-6 text-center text-sm text-slate-600 md:col-span-2">
            Quando o administrador gerar a grade, a alocacao ou pendencia aparece automaticamente neste painel.
          </div>
        )}
      </div>
    </Panel>
  );
}

function EnrollmentStat({
  label,
  value,
  tone = "default"
}: {
  label: string;
  value: number;
  tone?: "default" | "warning";
}) {
  return (
    <div className="rounded-md border border-slateLine bg-slate-50 px-3 py-2">
      <div className={tone === "warning" ? "text-lg font-semibold text-amber-700" : "text-lg font-semibold text-ink"}>
        {value}
      </div>
      <div className="text-slate-600">{label}</div>
    </div>
  );
}

function EnrollmentOutcomeItem({
  enrollment,
  course
}: {
  enrollment: StudentEnrollment;
  course?: Course;
}) {
  const Icon = enrollment.status === "enrolled" ? Check : enrollment.status === "blocked" ? CircleAlert : Clock3;
  const tone =
    enrollment.status === "enrolled"
      ? "border-moss/30 bg-moss/10 text-moss"
      : enrollment.status === "blocked"
        ? "border-rose/30 bg-rose/10 text-rose"
        : "border-amber-300 bg-amber-50 text-amber-800";

  return (
    <motion.div layout className={`rounded-md border px-3 py-3 text-sm ${tone}`}>
      <div className="flex items-start gap-3">
        <Icon size={17} className="mt-0.5 shrink-0" />
        <div className="min-w-0">
          <div className="font-semibold text-ink">{course?.name ?? enrollment.course_id}</div>
          <div className="mt-1 text-xs">{enrollmentStatusLabel(enrollment.status)}</div>
          {enrollment.reason ? <div className="mt-1 text-xs opacity-80">{enrollment.reason}</div> : null}
        </div>
        <span className="ml-auto rounded bg-white/70 px-2 py-1 text-xs font-semibold text-ink">
          {Math.round(enrollment.score)}
        </span>
      </div>
    </motion.div>
  );
}

function enrollmentStatusOrder(status: StudentEnrollment["status"]) {
  if (status === "enrolled") return 0;
  if (status === "waitlisted") return 1;
  if (status === "blocked") return 2;
  return 3;
}

function enrollmentStatusLabel(status: StudentEnrollment["status"]) {
  if (status === "enrolled") return "Alocado";
  if (status === "waitlisted") return "Sem vaga nesta rodada";
  if (status === "blocked") return "Bloqueado por restricao academica";
  return "Alternativa nao utilizada";
}

function FlowPanel({
  icon: Icon,
  step,
  title,
  primary,
  subtitle,
  items,
  tone = "default"
}: {
  icon: typeof CalendarCheck;
  step: string;
  title: string;
  primary: string;
  subtitle: string;
  items: string[];
  tone?: "default" | "warning";
}) {
  return (
    <Panel>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className={tone === "warning" ? "text-xs font-semibold uppercase text-amber-700" : "text-xs font-semibold uppercase text-lake"}>
            {step}
          </p>
          <h2 className="text-base font-semibold">{title}</h2>
        </div>
        <Icon size={20} className={tone === "warning" ? "text-amber-700" : "text-lake"} />
      </div>
      <div className="text-3xl font-semibold text-ink">{primary}</div>
      <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
      <div className="mt-4 grid gap-2">
        {items.length ? (
          items.map((item) => (
            <div key={item} className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-xs text-slate-700">
              {item}
            </div>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-slateLine px-3 py-4 text-center text-xs text-slate-600">
            Sem itens para comparar.
          </div>
        )}
      </div>
    </Panel>
  );
}

function SuggestionOption({
  course,
  eligible,
  selected,
  order,
  score,
  relation,
  reasons,
  onToggle
}: {
  course: Course;
  eligible: boolean;
  selected: boolean;
  order: number;
  score: number;
  relation: StudentCourseSuggestion["regular_relation"];
  reasons: string[];
  onToggle: () => void;
}) {
  return (
    <motion.label
      layout
      whileHover={{ y: eligible ? -1 : 0 }}
      className={`grid gap-2 rounded-md border px-3 py-3 text-sm transition ${
        selected
          ? "border-lake bg-lake/10"
          : eligible
            ? "border-slateLine bg-white hover:border-lake/50"
            : "border-slateLine bg-slate-50 opacity-70"
      }`}
    >
      <span className="flex items-start gap-3">
        <input
          className="mt-1"
          type="checkbox"
          checked={selected}
          disabled={!eligible}
          onChange={onToggle}
        />
        <span className="min-w-0">
          <span className="block font-semibold text-ink">{course.name}</span>
          <span className="mt-1 inline-flex rounded bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
            {relationLabel(relation)}
          </span>
          {selected ? (
            <span className="ml-2 inline-flex rounded bg-lake/10 px-2 py-0.5 text-[11px] font-semibold text-lake">
              ordem {order}
            </span>
          ) : null}
          <span className={eligible ? "mt-1 block text-xs text-slate-600" : "mt-1 block text-xs text-rose"}>
            {reasons.join(" · ")}
          </span>
        </span>
        <span className="ml-auto rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
          {score}
        </span>
      </span>
    </motion.label>
  );
}

function relationLabel(relation: StudentCourseSuggestion["regular_relation"]) {
  if (relation === "regular") return "Regular do semestre";
  if (relation === "reoffer") return "Reoferta/dependência";
  if (relation === "elective") return "Optativa";
  if (relation === "future") return "Semestre futuro";
  return "Institucional";
}
