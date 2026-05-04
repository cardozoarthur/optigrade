"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CalendarClock,
  DoorOpen,
  GraduationCap,
  MapPinned,
  UserRoundCog,
  Workflow
} from "lucide-react";
import {
  Campus,
  Course,
  CourseRestriction,
  DegreeProgram,
  Professor,
  Room,
  Student,
  TimeSlot,
  api,
  dayLabels,
  minutesToLabel
} from "@/lib/api";
import {
  CheckboxInput,
  EntityCrudPage,
  SelectInput,
  TextInput
} from "@/components/resources/entity-crud";
import { Field, inputClass } from "@/components/ui";

type CampusForm = {
  name: string;
  city: string;
};

type DegreeProgramForm = {
  name: string;
  code: string;
  department: string;
  campus_id: string;
  schedule_start: string;
  schedule_end: string;
};

type CourseForm = {
  code: string;
  name: string;
  campus_id: string;
  degree_program_id: string;
  workload_hours: number;
  theoretical_hours: number;
  practical_hours: number;
  kind: "mandatory" | "elective";
  recommended_semester: number;
  expected_demand: number;
  requires_lab: boolean;
  criticality: number;
  context_key: string;
  shareable: boolean;
};

type RestrictionForm = {
  course_id: string;
  required_course_ids: string[];
  kind: "prerequisite" | "corequisite";
  strength: "hard" | "soft" | "manual_override";
  minimum_grade: string;
  note: string;
};

type StudentForm = {
  name: string;
  email: string;
  registration_number: string;
  degree_program_id: string;
  current_semester: number;
};

type ProfessorForm = {
  name: string;
  email: string;
  department: string;
  min_hours: number;
  max_hours: number;
  regime: string;
  semester: string;
  is_borrowed: boolean;
  borrowed_from_department: string;
  legal_notes: string;
  loan_notes: string;
};

type RoomForm = {
  name: string;
  campus_id: string;
  capacity: number;
  kind: "lecture" | "lab";
};

type TimeSlotForm = {
  day: number;
  start: string;
  end: string;
  label: string;
};

export function CampusesPage() {
  return (
    <EntityCrudPage<Campus, CampusForm>
      title="Campi"
      subtitle="Unidades fisicas usadas para filtrar cursos, salas e ofertas."
      icon={MapPinned}
      addLabel="Adicionar campus"
      load={() => api<Campus[]>("/campuses")}
      create={(form) => api("/campuses", { method: "POST", body: JSON.stringify(campusPayload(form)) })}
      update={(item, form) => api(`/campuses/${item.id}`, { method: "PUT", body: JSON.stringify(campusPayload(form)) })}
      remove={(item) => api(`/campuses/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Cidade", render: (item) => item.city ?? "-" }
      ]}
      initialForm={() => ({ name: "", city: "" })}
      formFromItem={(item) => ({ name: item.name, city: item.city ?? "" })}
      searchText={(item) => `${item.name} ${item.city ?? ""}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
          <TextInput label="Cidade" value={form.city} onChange={(city) => setForm((current) => ({ ...current, city }))} />
        </div>
      )}
    />
  );
}

