import type { PermissionKey } from "@/lib/auth/permissions";

export type BffSelfContext = {
  professorId: string | null;
  studentId: string | null;
};

export function resolveBffPermission(
  path: string[],
  method: string,
  self: BffSelfContext
): PermissionKey {
  const [resource, id, child] = path;
  const write = !["GET", "HEAD"].includes(method);

  if (resource === "health" || resource === "readiness") return "readiness:read";
  if (resource === "optimization") {
    if (!write) return "optimization:read";
    return child === "manual-adjustments" || path.includes("manual-adjustments")
      ? "optimization:adjust"
      : "optimization:run";
  }
  if (resource === "professors") {
    if (id && ["availability", "course-preferences", "constraints", "preference-batch"].includes(child ?? "")) {
      return self.professorId === id ? "faculty:self" : write ? "faculty:write" : "faculty:read";
    }
    return write ? "faculty:write" : "faculty:read";
  }
  if (resource === "students") {
    if (!id && !write) return "students:self";
    if (id && ["suggestions", "course-requests", "history", "enrollments"].includes(child ?? "")) {
      return self.studentId === id ? "students:self" : write ? "students:write" : "students:read";
    }
    if (id && self.studentId === id) return "students:self";
    return write ? "students:write" : "students:read";
  }
  if (resource === "imports") return "catalog:write";
  if (["courses", "campuses", "degree-programs", "course-restrictions", "rooms", "timeslots"].includes(resource)) {
    return write ? "catalog:write" : "catalog:read";
  }

  return write ? "catalog:write" : "catalog:read";
}
