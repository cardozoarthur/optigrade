export const API_URL = "/api/bff";

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
  stage: string;
  source: string;
  note?: string | null;
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
  score_breakdown: Record<string, any>;
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
  metrics: Record<string, any>;
  pareto_front: Array<Record<string, any>>;
  explanation: string | null;
  score: number | null;
  created_at: string;
  finished_at: string | null;
};

export type PresentationStats = {
  campuses: number;
  degree_programs: number;
  courses: number;
  professors: number;
  students: number;
  rooms: number;
  threads: number;
  cpu_count: number;
  memory_total_mb?: number | null;
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
  hard_violations: Array<Record<string, any>>;
  soft_violations: Array<Record<string, any>>;
  origin: string;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
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