export function DegreeProgramsPage() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  useEffect(() => {
    api<Campus[]>("/campuses").then(setCampuses).catch(() => setCampuses([]));
  }, []);
  const campusById = useMemo(() => indexBy(campuses), [campuses]);
  const campusOptions = [{ value: "", label: "Sem campus" }, ...campuses.map((item) => ({ value: item.id, label: item.name }))];

  return (
    <EntityCrudPage<DegreeProgram, DegreeProgramForm>
      title="Cursos"
      subtitle="Cursos de graduacao com janela regular de aula por turno ou horario customizado."
      icon={GraduationCap}
      addLabel="Adicionar curso"
      load={() => api<DegreeProgram[]>("/degree-programs")}
      create={(form) => api("/degree-programs", { method: "POST", body: JSON.stringify(degreeProgramPayload(form)) })}
      update={(item, form) =>
        api(`/degree-programs/${item.id}`, { method: "PUT", body: JSON.stringify(degreeProgramPayload(form)) })
      }
      remove={(item) => api(`/degree-programs/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Codigo", render: (item) => item.code ?? "-" },
        { header: "Campus", render: (item) => campusById[item.campus_id ?? ""]?.name ?? "-" },
        { header: "Horario regular", render: formatProgramSchedule }
      ]}
      initialForm={() => ({
        name: "",
        code: "",
        department: "",
        campus_id: "",
        schedule_start: "",
        schedule_end: ""
      })}
      formFromItem={(item) => ({
        name: item.name,
        code: item.code ?? "",
        department: item.department ?? "",
        campus_id: item.campus_id ?? "",
        schedule_start: minuteToTime(item.schedule_start_minute),
        schedule_end: minuteToTime(item.schedule_end_minute)
      })}
      searchText={(item) => `${item.name} ${item.code ?? ""} ${campusById[item.campus_id ?? ""]?.name ?? ""}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => (
        <div className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
            <TextInput label="Codigo" value={form.code} onChange={(code) => setForm((current) => ({ ...current, code }))} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput
              label="Departamento"
              value={form.department}
              onChange={(department) => setForm((current) => ({ ...current, department }))}
            />
            <SelectInput
              label="Campus"
              value={form.campus_id}
              options={campusOptions}
              onChange={(campus_id) => setForm((current) => ({ ...current, campus_id }))}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput
              label="Inicio regular"
              type="time"
              value={form.schedule_start}
              onChange={(schedule_start) => setForm((current) => ({ ...current, schedule_start }))}
            />
            <TextInput
              label="Fim regular"
              type="time"
              value={form.schedule_end}
              onChange={(schedule_end) => setForm((current) => ({ ...current, schedule_end }))}
            />
          </div>
        </div>
      )}
    />
  );
}

