import { NextRequest } from "next/server";

export async function publicRequestBody(request: NextRequest, path: string[]) {
  if (path[0] !== "optimization" || path[1] !== "runs" || request.method !== "POST") {
    return request.text();
  }
  const rawBody = await request.text();
  let data: Record<string, unknown> = {};
  try {
    data = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    data = {};
  }
  const parameters =
    typeof data.parameters === "object" && data.parameters
      ? (data.parameters as Record<string, unknown>)
      : {};
  return JSON.stringify({
    semester: "2026/2",
    profile: "balanced",
    parameters: {
      student_demand_only: true,
      auto_enrollment: true,
      enrollment_stage: "pre_enrollment",
      source: "trabalho",
      presentation_run_id: typeof parameters.presentation_run_id === "string" ? parameters.presentation_run_id : undefined,
      requested_at: typeof parameters.requested_at === "string" ? parameters.requested_at : undefined
    }
  });
}

export function isAllowedPublicPresentationPath(path: string[], method: string) {
  const [resource, id, child] = path;
  if (resource === "presentation") {
    if (method === "GET" && id === "stats") return true;
    if (method === "POST" && ["teacher-link", "student-link"].includes(id ?? "") && path.length === 2) {
      return true;
    }
    if (method === "POST" && ["teacher-link", "student-link"].includes(id ?? "") && child && path[3] === "revoke") {
      return true;
    }
  }
  if (method === "GET" && ["courses", "professors", "rooms", "timeslots", "campuses"].includes(resource ?? "")) {
    return path.length === 1;
  }
  if (resource === "optimization" && id === "runs") {
    if (method === "POST" && path.length === 2) return true;
    if (method === "GET" && path.length === 3) return true;
    if (method === "GET" && path.length === 4 && path[3] === "assignments") return true;
  }
  return false;
}
