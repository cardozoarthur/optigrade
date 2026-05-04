#!/usr/bin/env node

const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8002";
const semester = process.env.PILOT_SEMESTER ?? "2026/2";
const stamp = Date.now().toString();

async function api(path, options = {}) {
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...(options.headers ?? {})
    }
  });
  const bodyText = await response.text();
  const body = bodyText ? JSON.parse(bodyText) : null;
  if (!response.ok) {
    throw new Error(`${options.method ?? "GET"} ${path} -> ${response.status}: ${bodyText}`);
  }
  return body;
}

async function post(path, payload) {
  return api(path, { method: "POST", body: JSON.stringify(payload) });
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

await api("/health");
const initialReadiness = await api(`/readiness?semester=${encodeURIComponent(semester)}`);
assert(initialReadiness.database === "ok", "database readiness failed");

const campus = await post("/campuses", {
  name: `PILOT Campus ${stamp}`,
  city: "Pelotas"
});
const civil = await post("/degree-programs", {
  name: `PILOT Engenharia Civil ${stamp}`,
  code: `PILOT-EC-${stamp}`,
  department: "Engenharias",
  campus_id: campus.id
});
const production = await post("/degree-programs", {
  name: `PILOT Engenharia de Producao ${stamp}`,
  code: `PILOT-EP-${stamp}`,
  department: "Engenharias",
  campus_id: campus.id
});

const contextKey = `pilot-calculo-a-${stamp}:engenharias`;
const calculusCivil = await post("/courses", {
  code: `PILOT-CALC-EC-${stamp}`,
  name: `PILOT Calculo A Civil ${stamp}`,
  campus_id: campus.id,
  degree_program_id: civil.id,
  workload_hours: 2,
  theoretical_hours: 2,
  practical_hours: 0,
  kind: "mandatory",
  recommended_semester: 1,
  expected_demand: 6,
  requires_lab: false,
  criticality: 5,
  context_key: contextKey,
  shareable: true
});
const calculusProduction = await post("/courses", {
  code: `PILOT-CALC-EP-${stamp}`,
  name: `PILOT Calculo A Producao ${stamp}`,
  campus_id: campus.id,
  degree_program_id: production.id,
  workload_hours: 2,
  theoretical_hours: 2,
  practical_hours: 0,
  kind: "mandatory",
  recommended_semester: 1,
  expected_demand: 7,
  requires_lab: false,
  criticality: 5,
  context_key: contextKey,
  shareable: true
});
const physics = await post("/courses", {
  code: `PILOT-FIS-${stamp}`,
  name: `PILOT Fisica I ${stamp}`,
  campus_id: campus.id,
  degree_program_id: civil.id,
  workload_hours: 2,
  theoretical_hours: 2,
  practical_hours: 0,
  kind: "mandatory",
  recommended_semester: 2,
  expected_demand: 5,
  requires_lab: false,
  criticality: 4,
  context_key: `pilot-fisica-${stamp}:engenharias`,
  shareable: true
});

await post("/course-restrictions", {
  course_id: physics.id,
  required_course_id: calculusCivil.id,
  kind: "prerequisite",
  strength: "hard",
  minimum_grade: 6,
  note: "Smoke de piloto"
});

const professor = await post("/professors", {
  name: `PILOT Docente ${stamp}`,
  email: `pilot.docente.${stamp}@ufpel.edu.br`,
  department: "Matematica"
});
await post(`/professors/${professor.id}/contract`, {
  min_hours: 0,
  max_hours: 8,
  regime: "PILOT"
});
for (const course of [calculusCivil, calculusProduction, physics]) {
  await post(`/professors/${professor.id}/qualifications`, {
    course_id: course.id,
    strength: "hard",
    source: "pilot-smoke"
  });
}

await post("/rooms", {
  name: `PILOT Sala ${stamp}`,
  capacity: 140,
  kind: "lecture",
  availability: {}
});
await post("/timeslots", {
  day: 4,
  start_minute: 1080,
  end_minute: 1200,
  label: `Sex 18-20 PILOT ${stamp}`
});

const student = await post("/students", {
  name: `PILOT Aluno ${stamp}`,
  email: `pilot.aluno.${stamp}@ufpel.edu.br`,
  registration_number: `PILOT-ALUNO-${stamp}`,
  degree_program_id: civil.id,
  current_semester: 2
});

const beforeHistory = await api(
  `/students/${student.id}/suggestions?target_semester=${encodeURIComponent(semester)}`
);
const blockedPhysics = beforeHistory.suggestions.find((item) => item.course.id === physics.id);
assert(blockedPhysics?.eligible === false, "expected prerequisite to block physics before history");

await post(`/students/${student.id}/history`, {
  course_id: calculusProduction.id,
  status: "completed",
  semester: "2026/1",
  grade: 8.5
});

const afterHistory = await api(
  `/students/${student.id}/suggestions?target_semester=${encodeURIComponent(semester)}`
);
const eligiblePhysics = afterHistory.suggestions.find((item) => item.course.id === physics.id);
assert(eligiblePhysics?.eligible === true, "expected equivalent completed course to unlock physics");

const requests = await post(`/students/${student.id}/course-requests`, {
  target_semester: semester,
  course_ids: [physics.id],
  priority: 5,
  note: "Selecionado pelo smoke de piloto"
});
assert(requests.length === 1 && requests[0].course_id === physics.id, "student request was not persisted");

const run = await post("/optimization/runs", {
  semester,
  profile: "fast",
  parameters: { attempts: 24, local_steps: 24 }
});
assert(run.status === "feasible", `optimization was not feasible: ${JSON.stringify(run.metrics)}`);
assert((run.metrics.hard_conflicts ?? 1) === 0, "optimization returned hard conflicts");
assert((run.metrics.student_demand_requests ?? 0) >= 1, "student demand was not included");

const finalReadiness = await api(`/readiness?semester=${encodeURIComponent(semester)}`);
assert(finalReadiness.status === "ready", `final readiness is ${finalReadiness.status}`);

console.log(JSON.stringify({
  apiUrl,
  semester,
  stamp,
  readiness: finalReadiness.status,
  student_id: student.id,
  selected_requests: requests.length,
  optimization_run_id: run.id,
  optimization_status: run.status,
  hard_conflicts: run.metrics.hard_conflicts,
  student_demand_requests: run.metrics.student_demand_requests
}, null, 2));