export function CoursesPage() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [degreePrograms, setDegreePrograms] = useState<DegreeProgram[]>([]);
  useEffect(() => {
    Promise.all([api<Campus[]>("/campuses"), api<DegreeProgram[]>("/degree-programs")])
      .then(([nextCampuses, nextPrograms]) => {
        setCampuses(nextCampuses);
        setDegreePrograms(nextPrograms);
      })
      .catch(() => undefined);
  }, []);
  const campusById = useMemo(() => indexBy(campuses), [campuses]);
  const programById = useMemo(() => indexBy(degreePrograms), [degreePrograms]);

  return (
    <EntityCrudPage<Course, CourseForm>
      title="Cadeiras"
      subtitle="Catalogo academico com contexto, carga teorica/pratica e compartilhamento entre cursos."
      icon={BookOpen}
      addLabel="Adicionar cadeira"
      load={() => api<Course[]>("/courses")}
      create={(form) => api("/courses", { method: "POST", body: JSON.stringify(coursePayload(form)) })}
      update={(item, form) => api(`/courses/${item.id}`, { method: "PUT", body: JSON.stringify(coursePayload(form)) })}
      remove={(item) => api(`/courses/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Codigo", render: (item) => item.code ?? "-" },
        { header: "Curso", render: (item) => programById[item.degree_program_id ?? ""]?.name ?? "-" },
        { header: "Carga", render: (item) => `${item.workload_hours}h · ${item.theoretical_hours ?? 0}T/${item.practical_hours}P` },
        { header: "Contexto", render: (item) => item.context_key ?? "-" },
        { header: "Demanda", render: (item) => item.expected_demand }
      ]}
      initialForm={() => ({
        code: "",
        name: "",
        campus_id: "",
        degree_program_id: "",
        workload_hours: 4,
        theoretical_hours: 4,
        practical_hours: 0,
        kind: "mandatory",
        recommended_semester: 1,
        expected_demand: 40,
        requires_lab: false,
        criticality: 3,
        context_key: "",
        shareable: true
      })}
      formFromItem={(item) => ({
        code: item.code ?? "",
        name: item.name,
        campus_id: item.campus_id ?? "",
        degree_program_id: item.degree_program_id ?? "",
        workload_hours: item.workload_hours,
        theoretical_hours: item.theoretical_hours ?? Math.max(0, item.workload_hours - item.practical_hours),
        practical_hours: item.practical_hours,
        kind: item.kind,
        recommended_semester: item.recommended_semester,
        expected_demand: item.expected_demand,
        requires_lab: item.requires_lab,
        criticality: item.criticality,
        context_key: item.context_key ?? "",
        shareable: item.shareable
      })}
      searchText={(item) => `${item.name} ${item.code ?? ""} ${item.context_key ?? ""}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => {
        const filteredPrograms = degreePrograms.filter(
          (program) => !form.campus_id || !program.campus_id || program.campus_id === form.campus_id
        );
        return (
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
              <TextInput label="Codigo" value={form.code} onChange={(code) => setForm((current) => ({ ...current, code }))} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <SelectInput
                label="Campus"
                value={form.campus_id}
                options={[{ value: "", label: "Sem campus" }, ...campuses.map((item) => ({ value: item.id, label: item.name }))]}
                onChange={(campus_id) => setForm((current) => ({ ...current, campus_id, degree_program_id: "" }))}
              />
              <SelectInput
                label="Curso"
                value={form.degree_program_id}
                options={[
                  { value: "", label: "Sem curso" },
                  ...filteredPrograms.map((item) => ({ value: item.id, label: `${item.code ? `${item.code} · ` : ""}${item.name}` }))
                ]}
                onChange={(degree_program_id) => setForm((current) => ({ ...current, degree_program_id }))}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <NumberField label="Total" value={form.workload_hours} min={1} max={120} onChange={(workload_hours) => setForm((current) => ({ ...current, workload_hours }))} />
              <NumberField label="Teoricas" value={form.theoretical_hours} min={0} max={120} onChange={(theoretical_hours) => setForm((current) => ({ ...current, theoretical_hours }))} />
              <NumberField label="Praticas" value={form.practical_hours} min={0} max={120} onChange={(practical_hours) => setForm((current) => ({ ...current, practical_hours }))} />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <SelectInput
                label="Tipo"
                value={form.kind}
                options={[
                  { value: "mandatory", label: "Obrigatoria" },
                  { value: "elective", label: "Optativa/reoferta" }
                ]}
                onChange={(kind) => setForm((current) => ({ ...current, kind: kind as CourseForm["kind"] }))}
              />
              <NumberField label="Semestre" value={form.recommended_semester} min={1} max={20} onChange={(recommended_semester) => setForm((current) => ({ ...current, recommended_semester }))} />
              <NumberField label="Demanda" value={form.expected_demand} min={1} onChange={(expected_demand) => setForm((current) => ({ ...current, expected_demand }))} />
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
              <TextInput
                label="Contexto"
                value={form.context_key}
                placeholder="calculo-a:engenharias"
                onChange={(context_key) => setForm((current) => ({ ...current, context_key }))}
              />
              <NumberField label="Criticidade" value={form.criticality} min={1} max={5} onChange={(criticality) => setForm((current) => ({ ...current, criticality }))} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <CheckboxInput label="Requer laboratorio" checked={form.requires_lab} onChange={(requires_lab) => setForm((current) => ({ ...current, requires_lab }))} />
              <CheckboxInput label="Compartilhavel por contexto" checked={form.shareable} onChange={(shareable) => setForm((current) => ({ ...current, shareable }))} />
            </div>
          </div>
        );
      }}
    />
  );
}

