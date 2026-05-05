export const API_URL = "/api/bff";
export const PUBLIC_PRESENTATION_API_URL = "/api/trabalho/public-bff";

export type Course = {
  id: string;
  code?: string | null;
  name: string;
  campus_id?: string | null;
  degree_program_id?: string | null;
  workload_hours: number;
  theoretical_hours?: number | null;
  practical_hours: number;
  kind: "mandatory" | "elective";
  recommended_semester: number;
  expected_demand: number;
  requires_lab: boolean;
  criticality: number;
  context_key?: string | null;
  shareable: boolean;
  approval_grade?: number | null;
  approval_frequency_percent?: number | null;
  source_url?: string | null;
  official_period?: string | null;
  official_class?: string | null;
  official_schedule?: Array<Record<string, unknown>>;
};

export type Campus = {
  id: string;
  name: string;
  city?: string | null;
};

export type DegreeProgram = {
  id: string;
  name: string;
  code?: string | null;
  department?: string | null;
  campus_id?: string | null;
  schedule_start_minute?: number | null;
  schedule_end_minute?: number | null;
  required_hours?: number | null;
  minimum_semesters?: number | null;
  maximum_semesters?: number | null;
  legal_notes?: string | null;
  source_url?: string | null;
};

export type CourseRestriction = {
  id: string;
  course_id: string;
  required_course_id: string;
  kind: "prerequisite" | "corequisite";
  strength: "hard" | "soft" | "manual_override";
  minimum_grade?: number | null;
  note?: string | null;
};

export type Student = {
  id: string;
  name: string;
  email?: string | null;
  registration_number?: string | null;
  degree_program_id: string;
  current_semester: number;
};

export type StudentCourseHistory = {
  id: string;
  student_id: string;
  course_id: string;
  status: "completed" | "failed" | "enrolled" | "withdrawn";
  semester?: string | null;
  grade?: number | null;
};

export type StudentCourseRequest = {
  id: string;
  student_id: string;
  course_id: string;
  target_semester: string;
  priority: number;
  preference_order: number;
  alternative_group?: string | null;
  desired_day?: number | null;
  desired_start_minute?: number | null;
  desired_end_minute?: number | null;
  time_preference_strength?: "hard" | "soft" | "manual_override";
  stage: string;
  source: string;
  note?: string | null;
};

export type StudentCoursePlanItem = {
  course_id: string;
  priority?: number | null;
  desired_day?: number | null;
  desired_start_minute?: number | null;
  desired_end_minute?: number | null;
  time_preference_strength?: "hard" | "soft" | "manual_override";
  note?: string | null;
};

export type StudentCoursePlanBranch = {
  preference_order: number;
  priority: number;
  label?: string | null;
  items: StudentCoursePlanItem[];
};

export type StudentCoursePlan = {
  target_semester: string;
  alternative_group: string;
  branches: StudentCoursePlanBranch[];
  stage?: string;
  source?: string;
};

export type StudentCourseSuggestion = {
  course: Course;
  eligible: boolean;
  score: number;
  reasons: string[];
  missing_requirements: Course[];
  already_requested: boolean;
  regular_relation: "regular" | "reoffer" | "elective" | "future" | "institutional";
  is_regular_for_student: boolean;
};

export type StudentSuggestions = {
  student_id: string;
  target_semester: string;
  suggestions: StudentCourseSuggestion[];
};

export type StudentEnrollment = {
  id: string;
  student_id: string;
  course_id: string;
  request_id?: string | null;
  run_id?: string | null;
  target_semester: string;
  stage: string;
  status: "enrolled" | "waitlisted" | "superseded" | "blocked";
  score: number;
  score_breakdown: Record<string, unknown>;
  reason?: string | null;
};

export type EnrollmentRoundSummary = {
  target_semester: string;
  stage: string;
  run_id?: string | null;
  enrolled: number;
  waitlisted: number;
  superseded: number;
  blocked: number;
  unallocated_groups: number;
  capacity_by_course?: Record<string, number>;
  capacity_by_bucket?: Record<string, number>;
  bucket_by_course?: Record<string, string>;
  enrolled_by_course?: Record<string, number>;
  waitlisted_by_course?: Record<string, number>;
};

export type Professor = {
  id: string;
  name: string;
  email?: string | null;
  department: string;
  contract?: {
    min_hours: number;
    max_hours: number;
    regime: string;
    semester?: string | null;
    is_borrowed: boolean;
    borrowed_from_department?: string | null;
  } | null;
};

export type Room = {
  id: string;
  name: string;
  campus_id?: string | null;
  capacity: number;
  kind: "lecture" | "lab";
};

export type TimeSlot = {
  id: string;
  day: number;
  start_minute: number;
  end_minute: number;
  label: string;
};

export type OptimizationRun = {
  id: string;
  status: "pending" | "running" | "feasible" | "infeasible" | "failed";
  semester: string;
  profile: string;
  metrics: OptimizationMetrics;
  pareto_front: ParetoSolution[];
  explanation: string | null;
  score: number | null;
  created_at: string;
  finished_at: string | null;
};

export type OptimizationMetrics = Record<string, unknown> & {
  hard_conflicts?: number;
  coverage?: number;
  min_load_warnings?: number;
  student_demand_requests?: number;
  elapsed_ms?: number;
  optimization_status?: string;
  post_processing?: string | null;
  enrollment_round?: EnrollmentRoundSummary;
  planned_sections?: unknown[];
  student_demand_plan?: {
    alternative_assignments?: number;
    unplanned_choice_groups?: number;
    unplanned_request_count?: number;
  } & Record<string, unknown>;
  hard_diagnostics?: Array<Record<string, unknown>>;
};

export type ParetoSolution = Record<string, unknown> & {
  rank?: number;
  score?: number;
  objectives?: {
    hard_conflicts?: number;
    preference_loss?: number;
    room_waste?: number;
  } & Record<string, unknown>;
  explanation?: string;
};

export type PresentationStats = {
  campuses: number;
  degree_programs: number;
  courses: number;
  professors: number;
  students: number;
  student_teacher_ratio: number;
  minimum_student_target: number;
  students_needed_for_minimum: number;
  rooms: number;
  threads: number;
  cpu_count: number;
  memory_total_mb?: number | null;
  updated_at: string;
};

export type PresentationLink = {
  token: string;
  url: string;
  expires_at: string;
  kind: "teacher" | "student";
};

export type PresentationStudentToken = {
  token: string;
  semester: string;
  degree_program: DegreeProgram;
  courses: Course[];
};

export type PresentationStudentCreated = {
  student: Student;
  suggestions: StudentSuggestions;
};

export type Assignment = {
  id: string;
  run_id: string;
  course_id: string;
  professor_id: string;
  room_id: string;
  time_slot_id: string;
  session_index: number;
  fixed: boolean;
  hard_violations: Array<Record<string, unknown>>;
  soft_violations: Array<Record<string, unknown>>;
  origin: string;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return fetchJson<T>(`${API_URL}${path}`, init);
}

export async function publicPresentationApi<T>(path: string, init?: RequestInit): Promise<T> {
  return fetchJson<T>(`${PUBLIC_PRESENTATION_API_URL}${path}`, init);
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
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

export function minutesToLabel(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}

export const dayLabels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"];