export function CourseRestrictionsPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  useEffect(() => {
    api<Course[]>("/courses").then(setCourses).catch(() => setCourses([]));
  }, []);
  const courseById = useMemo(() => indexBy(courses), [courses]);
  const courseOptions = [
    { value: "", label: "Selecione" },
    ...courses.map((item) => ({ value: item.id, label: `${item.code ? `${item.code} · ` : ""}${item.name}` }))
  ];

  return (
    <EntityCrudPage<CourseRestriction, RestrictionForm>
      title="Restrições de cadeiras"
      subtitle="Pré-requisitos e co-requisitos; uma cadeira pode exigir várias dependências no mesmo cadastro."
      icon={Workflow}
      addLabel="Adicionar restrição"
      load={() => api<CourseRestriction[]>("/course-restrictions")}
      create={async (form) => {
        if (form.required_course_ids.length === 0) throw new Error("Selecione ao menos uma dependência.");
        await api("/course-restrictions/batch", {
          method: "POST",
          body: JSON.stringify(restrictionBatchPayload(form))
        });
      }}
      update={(item, form) => {
        if (form.required_course_ids.length === 0) throw new Error("Selecione uma dependência.");
        return api(`/course-restrictions/${item.id}`, {
          method: "PUT",
          body: JSON.stringify(restrictionPayload(form, form.required_course_ids[0] ?? ""))
        });
      }}
      remove={(item) => api(`/course-restrictions/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Cadeira", render: (item) => courseById[item.course_id]?.name ?? item.course_id },
        { header: "Dependência", render: (item) => courseById[item.required_course_id]?.name ?? item.required_course_id },
        { header: "Tipo", render: (item) => (item.kind === "prerequisite" ? "Pré-requisito" : "Co-requisito") },
        { header: "Força", render: (item) => strengthLabel(item.strength) },
        { header: "Nota mínima", render: (item) => item.minimum_grade ?? "-" }
      ]}
      initialForm={() => ({
        course_id: "",
        required_course_ids: [],
        kind: "prerequisite",
        strength: "hard",
        minimum_grade: "",
        note: ""
      })}
      formFromItem={(item) => ({
        course_id: item.course_id,
        required_course_ids: [item.required_course_id],
        kind: item.kind,
        strength: item.strength,
        minimum_grade: item.minimum_grade?.toString() ?? "",
        note: item.note ?? ""
      })}
      searchText={(item) => `${courseById[item.course_id]?.name ?? ""} ${courseById[item.required_course_id]?.name ?? ""}`}
      itemTitle={(item) => `${courseById[item.course_id]?.name ?? "Cadeira"} -> ${courseById[item.required_course_id]?.name ?? "dependência"}`}
      renderForm={(form, setForm, mode) => (
        <div className="grid gap-3">
          <SelectInput
            label="Cadeira"
            value={form.course_id}
            options={courseOptions}
            required
            onChange={(course_id) => setForm((current) => ({ ...current, course_id, required_course_ids: [] }))}
          />
          <Field label={mode === "create" ? "Dependências" : "Dependência"}>
            <select
              className="focus-ring min-h-36 rounded-md border border-slateLine bg-white px-3 py-2 text-sm text-ink"
              multiple={mode === "create"}
              value={form.required_course_ids}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  required_course_ids: Array.from(event.target.selectedOptions).map((option) => option.value)
                }))
              }
              required
            >
              {courses
                .filter((course) => course.id !== form.course_id)
                .map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.code ? `${course.code} · ` : ""}
                    {course.name}
                  </option>
                ))}
            </select>
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <SelectInput
              label="Tipo"
              value={form.kind}
              options={[
                { value: "prerequisite", label: "Pré-requisito" },
                { value: "corequisite", label: "Co-requisito" }
              ]}
              onChange={(kind) => setForm((current) => ({ ...current, kind: kind as RestrictionForm["kind"] }))}
            />
            <SelectInput
              label="Força"
              value={form.strength}
              options={[
                { value: "hard", label: "Obrigatória" },
                { value: "soft", label: "Preferência" },
                { value: "manual_override", label: "Manual" }
              ]}
              onChange={(strength) => setForm((current) => ({ ...current, strength: strength as RestrictionForm["strength"] }))}
            />
            <TextInput
              label="Nota mínima"
              type="number"
              value={form.minimum_grade}
              min={0}
              max={10}
              onChange={(minimum_grade) => setForm((current) => ({ ...current, minimum_grade }))}
            />
          </div>
          <TextInput label="Observação" value={form.note} onChange={(note) => setForm((current) => ({ ...current, note }))} />
        </div>
      )}
    />
  );
}

export function StudentsPage() {
  const [degreePrograms, setDegreePrograms] = useState<DegreeProgram[]>([]);
  useEffect(() => {
    api<DegreeProgram[]>("/degree-programs").then(setDegreePrograms).catch(() => setDegreePrograms([]));
  }, []);
  const programById = useMemo(() => indexBy(degreePrograms), [degreePrograms]);
  const programOptions = [
    { value: "", label: "Selecione" },
    ...degreePrograms.map((item) => ({ value: item.id, label: `${item.code ? `${item.code} · ` : ""}${item.name}` }))
  ];

  return (
    <EntityCrudPage<Student, StudentForm>
      title="Alunos"
      subtitle="Cadastro discente usado para histórico, dependências e sugestões de matrícula."
      icon={GraduationCap}
      addLabel="Adicionar aluno"
      load={() => api<Student[]>("/students")}
      create={(form) => api("/students", { method: "POST", body: JSON.stringify(studentPayload(form)) })}
      update={(item, form) => api(`/students/${item.id}`, { method: "PUT", body: JSON.stringify(studentPayload(form)) })}
      remove={(item) => api(`/students/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Matrícula", render: (item) => item.registration_number ?? "-" },
        { header: "Curso", render: (item) => programById[item.degree_program_id]?.name ?? "-" },
        { header: "Semestre", render: (item) => `S${item.current_semester}` },
        { header: "E-mail", render: (item) => item.email ?? "-" }
      ]}
      initialForm={() => ({ name: "", email: "", registration_number: "", degree_program_id: "", current_semester: 1 })}
      formFromItem={(item) => ({
        name: item.name,
        email: item.email ?? "",
        registration_number: item.registration_number ?? "",
        degree_program_id: item.degree_program_id,
        current_semester: item.current_semester
      })}
      searchText={(item) => `${item.name} ${item.email ?? ""} ${item.registration_number ?? ""}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => (
        <div className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
            <TextInput label="E-mail" type="email" value={form.email} onChange={(email) => setForm((current) => ({ ...current, email }))} />
          </div>
          <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
            <TextInput label="Matrícula" value={form.registration_number} onChange={(registration_number) => setForm((current) => ({ ...current, registration_number }))} />
            <NumberField label="Semestre" value={form.current_semester} min={1} max={20} onChange={(current_semester) => setForm((current) => ({ ...current, current_semester }))} />
          </div>
          <SelectInput label="Curso" value={form.degree_program_id} required options={programOptions} onChange={(degree_program_id) => setForm((current) => ({ ...current, degree_program_id }))} />
        </div>
      )}
    />
  );
}

export function ProfessorsPage() {
  return (
    <EntityCrudPage<Professor, ProfessorForm>
      title="Professores"
      subtitle="Docentes permanentes e emprestados, com carga mínima/máxima e vínculo semestral."
      icon={UserRoundCog}
      addLabel="Adicionar professor"
      load={() => api<Professor[]>("/professors")}
      create={async (form) => {
        const professor = await api<Professor>("/professors", { method: "POST", body: JSON.stringify(professorPayload(form)) });
        await api(`/professors/${professor.id}/contract`, { method: "POST", body: JSON.stringify(contractPayload(form)) });
      }}
      update={async (item, form) => {
        await api(`/professors/${item.id}`, { method: "PUT", body: JSON.stringify(professorPayload(form)) });
        await api(`/professors/${item.id}/contract`, { method: "POST", body: JSON.stringify(contractPayload(form)) });
      }}
      remove={(item) => api(`/professors/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Departamento", render: (item) => item.department },
        { header: "Carga", render: (item) => formatProfessorLoad(item) },
        { header: "Tipo", render: (item) => (item.contract?.is_borrowed ? "Emprestado" : "Permanente") },
        { header: "E-mail", render: (item) => item.email ?? "-" }
      ]}
      initialForm={() => ({
        name: "",
        email: "",
        department: "UFPel",
        min_hours: 0,
        max_hours: 10,
        regime: "DE",
        semester: "",
        is_borrowed: false,
        borrowed_from_department: "",
        legal_notes: "",
        loan_notes: ""
      })}
      formFromItem={(item) => ({
        name: item.name,
        email: item.email ?? "",
        department: item.department,
        min_hours: item.contract?.min_hours ?? 0,
        max_hours: item.contract?.max_hours ?? 10,
        regime: item.contract?.regime ?? "DE",
        semester: item.contract?.semester ?? "",
        is_borrowed: item.contract?.is_borrowed ?? false,
        borrowed_from_department: item.contract?.borrowed_from_department ?? "",
        legal_notes: "",
        loan_notes: ""
      })}
      searchText={(item) => `${item.name} ${item.email ?? ""} ${item.department}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => (
        <div className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
            <TextInput label="E-mail" type="email" value={form.email} onChange={(email) => setForm((current) => ({ ...current, email }))} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput label="Departamento" value={form.department} onChange={(department) => setForm((current) => ({ ...current, department }))} />
            <TextInput label="Regime" value={form.regime} onChange={(regime) => setForm((current) => ({ ...current, regime }))} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberField label="Carga mínima" value={form.min_hours} min={0} max={60} onChange={(min_hours) => setForm((current) => ({ ...current, min_hours }))} />
            <NumberField label="Carga máxima" value={form.max_hours} min={1} max={80} onChange={(max_hours) => setForm((current) => ({ ...current, max_hours }))} />
          </div>
          <CheckboxInput label="Professor emprestado" checked={form.is_borrowed} onChange={(is_borrowed) => setForm((current) => ({ ...current, is_borrowed }))} />
          {form.is_borrowed ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <TextInput label="Semestre" value={form.semester} required onChange={(semester) => setForm((current) => ({ ...current, semester }))} />
              <TextInput
                label="Origem"
                value={form.borrowed_from_department}
                required
                onChange={(borrowed_from_department) => setForm((current) => ({ ...current, borrowed_from_department }))}
              />
            </div>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <TextInput label="Notas legais" value={form.legal_notes} onChange={(legal_notes) => setForm((current) => ({ ...current, legal_notes }))} />
            <TextInput label="Notas de empréstimo" value={form.loan_notes} onChange={(loan_notes) => setForm((current) => ({ ...current, loan_notes }))} />
          </div>
        </div>
      )}
    />
  );
}

export function RoomsPage() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  useEffect(() => {
    api<Campus[]>("/campuses").then(setCampuses).catch(() => setCampuses([]));
  }, []);
  const campusById = useMemo(() => indexBy(campuses), [campuses]);
  const campusOptions = [{ value: "", label: "Sem campus fixo" }, ...campuses.map((item) => ({ value: item.id, label: item.name }))];

  return (
    <EntityCrudPage<Room, RoomForm>
      title="Salas"
      subtitle="Capacidade, campus e tipo de ambiente usado na otimização."
      icon={DoorOpen}
      addLabel="Adicionar sala"
      load={() => api<Room[]>("/rooms")}
      create={(form) => api("/rooms", { method: "POST", body: JSON.stringify(roomPayload(form)) })}
      update={(item, form) => api(`/rooms/${item.id}`, { method: "PUT", body: JSON.stringify(roomPayload(form)) })}
      remove={(item) => api(`/rooms/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Nome", render: (item) => item.name },
        { header: "Campus", render: (item) => campusById[item.campus_id ?? ""]?.name ?? "-" },
        { header: "Capacidade", render: (item) => item.capacity },
        { header: "Tipo", render: (item) => (item.kind === "lab" ? "Laboratório" : "Teórica") }
      ]}
      initialForm={() => ({ name: "", campus_id: "", capacity: 40, kind: "lecture" })}
      formFromItem={(item) => ({ name: item.name, campus_id: item.campus_id ?? "", capacity: item.capacity, kind: item.kind })}
      searchText={(item) => `${item.name} ${item.kind} ${campusById[item.campus_id ?? ""]?.name ?? ""}`}
      itemTitle={(item) => item.name}
      renderForm={(form, setForm) => (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <TextInput label="Nome" value={form.name} required onChange={(name) => setForm((current) => ({ ...current, name }))} />
          </div>
          <NumberField label="Capacidade" value={form.capacity} min={1} onChange={(capacity) => setForm((current) => ({ ...current, capacity }))} />
          <div className="sm:col-span-3">
            <SelectInput
              label="Campus"
              value={form.campus_id}
              options={campusOptions}
              onChange={(campus_id) => setForm((current) => ({ ...current, campus_id }))}
            />
          </div>
          <div className="sm:col-span-3">
            <SelectInput
              label="Tipo"
              value={form.kind}
              options={[
                { value: "lecture", label: "Teórica" },
                { value: "lab", label: "Laboratório" }
              ]}
              onChange={(kind) => setForm((current) => ({ ...current, kind: kind as RoomForm["kind"] }))}
            />
          </div>
        </div>
      )}
    />
  );
}

export function TimeSlotsPage() {
  return (
    <EntityCrudPage<TimeSlot, TimeSlotForm>
      title="Horários"
      subtitle="Slots base da grade; cursos e professores filtram a alocação sobre estes horários."
      icon={CalendarClock}
      addLabel="Adicionar horário"
      load={() => api<TimeSlot[]>("/timeslots")}
      create={(form) => api("/timeslots", { method: "POST", body: JSON.stringify(timeSlotPayload(form)) })}
      update={(item, form) => api(`/timeslots/${item.id}`, { method: "PUT", body: JSON.stringify(timeSlotPayload(form)) })}
      remove={(item) => api(`/timeslots/${item.id}`, { method: "DELETE" })}
      columns={[
        { header: "Dia", render: (item) => dayLabels[item.day] },
        { header: "Inicio", render: (item) => minutesToLabel(item.start_minute) },
        { header: "Fim", render: (item) => minutesToLabel(item.end_minute) },
        { header: "Rótulo", render: (item) => item.label }
      ]}
      initialForm={() => ({ day: 0, start: "08:00", end: "10:00", label: "" })}
      formFromItem={(item) => ({
        day: item.day,
        start: minuteToTime(item.start_minute),
        end: minuteToTime(item.end_minute),
        label: item.label
      })}
      searchText={(item) => `${dayLabels[item.day]} ${item.label}`}
      itemTitle={(item) => item.label}
      renderForm={(form, setForm) => (
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectInput
            label="Dia"
            value={String(form.day)}
            options={dayLabels.map((label, index) => ({ value: String(index), label }))}
            onChange={(day) => setForm((current) => ({ ...current, day: Number(day) }))}
          />
          <TextInput label="Rótulo" value={form.label} onChange={(label) => setForm((current) => ({ ...current, label }))} />
          <TextInput label="Inicio" type="time" value={form.start} required onChange={(start) => setForm((current) => ({ ...current, start }))} />
          <TextInput label="Fim" type="time" value={form.end} required onChange={(end) => setForm((current) => ({ ...current, end }))} />
        </div>
      )}
    />
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <TextInput
      label={label}
      type="number"
      value={value}
      min={min}
      max={max}
      onChange={(next) => onChange(Number(next))}
    />
  );
}

function campusPayload(form: CampusForm) {
  return {
    name: form.name,
    city: form.city || null
  };
}

function degreeProgramPayload(form: DegreeProgramForm) {
  return {
    name: form.name,
    code: form.code || null,
    department: form.department || null,
    campus_id: form.campus_id || null,
    schedule_start_minute: form.schedule_start ? toMinutes(form.schedule_start) : null,
    schedule_end_minute: form.schedule_end ? toMinutes(form.schedule_end) : null
  };
}

function coursePayload(form: CourseForm) {
  return {
    ...form,
    code: form.code || null,
    campus_id: form.campus_id || null,
    degree_program_id: form.degree_program_id || null,
    context_key: form.context_key || null
  };
}

function restrictionPayload(form: RestrictionForm, requiredCourseId: string) {
  return {
    course_id: form.course_id,
    required_course_id: requiredCourseId,
    kind: form.kind,
    strength: form.strength,
    minimum_grade: form.minimum_grade === "" ? null : Number(form.minimum_grade),
    note: form.note || null
  };
}

function restrictionBatchPayload(form: RestrictionForm) {
  return {
    course_id: form.course_id,
    required_course_ids: form.required_course_ids,
    kind: form.kind,
    strength: form.strength,
    minimum_grade: form.minimum_grade === "" ? null : Number(form.minimum_grade),
    note: form.note || null
  };
}

function studentPayload(form: StudentForm) {
  return {
    name: form.name,
    email: form.email || null,
    registration_number: form.registration_number || null,
    degree_program_id: form.degree_program_id,
    current_semester: form.current_semester
  };
}

function professorPayload(form: ProfessorForm) {
  return {
    name: form.name,
    email: form.email || null,
    department: form.department || "UFPel"
  };
}

function contractPayload(form: ProfessorForm) {
  return {
    min_hours: form.min_hours,
    max_hours: form.max_hours,
    regime: form.regime || "DE",
    semester: form.is_borrowed ? form.semester : form.semester || null,
    is_borrowed: form.is_borrowed,
    borrowed_from_department: form.is_borrowed ? form.borrowed_from_department || null : null,
    legal_notes: form.legal_notes || null,
    loan_notes: form.loan_notes || null
  };
}

function roomPayload(form: RoomForm) {
  return {
    name: form.name,
    campus_id: form.campus_id || null,
    capacity: form.capacity,
    kind: form.kind,
    availability: {}
  };
}

function timeSlotPayload(form: TimeSlotForm) {
  return {
    day: form.day,
    start_minute: toMinutes(form.start),
    end_minute: toMinutes(form.end),
    label: form.label || `${dayLabels[form.day]} ${form.start}-${form.end}`
  };
}

function formatProgramSchedule(item: DegreeProgram) {
  if (item.schedule_start_minute === null || item.schedule_start_minute === undefined) return "-";
  if (item.schedule_end_minute === null || item.schedule_end_minute === undefined) return "-";
  return `${minutesToLabel(item.schedule_start_minute)}-${minutesToLabel(item.schedule_end_minute)}`;
}

function formatProfessorLoad(item: Professor) {
  if (!item.contract) return "-";
  return `${item.contract.min_hours}-${item.contract.max_hours}h`;
}

function strengthLabel(value: string) {
  if (value === "hard") return "Obrigatória";
  if (value === "manual_override") return "Manual";
  return "Preferência";
}

function indexBy<T extends { id: string }>(items: T[]) {
  return Object.fromEntries(items.map((item) => [item.id, item])) as Record<string, T>;
}

function toMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function minuteToTime(value: number | null | undefined) {
  if (value === null || value === undefined) return "";
  return minutesToLabel(value);
}
